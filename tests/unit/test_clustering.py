"""Testes unitarios da clusterizacao (src/analytics/clustering.py).

Blobs sinteticos do sklearn (make_blobs) com estrutura conhecida: 3
grupos bem separados, para os quais K=3 deve recuperar silhouette alta.
"""
import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import make_blobs

from src.analytics import clustering as clu

FEATURES = ["f1", "f2", "f3", "f4", "f5"]
N = 300


def _blobs(n=N, seed=0):
    X, _ = make_blobs(
        n_samples=n, centers=3, n_features=5, cluster_std=0.6, random_state=seed
    )
    return pd.DataFrame(X, columns=FEATURES)


# ------------------------------------------------------------ avaliar_k


def test_avaliar_k_retorna_contrato_para_cada_k():
    df = _blobs()
    resultado = clu.avaliar_k(df, FEATURES, ks=[2, 3, 4])

    assert list(resultado.columns) == clu.COLUNAS_AVALIACAO_K
    assert resultado["k"].tolist() == [2, 3, 4]
    assert resultado["silhouette_kmeans"].between(-1, 1).all()
    # BIC so tem sentido comparando K entre si (menor melhor) — o sinal
    # absoluto depende dos dados, entao aqui so checamos ser finito.
    assert np.isfinite(resultado["bic_gmm"]).all()
    assert (resultado["tempo_seg_kmeans"] >= 0).all()


def test_avaliar_k_bem_separado_tem_silhouette_alta_no_k_cert():
    df = _blobs()
    resultado = clu.avaliar_k(df, FEATURES, ks=[3]).iloc[0]

    assert resultado["silhouette_kmeans"] > 0.8
    assert resultado["silhouette_gmm"] > 0.8


def test_avaliar_k_rejeita_k_menor_que_2():
    with pytest.raises(ValueError, match="k >= 2"):
        clu.avaliar_k(_blobs(), FEATURES, ks=[1, 3])


def test_avaliar_k_rejeita_feature_faltante():
    with pytest.raises(ValueError, match="ausentes"):
        clu.avaliar_k(_blobs(), FEATURES + ["fantasma"], ks=[3])


# --------------------------------------------------------- ajuste final


def test_ajustar_kmeans_retorna_labels_validos_e_reprodutivel():
    df = _blobs()
    _, labels1, scaler1 = clu.ajustar_kmeans(df, FEATURES, k=3)
    _, labels2, _ = clu.ajustar_kmeans(df, FEATURES, k=3)

    assert labels1.name == "cluster_kmeans"
    assert labels1.index.equals(df.index)
    assert set(labels1.unique()) == {0, 1, 2}
    assert labels1.equals(labels2)  # mesma seed -> mesmo agrupamento
    assert np.allclose(scaler1.mean_, df[FEATURES].mean(), atol=1e-6)


def test_ajustar_gmm_retorna_probs_que_somam_um():
    df = _blobs()
    _, labels, probs, _ = clu.ajustar_gmm(df, FEATURES, k=3)

    assert labels.name == "cluster_gmm"
    assert list(probs.columns) == ["prob_cluster_0", "prob_cluster_1", "prob_cluster_2"]
    assert probs.index.equals(df.index)
    assert np.allclose(probs.sum(axis=1), 1.0)


def test_ajustar_rejeita_k_invalido():
    with pytest.raises(ValueError, match=">= 2"):
        clu.ajustar_kmeans(_blobs(), FEATURES, k=1)
    with pytest.raises(ValueError, match=">= 2"):
        clu.ajustar_gmm(_blobs(), FEATURES, k=1)


# -------------------------------------------------------------- perfis


def test_perfis_clusters_tamanho_medias_e_desvios():
    df = _blobs()
    _, labels, _ = clu.ajustar_kmeans(df, FEATURES, k=3)

    perfis = clu.perfis_clusters(df, FEATURES, labels)

    assert len(perfis) == 3
    assert perfis["n_municipios"].sum() == N
    assert perfis["pct_municipios"].sum() == pytest.approx(100.0)
    for f in FEATURES:
        assert f"{f}_media" in perfis.columns
        assert f"{f}_desvio" in perfis.columns


def test_perfis_rejeita_labels_com_tamanho_errado():
    df = _blobs()
    with pytest.raises(ValueError, match="tamanho"):
        clu.perfis_clusters(df, FEATURES, pd.Series([0, 1]))


# ------------------------------------------------- nomes dos arquetipos


def _perfis_fake():
    """3 clusters: um turistico, um 'sem rede' e um intermediario."""
    return pd.DataFrame(
        {
            "n_municipios": [10, 10, 10],
            "unidades_alojamento_alimentacao_por_1000_hab_media": [100.0, 1.0, 1.0],
            "pix_pj_pct_media": [1.0, 1.0, 1.0],
            "empregos_formais_por_1000_hab_media": [1.0, 1.0, 1.0],
            "agencias_por_100k_hab_media": [1.0, 1.0, 0.001],
            "correspondentes_por_100k_hab_media": [1.0, 1.0, 1.0],
        },
        index=[0, 1, 2],
    )


def test_sugerir_nomes_detecta_regras_pelos_dados():
    nomes = clu.sugerir_nomes_perfis(_perfis_fake())

    assert nomes[0] == "Turismo"  # alojamento 100x a media nacional
    assert nomes[1] == clu.NOME_PADRAO_PERFIL  # nada destoa
    assert nomes[2] == "Sem rede bancaria"  # agencias ~0 vs nacional


def test_sugerir_nomes_rejeita_perfil_sem_colunas():
    with pytest.raises(ValueError, match="obrigatorias"):
        clu.sugerir_nomes_perfis(pd.DataFrame({"n_municipios": [10]}))


def _perfis_com_repeticao():
    """6 clusters formando pares de nomes repetidos (Turismo, Sem rede,
    Intermediario) — cenário que exige a desambiguação pelos dados."""
    return pd.DataFrame(
        {
            "n_municipios": [100] * 6,
            "unidades_alojamento_alimentacao_por_1000_hab_media": [90.0, 1.0, 1.0, 90.0, 1.0, 1.0],
            "pix_pj_pct_media": [1.0, 1.0, 0.9, 1.0, 1.0, 1.1],
            "empregos_formais_por_1000_hab_media": [1.0] * 6,
            "agencias_por_100k_hab_media": [10.0, 0.001, 1.0, 0.5, 0.002, 5.0],
            "correspondentes_por_100k_hab_media": [1.0] * 6,
            "pib_per_capita_media": [1.0, 10.0, 50.0, 1.0, 1.0, 1.0],
        },
        index=[0, 1, 2, 3, 4, 5],
    )


def test_sugerir_nomes_desambigua_pares_repetidos_pelos_dados():
    nomes = clu.sugerir_nomes_perfis(_perfis_com_repeticao())

    # Nomes unicos por construcao e discriminadores corretos em cada par.
    assert len(set(nomes.values())) == 6
    assert nomes[0] == "Turismo - com rede"
    assert nomes[3] == "Turismo - sem banco"
    assert nomes[1] == "Sem rede bancaria - renda alta"
    assert nomes[4] == "Sem rede bancaria - renda baixa"
    assert nomes[2] == "Perfil intermediario - tradicional"
    assert nomes[5] == "Perfil intermediario - empresarial"
