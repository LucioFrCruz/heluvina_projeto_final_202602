"""
Testes de integridade da tabela raw_ibge_cempre no BigQuery.

Validam a camada `raw_` do CEMPRE lendo direto do BigQuery, seguindo a
cultura de data quality do projeto:

- 5.570 municípios distintos na seção CNAE "total" para cada variável;
- chave (id_municipio, variavel_codigo, cnae_secao) única;
- valores não nulos na seção "total" (sigilo estatístico só atinge
  seções detalhadas, com menos de 3 informantes);
- total nacional de unidades locais positivo e compatível com a
  divulgação do IBGE (ordem de grandeza de milhões).

Requer acesso ao BigQuery (mesmas credenciais dos ingestores).
"""
from __future__ import annotations

import pytest

from src.config import TABLE_RAW_IBGE_CEMPRE
from src.utils.bigquery import read_table_to_dataframe

N_MUNICIPIOS = 5_570


def _ler_tabela():
    try:
        return read_table_to_dataframe(TABLE_RAW_IBGE_CEMPRE)
    except Exception as exc:  # sem rede/credenciais: pula em vez de falhar
        pytest.skip(f"BigQuery indisponível para {TABLE_RAW_IBGE_CEMPRE}: {exc}")


def test_total_cnae_cobre_5570_municipios_por_variavel():
    df = _ler_tabela()
    total = df[df["cnae_secao"] == "total"]
    for variavel in ["unidades_locais", "pessoal_ocupado_total"]:
        subset = total[total["variavel"] == variavel]
        assert subset["id_municipio"].nunique() == N_MUNICIPIOS


def test_chave_unica_municipio_variavel_cnae():
    df = _ler_tabela()
    chave = ["id_municipio", "variavel_codigo", "cnae_secao"]
    assert not df.duplicated(subset=chave).any()


def test_secao_total_sem_valores_nulos():
    df = _ler_tabela()
    total = df[df["cnae_secao"] == "total"]
    assert total["valor"].notna().all()


def test_total_nacional_ordem_de_grandeza():
    df = _ler_tabela()
    total = df[(df["cnae_secao"] == "total") & (df["variavel"] == "unidades_locais")]
    nacional = total["valor"].sum()
    assert 5_000_000 < nacional < 50_000_000  # ~11,9 milhões em 2024
