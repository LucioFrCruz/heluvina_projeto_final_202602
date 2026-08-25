from google.cloud import storage
import os
import logging
from src.config import GCS_BUCKET_NAME

logger = logging.getLogger(__name__)

def download_file_from_gcs(blob_name: str, local_path: str) -> str:
    """Faz o download de um arquivo do GCS para uma rota local temporária."""
    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(blob_name)
    
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    blob.download_to_filename(local_path)
    logger.info(f"Arquivo {blob_name} baixado com sucesso para {local_path}")
    return local_path
