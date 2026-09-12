"""
Deteccao de anomalias (Etapa 3): Isolation Forest.

Aponta os municipios com perfil ATIPICO para leitura humana: alta renda
+ Pix alto + zero presenca bancaria (candidato a oportunidade que o
indice pode estar sub-premiando) ou o inverso. O produto e uma lista
curta (Top N) — custo de erro baixo, valor narrativo alto ("os 30
municipios mais atipicos do Brasil bancario").

Score: `-decision_function` do Isolation Forest, de forma que QUANTO
MAIOR o `score_anomalia`, mais atipico o municipio (mais facil de
explicar do que o sinal original do modelo).
"""

from __future__ import annotations

import logging

import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from src.analytics.modelagem import SEED

logger = logging.getLogger(__name__)


def detectar_anomalias(
    df: pd.DataFrame,
    features: list[str],
    n_top: int = 30,
    seed: int = SEED,
    n_estimators: int = 300,
) -> pd.DataFrame:
    """
    Pontua cada municipio pelo quanto seu perfil desvia do restante.

    Args:
        df: Dataset de modelagem.
        features: Variaveis do perfil (as mesmas 19 do modelo).
        n_top: Quantidade de municipios marcados em `flag_anomalia`
            (os de maior score) — a lista curta para leitura.
        seed: Seed da floresta (reprodutibilidade).
        n_estimators: Numero de arvores (mesmo padrao dos demais
            modelos da etapa).

    Returns:
        DataFrame indexado como `df` com duas colunas:
        `score_anomalia` (maior = mais atipico) e `flag_anomalia`
        (True para os `n_top` maiores scores).

    Raises:
        ValueError: Se faltar feature ou `n_top` estiver fora de
            [1, len(df)].
    """
    faltantes = set(features) - set(df.columns)
    if faltantes:
        raise ValueError(f"features ausentes no dataset: {sorted(faltantes)}")
    if not 1 <= n_top <= len(df):
        raise ValueError(f"n_top precisa estar em [1, {len(df)}]; recebido {n_top}")

    scaler = StandardScaler()
    X_pad = scaler.fit_transform(df[features])

    modelo = IsolationForest(
        n_estimators=n_estimators, random_state=seed, n_jobs=-1
    )
    modelo.fit(X_pad)
    score = -modelo.decision_function(X_pad)  # maior = mais atipico

    resultado = pd.DataFrame(
        {"score_anomalia": score, "flag_anomalia": False}, index=df.index
    )
    top_index = resultado["score_anomalia"].nlargest(n_top).index
    resultado.loc[top_index, "flag_anomalia"] = True

    logger.info("Anomalias: top %d marcados entre %d municipios", n_top, len(df))
    return resultado
