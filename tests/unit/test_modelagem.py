"""Testes unitarios do dataset de modelagem (src/analytics/modelagem.py).

Sem rede: os DataFrames sao brinquedos deterministicos gerados em memoria.
"""
import numpy as np
import pandas as pd
import pytest

from src.analytics import modelagem as mod

N = 8


def _trusted_fake(n=N):
    """Trusted de brinquedo com o contrato completo."""
    ids = [f"11000{i:02d}" for i in range(n)]
    return pd.DataFrame(
        {
            "id_municipio": ids,
            "nome_municipio": [f"Municipio {i}" for i in range(n)],
            "sigla_uf": ["SP"] * n,
            "nome_regiao": ["Sudeste"] * n,
            "estrato_populacional": ["pequena"] * n,
            "populacao_total": [10_000 * (i + 1) for i in range(n)],
            "populacao_18_35_pct": [30.0] * n,
            "populacao_urbana_pct": [80.0] * n,
            "rendimento_domiciliar_per_capita": [500.0 + i for i in range(n)],
            "escolaridade_ensino_medio_pct": [40.0] * n,
            "pib_per_capita": [10_000.0 + i for i in range(n)],
            "pix_per_capita_12m": [1_000.0 + i for i in range(n)],
            "pix_pj_pct": [0.3] * n,
            "pix_ticket_medio": [100.0] * n,
            "banda_larga_fixa_por_100_hab": [20.0] * n,
            # Alterna 1/0 para garantir as duas classes do alvo.
            "quantidade_agencias": [i % 2 for i in range(n)],
            "agencias_por_100k_hab": [10.0] * n,
            "depositos_per_capita": [1_000.0] * n,
            "credito_per_capita": [500.0] * n,
        }
    )


def _v3_fake(ids):
    """Analytics V3 de brinquedo (CEMPRE, correspondentes, referencia)."""
    n = len(ids)
    return pd.DataFrame(
        {
            "id_municipio": ids,
            "ipb": [10.0 + i for i in range(n)],
            "rank": list(range(1, n + 1)),
            "empregos_formais_por_1000_hab": [200.0] * n,
            "unidades_locais_por_1000_hab": [50.0] * n,
            "unidades_alojamento_alimentacao_por_1000_hab": [5.0] * n,
            "quantidade_correspondentes": [i % 2 for i in range(n)],
            "correspondentes_por_100k_hab": [30.0] * n,
        }
    )


def _dataset_fake(n=N):
    trusted = _trusted_fake(n)
    return mod.montar_dataset_modelagem(trusted, _v3_fake(trusted["id_municipio"]), n_esperado=n)


# ---------------------------------------------------------------- builder


def test_montar_retorna_contrato_com_features_alvos_e_referencia():
    df = _dataset_fake()

    assert len(df) == N
    assert list(df.columns) == (
        mod.COLUNAS_IDENTIDADE + mod.FEATURES_MODELO + mod.ALVOS + mod.COLUNAS_REFERENCIA_IPB
    )
    # Alvo agencia: alterna 1/0 conforme quantidade_agencias.
    assert df["flag_tem_agencia"].tolist() == [i % 2 for i in range(N)]
    assert df["flag_tem_correspondente"].tolist() == [i % 2 for i in range(N)]


def test_montar_normaliza_id_municipio_int_e_str():
    trusted = _trusted_fake()
    trusted["id_municipio"] = trusted["id_municipio"].astype(int)

    df = mod.montar_dataset_modelagem(trusted, _v3_fake(_trusted_fake()["id_municipio"]), n_esperado=N)

    assert df["id_municipio"].tolist() == [f"11000{i:02d}" for i in range(N)]


def test_montar_rejeita_coluna_faltante():
    with pytest.raises(ValueError, match="obrigatorias"):
        mod.montar_dataset_modelagem(
            _trusted_fake().drop(columns=["pib_per_capita"]),
            _v3_fake(_trusted_fake()["id_municipio"]),
            n_esperado=N,
        )


def test_montar_rejeita_id_duplicado():
    trusted = pd.concat([_trusted_fake(), _trusted_fake().iloc[[0]]], ignore_index=True)

    with pytest.raises(ValueError, match="duplicado"):
        mod.montar_dataset_modelagem(
            trusted, _v3_fake(trusted["id_municipio"]), n_esperado=N + 1
        )


def test_montar_rejeita_tamanho_inesperado_apos_merge():
    trusted = _trusted_fake()
    v3 = _v3_fake(trusted["id_municipio"]).iloc[:-1]  # perde um municipio

    with pytest.raises(ValueError, match="esperado"):
        mod.montar_dataset_modelagem(trusted, v3, n_esperado=N)


def test_montar_rejeita_nulos_em_feature():
    trusted = _trusted_fake()
    trusted.loc[0, "pix_per_capita_12m"] = np.nan

    with pytest.raises(ValueError, match="nulos"):
        mod.montar_dataset_modelagem(
            trusted, _v3_fake(trusted["id_municipio"]), n_esperado=N
        )


