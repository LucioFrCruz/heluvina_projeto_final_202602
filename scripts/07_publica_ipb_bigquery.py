"""
Publica as tres versoes do Indice de Potencial Bancario (IPB) no BigQuery.

Le a base mestra `trusted_municipios`, os correspondentes bancarios
(`raw_bcb_correspondentes`) e o CEMPRE (`raw_ibge_cempre`, dimensao PJ)
direto do BigQuery, calcula as versoes V1 (Classico), V2 (Recalibrado) e
V3 (Presenca Bancaria Completa) via `src/analytics/ipb.py` e sobe quatro
tabelas no dataset `ipb_staging` (prefixo `analytics_`, carga
WRITE_TRUNCATE).

Inputs (BigQuery, dataset ipb_staging):
    - trusted_municipios
    - raw_bcb_correspondentes
    - raw_ibge_cempre

Outputs (BigQuery, dataset ipb_staging):
    - analytics_ipb_v1_classico
    - analytics_ipb_v2_recalibrado
    - analytics_ipb_v3_presenca_completa
    - analytics_ipb_comparacao (visao larga com as 3 versoes lado a lado)

Outputs (locais, fora do Git):
    - data/processed/analytics_ipb_*.parquet (um por tabela)
    - docs/Comparacao_Tres_Abordagens_IPB.md (regenerado via
      gerar_documento_comparacao)
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src.analytics.ipb import (
    COL_IPB_V1,
    COL_IPB_V2,
    COL_IPB_V3,
    adicionar_ranks,
    agregar_cempre,
    agregar_correspondentes_por_tipo,
    computar_ipb_v1_classico,
    computar_ipb_v2_recalibrado,
    computar_ipb_v3_presenca_completa,
    derive_estrato,
    derive_regiao,
    gerar_documento_comparacao,
)
from src.config import (
    PROCESSED_DATA_DIR,
    TABLE_ANALYTICS_IPB_COMPARACAO,
    TABLE_ANALYTICS_IPB_V1,
    TABLE_ANALYTICS_IPB_V2,
    TABLE_ANALYTICS_IPB_V3,
    TABLE_RAW_BCB_CORRESPONDENTES,
    TABLE_RAW_IBGE_CEMPRE,
    TABLE_TRUSTED_MUNICIPIOS,
)
from src.utils.bigquery import read_table_to_dataframe, upload_dataframe_to_raw

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DOCS_DIR = Path("docs")
DOC_COMPARACAO_PATH = DOCS_DIR / "Comparacao_Tres_Abordagens_IPB.md"

COLUNAS_IDENTIDADE = [
    "id_municipio",
    "nome_municipio",
    "sigla_uf",
    "nome_regiao",
    "estrato_populacional",
]


def preparar_base_trusted(df_trusted: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara a base municipal: remove colunas de auditoria e garante as
    colunas derivadas `estrato_populacional` e `nome_regiao`.
    """
    df = df_trusted.drop(columns=["_extracted_at", "_source_url"], errors="ignore")
    # Normaliza a chave de join: a trusted vem com id numerico e o raw de
    # correspondentes com string de 7 digitos — sem isso o merge falha em
    # silencio e zeraria as contagens.
    df["id_municipio"] = df["id_municipio"].astype(str).str.zfill(7)
    df["estrato_populacional"] = derive_estrato(df["populacao_total"])
    df["nome_regiao"] = derive_regiao(df["sigla_uf"])
    return df


def montar_tabela_versao(df: pd.DataFrame, prefixo: str, col_ipb: str) -> pd.DataFrame:
    """
    Monta a tabela de uma versao do IPB com identidade, pilares (score_a..e),
    ipb e rankings. `prefixo` e "v1", "v2" ou "v3".
    """
    colunas = COLUNAS_IDENTIDADE + [
        f"A_{prefixo}",
        f"B_{prefixo}",
        f"C_{prefixo}",
        f"D_{prefixo}",
        f"E_{prefixo}",
        col_ipb,
        f"rank_{prefixo}",
        f"rank_{prefixo}_estrato",
    ]
    df_versao = df[colunas].copy()
    renomeacao = {
        f"A_{prefixo}": "score_a",
        f"B_{prefixo}": "score_b",
        f"C_{prefixo}": "score_c",
        f"D_{prefixo}": "score_d",
        f"E_{prefixo}": "score_e",
        col_ipb: "ipb",
        f"rank_{prefixo}": "rank",
        f"rank_{prefixo}_estrato": "rank_estrato",
    }
    return df_versao.rename(columns=renomeacao)


