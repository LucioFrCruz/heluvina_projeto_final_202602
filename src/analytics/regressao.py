"""
Regressao da Etapa 3: explicar o IPB e estimar potencial latente.

Dois usos distintos (discussao da Etapa 3, secao 4.4):

(a) `explicar_ipb` — regressao com alvo = valor do IPB. O acerto sai
    alto POR CONSTRUCAO (as features ja entraram na formula do indice —
    o modelo so esta decorando a receita, circularidade declarada no
    relatorio). O produto real e a ORDEM de importancia das variaveis:
    responder com numero "o que mais pesa no IPB?".

(b) `estimar_potencial_latente` — treina SOMENTE em municipios com
    agencia: aprende como o perfil socioeconomico + digital se traduz
    em depositos per capita (SEM usar variaveis de presenca bancaria
    como preditora). Aplicado aos municipios SEM agencia, estima
    "quanto essa cidade depositaria se tivesse banco" — a lista de
    potencial latente para cruzar com o IPB (Spearman).
"""

from __future__ import annotations

import logging
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Lasso, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.analytics.modelagem import (
    FEATURES_MODELO,
    SEED,
    dividir_treino_teste,
    padronizar,
)

logger = logging.getLogger(__name__)

# Contrato da matriz de comparacao (uma linha por modelo).
COLUNAS_MATRIZ_REGRESSAO = ["modelo", "mae", "rmse", "r2", "tempo_seg"]

MODELOS_REGRESSAO = {
    "ridge": Ridge(),
    "lasso": Lasso(max_iter=5000, random_state=SEED),
    "random_forest": RandomForestRegressor(
        n_estimators=300, random_state=SEED, n_jobs=-1
    ),
}

# Variaveis de presenca bancaria: no potencial latente elas NAO podem
# ser preditoras (o municipio sem agencia nao tem o que medir — e seria
# vazamento do proprio alvo).
FEATURES_PRESENCA = [
    "quantidade_agencias",
    "agencias_por_100k_hab",
    "quantidade_correspondentes",
    "correspondentes_por_100k_hab",
    "depositos_per_capita",
    "credito_per_capita",
]

# Socioeconomicas + digitais puro: o que sobra quando tira a presenca.
FEATURES_SEM_PRESENCA = [
    f for f in FEATURES_MODELO if f not in FEATURES_PRESENCA
]


def treinar_regressores(
    X_tr: pd.DataFrame,
    y_tr: pd.Series,
    X_te: pd.DataFrame,
    y_te: pd.Series,
    modelos: dict | None = None,
) -> pd.DataFrame:
    """
    Treina regressores no treino e avalia no teste (holdout).

    Args:
        X_tr, y_tr: Features e alvo de treino (idealmente padronizados;
            padronizar importa para Ridge/Lasso, indiferente para RF).
        X_te, y_te: Teste (a prova).
        modelos: Dict {nome: estimador}; default `MODELOS_REGRESSAO`.

    Returns:
        DataFrame com `COLUNAS_MATRIZ_REGRESSAO`, ordenado por R2
        descendente. MAE/RMSE na unidade do alvo (R$ se depósitos pc);
        R2 em escala 0-1 tipicamente (1 = acertou tudo, 0 = chutou a
        media, negativo = pior que chutar a media).

    Raises:
        ValueError: Se colunas divergirem ou tamanhos nao baterem.
    """
    if list(X_tr.columns) != list(X_te.columns):
        raise ValueError("X_treino e X_teste com colunas diferentes")
    if len(X_tr) != len(y_tr) or len(X_te) != len(y_te):
        raise ValueError("X e y com tamanhos diferentes")
    modelos = modelos or MODELOS_REGRESSAO

    linhas = []
    for nome, modelo in modelos.items():
        t0 = time.perf_counter()
        modelo.fit(X_tr, y_tr)
        tempo = time.perf_counter() - t0

        pred = modelo.predict(X_te)
        mse = mean_squared_error(y_te, pred)
        linhas.append(
            {
                "modelo": nome,
                "mae": mean_absolute_error(y_te, pred),
                "rmse": float(np.sqrt(mse)),
                "r2": r2_score(y_te, pred),
                "tempo_seg": round(tempo, 3),
            }
        )

    matriz = (
        pd.DataFrame(linhas, columns=COLUNAS_MATRIZ_REGRESSAO)
        .sort_values("r2", ascending=False)
        .reset_index(drop=True)
    )
    logger.info("Matriz de regressao: %d modelos avaliados", len(matriz))
    return matriz


