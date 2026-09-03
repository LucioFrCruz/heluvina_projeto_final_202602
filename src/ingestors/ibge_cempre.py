"""
Ingestor do CEMPRE (Cadastro Central de Empresas - IBGE).

Fonte: SIDRA, tabela 9528 ("Unidades locais, pessoal ocupado total e
assalariado, salarios... por secao CNAE"), serie iniciada em 2022 apos a
quebra metodologica do CEMPRE (incorporacao dos CNPJs ativos da Receita
Federal e do eSocial). Periodicidade anual; nivel municipal (N6).

A camada `raw_` e gravada em formato longo: uma linha por municipio x
variavel x secao CNAE, fiel a estrutura de disseminacao do SIDRA.

Coberturas coletadas (secoes da CNAE 2.0):
    - Total (117897): base municipal de unidades locais e emprego formal;
    - Comercio G (117363): dinamismo do varejo/local;
    - Alojamento e alimentacao I (117543): proxy objetivo de turismo
      (valida a heuristica `score_turismo` da V3);
    - Atividades financeiras K (117608): presenca formal do setor
      financeiro por municipio.

Reutiliza `fetch_sidra_table` do ingestor do Censo 2022 (mesma API
Agregados v3, mesma logica de retry e parsing).
"""

import logging

import pandas as pd

from src.config import TABLE_RAW_IBGE_CEMPRE
from src.ingestors.sidra_censo_2022 import fetch_sidra_table
from src.utils.bigquery import upload_dataframe_to_raw
from src.utils.ibge import normalize_ibge_code
from src.utils.storage import save_raw_parquet

logger = logging.getLogger(__name__)

TABLE_CEMPRE = 9528
CLASS_CNAE = "12762"
ANO_REFERENCIA = "2024"

# Variaveis da tabela 9528: unidades locais e pessoal ocupado total.
VARIAVEIS = {
    706: "unidades_locais",
    707: "pessoal_ocupado_total",
}

# Secoes CNAE coletadas: codigo SIDRA -> nome amigavel.
CNAE_CATEGORIAS = {
    "117897": "total",
    "117363": "comercio",
    "117543": "alojamento_alimentacao",
    "117608": "atividades_financeiras",
}

COLUNAS_FINAIS = [
    "id_municipio",
    "ano",
    "variavel_codigo",
    "variavel",
    "cnae_codigo",
    "cnae_secao",
    "valor",
]


def _extrair_cnae(row: pd.Series) -> str | None:
    """Extrai o codigo da secao CNAE do dict `_classificacao` do SIDRA."""
    classificacao = row.get("_classificacao", {})
    mapping = classificacao.get(CLASS_CNAE, {})
    if mapping:
        return list(mapping.keys())[0]
    return None


def build_cempre(period: str = ANO_REFERENCIA) -> pd.DataFrame:
    """
    Coleta unidades locais e pessoal ocupado por municipio e secao CNAE.

    Args:
        period: Ano de referencia do CEMPRE (padrao 2024, ultimo disponivel
            na serie 2022+).

    Returns:
        DataFrame em formato longo com as colunas de `COLUNAS_FINAIS`;
        valores suprimidos pelo siglo estatistico (< 3 informantes) vêm
        como nulos.
    """
    partes = []
    for var_codigo, var_nome in VARIAVEIS.items():
        df = fetch_sidra_table(
            TABLE_CEMPRE,
            period,
            var_codigo,
            classifications={CLASS_CNAE: list(CNAE_CATEGORIAS)},
        )
        if df.empty:
            logger.warning("SIDRA nao retornou dados para a variavel %s.", var_codigo)
            continue
        df["cnae_codigo"] = df.apply(_extrair_cnae, axis=1)
        df["cnae_secao"] = df["cnae_codigo"].map(CNAE_CATEGORIAS)
        df = df.rename(columns={f"var_{var_codigo}": "valor"})
        df["variavel_codigo"] = var_codigo
        df["variavel"] = var_nome
        df["ano"] = period
        partes.append(df[COLUNAS_FINAIS])

    if not partes:
        logger.error("CEMPRE: nenhuma variavel coletada do SIDRA.")
        return pd.DataFrame(columns=COLUNAS_FINAIS)

    resultado = pd.concat(partes, ignore_index=True)
    logger.info(
        "CEMPRE %s: %d linhas (%d municipios x %d variaveis x %d secoes CNAE).",
        period,
        len(resultado),
        resultado["id_municipio"].nunique(),
        resultado["variavel_codigo"].nunique(),
        resultado["cnae_secao"].nunique(),
    )
    return resultado


def transform_raw(raw_data: pd.DataFrame) -> pd.DataFrame:
    """Padroniza o codigo IBGE para 7 digitos e tipa a chave CNAE."""
    df = raw_data.copy()
    if "id_municipio" in df.columns:
        df["id_municipio"] = df["id_municipio"].apply(normalize_ibge_code)
    if "cnae_codigo" in df.columns:
        df["cnae_codigo"] = df["cnae_codigo"].astype(str)
    return df


def run(period: str = ANO_REFERENCIA) -> None:
    """Executa a coleta, transformacao, cache local em Parquet e carga no BigQuery."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    raw_data = build_cempre(period)
    df = transform_raw(raw_data)

    # Validacoes defensivas antes da carga
    chave = ["id_municipio", "variavel_codigo", "cnae_secao"]
    if df.duplicated(subset=chave).any():
        raise ValueError("Existem chaves duplicadas (municipio x variavel x CNAE) no CEMPRE.")
    total = df[df["cnae_secao"] == "total"]
    if total["valor"].isna().any():
        nulos = total[total["valor"].isna()]["id_municipio"].tolist()
        raise ValueError(f"CEMPRE Total CNAE com valores suprimidos/nulos: {nulos[:10]}")
    logger.info("CEMPRE: %d municipios na secao Total.", total["id_municipio"].nunique())

    source_url = (
        "https://servicodados.ibge.gov.br/api/v3/agregados/"
        f"{TABLE_CEMPRE}/periodos/{period}"
    )
    save_raw_parquet(df, "ibge_cempre", "ibge_cempre")
    upload_dataframe_to_raw(df, TABLE_RAW_IBGE_CEMPRE, source_url=source_url)
    logger.info("Sucesso: %d registros do CEMPRE coletados e carregados.", len(df))


if __name__ == "__main__":
    run()
