"""
Exporta os dados do site estatico (GitHub Pages) para docs/data/municipios.json.

Le os parquets locais em data/processed/ — 100% offline, sem BigQuery — da
camada analytics (IPB V1/V2/V3 + comparacao), da modelagem da Etapa 3
(arquetipos, clusters, potencial latente, anomalias) e da trusted municipal
(Pix, IDH, escolaridade, PIB, agencias, correspondentes), consolida um
registro por municipio e grava uma lista plana de objetos JSON com
arredondamento de casas decimais e validacoes de integridade (5.570
municipios, id unico de 7 digitos, sem nulos criticos).

Inputs (data/processed/):
    - analytics_ipb_v1_classico.parquet (ipb V1)
    - analytics_ipb_v2_recalibrado.parquet (ipb V2)
    - analytics_ipb_v3_presenca_completa.parquet (ipb V3, scores, correspondentes)
    - analytics_ipb_comparacao.parquet (identidade + rank_v1..rank_v3)
    - modelagem_resultados.parquet (arquetipo, cluster, potencial latente, anomalia)
    - trusted_municipios_eda.parquet (pix, idhm, escolaridade, pib, agencias)

Outputs:
    - docs/data/municipios.json (lista plana com um objeto por municipio)

Mapeamento campo do schema -> coluna real (fonte):
    ipb_v1 -> ipb (analytics_ipb_v1_classico)
    ipb_v2 -> ipb (analytics_ipb_v2_recalibrado)
    ipb_v3 -> ipb (analytics_ipb_v3_presenca_completa)
    rank_v1/v2/v3 -> rank_v1/v2/v3 (analytics_ipb_comparacao)
    score_a_v3..score_e_v3 -> score_a..score_e (analytics_ipb_v3_presenca_completa)
    arquetipo -> arquetipo, cluster -> cluster_kmeans (K=6 confirmado),
    potencial_latente -> potencial_latente_depositos_pc,
    flag_anomalia -> flag_anomalia_top30 (modelagem_resultados)
    pix_per_capita -> pix_per_capita_12m, pix_pj_pct -> pix_pj_pct,
    idhm -> idhm, escolaridade_pct -> escolaridade_ensino_medio_pct,
    pib_per_capita -> pib_per_capita, agencias_por_100k -> agencias_por_100k_hab
    (trusted_municipios_eda)
    correspondentes_por_100k -> correspondentes_por_100k_hab
    (analytics_ipb_v3_presenca_completa — a trusted nao carrega correspondentes)
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_DATA_DIR = Path("data/processed")
SAIDA_DIR = Path("docs/data")
SAIDA_PATH = SAIDA_DIR / "municipios.json"

QUANTIDADE_ESPERADA = 5_570
TAMANHO_MAXIMO_BYTES = 3 * 1024 * 1024

ARQUIVOS_ENTRADA = {
    "v1": "analytics_ipb_v1_classico.parquet",
    "v2": "analytics_ipb_v2_recalibrado.parquet",
    "v3": "analytics_ipb_v3_presenca_completa.parquet",
    "comparacao": "analytics_ipb_comparacao.parquet",
    "resultados": "modelagem_resultados.parquet",
    "trusted": "trusted_municipios_eda.parquet",
}

# Campo do schema do site -> (fonte, coluna real no parquet).
MAPEAMENTO: dict[str, tuple[str, str]] = {
    "id_municipio": ("comparacao", "id_municipio"),
    "nome_municipio": ("comparacao", "nome_municipio"),
    "sigla_uf": ("comparacao", "sigla_uf"),
    "nome_regiao": ("comparacao", "nome_regiao"),
    "estrato_populacional": ("comparacao", "estrato_populacional"),
    "ipb_v1": ("v1", "ipb"),
    "ipb_v2": ("v2", "ipb"),
    "ipb_v3": ("v3", "ipb"),
    "rank_v1": ("comparacao", "rank_v1"),
    "rank_v2": ("comparacao", "rank_v2"),
    "rank_v3": ("comparacao", "rank_v3"),
    "score_a_v3": ("v3", "score_a"),
    "score_b_v3": ("v3", "score_b"),
    "score_c_v3": ("v3", "score_c"),
    "score_d_v3": ("v3", "score_d"),
    "score_e_v3": ("v3", "score_e"),
    "arquetipo": ("resultados", "arquetipo"),
    "cluster": ("resultados", "cluster_kmeans"),
    "potencial_latente": ("resultados", "potencial_latente_depositos_pc"),
    "flag_anomalia": ("resultados", "flag_anomalia_top30"),
    "pix_per_capita": ("trusted", "pix_per_capita_12m"),
    "pix_pj_pct": ("trusted", "pix_pj_pct"),
    "idhm": ("trusted", "idhm"),
    "escolaridade_pct": ("trusted", "escolaridade_ensino_medio_pct"),
    "pib_per_capita": ("trusted", "pib_per_capita"),
    "agencias_por_100k": ("trusted", "agencias_por_100k_hab"),
    "correspondentes_por_100k": ("v3", "correspondentes_por_100k_hab"),
}

# Casas decimais por campo numerico continuo (default: 2). Valores monetarios
# per capita sao exportados inteiros (centavos sem valor analitico) e os
# ratios por 100 mil/hab usam 1 casa — o piso estrutural do schema plano
# (27 chaves por registro) fica em ~3,2 MB.
CASAS_DECIMAIS = {
    "ipb_v1": 2,
    "ipb_v2": 2,
    "ipb_v3": 2,
    "score_a_v3": 2,
    "score_b_v3": 2,
    "score_c_v3": 2,
    "score_d_v3": 2,
    "score_e_v3": 2,
    "potencial_latente": 1,
    "pix_per_capita": 0,
    "pix_pj_pct": 3,
    "idhm": 3,
    "escolaridade_pct": 1,
    "pib_per_capita": 0,
    "agencias_por_100k": 1,
    "correspondentes_por_100k": 1,
}

CAMPOS_OBRIGATORIOS = [
    "id_municipio",
    "nome_municipio",
    "sigla_uf",
    "ipb_v1",
    "ipb_v2",
    "ipb_v3",
    "rank_v1",
    "rank_v2",
    "rank_v3",
]


def carregar_dataframes() -> dict[str, pd.DataFrame]:
    """Le os parquets de entrada e normaliza a chave `id_municipio`."""
    tabelas: dict[str, pd.DataFrame] = {}
    for chave, arquivo in ARQUIVOS_ENTRADA.items():
        caminho = PROCESSED_DATA_DIR / arquivo
        logger.info("Lendo %s...", caminho)
        df = pd.read_parquet(caminho)
        df["id_municipio"] = df["id_municipio"].astype(str).str.zfill(7)
        tabelas[chave] = df
        logger.info("  %s: %d linhas, %d colunas", chave, *df.shape)
    return tabelas


def selecionar_colunas(
    df: pd.DataFrame, campos: dict[str, str], origem: str
) -> pd.DataFrame:
    """
    Seleciona e renomeia as colunas mapeadas de uma fonte. Falha de forma
    explicita se alguma coluna real nao existir no parquet.
    """
    renomeacao = {
        col_real: campo
        for campo, col_real in campos.items()
        if col_real != "id_municipio"
    }
    faltantes = [col for col in renomeacao if col not in df.columns]
    if faltantes:
        raise ValueError(f"{origem}: colunas ausentes no parquet: {faltantes}")
    selecao = df[["id_municipio", *renomeacao.keys()]].copy()
    return selecao.rename(columns=renomeacao)


def consolidar_dataset(tabelas: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Consolida as fontes em um registro por municipio (join em id_municipio)."""
    por_fonte: dict[str, dict[str, str]] = {}
    for campo, (fonte, coluna_real) in MAPEAMENTO.items():
        por_fonte.setdefault(fonte, {})[campo] = coluna_real

    base = selecionar_colunas(
        tabelas["comparacao"], por_fonte["comparacao"], "comparacao"
    )
    logger.info("Consolidando dataset a partir da comparacao (%d linhas)...", len(base))
    for fonte in ["v1", "v2", "v3", "resultados", "trusted"]:
        pedaco = selecionar_colunas(tabelas[fonte], por_fonte[fonte], fonte)
        base = base.merge(pedaco, on="id_municipio", how="inner", validate="one_to_one")
        logger.info("  merge %s: %d linhas", fonte, len(base))
        if len(base) != QUANTIDADE_ESPERADA:
            raise ValueError(
                f"merge com {fonte}: perda de linhas, esperado {QUANTIDADE_ESPERADA}, "
                f"encontrado {len(base)}"
            )
    return base[list(MAPEAMENTO.keys())]


