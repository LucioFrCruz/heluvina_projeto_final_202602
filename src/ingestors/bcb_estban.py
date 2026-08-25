import pandas as pd
from src.utils.ibge import normalize_ibge_code
from src.utils.storage import save_raw_parquet
from src.utils.bigquery import upload_dataframe_to_raw
from src.utils.gcs import download_file_from_gcs
from src.config import TABLE_RAW_BCB_ESTBAN, RAW_DATA_DIR

def extract() -> pd.DataFrame:
    """Lê arquivo CSV do BCB Estban do GCS."""
    local_path = str(RAW_DATA_DIR / "tmp_estban.csv")
    file_path = download_file_from_gcs("estban/202603_ESTBAN.CSV", local_path)
    return pd.read_csv(file_path, sep=";", encoding="latin1", skiprows=2)

def transform_raw(raw_data: pd.DataFrame) -> pd.DataFrame:
    """Agrupa Estban por município."""
    df = raw_data.copy()
    
    # Coluna CODMUN_IBGE
    if "CODMUN_IBGE" in df.columns:
        df = df.dropna(subset=["CODMUN_IBGE"])
        df["CODMUN_IBGE"] = df["CODMUN_IBGE"].apply(normalize_ibge_code)
    
    # Extrair Agências e rubricas reais
    # Se a coluna existir, agrupa, senao dummy
    agg_dict = {}
    if "AGEN_PROCESSADAS" in df.columns:
        df["AGEN_PROCESSADAS"] = pd.to_numeric(df["AGEN_PROCESSADAS"], errors="coerce").fillna(0)
        agg_dict["quantidade_agencias"] = pd.NamedAgg(column="AGEN_PROCESSADAS", aggfunc="sum")
    else:
        agg_dict["quantidade_agencias"] = pd.NamedAgg(column="CODMUN_IBGE", aggfunc="count")
        
    if "VERBETE_420_DEPOSITOS_DE_POUPANCA" in df.columns:
        df["VERBETE_420_DEPOSITOS_DE_POUPANCA"] = pd.to_numeric(df["VERBETE_420_DEPOSITOS_DE_POUPANCA"], errors="coerce").fillna(0)
        agg_dict["volume_depositos"] = pd.NamedAgg(column="VERBETE_420_DEPOSITOS_DE_POUPANCA", aggfunc="sum")
    else:
        agg_dict["volume_depositos"] = pd.NamedAgg(column="CODMUN_IBGE", aggfunc="count")
        
    if "VERBETE_160_OPERACOES_DE_CREDITO" in df.columns:
        df["VERBETE_160_OPERACOES_DE_CREDITO"] = pd.to_numeric(df["VERBETE_160_OPERACOES_DE_CREDITO"], errors="coerce").fillna(0)
        agg_dict["volume_credito"] = pd.NamedAgg(column="VERBETE_160_OPERACOES_DE_CREDITO", aggfunc="sum")
    else:
        agg_dict["volume_credito"] = pd.NamedAgg(column="CODMUN_IBGE", aggfunc="count")
        
    result = df.groupby("CODMUN_IBGE").agg(**agg_dict).reset_index()
    
    result = result.rename(columns={"CODMUN_IBGE": "id_municipio"})
    
    return result

def run() -> None:
    print("Coletando bcb_estban...")
    raw_data = extract()
    df = transform_raw(raw_data)
    
    save_raw_parquet(df, "bcb_estban", "bcb_estban")
    upload_dataframe_to_raw(df, TABLE_RAW_BCB_ESTBAN, source_url="local_file")
    print(f"Sucesso: {len(df)} registros do Estban processados.")

if __name__ == "__main__":
    run()
