"""
Publica a tabela analytics_ipb_clusters no BigQuery (Etapa 3 - ML).

Le o consolidado gerado pelo notebook 03
(`data/processed/modelagem_resultados.parquet`), valida o contrato da
tabela e sobe no dataset `ipb_staging` com carga WRITE_TRUNCATE (mesmo
padrao do script 07).

Input (local, fora do Git):
    - data/processed/modelagem_resultados.parquet (notebooks/01_modelagem)

Output (BigQuery, dataset ipb_staging):
    - analytics_ipb_clusters: identidade, clusters (K-Means/GMM),
      probabilidade do GMM, arquetipo (nome sugerido, pendente de
      validacao do grupo), probabilidade do RF (tem agencia),
      potencial latente, score de anomalia e referencia ipb/rank V3
      para cruzamento (nunca usada como feature).

O upload adiciona as colunas de auditoria `_extracted_at` e
`_source_url` (padrao de src/utils/bigquery.py).
"""

from __future__ import annotations

import logging

import pandas as pd

from src.config import PROCESSED_DATA_DIR, TABLE_ANALYTICS_IPB_CLUSTERS
from src.utils.bigquery import upload_dataframe_to_raw

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PARQUET_RESULTADOS = PROCESSED_DATA_DIR / "modelagem_resultados.parquet"
SOURCE_URL = "modelagem_resultados.parquet (Etapa 3; notebooks/01_modelagem)"

N_MUNICIPIOS_ESPERADO = 5_570

COLUNAS_OBRIGATORIAS = [
    "id_municipio",
    "nome_municipio",
    "sigla_uf",
    "nome_regiao",
    "estrato_populacional",
    "cluster_kmeans",
    "cluster_gmm",
    "prob_cluster_gmm",
    "arquetipo",
    "prob_tem_agencia_rf",
    "pred_tem_agencia_rf",
    "potencial_latente_depositos_pc",
    "score_anomalia",
    "flag_anomalia_top30",
    "ipb",
    "rank",
]


def validar_consolidado(df: pd.DataFrame) -> None:
    """Garante o contrato da tabela antes de subir (falha rapida, sem carga pela metade)."""
    faltantes = set(COLUNAS_OBRIGATORIAS) - set(df.columns)
    if faltantes:
        raise ValueError(f"consolidado sem as colunas obrigatorias: {sorted(faltantes)}")

    if len(df) != N_MUNICIPIOS_ESPERADO:
        raise ValueError(
            f"consolidado com {len(df)} linhas; esperado {N_MUNICIPIOS_ESPERADO}"
        )
    ids = df["id_municipio"].astype(str).str.zfill(7)
    if not ids.is_unique:
        raise ValueError("id_municipio duplicado no consolidado")

    for coluna in ("prob_tem_agencia_rf", "prob_cluster_gmm"):
        if not df[coluna].between(0, 1).all():
            raise ValueError(f"{coluna} fora de [0, 1]")
    if df["arquetipo"].isna().any():
        raise ValueError("arquetipo com nulos")
    if int(df["flag_anomalia_top30"].sum()) != 30:
        raise ValueError("flag_anomalia_top30 deve marcar exatamente 30 municipios")
    if (df["potencial_latente_depositos_pc"].dropna() < 0).any():
        raise ValueError("potencial_latente_depositos_pc com valores negativos")
    if not df["ipb"].between(0, 100).all():
        raise ValueError("ipb fora de [0, 100]")


def main() -> None:
    logger.info("Lendo %s", PARQUET_RESULTADOS)
    consolidado = pd.read_parquet(PARQUET_RESULTADOS)

    validar_consolidado(consolidado)
    logger.info(
        "Validacao OK: %d municipios, %d clusters K-Means, %d anomalias top30",
        len(consolidado),
        consolidado["cluster_kmeans"].nunique(),
        int(consolidado["flag_anomalia_top30"].sum()),
    )

    upload_dataframe_to_raw(
        consolidado,
        TABLE_ANALYTICS_IPB_CLUSTERS,
        if_exists="replace",
        source_url=SOURCE_URL,
    )
    logger.info("Publicada %s no BigQuery", TABLE_ANALYTICS_IPB_CLUSTERS)


if __name__ == "__main__":
    main()
