import requests
import pandas as pd
from datetime import datetime, timezone
from src.utils.ibge import normalize_ibge_code
from src.utils.storage import save_raw_parquet
from src.utils.bigquery import upload_dataframe_to_raw
from src.config import TABLE_RAW_PNUD_IDHM

# Fonte: Ipeadata (IPEA) - série ADH_IDHM
# O IPEA é parceiro do Atlas do Desenvolvimento Humano no Brasil (PNUD/IPEA/FJP).
# Essa série reproduz o IDHM municipal calculado a partir do Censo Demográfico.
API_URL = "http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='ADH_IDHM')"
SOURCE_URL = "http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='ADH_IDHM')"


def extract() -> pd.DataFrame:
    """
    Extrai o IDHM municipal da API do Ipeadata.

    A série ADH_IDHM contém o Índice de Desenvolvimento Humano Municipal (IDHM)
    para os anos de referência 1991, 2000 e 2010, calculado pelo IPEA a partir
    dos Censos Demográficos do IBGE.

    Returns:
        DataFrame bruto com todos os valores da série ADH_IDHM.
    """
    response = requests.get(API_URL, timeout=120)
    response.raise_for_status()
    data = response.json()
    return pd.DataFrame(data["value"])


def transform_raw(raw_data: pd.DataFrame) -> pd.DataFrame:
    """
    Transforma os dados brutos do Ipeadata no schema raw_pnud_idhm.

    Passos:
        1. Filtra apenas o nível territorial "Municípios".
        2. Seleciona o ano de referência 2010 (último Censo disponível).
        3. Padroniza o código IBGE para 7 dígitos.
        4. Remove duplicatas por município.
        5. Adiciona metadados de auditoria (_source_url, _extracted_at).
    """
    df = raw_data.copy()

    # Converte data de referência para ano
    df["ano"] = pd.to_datetime(df["VALDATA"]).dt.year

    # Filtra apenas municípios e ano de 2010
    df = df[df["NIVNOME"] == "Municípios"].copy()
    df = df[df["ano"] == 2010].copy()

    # Renomeia e padroniza a chave primária
    df = df.rename(columns={"TERCODIGO": "id_municipio", "VALVALOR": "idhm"})
    df["id_municipio"] = df["id_municipio"].astype(str).apply(normalize_ibge_code)

    # Seleciona colunas finais
    df = df[["id_municipio", "ano", "idhm"]].copy()

    # Remove possíveis duplicatas (município aparece uma única vez por ano)
    df = df.drop_duplicates(subset=["id_municipio"], keep="first")

    # Adiciona colunas de auditoria
    df["_source_url"] = SOURCE_URL
    df["_extracted_at"] = datetime.now(timezone.utc)

    return df


def run() -> None:
    """Executa a coleta, transformação e carga do IDHM municipal."""
    print("Coletando PNUD IDHM via Ipeadata (série ADH_IDHM, ano 2010)...")

    raw_data = extract()
    df = transform_raw(raw_data)

    # Cache local em Parquet
    save_raw_parquet(df, "pnud_idhm", "pnud_idhm")

    # Carga na camada raw do BigQuery
    upload_dataframe_to_raw(df, TABLE_RAW_PNUD_IDHM, source_url=SOURCE_URL)

    print(f"Sucesso: {len(df)} municípios com IDHM 2010 coletados.")


if __name__ == "__main__":
    run()
