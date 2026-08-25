import logging
import time
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from src.utils.bigquery import upload_dataframe_to_raw
from src.utils.ibge import normalize_ibge_code
from src.utils.storage import save_raw_parquet
from src.config import TABLE_RAW_SIDRA_CENSO_2022

logger = logging.getLogger(__name__)

SIDRA_BASE_URL = "https://servicodados.ibge.gov.br/api/v3/agregados"

# Configuração das tabelas SIDRA utilizadas no ingestor
TABLE_POPULACAO_TOTAL = 4709
VAR_POPULACAO_TOTAL = 93

TABLE_DISTRIBUICAO_ETARIA = 9514
VAR_DISTRIBUICAO_ETARIA = 93
CLASS_IDADE = "287"

TABLE_POPULACAO_URBANA = 10089
VAR_POPULACAO_URBANA = 93
CLASS_SITUACAO_DOMICILIO = "1"

TABLE_RENDA = 10295
VAR_RENDA = 13431

TABLE_ESCOLARIDADE = 10061
VAR_ESCOLARIDADE = 2667
CLASS_NIVEL_INSTRUCAO = "1568"

TABLE_INTERNET = 7307
VAR_INTERNET = 9784
CLASS_INTERNET = "688"

IDADES_18_35 = [6575, 6576, 93087, 93088, 93089, 6588]
CATEGORIAS_ENSINO_MEDIO_PLUS = [9495, 99713]


def _build_classifications_param(classifications: Optional[Dict[str, Any]]) -> str:
    """Monta o parâmetro `classificacao` da URL do SIDRA a partir de um dict."""
    if not classifications:
        return ""

    parts = []
    for class_id, categories in classifications.items():
        if categories == "all":
            parts.append(f"{class_id}[all]")
        elif isinstance(categories, (list, tuple)):
            cat_str = ",".join(str(c) for c in categories)
            parts.append(f"{class_id}[{cat_str}]")
        else:
            parts.append(f"{class_id}[{categories}]")
    return "|".join(parts)


def fetch_sidra_table(
    table_id: int,
    period: str,
    variable: int,
    classifications: Optional[Dict[str, Any]] = None,
    localidade: str = "N6[all]",
    retries: int = 3,
    backoff_seconds: float = 1.0,
) -> pd.DataFrame:
    """
    Faz requisição para a API do SIDRA e retorna um DataFrame com id_municipio e valor.

    Args:
        table_id: Código do agregado SIDRA.
        period: Período da pesquisa (ex: "2022").
        variable: Código da variável SIDRA.
        classifications: Dict com classificações e categorias desejadas.
        localidade: Filtro de localidade no formato SIDRA (padrão N6[all]).
        retries: Número de tentativas em caso de falha temporária.
        backoff_seconds: Tempo base de espera entre retries.

    Returns:
        DataFrame com colunas `id_municipio` e uma coluna nomeada pelo código da variável.
    """
    class_param = _build_classifications_param(classifications)
    url = f"{SIDRA_BASE_URL}/{table_id}/periodos/{period}/variaveis/{variable}?localidades={localidade}"
    if class_param:
        url += f"&classificacao={class_param}"

    last_exception: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=120)
            if response.status_code == 200:
                break
            logger.warning(
                "Tentativa %d/%d falhou para tabela %d (status %s): %s",
                attempt, retries, table_id, response.status_code, url
            )
        except requests.RequestException as exc:
            last_exception = exc
            logger.warning(
                "Tentativa %d/%d falhou para tabela %d: %s",
                attempt, retries, table_id, exc
            )
        if attempt < retries:
            time.sleep(backoff_seconds * attempt)
    else:
        logger.error("Todas as tentativas falharam para tabela %d: %s", table_id, url)
        return pd.DataFrame()

    data = response.json()
    if not data or "resultados" not in data[0]:
        logger.warning("Resposta vazia ou inesperada para tabela %d", table_id)
        return pd.DataFrame()

    records = []
    col_name = f"var_{variable}"
    for resultado in data[0]["resultados"]:
        # Classificações vêm como lista de dicts; extraímos a primeira categoria para metadados
        classificacao = {
            c["id"]: c["categoria"]
            for c in resultado.get("classificacoes", [])
        }
        for serie in resultado.get("series", []):
            loc_id = serie["localidade"]["id"]
            raw_value = serie["serie"].get(period)
            try:
                value = float(raw_value) if raw_value not in ("-", "X", "...", "", None) else None
            except (ValueError, TypeError):
                value = None

            record = {
                "id_municipio": loc_id,
                col_name: value,
                "_classificacao": classificacao,
            }
            records.append(record)

    return pd.DataFrame(records)


