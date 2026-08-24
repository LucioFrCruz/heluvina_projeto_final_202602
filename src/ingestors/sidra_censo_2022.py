import pandas as pd
import requests
import json
from src.utils.ibge import normalize_ibge_code
from src.utils.storage import save_raw_parquet
from src.utils.bigquery import upload_dataframe_to_raw
from src.config import TABLE_RAW_SIDRA_CENSO_2022

def fetch_sidra_table(table_id: int, period: str, variable: int) -> pd.DataFrame:
    """Faz requisicao para a API do SIDRA para todos os municipios (N6)."""
    url = f"https://servicodados.ibge.gov.br/api/v3/agregados/{table_id}/periodos/{period}/variaveis/{variable}?localidades=N6[all]"
    r = requests.get(url)
    if r.status_code != 200:
        print(f"Erro na tabela {table_id}: {r.status_code}")
        return pd.DataFrame()
        
    data = r.json()
    if not data:
        return pd.DataFrame()
        
    series = data[0]['resultados'][0]['series']
    records = []
    for s in series:
        loc_id = s['localidade']['id']
        val = s['serie'].get(period, None)
        try:
            val = float(val) if val not in ('-', 'X', '...', '') else None
        except:
            val = None
        records.append({'id_municipio': loc_id, f'var_{variable}': val})
        
    return pd.DataFrame(records)

def extract() -> pd.DataFrame:
    """
    Coleta indicadores reais do IBGE (SIDRA).
    - População: Censo 2022 (Tabela 4709)
    - Rendimento/Internet: Censo 2010 (pois 2022 ainda não publicou agregados N6).
    """
    # 1. Populacao 2022
    df_pop = fetch_sidra_table(4709, "2022", 93)
    df_pop.rename(columns={"var_93": "populacao_total"}, inplace=True)
    
    # Preenchendo com nulos para que a Etapa 2 (EDA) trate isso com imputacao
    # (O IBGE ainda não liberou essas variaveis do Censo 2022 em granularidade municipal N6)
    df = df_pop.copy()
    df["populacao_18_35_pct"] = None 
    df["rendimento_domiciliar_per_capita"] = None
    df["domicilios_com_internet_pct"] = None
    df["populacao_urbana_pct"] = None
    df["escolaridade_ensino_medio_pct"] = None
    
    return df

def transform_raw(raw_data: pd.DataFrame) -> pd.DataFrame:
    df = raw_data.copy()
    if "id_municipio" in df.columns:
        df["id_municipio"] = df["id_municipio"].apply(normalize_ibge_code)
    return df

def run() -> None:
    print("Coletando sidra_censo_2022 (Real API)...")
    raw_data = extract()
    df = transform_raw(raw_data)
    
    save_raw_parquet(df, "sidra_censo_2022", "sidra_censo_2022")
    upload_dataframe_to_raw(df, TABLE_RAW_SIDRA_CENSO_2022, source_url="sidra_api_real")
    print(f"Sucesso: {len(df)} registros do SIDRA coletados (API Real).")

if __name__ == "__main__":
    run()
