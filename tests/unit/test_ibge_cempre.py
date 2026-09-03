"""Testes unitarios do ingestor do CEMPRE (src/ingestors/ibge_cempre.py).

Sem rede: o acesso ao SIDRA (fetch_sidra_table) e sempre mockado.
"""
import pandas as pd
import pytest

from src.ingestors import ibge_cempre as cempre


def _classif(cnae_codigo: str) -> dict:
    """Monta o dict de classificacao no formato retornado pelo SIDRA."""
    return {"12762": {cnae_codigo: f"cat_{cnae_codigo}"}}


def _fake_fetch(dados_por_variavel: dict) -> callable:
    """Fabrica um fake de fetch_sidra_table que responde por variavel."""

    def fake_fetch(table_id, period, variable, classifications=None, **kwargs):
        linhas = dados_por_variavel.get(variable)
        if linhas is None:
            return pd.DataFrame()
        return pd.DataFrame(linhas)

    return fake_fetch


_DADOS = {
    706: [  # unidades locais
        {"id_municipio": "1100015", "var_706": 908.0, "_classificacao": _classif("117897")},
        {"id_municipio": "1100015", "var_706": 300.0, "_classificacao": _classif("117363")},
        {"id_municipio": "3550308", "var_706": 1282682.0, "_classificacao": _classif("117897")},
    ],
    707: [  # pessoal ocupado total
        {"id_municipio": "1100015", "var_707": 4521.0, "_classificacao": _classif("117897")},
        {"id_municipio": "1100015", "var_707": 1400.0, "_classificacao": _classif("117897")},
        {"id_municipio": "3550308", "var_707": 6822182.0, "_classificacao": _classif("117897")},
    ],
}


def test_build_cempre_formato_longo_e_mapeamento_cnae(monkeypatch):
    monkeypatch.setattr(cempre, "fetch_sidra_table", _fake_fetch(_DADOS))

    df = cempre.build_cempre("2024")

    # 2 variaveis x 3 linhas cada = 6 linhas, colunas do contrato
    assert len(df) == 6
    assert list(df.columns) == cempre.COLUNAS_FINAIS
    # Mapeamento codigo -> secao
    assert set(df["cnae_secao"]) == {"total", "comercio"}
    assert df.loc[df["cnae_codigo"] == "117363", "cnae_secao"].iloc[0] == "comercio"
    # Metadados de variavel preenchidos
    assert set(df["variavel"]) == {"unidades_locais", "pessoal_ocupado_total"}
    assert (df["ano"] == "2024").all()


def test_build_cempre_sem_dados_retorna_vazio(monkeypatch):
    monkeypatch.setattr(cempre, "fetch_sidra_table", _fake_fetch({}))

    df = cempre.build_cempre("2024")

    assert df.empty
    assert list(df.columns) == cempre.COLUNAS_FINAIS


def test_transform_raw_padroniza_codigo_ibge():
    raw = pd.DataFrame(
        {
            "id_municipio": ["1100015", "3550308", "355030"],
            "ano": ["2024"] * 3,
            "variavel_codigo": [706] * 3,
            "variavel": ["unidades_locais"] * 3,
            "cnae_codigo": ["117897", "117897", "117897"],
            "cnae_secao": ["total"] * 3,
            "valor": [1.0, 2.0, 3.0],
        }
    )

    resultado = cempre.transform_raw(raw)

    assert resultado["id_municipio"].tolist() == ["1100015", "3550308", "0355030"]
    assert resultado["cnae_codigo"].tolist() == ["117897"] * 3


def test_extrair_cnae_sem_classificacao_retorna_none():
    linha = pd.Series({"_classificacao": {}})
    assert cempre._extrair_cnae(linha) is None
