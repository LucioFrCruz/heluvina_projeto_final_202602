"""Testes unitarios do modulo de calculo do IPB (src/analytics/ipb.py).

Sem rede e sem BigQuery: todos os testes usam DataFrames sinteticos pequenos.
"""

import numpy as np
import pandas as pd
import pytest

from src.analytics import ipb


def _fixture_base() -> pd.DataFrame:
    """Fixture municipal pequena com as variaveis base das tres versoes."""
    n = 8
    return pd.DataFrame(
        {
            "id_municipio": [f"{i:07d}" for i in range(1, n + 1)],
            "nome_municipio": [f"Municipio {i}" for i in range(1, n + 1)],
            "sigla_uf": ["SP", "MG", "BA", "PR", "AM", "GO", "RJ", "CE"],
            "pib_per_capita": np.linspace(8_000, 80_000, n),
            "rendimento_domiciliar_per_capita": np.linspace(600, 3_500, n),
            "pix_per_capita_12m": np.linspace(2.0, 60.0, n),
            "banda_larga_fixa_por_100_hab": np.linspace(5.0, 45.0, n),
            "agencias_por_100k_hab": np.linspace(0.0, 80.0, n),
            "depositos_per_capita": np.linspace(1_000, 60_000, n),
            "credito_per_capita": np.linspace(500, 40_000, n),
            "escolaridade_ensino_medio_pct": np.linspace(10.0, 45.0, n),
            "populacao_18_35_pct": np.linspace(20.0, 35.0, n),
            "populacao_urbana_pct": np.linspace(30.0, 98.0, n),
            "populacao_total": np.linspace(20_000, 1_200_000, n),
        }
    )


def _fixture_completo() -> pd.DataFrame:
    """Fixture enriquecida com estrato e correspondentes para V3."""
    df = _fixture_base()
    df["estrato_populacional"] = ipb.derive_estrato(df["populacao_total"])
    df["quantidade_correspondentes_posto"] = [0, 1, 2, 0, 3, 1, 0, 5]
    df["quantidade_correspondentes_filial"] = [0, 0, 1, 2, 0, 1, 0, 1]
    df["quantidade_correspondentes_sede"] = [0, 0, 0, 1, 0, 0, 1, 0]
    df["quantidade_correspondentes_agencia"] = [1, 0, 0, 0, 2, 0, 0, 1]
    return df


# ---------------------------------------------------------------------------
# winsorize / normalize
# ---------------------------------------------------------------------------


def test_winsorize_clipa_nos_quantis_1_e_99_pct():
    serie = pd.Series(range(1, 101), dtype=float)
    resultado = ipb.winsorize(serie)

    limite_inferior = serie.quantile(0.01)
    limite_superior = serie.quantile(0.99)

    assert resultado.min() == pytest.approx(limite_inferior)
    assert resultado.max() == pytest.approx(limite_superior)
    # Valores dentro da faixa ficam inalterados
    assert resultado.iloc[49] == pytest.approx(50.0)
    assert resultado.iloc[0] == pytest.approx(limite_inferior)
    assert resultado.iloc[-1] == pytest.approx(limite_superior)


def test_normalize_retorna_escala_0_a_1():
    serie = pd.Series([3.0, 7.5, 12.0, 42.0, 99.0])
    resultado = ipb.normalize(serie)

    assert resultado.min() == pytest.approx(0.0)
    assert resultado.max() == pytest.approx(1.0)
    assert resultado.between(0, 1).all()


def test_normalize_serie_constante_retorna_zeros():
    serie = pd.Series([5.0] * 6)
    resultado = ipb.normalize(serie)

    assert (resultado == 0.0).all()


# ---------------------------------------------------------------------------
# derive_estrato / derive_regiao
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "populacao,esperado",
    [
        (49_999, "pequena"),
        (50_000, "media"),
        (500_000, "media"),
        (500_001, "grande"),
    ],
)
def test_derive_estrato_casos_de_borda(populacao, esperado):
    resultado = ipb.derive_estrato(pd.Series([populacao]))
    assert resultado.iloc[0] == esperado


