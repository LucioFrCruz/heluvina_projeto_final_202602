import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "ipb_staging")
BIGQUERY_LOCATION = os.getenv("BIGQUERY_LOCATION", "US")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "ipb-raw-data-mba-projetc-final")


# Diretórios
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Tabelas
TABLE_RAW_IBGE_LOCALIDADES = "raw_ibge_localidades"
TABLE_RAW_SIDRA_CENSO_2022 = "raw_sidra_censo_2022"
TABLE_RAW_PIB_MUNICIPIOS = "raw_pib_municipios"
TABLE_RAW_BCB_PIX = "raw_bcb_pix_transacoes"
TABLE_RAW_BCB_ESTBAN = "raw_bcb_estban"
TABLE_RAW_ANATEL_BANDA_LARGA_FIXA = "raw_anatel_banda_larga_fixa"
TABLE_RAW_PNUD_IDHM = "raw_pnud_idhm"
TABLE_TRUSTED_MUNICIPIOS = "trusted_municipios"
