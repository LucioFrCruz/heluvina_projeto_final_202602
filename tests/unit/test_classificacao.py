"""Testes unitarios da classificacao binaria (src/analytics/classificacao.py).

Dados sinteticos do sklearn (make_classification) com sinal real: as
metricas dos modelos devem superar o acaso de forma clara.
"""
import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import make_classification

from src.analytics import classificacao as clf

FEATURES = [f"f{i}" for i in range(6)]


def _dados(n=400, seed=0):
    X, y = make_classification(
        n_samples=n,
        n_features=6,
        n_informative=3,
        n_redundant=0,
        random_state=seed,
    )
    return pd.DataFrame(X, columns=FEATURES), pd.Series(y, name="alvo")


def _split(seed=0):
    X, y = _dados(seed=seed)
    return X.iloc[:300], y.iloc[:300], X.iloc[300:], y.iloc[300:]


# ------------------------------------------------------------- matriz


def test_matriz_retorna_metricas_de_todos_os_modelos_no_teste():
    X_tr, y_tr, X_te, y_te = _split()

    matriz = clf.treinar_classificadores(X_tr, y_tr, X_te, y_te)

    assert list(matriz.columns) == clf.COLUNAS_MATRIZ
    assert set(matriz["modelo"]) == {"logistica", "random_forest", "knn", "arvore"}
    assert matriz["roc_auc"].between(0, 1).all()
    assert (matriz["tempo_seg"] >= 0).all()
    # Ordenado por ROC-AUC descendente.
    assert matriz["roc_auc"].is_monotonic_decreasing
    # Sinal real no brinquedo: todos superam o acaso com folga. A
    # logistica (linear) fica abaixo da RF aqui porque a geometria do
    # brinquedo nao e linear — patamar de comparacao fica para os
    # notebooks, com os dados reais.
    assert (matriz["roc_auc"] > 0.6).all()
    assert matriz.set_index("modelo").loc["random_forest", "roc_auc"] > 0.7


def test_matriz_reprodutivel_com_mesma_seed():
    m1 = clf.treinar_classificadores(*_split())
    m2 = clf.treinar_classificadores(*_split())

    # tempo_seg varia entre execucoes; as metricas sao reprodutiveis.
    colunas = [c for c in clf.COLUNAS_MATRIZ if c != "tempo_seg"]
    pd.testing.assert_frame_equal(m1[colunas], m2[colunas])


def test_matriz_rejeita_alvo_nao_binario():
    X_tr, y_tr, X_te, y_te = _split()
    y_ruim = y_tr.replace({0: 0, 1: 2})

    with pytest.raises(ValueError, match="binario"):
        clf.treinar_classificadores(X_tr, y_ruim, X_te, y_te)


def test_matriz_rejeita_colunas_divergentes():
    X_tr, y_tr, X_te, y_te = _split()

    with pytest.raises(ValueError, match="colunas"):
        clf.treinar_classificadores(X_tr, y_tr, X_te[FEATURES[::-1]], y_te)


# --------------------------------------------------------- importancia


def test_importancia_por_permutacao_ordenada_e_com_todas_features():
    X_tr, y_tr, _, _ = _split()
    modelo = clf.MODELOS["random_forest"].fit(X_tr, y_tr)

    importancia = clf.importancia_features(modelo, X_tr, y_tr, n_repeats=5)

    assert list(importancia.index) == FEATURES or set(importancia.index) == set(FEATURES)
    assert importancia.is_monotonic_decreasing
    assert (importancia >= 0).all()  # em dados com sinal, queda >= 0


# ------------------------------------------------------------- residuos


def _df_residuo_fake():
    return pd.DataFrame(
        {
            "id_municipio": ["1", "2", "3", "4"],
            "flag_tem_agencia": [0, 1, 0, 0],
        },
        index=[10, 11, 12, 13],
    )


def test_residuos_selecionam_so_falsos_negativos():
    df = _df_residuo_fake()
    prob = pd.Series([0.9, 0.9, 0.1, 0.4], index=df.index)  # altas, mas so id 1 e 4 sem agencia

    residuos = clf.extrair_residuos_oportunidade(
        df, "flag_tem_agencia", prob, colunas=["id_municipio", "flag_tem_agencia"]
    )

    assert residuos["id_municipio"].tolist() == ["1"]  # id 4 fica abaixo do limiar
    assert residuos["prob_prevista"].tolist() == [0.9]


def test_residuos_respeitam_limiar():
    df = _df_residuo_fake()
    prob = pd.Series([0.9, 0.9, 0.55, 0.4], index=df.index)

    residuos = clf.extrair_residuos_oportunidade(
        df, "flag_tem_agencia", prob, limiar=0.6
    )

    assert residuos.index.tolist() == [10]


def test_residuos_rejeitam_entrada_invalida():
    df = _df_residuo_fake()
    with pytest.raises(ValueError, match="nao encontrado"):
        clf.extrair_residuos_oportunidade(df, "fantasma", [0.1] * 4)
    with pytest.raises(ValueError, match="alinhadas"):
        clf.extrair_residuos_oportunidade(df, "flag_tem_agencia", [0.1] * 3)
    with pytest.raises(ValueError, match="\[0, 1\]"):
        clf.extrair_residuos_oportunidade(df, "flag_tem_agencia", [0.1] * 4, limiar=1.5)


# ---------------------------------------------------- matriz confusao


def test_matriz_confusao_2x2_legivel():
    _, _, _, y_te = _split()
    y_te = y_te.iloc[:50]
    prob = np.where(y_te.to_numpy() == 1, 0.9, 0.1)  # classificador quase perfeito
    prob[0], prob[1] = 0.1, 0.9  # um erro de cada tipo

    cm = clf.matriz_confusao(y_te, prob)

    assert list(cm.index) == ["obs_negativo", "obs_positivo"]
    assert list(cm.columns) == ["prev_negativo", "prev_positivo"]
    assert cm.to_numpy().sum() == 50


# ------------------------------------------------------- multiclasse


def _dados_multiclasse(n=300, seed=1):
    from sklearn.datasets import make_classification

    X, y = make_classification(
        n_samples=n,
        n_features=6,
        n_informative=4,
        n_classes=3,
        n_redundant=0,
        random_state=seed,
    )
    return pd.DataFrame(X, columns=FEATURES), pd.Series(y, name="cluster_kmeans")


def test_multiclasse_retorna_f1_macro_e_confusao_por_modelo():
    X, y = _dados_multiclasse()

    matriz, confusao = clf.treinar_multiclasse(X.iloc[:200], y.iloc[:200], X.iloc[200:], y.iloc[200:])

    assert list(matriz.columns) == clf.COLUNAS_MATRIZ_MULTICLASSE
    assert set(matriz["modelo"]) == {"random_forest", "logistica"}
    assert (matriz["f1_macro"] > 0.5).all()  # sinal real no brinquedo
    # Uma matriz de confusao 3x3 legivel por modelo.
    assert set(confusao.keys()) == {"random_forest", "logistica"}
    assert confusao["random_forest"].shape == (3, 3)
    assert confusao["random_forest"].to_numpy().sum() == 100


def test_multiclasse_rejeita_rotulo_unico():
    X, y = _dados_multiclasse()
    y_unico = pd.Series([0] * len(y))

    with pytest.raises(ValueError, match="ao menos 2 classes"):
        clf.treinar_multiclasse(X.iloc[:200], y_unico.iloc[:200], X.iloc[200:], y_unico.iloc[200:])