def test_derive_estrato_faixas_completas():
    populacao = pd.Series([1_000, 49_999, 50_000, 300_000, 500_000, 500_001, 3_000_000])
    resultado = ipb.derive_estrato(populacao)
    assert resultado.tolist() == [
        "pequena",
        "pequena",
        "media",
        "media",
        "media",
        "grande",
        "grande",
    ]


@pytest.mark.parametrize(
    "uf,regiao",
    [
        ("AM", "Norte"),
        ("BA", "Nordeste"),
        ("MT", "Centro-Oeste"),
        ("SP", "Sudeste"),
        ("RS", "Sul"),
    ],
)
def test_derive_regiao_uma_uf_de_cada_regiao(uf, regiao):
    resultado = ipb.derive_regiao(pd.Series([uf]))
    assert resultado.iloc[0] == regiao


def test_derive_regiao_normaliza_minuscula_e_desconhecida_vira_nan():
    resultado = ipb.derive_regiao(pd.Series(["sp", "XX"]))
    assert resultado.iloc[0] == "Sudeste"
    assert pd.isna(resultado.iloc[1])


# ---------------------------------------------------------------------------
# agregar_correspondentes_por_tipo
# ---------------------------------------------------------------------------


def test_agregar_correspondentes_conta_por_tipo():
    raw = pd.DataFrame(
        {
            "id_municipio": ["0000001"] * 4 + ["0000002"],
            "Tipo": ["Posto", "Posto", "Filial", "Agência", "Sede"],
        }
    )
    enriquecido = pd.DataFrame(
        {
            "id_municipio": ["0000001", "0000002", "0000003"],
            "populacao_total": [100_000, 200_000, 50_000],
        }
    )

    resultado = ipb.agregar_correspondentes_por_tipo(raw, enriquecido)

    linha1 = resultado[resultado["id_municipio"] == "0000001"].iloc[0]
    assert linha1["quantidade_correspondentes_posto"] == 2
    assert linha1["quantidade_correspondentes_filial"] == 1
    assert linha1["quantidade_correspondentes_sede"] == 0
    assert linha1["quantidade_correspondentes_agencia"] == 1
    assert linha1["quantidade_correspondentes"] == 4
    assert linha1["correspondentes_por_100k_hab"] == pytest.approx(4.0)

    linha2 = resultado[resultado["id_municipio"] == "0000002"].iloc[0]
    assert linha2["quantidade_correspondentes_sede"] == 1
    assert linha2["quantidade_correspondentes"] == 1
    assert linha2["correspondentes_por_100k_hab"] == pytest.approx(0.5)


def test_agregar_correspondentes_municipio_sem_correspondente_recebe_zero():
    raw = pd.DataFrame(
        {"id_municipio": ["0000001"], "Tipo": ["Posto"]}
    )
    enriquecido = pd.DataFrame(
        {
            "id_municipio": ["0000001", "0000002"],
            "populacao_total": [100_000, 200_000],
        }
    )

    resultado = ipb.agregar_correspondentes_por_tipo(raw, enriquecido)

    linha2 = resultado[resultado["id_municipio"] == "0000002"].iloc[0]
    assert linha2["quantidade_correspondentes"] == 0
    assert linha2["quantidade_correspondentes_posto"] == 0
    assert linha2["quantidade_correspondentes_filial"] == 0
    assert linha2["quantidade_correspondentes_sede"] == 0
    assert linha2["quantidade_correspondentes_agencia"] == 0
    assert linha2["correspondentes_por_100k_hab"] == pytest.approx(0.0)


