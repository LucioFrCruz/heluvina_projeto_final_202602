"""
Testes de integridade da tabela analytics_ipb_clusters no BigQuery.

Seguem a cultura de data quality do projeto (mesmo padrao de
test_analytics_ipb.py): cobertura total dos 5.570 municipios, chave
unica, probabilidades em [0, 1], exatamente 30 anomalias marcadas,
potencial latente nao-negativo (nulo apenas onde o municipio tem agencia
na pratica — a estimativa nao observa o que ja se observa) e
consistencia da referencia ipb/rank com a analytics_ipb_v3.

Requer acesso ao BigQuery (mesmas credenciais dos ingestores); sem
rede/credenciais o teste pula em vez de falhar.
"""
from __future__ import annotations

import pytest

from src.config import TABLE_ANALYTICS_IPB_CLUSTERS, TABLE_ANALYTICS_IPB_V3
from src.utils.bigquery import read_table_to_dataframe

N_MUNICIPIOS = 5_570
CODIGO_MUNICIPIO_EXTINTO = "5101837"  # Boa Esperanca do Norte/MT (extinto)

COLUNAS_ESPERADAS = {
    "id_municipio",
    "nome_municipio",
    "sigla_uf",
    "nome_regiao",
    "estrato_populacional",
    "cluster_kmeans",
    "cluster_gmm",
    "prob_cluster_gmm",
    "arquetipo",
    "prob_tem_agencia_rf",
    "pred_tem_agencia_rf",
    "potencial_latente_depositos_pc",
    "score_anomalia",
    "flag_anomalia_top30",
    "ipb",
    "rank",
}


def _ler_tabela(nome: str):
    try:
        return read_table_to_dataframe(nome)
    except Exception as exc:  # sem rede/credenciais: pula em vez de falhar
        pytest.skip(f"BigQuery indisponível para {nome}: {exc}")


@pytest.fixture(scope="module")
def clusters():
    return _ler_tabela(TABLE_ANALYTICS_IPB_CLUSTERS)


def _chave(df):
    return df["id_municipio"].astype(str).str.zfill(7)


def test_cobertura_e_chave_unica(clusters):
    assert len(clusters) == N_MUNICIPIOS, f"{len(clusters)} linhas, esperado {N_MUNICIPIOS}"
    assert _chave(clusters).is_unique, "id_municipio com duplicatas"


def test_estrutura_do_schema(clusters):
    assert COLUNAS_ESPERADAS <= set(clusters.columns), (
        f"faltam colunas: {sorted(COLUNAS_ESPERADAS - set(clusters.columns))}"
    )


def test_probabilidades_em_faixa_e_sem_nulos(clusters):
    for coluna in ("prob_tem_agencia_rf", "prob_cluster_gmm"):
        assert clusters[coluna].notna().all(), f"nulos em {coluna}"
        assert clusters[coluna].between(0, 1).all(), f"{coluna} fora de [0, 1]"
    assert set(clusters["pred_tem_agencia_rf"].unique()) <= {0, 1}


def test_clusters_e_arquetipo_validos(clusters):
    assert (clusters["cluster_kmeans"] >= 0).all()
    assert (clusters["cluster_gmm"] >= 0).all()
    # K razoavel (nao degenerado em centenas de grupos, como documentado).
    assert clusters["cluster_kmeans"].nunique() < 50
    assert clusters["arquetipo"].notna().all()
    assert clusters["arquetipo"].str.len().gt(0).all()


def test_exatamente_30_anomalias_e_score_finito(clusters):
    assert int(clusters["flag_anomalia_top30"].sum()) == 30, (
        "flag_anomalia_top30 deve marcar exatamente 30 municipios"
    )
    assert clusters["score_anomalia"].notna().all()
    assert clusters.loc[clusters["flag_anomalia_top30"], "score_anomalia"].min() >= clusters.loc[
        ~clusters["flag_anomalia_top30"], "score_anomalia"
    ].max(), "flag top30 deve conter os maiores scores"


def test_potencial_latente_nao_negativo(clusters):
    preenchido = clusters["potencial_latente_depositos_pc"].dropna()
    assert not preenchido.empty, "potencial latente todo nulo: estimativa nao rodou"
    assert (preenchido >= 0).all()


def test_referencia_ipb_consistente_com_v3(clusters):
    """ipb/rank sao referencia de cruzamento copiada da V3: devem bater."""
    v3 = _ler_tabela(TABLE_ANALYTICS_IPB_V3)
    juncao = clusters.assign(id_municipio=_chave(clusters))[
        ["id_municipio", "ipb", "rank"]
    ].merge(
        v3.assign(id_municipio=_chave(v3))[["id_municipio", "ipb", "rank"]],
        on="id_municipio",
        how="inner",
        suffixes=("", "_v3"),
    )
    assert len(juncao) == N_MUNICIPIOS, "join clusters x v3 perdeu municipios"
    assert (juncao["ipb"].sub(juncao["ipb_v3"]).abs() < 1e-6).all(), "ipb divergente da V3"
    assert (juncao["rank"].sub(juncao["rank_v3"]).abs() < 1e-6).all(), "rank divergente da V3"


def test_municipio_extinto_fora_da_tabela(clusters):
    assert CODIGO_MUNICIPIO_EXTINTO not in set(_chave(clusters)), (
        "municipio extinto 5101837 nao deveria estar na tabela"
    )