def explicar_ipb(
    df: pd.DataFrame,
    features: list[str] | None = None,
    col_ipb: str = "ipb",
    seed: int = SEED,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Regressao com alvo = IPB (sanity check declarado como circular).

    O acerto esperado e alto porque as features ENTRAM na formula do
    indice — o exercicio existe para ranquear a importancia das
    variaveis, nao para "prever" nada. A circularidade fica registrada
    no relatorio e na docstring; ninguem usa isso como evidencia de
    poder preditivo.

    Returns:
        (matriz_metricas, importancia). A importancia e por permutacao
        (queda de R2 ao embaralhar a coluna) do Random Forest medida no
        TESTE — ordena "o que pesa no IPB".
    """
    features = features or FEATURES_MODELO
    faltantes = set(features + [col_ipb]) - set(df.columns)
    if faltantes:
        raise ValueError(f"colunas ausentes no dataset: {sorted(faltantes)}")

    X_tr, X_te, y_tr, y_te = dividir_treino_teste(
        df, col_ipb, estratificar=False, seed=seed
    )
    X_tr_pad, X_te_pad, _ = padronizar(X_tr, X_te)
    matriz = treinar_regressores(X_tr_pad, y_tr, X_te_pad, y_te)

    rf = MODELOS_REGRESSAO["random_forest"]
    resultado = permutation_importance(
        rf, X_te_pad, y_te, n_repeats=10, random_state=seed, scoring="r2"
    )
    importancia = pd.Series(
        resultado.importances_mean, index=features
    ).sort_values(ascending=False)
    logger.info("Regressao do IPB ajustada (circularidade declarada)")
    return matriz, importancia


def estimar_potencial_latente(
    df: pd.DataFrame,
    features: list[str] | None = None,
    col_alvo: str = "depositos_per_capita",
    col_flag: str = "flag_tem_agencia",
    test_size: float = 0.2,
    seed: int = SEED,
) -> tuple[pd.Series, pd.DataFrame]:
    """
    Estima o potencial bancario latente dos municipios SEM agencia.

    Logica: o modelo aprende (so nos municipios COM agencia) como
    perfil socioeconomico + digital se traduz em depositos per capita,
    SEM variaveis de presenca como preditora. Aplicado aos SEM agencia,
    responde "quanto essa cidade depositaria se tivesse banco".

    A qualidade do modelo e calibrada em holdout interno dos COM
    agencia (metricas em R$, escala original via expm1) — e o que da
    confianca para ler as estimativas.

    Args:
        df: Dataset de modelagem (`montar_dataset_modelagem`).
        features: Preditoras (default `FEATURES_SEM_PRESENCA`, 13).
        col_alvo: Coluna de depositos per capita.
        col_flag: Flag de presenca (1 = com agencia).
        test_size: Fracao do holdout interno (dos com agencia).
        seed: Seed.

    Returns:
        (estimativas, metricas). `estimativas` e uma Series indexada
        como `df`: valor estimado onde flag == 0, NaN onde flag == 1
        (nao se estima o que ja se observa). `metricas` e a linha de
        MAE/RMSE/R2 do holdout interno em escala original.

    Raises:
        ValueError: Se faltar coluna, a flag tiver um unico valor ou
            nao houver municipio em algum dos lados.
    """
    features = features or FEATURES_SEM_PRESENCA
    faltantes = set(features + [col_alvo, col_flag]) - set(df.columns)
    if faltantes:
        raise ValueError(f"colunas ausentes no dataset: {sorted(faltantes)}")
    if set(pd.unique(df[col_flag])) != {0, 1}:
        raise ValueError(f"{col_flag} precisa ser binaria (0/1)")

    com = df[df[col_flag] == 1]
    sem = df[df[col_flag] == 0]
    if com.empty or sem.empty:
        raise ValueError("precisa haver municipios com e sem agencia")

    # Holdout interno: so entre os COM agencia (a prova e neles).
    X_tr, X_te, y_tr, y_te = dividir_treino_teste(
        com.assign(**{col_alvo: np.log1p(com[col_alvo])}),
        col_alvo,
        test_size=test_size,
        seed=seed,
        estratificar=False,
    )
    X_tr_pad, X_te_pad, scaler = padronizar(X_tr, X_te)

    modelo = RandomForestRegressor(n_estimators=300, random_state=seed, n_jobs=-1)
    modelo.fit(X_tr_pad, y_tr)
    pred_log = modelo.predict(X_te_pad)
    mae = float(np.mean(np.abs(np.expm1(pred_log) - np.expm1(y_te))))
    rmse = float(np.sqrt(np.mean((np.expm1(pred_log) - np.expm1(y_te)) ** 2)))
    r2 = r2_score(np.expm1(y_te), np.expm1(pred_log))
    metricas = pd.DataFrame(
        [{"mae": mae, "rmse": rmse, "r2": r2, "n_treino": len(X_tr), "n_teste": len(X_te)}]
    )

    # Estimativa nos SEM agencia (mesmo scaler do treino).
    X_sem_pad = pd.DataFrame(
        scaler.transform(sem[features]), columns=features, index=sem.index
    )
    estimativas = pd.Series(np.expm1(modelo.predict(X_sem_pad)), index=sem.index)
    estimativas_reindex = pd.Series(np.nan, index=df.index, name="potencial_latente_depositos_pc")
    estimativas_reindex.loc[estimativas.index] = estimativas

    logger.info(
        "Potencial latente estimado para %d municipios sem agencia", len(sem)
    )
    return estimativas_reindex, metricas