def test_agregar_correspondentes_preenche_tipos_ausentes_no_raw():
    raw = pd.DataFrame(
        {"id_municipio": ["0000001", "0000001"], "Tipo": ["Posto", "Posto"]}
    )
    enriquecido = pd.DataFrame(
        {"id_municipio": ["0000001"], "populacao_total": [100_000]}
    )

    resultado = ipb.agregar_correspondentes_por_tipo(raw, enriquecido)

    linha1 = resultado.iloc[0]
    assert linha1["quantidade_correspondentes_posto"] == 2
    assert linha1["quantidade_correspondentes_filial"] == 0
    assert linha1["quantidade_correspondentes_sede"] == 0
    assert linha1["quantidade_correspondentes_agencia"] == 0
    assert linha1["quantidade_correspondentes"] == 2


def test_agregar_correspondentes_exige_colunas_obrigatorias():
    with pytest.raises(ValueError, match="id_municipio"):
        ipb.agregar_correspondentes_por_tipo(
            pd.DataFrame({"Tipo": ["Posto"]}),
            pd.DataFrame({"id_municipio": ["1"], "populacao_total": [100]}),
        )


# ---------------------------------------------------------------------------
# calculo das versoes
# ---------------------------------------------------------------------------


def test_v1_pilar_d_e_invertido():
    df = _fixture_completo()
    resultado = ipb.computar_ipb_v1_classico(df)

    # Menor valor de agencias normalizado vira 1 apos inversao
    assert resultado["agencias_por_100k_hab_norm"].max() == pytest.approx(1.0)
    # Pilar D positivo e nao superior a 1
    assert resultado["D_v1"].between(0, 1).all()


def test_v2_invariancia_a_escala_dos_pesos():
    """Multiplicar todos os pesos por uma constante nao altera o IPB."""
    df = _fixture_completo()
    resultado = ipb.computar_ipb_v2_recalibrado(df)

    def media_geometrica_ponderada(pesos):
        soma = sum(pesos.values())
        return (
            resultado["A_v2"] ** pesos["A"]
            * resultado["B_v2"] ** pesos["B"]
            * resultado["C_v2"] ** pesos["C"]
            * resultado["D_v2"] ** pesos["D"]
            * resultado["E_v2"] ** pesos["E"]
        ) ** (1 / soma) * 100

    ipb_pesos_originais = media_geometrica_ponderada(ipb.PESOS_V2)
    pesos_dobrados = {pilar: peso * 2 for pilar, peso in ipb.PESOS_V2.items()}
    ipb_pesos_dobrados = media_geometrica_ponderada(pesos_dobrados)

    assert np.allclose(ipb_pesos_originais, ipb_pesos_dobrados, rtol=1e-12)
    assert np.allclose(resultado[ipb.COL_IPB_V2], ipb_pesos_originais, rtol=1e-12)


def test_v2_cria_tensao_digital_bancaria():
    df = _fixture_completo()
    resultado = ipb.computar_ipb_v2_recalibrado(df)

    esperado = df["pix_per_capita_12m"] / (df["agencias_por_100k_hab"] + 1)
    assert np.allclose(resultado["tensao_digital_bancaria"], esperado)


def test_determinismo_mesma_entrada_mesma_saida():
    df = _fixture_completo()

    v1_a = ipb.computar_ipb_v1_classico(df)
    v1_b = ipb.computar_ipb_v1_classico(df)
    pd.testing.assert_frame_equal(v1_a, v1_b)

    v2_a = ipb.computar_ipb_v2_recalibrado(df)
    v2_b = ipb.computar_ipb_v2_recalibrado(df)
    pd.testing.assert_frame_equal(v2_a, v2_b)

    v3_a = ipb.computar_ipb_v3_presenca_completa(df)
    v3_b = ipb.computar_ipb_v3_presenca_completa(df)
    pd.testing.assert_frame_equal(v3_a, v3_b)


def test_v3_score_turismo_entre_0_e_1():
    df = _fixture_completo()
    resultado = ipb.computar_ipb_v3_presenca_completa(df)

    assert resultado["score_turismo"].between(0, 1).all()


