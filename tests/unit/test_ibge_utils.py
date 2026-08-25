import pytest
from src.utils.ibge import normalize_ibge_code, validate_ibge_code
import pandas as pd

def test_normalize_ibge_code():
    assert normalize_ibge_code(355030) == "0355030"
    assert normalize_ibge_code("3550308") == "3550308"
    assert normalize_ibge_code("3550308123") == "3550308"
    
def test_normalize_ibge_invalid():
    with pytest.raises(ValueError):
        normalize_ibge_code(pd.NA)

def test_validate_ibge_code():
    assert validate_ibge_code("3550308") is True
    assert validate_ibge_code("355030") is False
    assert validate_ibge_code(3550308) is False
