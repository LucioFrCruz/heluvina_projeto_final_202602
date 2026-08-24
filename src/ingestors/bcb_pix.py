import requests
import pandas as pd
import time
from src.utils.ibge import normalize_ibge_code
from src.utils.storage import save_raw_parquet
from src.utils.bigquery import upload_dataframe_to_raw
from src.config import TABLE_RAW_BCB_PIX

def extract() -> pd.DataFrame:
    """Extrai dados da API do BCB Pix."""
    # Para testes, coletaremos apenas 1 mês (ex: 202312) para não sobrecarregar
    meses = ['202312']
    all_data = []
    
    for mes in meses:
        url = f"https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/TransacoesPixPorMunicipio(DataBase=@DataBase)?$format=json&@DataBase='{mes}'"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json().get('value', [])
            all_data.extend(data)
        time.sleep(0.5)
        
    return pd.DataFrame(all_data)

def transform_raw(raw_data: pd.DataFrame) -> pd.DataFrame:
    """Transforma os dados brutos do BCB Pix."""
    if raw_data.empty:
        return pd.DataFrame(columns=["id_municipio", "ano_mes", "quantidade_pf", "quantidade_pj", "valor_pf", "valor_pj"])
        
    df = raw_data.copy()
    # Mapeamento de colunas dependendo do retorno da API (assumindo nomes padrão)
    df = df.rename(columns={
        "Municipio": "id_municipio",
        "AnoMes": "ano_mes",
        "QuantidadePF": "quantidade_pf",
        "QuantidadePJ": "quantidade_pj",
        "ValorPF": "valor_pf",
        "ValorPJ": "valor_pj"
    })
    
    # Nem toda API retorna com a mesma key, vou fazer lower e remover sufixos se precisar
    # Mas como não temos o schema exato garantido, vou iterar pelas colunas se as esperadas não existirem
    # Assumindo que o mock está no padrão snake case
    if "id_municipio" not in df.columns and len(df.columns) > 0:
        # Tenta achar a coluna que parece município
        for col in df.columns:
            if "Municipio" in col or "ibge" in col.lower():
                df = df.rename(columns={col: "id_municipio"})
                break
                
    if "id_municipio" in df.columns:
        df["id_municipio"] = df["id_municipio"].apply(normalize_ibge_code)
    
    return df

def run() -> None:
    print("Coletando bcb_pix...")
    raw_data = extract()
    df = transform_raw(raw_data)
    
    save_raw_parquet(df, "bcb_pix", "bcb_pix")
    upload_dataframe_to_raw(df, TABLE_RAW_BCB_PIX, source_url="https://olinda.bcb.gov.br/")
    print(f"Sucesso: {len(df)} registros do Pix coletados.")

if __name__ == "__main__":
    run()
