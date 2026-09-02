"""
Testes de integridade das tabelas analytics_ipb no BigQuery.

Validam a camada `analytics_` (produto final do IPB) lendo direto do
BigQuery, seguindo a cultura de data quality do projeto:

- 5.570 municípios, `id_municipio` único em cada tabela;
- IPBs em [0, 100], sem nulos; ranks contíguos (método ``min`` — empates
  compartilham a mesma posição, ex.: municípios com IPB 0);
- ``analytics_ipb_comparacao`` consistente com as 3 tabelas específicas;
- V3 com exatamente as colunas de features documentadas;
- Discrepância de cobertura conhecida: correspondentes cobrem 5.571
  municípios (inclui Boa Esperança do Norte/MT, código 5101837, município
  extinto) contra 5.570 da trusted.

Requer acesso ao BigQuery (mesmas credenciais dos ingestores).
"""
from __future__ import annotations

import pytest

from src.config import (
    TABLE_ANALYTICS_IPB_COMPARACAO,
    TABLE_ANALYTICS_IPB_V1,
    TABLE_ANALYTICS_IPB_V2,
    TABLE_ANALYTICS_IPB_V3,
    TABLE_RAW_BCB_CORRESPONDENTES,
)
from src.utils.bigquery import read_table_to_dataframe

N_MUNICIPIOS = 5_570
ESTRATOS = {"pequena", "media", "grande"}
COLUNAS_IDENTIDADE = {
    "id_municipio",
    "nome_municipio",
    "sigla_uf",
    "nome_regiao",
    "estrato_populacional",
}
COLUNAS_IPB = {"score_a", "score_b", "score_c", "score_d", "score_e", "ipb", "rank", "rank_estrato"}
COLUNAS_V3_EXTRAS = {
    "quantidade_correspondentes",
    "quantidade_correspondentes_posto",
    "quantidade_correspondentes_filial",
    "quantidade_correspondentes_sede",
    "quantidade_correspondentes_agencia",
    "correspondentes_por_100k_hab",
    "correspondentes_ponderados_por_100k_hab",
    "penetracao_digital_relativa",
    "gap_bancario_completo",
    "score_turismo",
}
CODIGO_MUNICIPIO_EXTINTO = "5101837"  # Boa Esperança do Norte/MT (extinto)


def _ler_tabela(nome: str):
    try:
        return read_table_to_dataframe(nome)
    except Exception as exc:  # sem rede/credenciais: pula em vez de falhar
        pytest.skip(f"BigQuery indisponível para {nome}: {exc}")


@pytest.fixture(scope="module")
def tabelas():
    return {
        "v1": _ler_tabela(TABLE_ANALYTICS_IPB_V1),
        "v2": _ler_tabela(TABLE_ANALYTICS_IPB_V2),
        "v3": _ler_tabela(TABLE_ANALYTICS_IPB_V3),
        "comparacao": _ler_tabela(TABLE_ANALYTICS_IPB_COMPARACAO),
    }


def _chave(df):
    return df["id_municipio"].astype(str).str.zfill(7)


@pytest.mark.parametrize("versao", ["v1", "v2", "v3", "comparacao"])
def test_cobertura_e_chave_unica(tabelas, versao):
    df = tabelas[versao]
    assert len(df) == N_MUNICIPIOS, f"{versao}: {len(df)} linhas, esperado {N_MUNICIPIOS}"
    assert _chave(df).is_unique, f"{versao}: id_municipio com duplicatas"


@pytest.mark.parametrize("versao", ["v1", "v2", "v3"])
def test_estrutura_e_identidade(tabelas, versao):
    df = tabelas[versao]
    assert COLUNAS_IDENTIDADE <= set(df.columns), f"{versao}: faltam colunas de identidade"
    assert COLUNAS_IPB <= set(df.columns), f"{versao}: faltam colunas de IPB/rank"
    assert set(df["estrato_populacional"].unique()) <= ESTRATOS
    assert df["nome_regiao"].notna().all()