def _extract_category_from_row(row: pd.Series, class_id: str) -> Optional[str]:
    """Extrai o id da categoria de uma classificação a partir da coluna `_classificacao`."""
    classificacao = row.get("_classificacao", {})
    mapping = classificacao.get(class_id, {})
    if mapping:
        return list(mapping.keys())[0]
    return None


def build_populacao_total(period: str = "2022") -> pd.DataFrame:
    """Coleta população total dos municípios (Censo 2022, tabela 4709)."""
    df = fetch_sidra_table(TABLE_POPULACAO_TOTAL, period, VAR_POPULACAO_TOTAL)
    if df.empty:
        return df
    return df[["id_municipio", "var_93"]].rename(columns={"var_93": "populacao_total"})


def build_populacao_18_35(period: str = "2022") -> pd.DataFrame:
    """
    Calcula o percentual da população entre 18 e 35 anos usando idades granulares.

    Utiliza a tabela 9514 do SIDRA, somando as categorias:
    18 anos, 19 anos, 20-24, 25-29, 30-34 e 35 anos.
    """
    df = fetch_sidra_table(
        TABLE_DISTRIBUICAO_ETARIA,
        period,
        VAR_DISTRIBUICAO_ETARIA,
        classifications={CLASS_IDADE: IDADES_18_35},
    )
    if df.empty:
        return pd.DataFrame()

    df = df[["id_municipio", "var_93"]].copy()
    df = df.groupby("id_municipio", as_index=False)["var_93"].sum()
    df = df.rename(columns={"var_93": "populacao_18_35"})
    return df


def build_populacao_urbana(period: str = "2022") -> pd.DataFrame:
    """
    Calcula o percentual de população urbana por município.

    Usa a tabela 10089 do SIDRA (população residente por situação do domicílio).
    """
    df = fetch_sidra_table(
        TABLE_POPULACAO_URBANA,
        period,
        VAR_POPULACAO_URBANA,
        classifications={
            "2": 6794,  # Sexo: Total
            "58": 95253,  # Grupo de idade: Total
            "2661": 32776,  # Localização: Total
            CLASS_SITUACAO_DOMICILIO: [1, 2, 6795],  # Urbana, Rural, Total
        },
    )
    if df.empty:
        return pd.DataFrame()

    df["situacao"] = df.apply(
        lambda row: _extract_category_from_row(row, CLASS_SITUACAO_DOMICILIO), axis=1
    )
    df = df[["id_municipio", "situacao", "var_93"]].copy()

    pivot = df.pivot(index="id_municipio", columns="situacao", values="var_93").reset_index()
    pivot.columns.name = None

    # Garante colunas esperadas
    for col in ["1", "2", "6795"]:
        if col not in pivot.columns:
            pivot[col] = None

    pivot["populacao_urbana_pct"] = (pivot["1"] / pivot["6795"]) * 100
    return pivot[["id_municipio", "populacao_urbana_pct"]]


def build_renda(period: str = "2022") -> pd.DataFrame:
    """Coleta rendimento domiciliar per capita médio mensal (tabela 10295)."""
    df = fetch_sidra_table(
        TABLE_RENDA,
        period,
        VAR_RENDA,
        classifications={
            "2": 6794,  # Sexo: Total
            "86": 95251,  # Cor ou raça: Total
            "58": 95253,  # Grupo de idade: Total
        },
    )
    if df.empty:
        return df
    return df[["id_municipio", f"var_{VAR_RENDA}"]].rename(
        columns={f"var_{VAR_RENDA}": "rendimento_domiciliar_per_capita"}
    )


def build_escolaridade(period: str = "2022") -> pd.DataFrame:
    """
    Calcula percentual de pessoas com 18 anos ou mais com ensino médio completo ou mais.

    Usa a tabela 10061 do SIDRA (nível de instrução).
    """
    df = fetch_sidra_table(
        TABLE_ESCOLARIDADE,
        period,
        VAR_ESCOLARIDADE,
        classifications={
            CLASS_NIVEL_INSTRUCAO: "all",
            "58": 95253,  # Grupo de idade: Total
            "2": 6794,  # Sexo: Total
            "86": 95251,  # Cor ou raça: Total
        },
    )
    if df.empty:
        return pd.DataFrame()

    df["nivel_instrucao"] = df.apply(
        lambda row: _extract_category_from_row(row, CLASS_NIVEL_INSTRUCAO), axis=1
    )
    df = df[["id_municipio", "nivel_instrucao", f"var_{VAR_ESCOLARIDADE}"]].copy()

    pivot = df.pivot(index="id_municipio", columns="nivel_instrucao", values=f"var_{VAR_ESCOLARIDADE}").reset_index()
    pivot.columns.name = None

    for col in ["120704", "9495", "99713"]:
        if col not in pivot.columns:
            pivot[col] = None
        pivot[col] = pd.to_numeric(pivot[col], errors="coerce")

    pivot["escolaridade_ensino_medio_pct"] = (
        (pivot["9495"].fillna(0) + pivot["99713"].fillna(0))
        / pivot["120704"].replace(0, None)
    ) * 100
    return pivot[["id_municipio", "escolaridade_ensino_medio_pct"]]