def _fixture_turismo_extremo() -> pd.DataFrame:
    """Fixture em que o ultimo municipio tem score_turismo = 1.0."""
    n = 10
    df = pd.DataFrame(
        {
            "pib_per_capita": np.linspace(20_000, 60_000, n),
            "rendimento_domiciliar_per_capita": np.linspace(1_000, 3_000, n),
            "pix_per_capita_12m": np.full(n, 15.0),
            "banda_larga_fixa_por_100_hab": np.linspace(5.0, 30.0, n),
            "agencias_por_100k_hab": np.linspace(1.0, 50.0, n),
            "escolaridade_ensino_medio_pct": np.linspace(15.0, 40.0, n),
            "populacao_18_35_pct": np.linspace(22.0, 33.0, n),
            "populacao_total": np.linspace(100_000, 1_000_000, n),
            "quantidade_correspondentes_posto": [1] * n,
            "quantidade_correspondentes_filial": [0] * n,
            "quantidade_correspondentes_sede": [0] * n,
            "quantidade_correspondentes_agencia": [0] * n,
        }
    )
    df.loc[n - 1, "pix_per_capita_12m"] = 1_000.0  # Pix alto
    df.loc[n - 1, "pib_per_capita"] = 10_000.0  # PIB baixo
    df.loc[n - 1, "populacao_total"] = 10_000.0  # Cidade pequena
    df["estrato_populacional"] = ipb.derive_estrato(df["populacao_total"])
    return df


def test_v3_desconto_turismo_no_maximo_15_pct():
    df = _fixture_turismo_extremo()
    resultado = ipb.computar_ipb_v3_presenca_completa(df)

    idx = df.index[-1]
    assert resultado.loc[idx, "score_turismo"] == pytest.approx(1.0)

    b_sem_desconto = resultado.loc[
        idx, ["pix_per_capita_12m_norm", "tensao_digital_bancaria_norm", "penetracao_digital_relativa_norm"]
    ].mean()
    b_com_desconto = resultado.loc[idx, "B_v3"]

    # Desconto exato de 15% quando score_turismo = 1.0
    assert b_com_desconto == pytest.approx(b_sem_desconto * 0.85)

    # Para todos os municipios: desconto entre 0% e 15%
    b_geral_sem = resultado[
        ["pix_per_capita_12m_norm", "tensao_digital_bancaria_norm", "penetracao_digital_relativa_norm"]
    ].mean(axis=1)
    assert (resultado["B_v3"] <= b_geral_sem + 1e-12).all()
    assert (resultado["B_v3"] >= 0.85 * b_geral_sem - 1e-12).all()


def test_v3_pilar_zerado_implica_ipb_zero():
    """Municipio com pilar D zerado (maxima presenca bancaria) tem IPB 0."""
    df = _fixture_completo().head(4).copy()
    df.loc[df.index[0], "agencias_por_100k_hab"] = 1_000_000.0
    df.loc[df.index[0], "quantidade_correspondentes_posto"] = 100_000
    df.loc[df.index[0], "populacao_total"] = 50_000

    resultado = ipb.computar_ipb_v3_presenca_completa(df)

    assert resultado.loc[df.index[0], "D_v3"] == pytest.approx(0.0)
    assert resultado.loc[df.index[0], ipb.COL_IPB_V3] == pytest.approx(0.0)


