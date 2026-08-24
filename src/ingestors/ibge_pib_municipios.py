import pandas as pd
from src.utils.ibge import normalize_ibge_code
from src.utils.storage import save_raw_parquet
from src.utils.bigquery import upload_dataframe_to_raw
from src.utils.gcs import download_file_from_gcs
from src.config import TABLE_RAW_PIB_MUNICIPIOS, RAW_DATA_DIR
import warnings

def extract() -> pd.DataFrame:
    """Lê arquivo XLSX do PIB dos Municípios do GCS."""
    warnings.simplefilter(action='ignore', category=UserWarning)
    local_path = str(RAW_DATA_DIR / "tmp_pib.xlsx")
    file_path = download_file_from_gcs("pib/pib_municipios_2010_2023.xlsx", local_path)
    return pd.read_excel(file_path)

def transform_raw(raw_data: pd.DataFrame) -> pd.DataFrame:
    """Filtra o ano mais recente e padroniza."""
    df = raw_data.copy()
    
    # Assumindo a coluna 'Ano' existe
    if 'Ano' in df.columns:
        ano_max = df['Ano'].max()
        df = df[df['Ano'] == ano_max]
    
    # Renomear colunas
    col_mapping = {}
    for col in df.columns:
        c_lower = str(col).lower()
        if "código" in c_lower and "município" in c_lower:
            col_mapping[col] = "id_municipio"
        elif "produto interno bruto per capita" in c_lower:
            col_mapping[col] = "pib_per_capita"
        elif "produto interno bruto, " in c_lower and "preços correntes" in c_lower:
            col_mapping[col] = "pib"
        elif "valor adicionado bruto dos serviços" in c_lower:
            col_mapping[col] = "va_servicos"
    
    if col_mapping:
        df = df.rename(columns=col_mapping)
        
    if "id_municipio" in df.columns:
        df["id_municipio"] = df["id_municipio"].apply(normalize_ibge_code)
    
    return df

def run() -> None:
    print("Coletando ibge_pib_municipios...")
    raw_data = extract()
    df = transform_raw(raw_data)
    
    save_raw_parquet(df, "ibge_pib_municipios", "ibge_pib_municipios")
    upload_dataframe_to_raw(df, TABLE_RAW_PIB_MUNICIPIOS, source_url="local_file")
    print(f"Sucesso: {len(df)} registros de PIB processados.")

if __name__ == "__main__":
    run()
