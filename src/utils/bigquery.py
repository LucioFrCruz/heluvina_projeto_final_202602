from datetime import datetime, timezone
import os
from pathlib import Path

import pandas as pd
from google.cloud import bigquery
from src.config import (
    BASE_DIR,
    GCP_PROJECT_ID,
    BIGQUERY_DATASET,
    BIGQUERY_LOCATION,
)


def get_bigquery_client() -> bigquery.Client:
    """Retorna cliente autenticado."""
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path and not Path(creds_path).is_absolute():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(BASE_DIR / creds_path)
    return bigquery.Client(project=GCP_PROJECT_ID, location=BIGQUERY_LOCATION)

def upload_dataframe_to_raw(df: pd.DataFrame, table_name: str, if_exists: str = "replace", source_url: str = "") -> None:
    """
    Adiciona colunas de auditoria obrigatórias e realiza carga no BigQuery via Parquet.
    """
    client = get_bigquery_client()
    import re
    
    # Audit columns and sanitize names
    df_upload = df.copy()
    df_upload.columns = [re.sub(r'[^a-zA-Z0-9_]', '_', col) for col in df_upload.columns]
    
    df_upload["_extracted_at"] = datetime.now(timezone.utc)
    df_upload["_source_url"] = source_url
    
    table_id = f"{GCP_PROJECT_ID}.{BIGQUERY_DATASET}.{table_name}"
    
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE" if if_exists == "replace" else "WRITE_APPEND",
        source_format=bigquery.SourceFormat.PARQUET,
    )
    
    job = client.load_table_from_dataframe(df_upload, table_id, job_config=job_config)
    job.result()  # Wait for the job to complete

def read_table_to_dataframe(table_name: str) -> pd.DataFrame:
    """
    Executa leitura da tabela no BigQuery retornando DataFrame.

    Desabilita o BigQuery Storage API para evitar necessidade de permissão
    `bigquery.readsessions.create` em service accounts com acesso restrito.
    """
    client = get_bigquery_client()
    table_id = f"{GCP_PROJECT_ID}.{BIGQUERY_DATASET}.{table_name}"

    query = f"SELECT * FROM `{table_id}`"
    return client.query(query).to_dataframe(create_bqstorage_client=False)
