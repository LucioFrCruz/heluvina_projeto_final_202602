"""Ingestor de correspondentes bancarios do Banco Central do Brasil.

Fonte: API OData (Olinda) do dataset "Correspondentes Bancarios — Informes".

Regra de cache idempotente: se o parquet local ja existir em
``data/raw/bcb_correspondentes/bcb_correspondentes.parquet``, os dados sao
carregados do cache e a API NAO e consultada. A coleta em rede so ocorre
quando o cache nao existe ou quando ``run(refresh=True)`` e passado
explicitamente. Isso evita rebaixar ~217 mil registros a cada execucao e
garante reprodutibilidade da posicao ja coletada.
"""

import logging
import time
from pathlib import Path

import pandas as pd
import requests

from src.config import RAW_DATA_DIR, TABLE_RAW_BCB_CORRESPONDENTES
from src.utils.bigquery import upload_dataframe_to_raw
from src.utils.ibge import normalize_ibge_code
from src.utils.storage import load_raw_parquet, save_raw_parquet

logger = logging.getLogger(__name__)

SOURCE_NAME = "bcb_correspondentes"
SOURCE_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/Informes_Correspondentes/"
    "versao/v1/odata/Correspondentes"
)
CACHE_PATH = RAW_DATA_DIR / SOURCE_NAME / f"{SOURCE_NAME}.parquet"

PAGE_SIZE = 1000
MAX_RETRIES = 5
EXPECTED_MUNICIPIOS = 5570


def extract() -> pd.DataFrame:
    """Coleta paginada da API OData de correspondentes bancarios.

    Usa ``$top``/``$skip`` com retentativas e backoff exponencial em falhas.

    Returns:
        DataFrame com os dados brutos retornados pela API.
    """
    all_data: list[dict] = []
    skip = 0
    page = 1

    while True:
        params = {
            "$top": PAGE_SIZE,
            "$skip": skip,
            "$format": "json",
        }
        data = _fetch_page(params, page)
        if not data:
            break
        all_data.extend(data)
        logger.info("Pagina %d coletada: %d registros (total acumulado: %d)",
                    page, len(data), len(all_data))
        if len(data) < PAGE_SIZE:
            break
        skip += PAGE_SIZE
        page += 1
        time.sleep(0.3)

    return pd.DataFrame(all_data)


def _fetch_page(params: dict, page: int) -> list[dict]:
    """Executa GET em uma pagina com retentativa e backoff exponencial."""
    delay = 2.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                SOURCE_URL,
                params=params,
                headers={"Accept": "application/json"},
                timeout=120,
            )
            response.raise_for_status()
            return response.json().get("value", [])
        except requests.RequestException as exc:
            logger.warning(
                "Falha ao coletar pagina %d (tentativa %d/%d): %s",
                page, attempt, MAX_RETRIES, exc,
            )
            if attempt == MAX_RETRIES:
                raise
            time.sleep(delay)
            delay *= 2
    return []


def extract_cached(refresh: bool = False) -> tuple[pd.DataFrame, str]:
    """Retorna dados do cache local ou, inexistente o cache, coleta da API.

    Args:
        refresh: Se True, ignora o cache e rebaixa os dados da API.

    Returns:
        Tupla com o DataFrame e a origem utilizada ("cache" ou "api").
    """
    if refresh or not Path(CACHE_PATH).exists():
        if refresh:
            logger.info("Refresh explicito: rebaixando dados da API...")
        else:
            logger.info("Cache nao encontrado em %s. Coletando da API...", CACHE_PATH)
        df = extract()
        if df.empty:
            raise ValueError("API retornou zero registros de correspondentes.")
        return df, "api"

    logger.info("Cache encontrado em %s. Carregando sem consultar a API.", CACHE_PATH)
    return load_raw_parquet(SOURCE_NAME, SOURCE_NAME), "cache"


def transform_raw(raw_data: pd.DataFrame) -> pd.DataFrame:
    """Normalizacao minima dos correspondentes, mantendo colunas da fonte.

    Apenas garante a chave padronizada ``id_municipio`` a partir de
    ``MunicipioIBGE`` (7 digitos, string) e tipos corretos. As demais
    colunas sao preservadas como vieram da fonte (camada raw).
    """
    if raw_data.empty:
        raise ValueError("DataFrame de correspondentes esta vazio.")

    df = raw_data.copy()

    if "MunicipioIBGE" not in df.columns:
        raise ValueError("Coluna MunicipioIBGE ausente nos dados da fonte.")

    # Registros sem municipio (ex.: correspondente no exterior) ficam com
    # id_municipio nulo e sao mantidos para fidelidade com a fonte.
    df["id_municipio"] = df["MunicipioIBGE"].apply(
        lambda code: normalize_ibge_code(code) if pd.notna(code) else pd.NA
    )

    return df


def _log_municipios_check(df: pd.DataFrame) -> None:
    """Loga contagem de municipios distintos e discrepancias conhecidas."""
    distintos = df["id_municipio"].nunique(dropna=True)
    nulos = int(df["id_municipio"].isna().sum())
    logger.info(
        "Correspondentes: %d municipios distintos, %d registros sem codigo IBGE.",
        distintos, nulos,
    )

    if nulos:
        logger.warning(
            "Existem %d registros sem MunicipioIBGE (ex.: correspondentes no "
            "exterior). Mantidos na camada raw por fidelidade com a fonte.",
            nulos,
        )

    if distintos != EXPECTED_MUNICIPIOS:
        logger.warning(
            "Discrepancia conhecida: %d municipios distintos vs %d esperados "
            "(IBGE/SIDRA). Codigo 5101837 (Boa Esperanca do Norte/MT, extinto) "
            "explica a diferenca; investigar na Etapa 2. Nao falhando por isso.",
            distintos, EXPECTED_MUNICIPIOS,
        )

    # Cruza com o cache de localidades IBGE, quando disponivel, para logar
    # codigos fora da base oficial de municipios.
    localidades_path = RAW_DATA_DIR / "ibge_localidades" / "ibge_localidades.parquet"
    if Path(localidades_path).exists() and distintos:
        loc = pd.read_parquet(localidades_path, engine="pyarrow")
        codigos_loc = set(loc["id_municipio"].astype(str))
        extras = sorted(set(df["id_municipio"].dropna()) - codigos_loc)
        if extras:
            logger.warning(
                "Codigos IBGE em correspondentes ausentes em ibge_localidades: %s",
                extras,
            )


def run(refresh: bool = False) -> None:
    """Executa a coleta (ou leitura de cache) e carga dos correspondentes.

    Args:
        refresh: Se True, ignora o cache local e rebaixa da API.
    """
    logger.info("Coletando bcb_correspondentes...")
    raw_data, origem = extract_cached(refresh=refresh)
    logger.info("Origem dos dados: %s (%d registros brutos).", origem, len(raw_data))

    df = transform_raw(raw_data)
    _log_municipios_check(df)

    save_raw_parquet(df, SOURCE_NAME, SOURCE_NAME)
    upload_dataframe_to_raw(df, TABLE_RAW_BCB_CORRESPONDENTES, source_url=SOURCE_URL)
    logger.info("Sucesso: %d registros de correspondentes carregados.", len(df))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
