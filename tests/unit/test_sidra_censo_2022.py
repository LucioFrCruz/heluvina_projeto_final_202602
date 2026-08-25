import pandas as pd
import pytest

from src.ingestors import sidra_censo_2022 as sidra


class FakeClassificacao:
    """Helper para criar o dict de classificação retornado pelo SIDRA."""

    @staticmethod
    def idade(*cat_ids):
        return {"287": {str(cid): f"cat_{cid}" for cid in cat_ids}}

    @staticmethod
    def situacao(*cat_ids):
        return {"1": {str(cid): f"cat_{cid}" for cid in cat_ids}}

    @staticmethod
    def instrucao(*cat_ids):
        return {"1568": {str(cid): f"cat_{cid}" for cid in cat_ids}}


def test_transform_raw_padroniza_codigo_ibge():
    raw = pd.DataFrame({"id_municipio": ["1100015", "3550308", "355030"]})
    result = sidra.transform_raw(raw)
    assert result["id_municipio"].tolist() == ["1100015", "3550308", "0355030"]


def test_build_populacao_18_35_soma_faixas_etarias(monkeypatch):
    def fake_fetch(table_id, period, variable, classifications=None, **kwargs):
        return pd.DataFrame(
            {
                "id_municipio": ["1100015"] * 6,
                "var_93": [300.0, 305.0, 1532.0, 1576.0, 1661.0, 297.0],
                "_classificacao": [
                    FakeClassificacao.idade(6575),
                    FakeClassificacao.idade(6576),
                    FakeClassificacao.idade(93087),
                    FakeClassificacao.idade(93088),
                    FakeClassificacao.idade(93089),
                    FakeClassificacao.idade(6588),
                ],
            }
        )

    monkeypatch.setattr(sidra, "fetch_sidra_table", fake_fetch)
    df = sidra.build_populacao_18_35()

    assert len(df) == 1
    assert df.iloc[0]["id_municipio"] == "1100015"
    # 300 + 305 + 1532 + 1576 + 1661 + 297 = 5671
    assert df.iloc[0]["populacao_18_35"] == 5671.0


def test_build_populacao_urbana_calcula_percentual(monkeypatch):
    def fake_fetch(table_id, period, variable, classifications=None, **kwargs):
        return pd.DataFrame(
            {
                "id_municipio": ["1100015", "1100015", "1100015"],
                "var_93": [12971.0, 8523.0, 21494.0],
                "_classificacao": [
                    FakeClassificacao.situacao(1),
                    FakeClassificacao.situacao(2),
                    FakeClassificacao.situacao(6795),
                ],
            }
        )

    monkeypatch.setattr(sidra, "fetch_sidra_table", fake_fetch)
    df = sidra.build_populacao_urbana()

    assert len(df) == 1
    assert df.iloc[0]["id_municipio"] == "1100015"
    # (12971 / 21494) * 100
    assert pytest.approx(df.iloc[0]["populacao_urbana_pct"], 0.01) == 60.35


def test_build_escolaridade_calcula_percentual_ensino_medio(monkeypatch):
    def fake_fetch(table_id, period, variable, classifications=None, **kwargs):
        return pd.DataFrame(
            {
                "id_municipio": ["1100015"] * 5,
                "var_2667": [15826.0, 8620.0, 2685.0, 3021.0, 1499.0],
                "_classificacao": [
                    FakeClassificacao.instrucao(120704),
                    FakeClassificacao.instrucao(9493),
                    FakeClassificacao.instrucao(9494),
                    FakeClassificacao.instrucao(9495),
                    FakeClassificacao.instrucao(99713),
                ],
            }
        )

    monkeypatch.setattr(sidra, "fetch_sidra_table", fake_fetch)
    df = sidra.build_escolaridade()

    assert len(df) == 1
    assert df.iloc[0]["id_municipio"] == "1100015"
    # (3021 + 1499) / 15826 * 100
    assert pytest.approx(df.iloc[0]["escolaridade_ensino_medio_pct"], 0.01) == 28.56


def test_extract_garante_colunas_de_contrato(monkeypatch):
    """Mesmo quando a tabela de internet falha, as colunas devem existir."""

    def fake_fetch(table_id, period, variable, classifications=None, **kwargs):
        if table_id == sidra.TABLE_INTERNET:
            return pd.DataFrame()

        if table_id == sidra.TABLE_POPULACAO_TOTAL:
            return pd.DataFrame({"id_municipio": ["1100015"], "var_93": [21494.0]})

        if table_id == sidra.TABLE_DISTRIBUICAO_ETARIA:
            return pd.DataFrame(
                {
                    "id_municipio": ["1100015"],
                    "var_93": [5671.0],
                    "_classificacao": [FakeClassificacao.idade(93087)],
                }
            )

        if table_id == sidra.TABLE_POPULACAO_URBANA:
            return pd.DataFrame(
                {
                    "id_municipio": ["1100015"],
                    "var_93": [12971.0],
                    "_classificacao": [FakeClassificacao.situacao(1)],
                }
            )

        if table_id == sidra.TABLE_RENDA:
            return pd.DataFrame({"id_municipio": ["1100015"], "var_13431": [1210.60]})

        if table_id == sidra.TABLE_ESCOLARIDADE:
            return pd.DataFrame(
                {
                    "id_municipio": ["1100015"],
                    "var_2667": [15826.0],
                    "_classificacao": [FakeClassificacao.instrucao(120704)],
                }
            )

        return pd.DataFrame()

    monkeypatch.setattr(sidra, "fetch_sidra_table", fake_fetch)
    df = sidra.extract()

    for col in [
        "id_municipio",
        "populacao_total",
        "populacao_18_35_pct",
        "populacao_urbana_pct",
        "rendimento_domiciliar_per_capita",
        "escolaridade_ensino_medio_pct",
        "domicilios_com_internet_pct",
    ]:
        assert col in df.columns

    assert df.iloc[0]["domicilios_com_internet_pct"] is None