def test_v3_gap_linear_nao_saturo_com_presenca_moderada():
    """Regressao do bug da saturacao: presenca moderada nao zera o gap.

    Na forma hiperbolica 1/(presenca + 1), uma cidade com 50 pontos/100k
    tinha gap ~0.02 e o IPB colapsava; com o gap linear ela deve ter
    gap ~0.9 e IPB positivo.
    """
    n = 6
    df = pd.DataFrame(
        {
            "pib_per_capita": np.linspace(20_000, 60_000, n),
            "rendimento_domiciliar_per_capita": np.linspace(1_000, 3_000, n),
            "pix_per_capita_12m": np.linspace(5.0, 50.0, n),
            "banda_larga_fixa_por_100_hab": np.linspace(5.0, 30.0, n),
            "agencias_por_100k_hab": [0.0, 10.0, 50.0, 100.0, 200.0, 500.0],
            "escolaridade_ensino_medio_pct": np.linspace(15.0, 40.0, n),
            "populacao_18_35_pct": np.linspace(22.0, 33.0, n),
            # Populacao grande: correspondentes somam ~0 na taxa por 100k,
            # deixando a presenca combinada igual a agencias_por_100k_hab.
            "populacao_total": np.full(n, 2_000_000),
            "quantidade_correspondentes_posto": [0] * n,
            "quantidade_correspondentes_filial": [0] * n,
            "quantidade_correspondentes_sede": [0] * n,
            "quantidade_correspondentes_agencia": [0] * n,
        }
    )
    df["estrato_populacional"] = ipb.derive_estrato(df["populacao_total"])

    resultado = ipb.computar_ipb_v3_presenca_completa(df)

    esperado = 1 - ipb.normalize(ipb.winsorize(df["agencias_por_100k_hab"]))
    assert np.allclose(resultado["D_v3"], esperado)

    # Cidade com presenca 50/100k: gap ~0.9 (na ~0.02 da hiperbolica)
    assert resultado["D_v3"].iloc[2] == pytest.approx(esperado.iloc[2])
    assert resultado["D_v3"].iloc[2] == pytest.approx(0.9, abs=0.01)
    assert resultado.loc[resultado.index[2], ipb.COL_IPB_V3] > 0
    # Monotonicidade: mais presenca -> menor gap
    assert resultado["D_v3"].is_monotonic_decreasing


def test_v3_regressao_contra_implementacao_de_referencia():
    """O calculo deve reproduzir a spec do script 06 implementada a parte."""
    df = _fixture_completo()
    resultado = ipb.computar_ipb_v3_presenca_completa(df)

    def normalizar(serie):
        lo, hi = serie.min(), serie.max()
        if hi == lo:
            return pd.Series(0.0, index=serie.index)
        return (serie - lo) / (hi - lo)

    def winsorizar(serie):
        return serie.clip(lower=serie.quantile(0.01), upper=serie.quantile(0.99))

    d = df
    ponderados = (
        1.0 * d["quantidade_correspondentes_posto"].fillna(0)
        + 0.70 * d["quantidade_correspondentes_filial"].fillna(0)
        + 0.40 * d["quantidade_correspondentes_sede"].fillna(0)
        + 1.00 * d["quantidade_correspondentes_agencia"].fillna(0)
    )
    corr_100k = ponderados / d["populacao_total"] * 100_000
    tensao = d["pix_per_capita_12m"] / (d["agencias_por_100k_hab"] + 1)
    pen = d["pix_per_capita_12m"] / d["pib_per_capita"]
    pen = pen.replace([np.inf, -np.inf], np.nan).fillna(0)
    presenca = (
        d["agencias_por_100k_hab"]
        + ipb.EQUIVALENCIA_CORRESPONDENTE_AGENCIA * corr_100k
    )
    gap = 1 - normalizar(winsorizar(presenca))

    a_ = normalizar(winsorizar(d["pib_per_capita"]))
    a_ = pd.concat([a_, normalizar(winsorizar(d["rendimento_domiciliar_per_capita"]))], axis=1).mean(axis=1)
    b_ = pd.concat(
        [
            normalizar(winsorizar(d["pix_per_capita_12m"])),
            normalizar(winsorizar(tensao)),
            normalizar(winsorizar(pen)),
        ],
        axis=1,
    ).mean(axis=1)
    c_ = normalizar(winsorizar(d["banda_larga_fixa_por_100_hab"]))
    d_ = gap
    e_ = pd.concat(
        [
            normalizar(winsorizar(d["escolaridade_ensino_medio_pct"])),
            normalizar(winsorizar(d["populacao_18_35_pct"])),
        ],
        axis=1,
    ).mean(axis=1)

    pix_alto = d["pix_per_capita_12m"] >= d["pix_per_capita_12m"].quantile(0.90)
    pib_baixo = d["pib_per_capita"] <= d["pib_per_capita"].median()
    pequena = d["estrato_populacional"] == "pequena"
    score = pix_alto.astype(int) * 0.5 + pib_baixo.astype(int) * 0.3 + pequena.astype(int) * 0.2
    b_ = b_ * (1 - 0.15 * score)

    pesos = {"A": 0.75, "B": 1.0, "C": 0.75, "D": 1.5, "E": 1.0}
    soma = sum(pesos.values())
    esperado = (
        a_ ** pesos["A"] * b_ ** pesos["B"] * c_ ** pesos["C"] * d_ ** pesos["D"] * e_ ** pesos["E"]
    ) ** (1 / soma) * 100

    assert np.allclose(resultado[ipb.COL_IPB_V3], esperado, rtol=1e-10)


