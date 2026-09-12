"""Testes unitarios de anomalias (src/analytics/anomalias.py).

Nuvem gaussiana 5D com UM ponto extremo: o Isolation Forest deve
ranquea-lo entre os mais atipicos.
"""
import numpy as np
import pandas as pd
import pytest

from src.analytics import anomalias as anom

FEATURES = [f"f{i}" for i in range(5)]


def _df_anomalia(n=200, seed=0):
    rng = np.random.default_rng(seed)
    dados = {f: rng.normal(0, 1, n) for f in FEATURES}
    df = pd.DataFrame(dados)
    # Um unico ponto extremo, distante de todo o resto.
    df.loc[0, FEATURES] = [50.0] * len(FEATURES)
    return df


def test_detecta_o_ponto_extremo_como_mais_atipico():
    df = _df_anomalia()

    resultado = anom.detectar_anomalias(df, FEATURES, n_top=10)

    assert list(resultado.columns) == ["score_anomalia", "flag_anomalia"]
    assert resultado.index.equals(df.index)
    # O ponto extremo esta entre os top mais atipicos.
    assert resultado.loc[0, "flag_anomalia"]
    assert resultado.loc[0, "score_anomalia"] == resultado["score_anomalia"].max()


def test_marca_exatamente_n_top_e_score_ordenavel():
    df = _df_anomalia()

    resultado = anom.detectar_anomalias(df, FEATURES, n_top=10)

    assert resultado["flag_anomalia"].sum() == 10
    # Os marcados sao exatamente os de maior score.
    marcados = resultado[resultado["flag_anomalia"]]["score_anomalia"]
    corte = resultado["score_anomalia"].nlargest(10).min()
    assert (marcados >= corte).all()


def test_reprodutivel_com_mesma_seed():
    df = _df_anomalia()
    r1 = anom.detectar_anomalias(df, FEATURES, n_top=10)
    r2 = anom.detectar_anomalias(df, FEATURES, n_top=10)

    pd.testing.assert_frame_equal(r1, r2)


def test_rejeita_feature_faltante_e_n_top_invalido():
    df = _df_anomalia()
    with pytest.raises(ValueError, match="ausentes"):
        anom.detectar_anomalias(df, FEATURES + ["fantasma"])
    with pytest.raises(ValueError, match="n_top"):
        anom.detectar_anomalias(df, FEATURES, n_top=0)
    with pytest.raises(ValueError, match="n_top"):
        anom.detectar_anomalias(df, FEATURES, n_top=len(df) + 1)