def validar_tabela(df: pd.DataFrame, nome: str, cols_ipb: list[str]) -> None:
    """Valida contagens, unicidade de id_municipio e faixa dos IPBs."""
    if len(df) != 5_570:
        raise ValueError(f"{nome}: esperado 5570 linhas, encontrado {len(df)}")
    if df["id_municipio"].nunique() != len(df):
        raise ValueError(f"{nome}: id_municipio com duplicatas")
    for col_ipb in cols_ipb:
        if df[col_ipb].isna().any():
            raise ValueError(f"{nome}: nulos em {col_ipb}")
        ipb_min, ipb_max = df[col_ipb].min(), df[col_ipb].max()
        if not (0 <= ipb_min and ipb_max <= 100):
            raise ValueError(f"{nome}: {col_ipb} fora de [0, 100]: [{ipb_min}, {ipb_max}]")


def main() -> None:
    logger.info("Lendo %s do BigQuery...", TABLE_TRUSTED_MUNICIPIOS)
    df_trusted = read_table_to_dataframe(TABLE_TRUSTED_MUNICIPIOS)
    logger.info("Trusted: %d linhas, %d colunas", *df_trusted.shape)

    logger.info("Lendo %s do BigQuery...", TABLE_RAW_BCB_CORRESPONDENTES)
    df_correspondentes = read_table_to_dataframe(TABLE_RAW_BCB_CORRESPONDENTES)
    df_correspondentes = df_correspondentes.dropna(subset=["id_municipio"])
    df_correspondentes["id_municipio"] = (
        df_correspondentes["id_municipio"].astype(str).str.zfill(7)
    )
    logger.info(
        "Correspondentes: %d vinculos, %d municipios distintos",
        len(df_correspondentes),
        df_correspondentes["id_municipio"].nunique(),
    )

    df = preparar_base_trusted(df_trusted)

    logger.info("Agregando correspondentes bancarios por tipo...")
    df = agregar_correspondentes_por_tipo(df_correspondentes, df)

    municipios_sem_correspondente = int((df["quantidade_correspondentes"] == 0).sum())
    logger.info(
        "Municipios da trusted sem correspondente: %d",
        municipios_sem_correspondente,
    )
    extras = set(df_correspondentes["id_municipio"]) - set(df["id_municipio"])
    logger.info(
        "Municipios dos correspondentes fora da trusted (esperado Boa Esperanca do Norte/MT, 5101837, extinto): %s",
        sorted(extras),
    )

    logger.info("Lendo %s do BigQuery...", TABLE_RAW_IBGE_CEMPRE)
    df_cempre = read_table_to_dataframe(TABLE_RAW_IBGE_CEMPRE)
    df_cempre["id_municipio"] = df_cempre["id_municipio"].astype(str).str.zfill(7)
    logger.info(
        "CEMPRE: %d linhas, %d municipios distintos, anos: %s",
        len(df_cempre),
        df_cempre["id_municipio"].nunique(),
        sorted(df_cempre["ano"].astype(str).unique()),
    )
    df = agregar_cempre(df_cempre, df)
    logger.info(
        "Empregos formais agregados: min=%.1f, mediana=%.1f, max=%.1f por 1000 hab",
        df["empregos_formais_por_1000_hab"].min(),
        df["empregos_formais_por_1000_hab"].median(),
        df["empregos_formais_por_1000_hab"].max(),
    )

    logger.info("Calculando IPB V1 Classico...")
    df = computar_ipb_v1_classico(df)
    logger.info("Calculando IPB V2 Recalibrado...")
    df = computar_ipb_v2_recalibrado(df)
    logger.info("Calculando IPB V3 Presenca Bancaria Completa...")
    df = computar_ipb_v3_presenca_completa(df)

    for prefixo, col_ipb in [("v1", COL_IPB_V1), ("v2", COL_IPB_V2), ("v3", COL_IPB_V3)]:
        df = adicionar_ranks(df, prefixo, col_ipb)

    tabelas: dict[str, pd.DataFrame] = {}

    df_v1 = montar_tabela_versao(df, "v1", COL_IPB_V1)
    tabelas[TABLE_ANALYTICS_IPB_V1] = df_v1

    df_v2 = montar_tabela_versao(df, "v2", COL_IPB_V2)
    df_v2["tensao_digital_bancaria"] = df["tensao_digital_bancaria"]
    tabelas[TABLE_ANALYTICS_IPB_V2] = df_v2

    df_v3 = montar_tabela_versao(df, "v3", COL_IPB_V3)
    for col in [
        "quantidade_correspondentes",
        "quantidade_correspondentes_posto",
        "quantidade_correspondentes_filial",
        "quantidade_correspondentes_sede",
        "quantidade_correspondentes_agencia",
        "correspondentes_por_100k_hab",
        "correspondentes_ponderados_por_100k_hab",
        "penetracao_digital_relativa",
        "gap_bancario_completo",
        "score_turismo",
        "empregos_formais",
        "unidades_locais",
        "empregos_formais_por_1000_hab",
        "unidades_locais_por_1000_hab",
        "unidades_alojamento_alimentacao_por_1000_hab",
    ]:
        df_v3[col] = df[col]
    tabelas[TABLE_ANALYTICS_IPB_V3] = df_v3

    colunas_comparacao = COLUNAS_IDENTIDADE + [
        COL_IPB_V1,
        COL_IPB_V2,
        COL_IPB_V3,
        "rank_v1",
        "rank_v2",
        "rank_v3",
        "rank_v1_estrato",
        "rank_v2_estrato",
        "rank_v3_estrato",
    ]
    tabelas[TABLE_ANALYTICS_IPB_COMPARACAO] = df[colunas_comparacao].copy()

    logger.info("Validando tabelas antes da carga...")
    cols_ipb_por_tabela = {
        TABLE_ANALYTICS_IPB_V1: ["ipb"],
        TABLE_ANALYTICS_IPB_V2: ["ipb"],
        TABLE_ANALYTICS_IPB_V3: ["ipb"],
        TABLE_ANALYTICS_IPB_COMPARACAO: [COL_IPB_V1, COL_IPB_V2, COL_IPB_V3],
    }
    for nome, tabela in tabelas.items():
        validar_tabela(tabela, nome, cols_ipb_por_tabela[nome])
        logger.info("  %s: %d linhas, %d colunas", nome, *tabela.shape)

    logger.info("Subindo tabelas para o BigQuery (WRITE_TRUNCATE)...")
    for nome, tabela in tabelas.items():
        upload_dataframe_to_raw(tabela, nome, source_url="src/analytics/ipb.py")
        logger.info("  %s carregada", nome)

    logger.info("Salvando cache local em parquet...")
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for nome, tabela in tabelas.items():
        caminho = PROCESSED_DATA_DIR / f"{nome}.parquet"
        tabela.to_parquet(caminho, index=False)
        logger.info("  %s", caminho)

    logger.info("Regenerando documento comparativo...")
    DOC_COMPARACAO_PATH.write_text(gerar_documento_comparacao(df), encoding="utf-8")
    logger.info("  %s", DOC_COMPARACAO_PATH)

    logger.info("Estatisticas dos IPBs:")
    for col_ipb in [COL_IPB_V1, COL_IPB_V2, COL_IPB_V3]:
        logger.info(
            "  %s: media=%.2f, mediana=%.2f, min=%.2f, max=%.2f",
            col_ipb,
            df[col_ipb].mean(),
            df[col_ipb].median(),
            df[col_ipb].min(),
            df[col_ipb].max(),
        )

    logger.info("Concluido: 4 tabelas analytics_ipb publicadas no BigQuery.")


if __name__ == "__main__":
    main()