def test_montar_nao_leva_colunas_do_indice_como_feature():
    df = _dataset_fake()
    colunas_indice = {
        "score_a",
        "score_b",
        "score_c",
        "score_d",
        "score_e",
        "gap_bancario_completo",
        "penetracao_digital_relativa",
        "score_turismo",
    }

    assert colunas_indice.isdisjoint(df.columns)
    assert "ipb" in df.columns and "rank" in df.columns  # so referencia


def test_features_sem_presenca_excluem_variaveis_que_vazam_o_alvo():
    # Variaveis de presenca medem a estrutura instalada — consequencia do
    # alvo, nao caracteristica exogena (vazamento: ROC-AUC 1.0 nos
    # notebooks). A classificacao de presenca so usa as exogenas.
    assert set(mod.FEATURES_PRESENCA) | set(mod.FEATURES_SEM_PRESENCA) == set(
        mod.FEATURES_MODELO
    )
    assert set(mod.FEATURES_PRESENCA).isdisjoint(mod.FEATURES_SEM_PRESENCA)
    assert len(mod.FEATURES_SEM_PRESENCA) == 13  # 19 - 6 de presenca


def test_cols_log_sao_nao_percentuais_e_reversiveis():
    # log1p so em variavel de cauda longa (nao-percentual); percentuais
    # ficam de fora. E a transformacao e reversivel (expm1) para quando
    # os valores reais sao necessarios (perfis/nomes dos arquetipos).
    import numpy as np

    assert len(mod.COLS_LOG) == 14
    assert set(mod.COLS_LOG) <= set(mod.FEATURES_MODELO)
    percentuais = [c for c in mod.FEATURES_MODELO if c.endswith("_pct")]
    assert set(percentuais).isdisjoint(mod.COLS_LOG)  # log so em nao-percentuais
    valores = np.array([0.0, 1.0, 100.0, 10_000.0])
    assert np.allclose(np.expm1(np.log1p(valores)), valores)


# ------------------------------------------------------------- holdout


def test_dividir_holdout_estratificado_mantem_proporcao():
    df = _dataset_fake(n=100)
    X_tr, X_te, y_tr, y_te = mod.dividir_treino_teste(df, "flag_tem_agencia")

    assert len(X_te) == 20
    assert len(X_tr) == 80
    assert y_te.value_counts().tolist() == [10, 10]  # 50/50 preservado
    assert y_tr.value_counts().tolist() == [40, 40]
    assert list(X_te.columns) == mod.FEATURES_MODELO


def test_dividir_reprodutivel_com_mesma_seed():
    df = _dataset_fake(n=100)
    X_tr1, X_te1, y_tr1, _ = mod.dividir_treino_teste(df, "flag_tem_agencia")
    X_tr2, X_te2, y_tr2, _ = mod.dividir_treino_teste(df, "flag_tem_agencia")

    pd.testing.assert_frame_equal(X_tr1, X_tr2)
    pd.testing.assert_frame_equal(X_te1, X_te2)
    pd.testing.assert_series_equal(y_tr1, y_tr2)


def test_dividir_rejeita_alvo_inexistente_ou_unico():
    df = _dataset_fake()
    with pytest.raises(ValueError, match="nao encontrado"):
        mod.dividir_treino_teste(df, "flag_inexistente")

    df["alvo_constante"] = 1
    with pytest.raises(ValueError, match="ao menos 2 classes"):
        mod.dividir_treino_teste(df, "alvo_constante")


def test_dividir_sem_estratificar_para_regressao():
    df = _dataset_fake(n=100)
    df["alvo_continuo"] = np.linspace(0.0, 1.0, 100)

    X_tr, X_te, y_tr, y_te = mod.dividir_treino_teste(df, "alvo_continuo", estratificar=False)

    assert len(X_te) == 20
    assert y_te.dtype == float


# ---------------------------------------------------------- padronizacao


def test_padronizar_ajusta_scaler_apenas_no_treino():
    # Treino e teste com medias BEM diferentes: se o scaler tivesse sido
    # ajustado no teste tambem, a media do teste padronizado colapsaria
    # para ~0. Nao colapsar e a prova de que a prova nao vazou.
    rng = np.random.default_rng(0)
    X_tr = pd.DataFrame({"a": 100.0 + rng.normal(0, 5, 80), "b": 50.0 + rng.normal(0, 5, 80)})
    X_te = pd.DataFrame({"a": 500.0 + rng.normal(0, 5, 20), "b": 10.0 + rng.normal(0, 5, 20)})

    X_tr_pad, X_te_pad, scaler = mod.padronizar(X_tr, X_te)

    assert np.allclose(X_tr_pad.mean(), 0.0, atol=1e-8)
    # StandardScaler usa desvio com ddof=0 (divisao por N); o std default
    # do pandas usa ddof=1 (N-1), daqui o ddof explicito no assert.
    assert np.allclose(X_tr_pad.std(ddof=0), 1.0, atol=1e-8)
    assert not np.allclose(X_te_pad["a"].mean(), 0.0, atol=0.1)
    # Scaler retornado reaplica a mesma transformacao em dados novos.
    X_novo = pd.DataFrame({"a": [100.0], "b": [50.0]})
    assert np.allclose(scaler.transform(X_novo)[0, 0], 0.0, atol=0.2)
