import requests
import pandas as pd
from src.utils.ibge import normalize_ibge_code
from src.utils.storage import save_raw_parquet
from src.utils.bigquery import upload_dataframe_to_raw
from src.config import TABLE_RAW_IBGE_LOCALIDADES

def extract() -> pd.DataFrame:
    """Extrai dados da API do IBGE."""
    url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
    response = requests.get(url)
    response.raise_for_status()
    return pd.DataFrame(response.json())

def transform_raw(raw_data: pd.DataFrame) -> pd.DataFrame:
    """Transforma a tabela-mestra."""
    df = pd.DataFrame()
    df["id_municipio"] = raw_data["id"].apply(normalize_ibge_code)
    df["nome_municipio"] = raw_data["nome"]
    
    # Extrair uf e regiao
    microrregiao = raw_data["microrregiao"].apply(pd.Series)
    mesorregiao = microrregiao["mesorregiao"].apply(pd.Series)
    uf = mesorregiao["UF"].apply(pd.Series)
    regiao = uf["regiao"].apply(pd.Series)
    
    df["sigla_uf"] = uf["sigla"]
    df["nome_uf"] = uf["nome"]
    df["nome_regiao"] = regiao["nome"]
    
    return df

def run() -> None:
    print("Coletando ibge_localidades...")
    raw_data = extract()
    df = transform_raw(raw_data)
    
    # Cache local
    save_raw_parquet(df, "ibge_localidades", "ibge_localidades")
    
    # BigQuery
    upload_dataframe_to_raw(df, TABLE_RAW_IBGE_LOCALIDADES, source_url="https://servicodados.ibge.gov.br/api/v1/localidades/municipios")
    print(f"Sucesso: {len(df)} municípios coletados.")

if __name__ == "__main__":
    run()
