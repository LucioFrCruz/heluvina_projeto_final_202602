"""Testes unitarios da regressao (src/analytics/regressao.py).

Brinquedos com relacao linear conhecida (y = combinacao das features +
ruido): os modelos devem recuperar a estrutura com R2 alto.
"""
import numpy as np
import pandas as pd
import pytest

from src.analytics import regressao as reg

FEATURES = [f"f{i}" for i in range(1, 6)]  # f1..f5, casando com o dict do brinquedo
N = 300


def _df_regressao(n=N, seed=0):
    rng = np.random.default_rng(seed)
    f1 = rng.normal(10, 2, n)
    f2 = rng.normal(5, 1, n)
    outras = [rng.normal(0, 1, n) for _ in range(3)]
    y = 3 * f1 + 2 * f2 + rng.normal(0, 0.5, n)  # sinal forte, pouco ruido
    dados = {"f1": f1, "f2": f2, "f3": outras[0], "f4": outras[1], "f5": outras[2]}
    return pd.DataFrame(dados, columns=FEATURES), pd.Series(y, name="alvo")


# ------------------------------------------------------ matriz


def test_matriz_retorna_metricas_de_todos_os_regressores():
    X, y = _df_regressao()
    matriz = reg.treinar_regressores(X.iloc[:200], y.iloc[:200], X.iloc[200:], y.iloc[200:])

    assert list(matriz.columns) == reg.COLUNAS_MATRIZ_REGRESSAO
    assert set(matriz["modelo"]) == {"ridge", "lasso", "random_forest"}
    assert (matriz["r2"] <= 1).all()
    assert matriz["r2"].is_monotonic_decreasing
    # Relacao linear com pouco ruido: R2 alto para todos (RF, sem
    # pressuposto de linearidade, fica naturalmente um pouco abaixo).
    assert (matriz["r2"] > 0.9).all()
    # MAE pequena frente a escala do alvo (~30-40).
    assert (matriz["mae"] < 2).all()


def test_matriz_rejeita_colunas_divergentes():
    X, y = _df_regressao()
    X_te_trocado = X.iloc[200:].rename(columns={"f5": "f5_trocado"})

    with pytest.raises(ValueError, match="colunas"):
        reg.treinar_regressores(X.iloc[:200], y.iloc[:200], X_te_trocado, y.iloc[200:])


# ------------------------------------------------------ explicar IPB


def test_explicar_ipb_detecta_features_que_constroem_o_alvo():
    df = pd.DataFrame(_df_regressao()[0])
    df["ipb"] = 2 * df["f1"] + df["f2"]  # "indice" construido das features

    matriz, importancia = reg.explicar_ipb(df, features=FEATURES)

    assert list(matriz.columns) == reg.COLUNAS_MATRIZ_REGRESSAO
    assert set(importancia.index) == set(FEATURES)
    assert importancia.is_monotonic_decreasing
    # f1 e f2 sustentam o alvo: as duas no topo, as irrelevantes embaixo.
    assert list(importancia.index[:2]) == ["f1", "f2"]
    assert (importancia.iloc[-3:] < importancia.iloc[0]).all()


def test_explicar_ipb_rejeita_coluna_faltante():
    df = pd.DataFrame(_df_regressao()[0])  # sem coluna ipb
    with pytest.raises(ValueError, match="ausentes"):
        reg.explicar_ipb(df)


# --------------------------------------------- potencial latente


def _df_latente(n=200, seed=0):
    """Metade com agencia (depositos > 0), metade sem (depositos = 0)."""
    X, _ = _df_regressao(n=n, seed=seed)
    depositos = 100 * X["f1"] + 50 * X["f2"] + np.random.default_rng(seed).normal(0, 20, n)
    flag = pd.Series([1] * (n // 2) + [0] * (n // 2))
    depositos = np.where(flag == 1, depositos, 0.0)
    df = X.copy()
    df["depositos_per_capita"] = depositos
    df["flag_tem_agencia"] = flag.values
    return df


def test_potencial_latente_so_estima_quem_nao_tem_agencia():
    df = _df_latente()

    estimativas, metricas = reg.estimar_potencial_latente(df, features=FEATURES)

    assert estimativas.index.equals(df.index)
    # Onde TEM agencia: NaN (nao se estima o que ja se observa).
    assert estimativas[df["flag_tem_agencia"] == 1].isna().all()
    # Onde NAO tem: estimativa positiva preenchida.
    sem = estimativas[df["flag_tem_agencia"] == 0]
    assert sem.notna().all()
    assert (sem > 0).all()
    # Metricas do holdout interno em escala original.
    assert list(metricas.columns) == ["mae", "rmse", "r2", "n_treino", "n_teste"]
    assert metricas["r2"].iloc[0] > 0.8


def test_potencial_latente_usa_somente_features_sem_presenca():
    assert set(reg.FEATURES_SEM_PRESENCA).isdisjoint(reg.FEATURES_PRESENCA)
    assert len(reg.FEATURES_SEM_PRESENCA) == 13  # 19 - 6 de presenca
    for col in reg.FEATURES_PRESENCA:
        assert col not in reg.FEATURES_SEM_PRESENCA


def test_potencial_latente_rejeita_flag_invalida():
    df = _df_latente()
    df_so_um_lado = df[df["flag_tem_agencia"] == 1].copy()

    with pytest.raises(ValueError, match="binaria"):
        reg.estimar_potencial_latente(df.assign(flag_tem_agencia=2), features=FEATURES)
    with pytest.raises(ValueError, match="com e sem agencia"):
        reg.estimar_potencial_latente(df.assign(flag_tem_agencia=1), features=FEATURES)
    with pytest.raises(ValueError, match="com e sem agencia"):
        reg.estimar_potencial_latente(df_so_um_lado, features=FEATURES)
