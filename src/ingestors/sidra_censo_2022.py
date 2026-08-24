import pandas as pd
import numpy as np
from src.utils.ibge import normalize_ibge_code
from src.utils.storage import save_raw_parquet
from src.utils.bigquery import upload_dataframe_to_raw
from src.config import TABLE_RAW_SIDRA_CENSO_2022
from src.utils.storage import load_raw_parquet

def extract() -> pd.DataFrame:
    """
    Mock da extração da API SIDRA (Agregados Censo 2022).
    Como os IDs das tabelas não estão especificados, geramos dados simulados
    baseados nos municípios reais coletados da tabela-mestra.
    """
    try:
        df_ibge = load_raw_parquet("ibge_localidades", "ibge_localidades")
        municipios = df_ibge["id_municipio"].tolist()
    except Exception:
        # Fallback if ibge is not yet run
        municipios = ["3550308", "3304557", "3106200"]
    
    np.random.seed(42)
    data = {
        "id_municipio": municipios,
        "populacao_total": np.random.randint(1000, 1000000, size=len(municipios)),
        "populacao_18_35_pct": np.random.uniform(15.0, 35.0, size=len(municipios)),
        "rendimento_domiciliar_per_capita": np.random.uniform(500, 5000, size=len(municipios)),
        "domicilios_com_internet_pct": np.random.uniform(30.0, 99.0, size=len(municipios)),
        "populacao_urbana_pct": np.random.uniform(40.0, 100.0, size=len(municipios)),
        "escolaridade_ensino_medio_pct": np.random.uniform(20.0, 80.0, size=len(municipios))
    }
    return pd.DataFrame(data)

def transform_raw(raw_data: pd.DataFrame) -> pd.DataFrame:
    """Transforma os dados brutos do SIDRA."""
    df = raw_data.copy()
    df["id_municipio"] = df["id_municipio"].apply(normalize_ibge_code)
    return df

def run() -> None:
    print("Coletando sidra_censo_2022 (Mock)...")
    raw_data = extract()
    df = transform_raw(raw_data)
    
    save_raw_parquet(df, "sidra_censo_2022", "sidra_censo_2022")
    upload_dataframe_to_raw(df, TABLE_RAW_SIDRA_CENSO_2022, source_url="mock_sidra")
    print(f"Sucesso: {len(df)} registros do SIDRA gerados.")

if __name__ == "__main__":
    run()
