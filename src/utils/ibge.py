import re
from typing import Any
import pandas as pd

def normalize_ibge_code(code: Any) -> str:
    """
    Garante código IBGE com exatamente 7 dígitos (com zero à esquerda se truncado).
    """
    if pd.isna(code):
        raise ValueError("Código IBGE não pode ser nulo.")
    
    code_str = str(code).strip().split(".")[0] # Trata float
    code_str = re.sub(r"\D", "", code_str)
    
    if len(code_str) == 6:
        # Padroniza código de 6 dígitos inserindo um zero à esquerda
        code_str = code_str.zfill(7)
    elif len(code_str) < 7:
        code_str = code_str.zfill(7)
    elif len(code_str) > 7:
        code_str = code_str[:7]
        
    return code_str

def validate_ibge_code(code: str) -> bool:
    """
    Valida formato e dígito verificador IBGE (simplificado: 7 dígitos).
    """
    if not isinstance(code, str):
        return False
    return bool(re.match(r"^\d{7}$", code))