def arredondar_campos(df: pd.DataFrame) -> pd.DataFrame:
    """Arredonda os campos continuous e tipa para serializacao JSON segura."""
    for campo, casas in CASAS_DECIMAIS.items():
        df[campo] = df[campo].round(casas).astype("Int64" if casas == 0 else "Float64")
    for campo in ["rank_v1", "rank_v2", "rank_v3", "cluster"]:
        df[campo] = df[campo].astype("Int64")
    df["flag_anomalia"] = df["flag_anomalia"].astype("boolean")
    return df


def validar_dataset(df: pd.DataFrame) -> None:
    """Valida contagens, unicidade/tamanho do id e nulos nos campos criticos."""
    if len(df) != QUANTIDADE_ESPERADA:
        raise ValueError(f"esperado {QUANTIDADE_ESPERADA} linhas, encontrado {len(df)}")
    if df["id_municipio"].nunique() != len(df):
        raise ValueError("id_municipio com duplicatas")
    if not df["id_municipio"].str.len().eq(7).all():
        raise ValueError("id_municipio com tamanho diferente de 7 caracteres")
    for campo in CAMPOS_OBRIGATORIOS:
        if df[campo].isna().any():
            raise ValueError(f"nulos em {campo}")
    for campo in ["ipb_v1", "ipb_v2", "ipb_v3"]:
        ipb_min, ipb_max = df[campo].min(), df[campo].max()
        if not (0 <= ipb_min and ipb_max <= 100):
            raise ValueError(f"{campo} fora de [0, 100]: [{ipb_min}, {ipb_max}]")


