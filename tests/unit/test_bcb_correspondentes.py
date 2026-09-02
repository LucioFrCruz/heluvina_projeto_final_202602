import pandas as pd
import pytest

from src.ingestors import bcb_correspondentes as correspondentes


def _fixture_raw() -> pd.DataFrame:
    """Fixture pequena imitando o retorno da API OData."""
    return pd.DataFrame(
        {
            "CnpjContratante": ["59285411", "07707650"],
            "NomeContratante": ["BANCO PAN S.A.", "SANTANDER S.A."],
            "CnpjCorrespondente": ["48630167", "32421621"],
            "NomeCorrespondente": ["CABRAL & MESQUITA LTDA", "R A FIGUEIREDO LTDA"],
            "Tipo": ["Sede", "Filial"],
            "Ordem": ["I00001", "I00001"],
            "MunicipioIBGE": ["2611606", "1600303"],
            "Municipio": ["RECIFE", "MACAPA"],
            "UF": ["PE", "AP"],
            "ServicosCorrespondentes": ["Inc. V", "Inc. V"],
            "Posicao": ["30/08/2026", "30/08/2026"],
        }
    )


def test_transform_raw_cria_id_municipio_padronizado():
    result = correspondentes.transform_raw(_fixture_raw())

    assert result["id_municipio"].tolist() == ["2611606", "1600303"]


def test_transform_raw_preserva_colunas_da_fonte():
    raw = _fixture_raw()
    result = correspondentes.transform_raw(raw)

    for col in raw.columns:
        assert col in result.columns
    assert result["NomeCorrespondente"].tolist() == raw["NomeCorrespondente"].tolist()
    assert result["Tipo"].tolist() == ["Sede", "Filial"]


def test_transform_raw_mantem_registro_sem_municipio():
    raw = _fixture_raw()
    raw.loc[1, "MunicipioIBGE"] = None
    raw.loc[1, "Municipio"] = None
    raw.loc[1, "UF"] = None

    result = correspondentes.transform_raw(raw)

    assert len(result) == 2
    assert result["id_municipio"].iloc[0] == "2611606"
    assert pd.isna(result["id_municipio"].iloc[1])


def test_transform_raw_rejeita_dataframe_vazio():
    with pytest.raises(ValueError, match="vazio"):
        correspondentes.transform_raw(pd.DataFrame())


def test_transform_raw_rejeita_coluna_ausente():
    with pytest.raises(ValueError, match="MunicipioIBGE"):
        correspondentes.transform_raw(pd.DataFrame({"OutraColuna": [1]}))
