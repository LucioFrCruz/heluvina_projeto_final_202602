import pandas as pd
from src.utils.ibge import normalize_ibge_code
from src.utils.storage import save_raw_parquet
from src.utils.bigquery import upload_dataframe_to_raw
from src.config import TABLE_RAW_ANATEL_BANDA_LARGA_FIXA, RAW_DATA_DIR

def extract() -> pd.DataFrame:
    """Lê arquivo CSV da Anatel Banda Larga Fixa."""
    source_dir = RAW_DATA_DIR / "anatel_banda_larga"
    # Pegar o Densidade_Banda_Larga_Fixa.csv
    file_path = source_dir / "Densidade_Banda_Larga_Fixa.csv"
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo CSV Anatel não encontrado em {file_path}")
    
    return pd.read_csv(file_path, sep=";", encoding="utf-8-sig")

def transform_raw(raw_data: pd.DataFrame) -> pd.DataFrame:
    """Transforma dados da Anatel."""
    df = raw_data.copy()
    
    # Encontrar as colunas certas, assumindo que variam um pouco
    col_mapping = {}
    for col in df.columns:
        c_lower = str(col).lower()
        if "código" in c_lower and "ibge" in c_lower:
            col_mapping[col] = "id_municipio"
        elif c_lower == "densidade":
            col_mapping[col] = "densidade"
        elif "ano" in c_lower:
            col_mapping[col] = "ano"
        elif "mês" in c_lower or "mes" in c_lower:
            col_mapping[col] = "mes"
            
    if col_mapping:
        df = df.rename(columns=col_mapping)
        
    if "ano" in df.columns and "mes" in df.columns:
        # Filtrar mais recente 2026-06 (ou max)
        max_ano = df["ano"].max()
        df = df[df["ano"] == max_ano]
        max_mes = df["mes"].max()
        df = df[df["mes"] == max_mes]
        
    if "id_municipio" in df.columns:
        df["id_municipio"] = df["id_municipio"].apply(normalize_ibge_code)
        
    if "densidade" in df.columns:
        # Tratar vírgula decimal
        if df["densidade"].dtype == object:
            df["densidade"] = df["densidade"].str.replace(",", ".").astype(float)
            
    return df

def run() -> None:
    print("Coletando anatel_banda_larga_fixa...")
    raw_data = extract()
    df = transform_raw(raw_data)
    
    save_raw_parquet(df, "anatel_banda_larga_fixa", "anatel_banda_larga_fixa")
    upload_dataframe_to_raw(df, TABLE_RAW_ANATEL_BANDA_LARGA_FIXA, source_url="local_file")
    print(f"Sucesso: {len(df)} registros da Anatel processados.")

if __name__ == "__main__":
    run()