def _serializar_padrao(objeto: object) -> object:
    """Fallback defensivo para escalares numpy sem importar numpy."""
    if hasattr(objeto, "item"):
        return objeto.item()
    raise TypeError(f"objeto nao serializavel: {type(objeto)!r}")


def exportar_json(df: pd.DataFrame, caminho: Path) -> int:
    """Grava o JSON compacto (UTF-8) e retorna o tamanho em bytes."""
    registros = df.to_dict(orient="records")
    conteudo = json.dumps(
        registros, ensure_ascii=False, separators=(",", ":"), default=_serializar_padrao
    )
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho.stat().st_size


def main() -> None:
    tabelas = carregar_dataframes()
    df = consolidar_dataset(tabelas)
    df = arredondar_campos(df)

    try:
        validar_dataset(df)
    except ValueError as exc:
        logger.error("Validacao falhou: %s", exc)
        sys.exit(1)

    tamanho = exportar_json(df, SAIDA_PATH)
    logger.info("Exportado %s: %d linhas, %d bytes", SAIDA_PATH, len(df), tamanho)
    if tamanho > TAMANHO_MAXIMO_BYTES:
        logger.warning("JSON acima do alvo de 3 MB: %d bytes", tamanho)

    for campo in ["potencial_latente", "idhm"]:
        logger.info(
            "  %s: %d nulos (permanecem null no JSON)", campo, df[campo].isna().sum()
        )
    for campo in ["ipb_v1", "ipb_v2", "ipb_v3"]:
        logger.info(
            "  %s: media=%.2f, mediana=%.2f, min=%.2f, max=%.2f",
            campo,
            df[campo].mean(),
            df[campo].median(),
            df[campo].min(),
            df[campo].max(),
        )
    logger.info(
        "Concluido: dados do site exportados offline a partir dos parquets locais."
    )


if __name__ == "__main__":
    main()