def build_internet(period: str = "2022") -> pd.DataFrame:
    """
    Tenta coletar percentual de domicílios com internet (tabela 7307).

    Em agosto/2026 o endpoint N6[all] desta tabela retornava instabilidade (HTTP 500).
    Caso falhe, retorna DataFrame vazio para que a coluna seja imputada na EDA.
    """
    df = fetch_sidra_table(
        TABLE_INTERNET,
        period,
        VAR_INTERNET,
        classifications={
            "1": 6795,  # Situação do domicílio: Total
            CLASS_INTERNET: 33298,  # Internet: Total
        },
        retries=2,
    )
    if df.empty:
        logger.warning("Tabela %d (internet) indisponível para N6; coluna será nula.", TABLE_INTERNET)
        return pd.DataFrame()

    return df[["id_municipio", f"var_{VAR_INTERNET}"]].rename(
        columns={f"var_{VAR_INTERNET}": "domicilios_com_internet_pct"}
    )


def extract(period: str = "2022") -> pd.DataFrame:
    """
    Consolida todos os indicadores do Censo 2022 por município.

    Args:
        period: Ano de referência do Censo (padrão 2022).

    Returns:
        DataFrame com id_municipio e colunas de indicadores socioeconômicos.
    """
    logger.info("Iniciando coleta do SIDRA Censo %s...", period)

    df_pop_total = build_populacao_total(period)
    df_pop_18_35 = build_populacao_18_35(period)
    df_pop_urbana = build_populacao_urbana(period)
    df_renda = build_renda(period)
    df_escolaridade = build_escolaridade(period)
    df_internet = build_internet(period)

    df = df_pop_total.copy()
    for d in [df_pop_18_35, df_pop_urbana, df_renda, df_escolaridade, df_internet]:
        if not d.empty:
            df = df.merge(d, on="id_municipio", how="left")

    # Calcula o percentual 18-35 em relação à população total
    df["populacao_18_35_pct"] = (df["populacao_18_35"] / df["populacao_total"]) * 100

    # Garante o contrato de colunas, mesmo quando o SIDRA não retorna dados
    # (ex: tabela 7307 de internet costuma retornar HTTP 500 para N6[all])
    cols_finais = [
        "id_municipio",
        "populacao_total",
        "populacao_18_35_pct",
        "populacao_urbana_pct",
        "rendimento_domiciliar_per_capita",
        "escolaridade_ensino_medio_pct",
        "domicilios_com_internet_pct",
    ]
    for col in cols_finais:
        if col not in df.columns:
            df[col] = None

    df = df[cols_finais]

    logger.info("Coleta finalizada: %d municípios.", len(df))
    return df


def transform_raw(raw_data: pd.DataFrame) -> pd.DataFrame:
    """Padroniza o código IBGE para 7 dígitos."""
    df = raw_data.copy()
    if "id_municipio" in df.columns:
        df["id_municipio"] = df["id_municipio"].apply(normalize_ibge_code)
    return df


def run(period: str = "2022") -> None:
    """Executa a coleta, transformação, cache local e carga no BigQuery."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    raw_data = extract(period)
    df = transform_raw(raw_data)

    source_url = (
        "https://servicodados.ibge.gov.br/api/v3/agregados/"
        f"{TABLE_POPULACAO_TOTAL},{TABLE_DISTRIBUICAO_ETARIA},"
        f"{TABLE_POPULACAO_URBANA},{TABLE_RENDA},{TABLE_ESCOLARIDADE},{TABLE_INTERNET}"
    )

    save_raw_parquet(df, "sidra_censo_2022", "sidra_censo_2022")
    upload_dataframe_to_raw(df, TABLE_RAW_SIDRA_CENSO_2022, source_url=source_url)
    logger.info("Sucesso: %d registros do SIDRA coletados e carregados.", len(df))


if __name__ == "__main__":
    run()