@pytest.mark.parametrize("versao", ["v1", "v2", "v3"])
def test_ipb_em_faixa_e_sem_nulos(tabelas, versao):
    df = tabelas[versao]
    assert df["ipb"].notna().all(), f"{versao}: nulos em ipb"
    assert 0 <= df["ipb"].min() and df["ipb"].max() <= 100, f"{versao}: ipb fora de [0, 100]"


@pytest.mark.parametrize("versao", ["v1", "v2", "v3"])
def test_ranks_contiguos(tabelas, versao):
    """Ranks usam método ``min``: empates compartilham posição, então os
    valores únicos devem formar a sequência 1..N sem buracos."""
    df = tabelas[versao]
    for coluna, grupo in [("rank", None), ("rank_estrato", "estrato_populacional")]:
        grupos = [(None, df)] if grupo is None else df.groupby(grupo)
        for _, sub in grupos:
            ranks = sorted(sub[coluna].unique())
            assert ranks == list(range(1, len(ranks) + 1)), (
                f"{versao}.{coluna}: ranks com buracos ou não iniciados em 1"
            )


def test_comparacao_consistente_com_tabelas_especificas(tabelas):
    comp = tabelas["comparacao"].assign(id_municipio=lambda d: _chave(d))
    for versao, col_ipb in [("v1", "ipb_v1_classico"), ("v2", "ipb_v2_recalibrado"), ("v3", "ipb_v3_presenca_completa")]:
        especifica = tabelas[versao].assign(id_municipio=lambda d: _chave(d))
        assert col_ipb in comp.columns, f"comparacao sem coluna {col_ipb}"
        juncao = comp[["id_municipio", col_ipb]].merge(
            especifica[["id_municipio", "ipb"]], on="id_municipio", how="inner"
        )
        assert len(juncao) == N_MUNICIPIOS, f"comparacao x {versao}: join perdeu municípios"
        assert juncao[f"{col_ipb}"].sub(juncao["ipb"]).abs().max() < 1e-6, (
            f"comparacao x {versao}: IPBs divergentes"
        )


def test_v3_features_documentadas(tabelas):
    df = tabelas["v3"]
    assert COLUNAS_V3_EXTRAS <= set(df.columns), "V3: faltam colunas de features derivadas"
    assert (df["quantidade_correspondentes"] >= 0).all()
    for tipo in ["posto", "filial", "sede", "agencia"]:
        assert (df[f"quantidade_correspondentes_{tipo}"] >= 0).all()
    soma_tipos = (
        df["quantidade_correspondentes_posto"]
        + df["quantidade_correspondentes_filial"]
        + df["quantidade_correspondentes_sede"]
        + df["quantidade_correspondentes_agencia"]
    )
    assert soma_tipos.eq(df["quantidade_correspondentes"]).all(), (
        "V3: quantidade_correspondentes != soma dos tipos"
    )
    assert 0 <= df["score_turismo"].min() and df["score_turismo"].max() <= 1
    assert (df["gap_bancario_completo"] > 0).all(), "V3: gap_bancario_completo deve ser > 0"


def test_municipio_extinto_fora_das_analytics(tabelas):
    """Boa Esperança do Norte/MT (5101837, extinto) existe nos correspondentes
    mas não pode aparecer nas analytics (base = trusted, 5.570 municípios)."""
    for versao, df in tabelas.items():
        assert CODIGO_MUNICIPIO_EXTINTO not in set(_chave(df)), (
            f"{versao}: município extinto 5101837 não deveria estar na tabela"
        )


def test_cobertura_correspondentes_maior_que_trusted():
    """Discrepância conhecida documentada: a raw de correspondentes cobre
    5.571 municípios (inclui o extinto 5101837) contra 5.570 da trusted."""
    corr = _ler_tabela(TABLE_RAW_BCB_CORRESPONDENTES)
    municipios = set(corr["id_municipio"].dropna().astype(str).str.zfill(7))
    assert len(municipios) == N_MUNICIPIOS + 1, (
        f"correspondentes cobrem {len(municipios)} municípios, esperado {N_MUNICIPIOS + 1}"
    )
    assert CODIGO_MUNICIPIO_EXTINTO in municipios
