from pathlib import Path
import pandas as pd
from src.config import RAW_DATA_DIR

def save_raw_parquet(df: pd.DataFrame, source_name: str, filename: str) -> Path:
    """
    Salva DataFrame em data/raw/{source_name}/{filename}.parquet com compressão snappy.
    Cria diretórios pais automaticamente se não existirem.
    """
    source_dir = RAW_DATA_DIR / source_name
    source_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = source_dir / f"{filename}.parquet"
    df.to_parquet(file_path, engine="pyarrow", compression="snappy")
    return file_path

def load_raw_parquet(source_name: str, filename: str) -> pd.DataFrame:
    """
    Lê arquivo Parquet do cache local.
    """
    file_path = RAW_DATA_DIR / source_name / f"{filename}.parquet"
    return pd.read_parquet(file_path, engine="pyarrow")
