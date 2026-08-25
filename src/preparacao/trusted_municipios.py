import logging
import pandas as pd
from src.utils.storage import save_raw_parquet, load_raw_parquet
from src.utils.bigquery import upload_dataframe_to_raw
from src.config import TABLE_TRUSTED_MUNICIPIOS, PROCESSED_DATA_DIR

logger = logging.getLogger(__name__)


def run() -> None:
    logger.info("Iniciando consolidação Trusted...")
    
    # Lendo caches locais
    df_ibge = load_raw_parquet("ibge_localidades", "ibge_localidades")
    df_sidra = load_raw_parquet("sidra_censo_2022", "sidra_censo_2022")
    df_pix = load_raw_parquet("bcb_pix", "bcb_pix")
    df_pib = load_raw_parquet("ibge_pib_municipios", "ibge_pib_municipios")
    df_estban = load_raw_parquet("bcb_estban", "bcb_estban")
    df_anatel = load_raw_parquet("anatel_banda_larga_fixa", "anatel_banda_larga_fixa")
    
    # 1. Base IBGE (Tabela Mestra)
    trusted = df_ibge.copy()

    # Descarta registros mestres sem identificação geográfica (erro pontual na API IBGE)
    registros_antes = len(trusted)
    trusted = trusted.dropna(subset=["sigla_uf", "nome_uf"])
    descartados = registros_antes - len(trusted)
    if descartados:
        logger.warning(
            "%s município(s) descartado(s) por falta de UF na base IBGE", descartados
        )

    # 2. Join SIDRA
    trusted = trusted.merge(df_sidra, on="id_municipio", how="left")
    
    # 3. Join PIX
    # Pix tem múltiplos meses, agrupar por município
    df_pix_agg = df_pix.groupby("id_municipio").agg(
        pix_total_volume_12m=("VL_PagadorPF", "sum"),
        pix_total_transacoes_12m=("QT_PagadorPF", "sum")
    ).reset_index()
    trusted = trusted.merge(df_pix_agg, on="id_municipio", how="left")
    trusted["pix_total_volume_12m"] = trusted["pix_total_volume_12m"].fillna(0)
    trusted["pix_total_transacoes_12m"] = trusted["pix_total_transacoes_12m"].fillna(0)
    
    # 4. Join PIB
    # va_servicos está descartado da trusted: IBGE não divulgou a rubrica para 2023 no arquivo de origem.
    df_pib_sub = df_pib[["id_municipio", "pib", "pib_per_capita"]]
    trusted = trusted.merge(df_pib_sub, on="id_municipio", how="left")
    
    # 5. Join Estban
    trusted = trusted.merge(df_estban, on="id_municipio", how="left")
    # Regra de negócio: municípios sem registro bancário recebem 0
    trusted["quantidade_agencias"] = trusted["quantidade_agencias"].fillna(0)
    trusted["volume_depositos"] = trusted["volume_depositos"].fillna(0.0)
    trusted["volume_credito"] = trusted["volume_credito"].fillna(0.0)
    
    # 6. Join Anatel
    df_anatel_sub = df_anatel[["id_municipio", "densidade"]]
    trusted = trusted.merge(df_anatel_sub, on="id_municipio", how="left")
    trusted = trusted.rename(columns={"densidade": "banda_larga_fixa_por_100_hab"})
    
    # 7. Join PNUD IDHM (via Ipeadata, série ADH_IDHM, ano 2010)
    df_idhm = load_raw_parquet("pnud_idhm", "pnud_idhm")
    df_idhm_sub = df_idhm[["id_municipio", "idhm"]]
    trusted = trusted.merge(df_idhm_sub, on="id_municipio", how="left")
    
    # 8. Normalizações per capita / por 100 mil hab. (evita divisão por zero)
    pop_safe = trusted["populacao_total"].replace(0, None)
    trusted["pix_per_capita_12m"] = trusted["pix_total_volume_12m"] / pop_safe
    trusted["agencias_por_100k_hab"] = (trusted["quantidade_agencias"] / pop_safe) * 100_000
    trusted["depositos_per_capita"] = trusted["volume_depositos"] / pop_safe
    trusted["credito_per_capita"] = trusted["volume_credito"] / pop_safe
    
    # Salva processado
    trusted_file = PROCESSED_DATA_DIR / "trusted_municipios.parquet"
    trusted.to_parquet(trusted_file, engine="pyarrow", compression="snappy")
    
    # Upload para BQ
    upload_dataframe_to_raw(trusted, TABLE_TRUSTED_MUNICIPIOS, source_url="consolidation_script")
    logger.info("Consolidação concluída! %s registros processados.", len(trusted))

if __name__ == "__main__":
    run()
