import logging
import time
from datetime import datetime

import pandas as pd
import requests

from src.config import TABLE_RAW_BCB_PIX
from src.utils.bigquery import upload_dataframe_to_raw
from src.utils.ibge import normalize_ibge_code
from src.utils.storage import save_raw_parquet

logger = logging.getLogger(__name__)


def _generate_last_n_months(n: int = 12) -> list[str]:
    """Gera lista de meses no formato YYYYMM a partir do mês anterior ao atual."""
    today = datetime.today()
    months = pd.date_range(end=today, periods=n + 1, freq="ME")[:-1]
    return [m.strftime("%Y%m") for m in months]


def extract(months: list[str] | None = None) -> pd.DataFrame:
    """Extrai dados da API do BCB Pix para os meses informados.

    Args:
        months: Lista de meses no formato YYYYMM. Se None, usa os últimos 12 meses.

    Returns:
        DataFrame com os dados brutos da API.
    """
    if months is None:
        months = _generate_last_n_months(12)

    all_data = []
    for mes in months:
        url = (
            f"https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/"
            f"TransacoesPixPorMunicipio(DataBase=@DataBase)?$format=json&@DataBase='{mes}'"
        )
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            data = response.json().get("value", [])
            all_data.extend(data)
            logger.info("Mês %s coletado: %d registros", mes, len(data))
        except requests.RequestException as exc:
            logger.warning("Falha ao coletar mês %s: %s", mes, exc)
        time.sleep(0.5)

    return pd.DataFrame(all_data)


def transform_raw(raw_data: pd.DataFrame) -> pd.DataFrame:
    """Transforma os dados brutos do BCB Pix."""
    if raw_data.empty:
        return pd.DataFrame(
            columns=[
                "id_municipio",
                "AnoMes",
                "VL_PagadorPF",
                "QT_PagadorPF",
                "VL_PagadorPJ",
                "QT_PagadorPJ",
                "VL_RecebedorPF",
                "QT_RecebedorPF",
                "VL_RecebedorPJ",
                "QT_RecebedorPJ",
            ]
        )

    df = raw_data.copy()

    # Renomear coluna de código IBGE para o padrão do projeto
    if "Municipio_Ibge" in df.columns:
        df = df.rename(columns={"Municipio_Ibge": "id_municipio"})

    if "id_municipio" in df.columns:
        df = df.dropna(subset=["id_municipio"])
        df["id_municipio"] = df["id_municipio"].apply(normalize_ibge_code)

    # Garante unicidade por municipio + mes, evitando duplicatas de execucoes
    # anteriores ou retornos acumulados da API.
    if "AnoMes" in df.columns:
        antes = len(df)
        df = df.drop_duplicates(subset=["id_municipio", "AnoMes"])
        removidos = antes - len(df)
        if removidos:
            logger.warning("Removidos %d registros duplicados de Pix.", removidos)

    return df


def run() -> None:
    """Executa a coleta e carga do Pix."""
    logger.info("Coletando bcb_pix...")
    raw_data = extract()
    df = transform_raw(raw_data)

    # Validação defensiva: nao deve haver duplicatas na camada raw
    if df.duplicated(subset=["id_municipio", "AnoMes"]).any():
        raise ValueError("Existem registros duplicados de Pix apos transformacao.")

    save_raw_parquet(df, "bcb_pix", "bcb_pix")
    upload_dataframe_to_raw(df, TABLE_RAW_BCB_PIX, source_url="https://olinda.bcb.gov.br/")
    logger.info("Sucesso: %d registros do Pix coletados.", len(df))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