def test_v3_colunas_esperadas_presentes_e_ipb_no_intervalo():
    df = _fixture_completo()
    resultado = ipb.computar_ipb_v3_presenca_completa(df)

    for col in [
        "correspondentes_ponderados",
        "correspondentes_ponderados_por_100k_hab",
        "presenca_bancaria_combinada",
        "tensao_digital_bancaria",
        "penetracao_digital_relativa",
        "gap_bancario_completo",
        "score_turismo",
        "A_v3",
        "B_v3",
        "C_v3",
        "D_v3",
        "E_v3",
        ipb.COL_IPB_V3,
    ]:
        assert col in resultado.columns

    assert resultado[ipb.COL_IPB_V3].between(0, 100).all()


def test_v1_v2_ipb_no_intervalo_0_100():
    df = _fixture_completo()
    assert ipb.computar_ipb_v1_classico(df)[ipb.COL_IPB_V1].between(0, 100).all()
    assert ipb.computar_ipb_v2_recalibrado(df)[ipb.COL_IPB_V2].between(0, 100).all()


# ---------------------------------------------------------------------------
# adicionar_ranks
# ---------------------------------------------------------------------------


def _fixture_ranks() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "estrato_populacional": ["pequena", "pequena", "media", "grande"],
            "ipb": [10.0, 20.0, 15.0, 5.0],
        }
    )


def test_adicionar_ranks_geral_unico_e_contiguo():
    resultado = ipb.adicionar_ranks(_fixture_ranks(), "v1", "ipb")

    assert sorted(resultado["rank_v1"].tolist()) == [1, 2, 3, 4]
    # Ordem descendente: maior IPB -> rank 1
    assert resultado["rank_v1"].tolist() == [3, 1, 2, 4]


def test_adicionar_ranks_estrato_reinicia_em_1():
    resultado = ipb.adicionar_ranks(_fixture_ranks(), "v1", "ipb")

    assert resultado["rank_v1_estrato"].tolist() == [2, 1, 1, 1]

    for estrato in resultado["estrato_populacional"].unique():
        ranks = resultado.loc[
            resultado["estrato_populacional"] == estrato, "rank_v1_estrato"
        ]
        assert sorted(ranks.tolist()) == list(range(1, len(ranks) + 1))


def test_adicionar_ranks_empate_usa_metodo_min():
    df = pd.DataFrame(
        {
            "estrato_populacional": ["pequena", "pequena", "pequena"],
            "ipb": [10.0, 10.0, 5.0],
        }
    )
    resultado = ipb.adicionar_ranks(df, "v3", "ipb")

    assert resultado["rank_v3"].tolist() == [1, 1, 3]


def test_adicionar_ranks_exige_coluna_de_ipb_e_estrato():
    with pytest.raises(ValueError, match="ipb_v1_classico"):
        ipb.adicionar_ranks(pd.DataFrame({"estrato_populacional": ["pequena"]}), "v1", "ipb_v1_classico")
    with pytest.raises(ValueError, match="estrato_populacional"):
        ipb.adicionar_ranks(pd.DataFrame({"ipb": [1.0]}), "v1", "ipb")
