"""
Classificacao de presenca bancaria (Etapa 3).

Estima a probabilidade de um municipio ja ser atrativo para rede fisica,
com alvo proxy (`flag_tem_agencia` / `flag_tem_correspondente`) — o
projeto nao tem rotulo de verdade, declarado no relatorio. NAO e o
indice e nao o substitui: e um complemento de validacao que cruza com
o IPB (ver discussao da Etapa 3, secao 4.2).

O produto principal nao e a classificacao em si, e o RESIDUO:
municipios com probabilidade prevista alta mas sem presenca (falso
negativo) formam a lista de oportunidade para cruzar com o rank do IPB.

Metricas no TESTE (a "prova"): ROC-AUC, PR-AUC, F1, precision, recall,
acuracia e tempo de treino — a matriz de comparacao da rubrica.
"""

from __future__ import annotations

import logging
import time

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.neighbors import KNeighborsClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier

from src.analytics.modelagem import SEED

logger = logging.getLogger(__name__)

# Contrato da matriz de comparacao (uma linha por modelo).
COLUNAS_MATRIZ = [
    "modelo",
    "roc_auc",
    "pr_auc",
    "f1",
    "precision",
    "recall",
    "acuracia",
    "tempo_seg",
]

# Modelos da matriz. `class_weight="balanced"` compensa o desbalanceamento
# leve (52/48) sem gambiarra de undersampling. KNN nao aceita o parametro
# (compensa-se com k maior e `weights="distance"`, ajustado no tuning).
MODELOS = {
    "logistica": LogisticRegression(
        max_iter=1000, class_weight="balanced", random_state=SEED
    ),
    "random_forest": RandomForestClassifier(
        n_estimators=300, class_weight="balanced", random_state=SEED, n_jobs=-1
    ),
    "knn": KNeighborsClassifier(n_neighbors=15, weights="distance"),
    "arvore": DecisionTreeClassifier(
        max_depth=4, class_weight="balanced", random_state=SEED
    ),
}


def _validar_xy(X_tr, y_tr, X_te, y_te) -> None:
    if list(X_tr.columns) != list(X_te.columns):
        raise ValueError("X_treino e X_teste com colunas diferentes")
    for nome, y in (("y_treino", y_tr), ("y_teste", y_te)):
        valores = set(pd.unique(y))
        if not valores.issubset({0, 1}):
            raise ValueError(f"{nome} precisa ser binario (0/1); recebido {valores}")
    if len(X_tr) != len(y_tr) or len(X_te) != len(y_te):
        raise ValueError("X e y com tamanhos diferentes")


def treinar_classificadores(
    X_tr: pd.DataFrame,
    y_tr: pd.Series,
    X_te: pd.DataFrame,
    y_te: pd.Series,
    modelos: dict | None = None,
) -> pd.DataFrame:
    """
    Treina cada modelo no treino e avalia no teste (holdout).

    Args:
        X_tr, y_tr: Features e alvo de TREINO (idealmente padronizados).
        X_te, y_te: Features e alvo de TESTE (a prova, nunca visto).
        modelos: Dict {nome: estimador}; default `MODELOS`.

    Returns:
        DataFrame com `COLUNAS_MATRIZ`, uma linha por modelo, ordenado
        por ROC-AUC descendente. Todas as metricas sao calculadas no
        teste; o tempo de treino alimenta a comparacao de custo da aula.

    Raises:
        ValueError: Se colunas divergirem, alvo nao for binario ou
            tamanhos nao baterem.
    """
    _validar_xy(X_tr, y_tr, X_te, y_te)
    modelos = modelos or MODELOS

    linhas = []
    for nome, modelo in modelos.items():
        t0 = time.perf_counter()
        modelo.fit(X_tr, y_tr)
        tempo = time.perf_counter() - t0

        prob = modelo.predict_proba(X_te)[:, 1]
        pred = (prob >= 0.5).astype(int)
        linhas.append(
            {
                "modelo": nome,
                "roc_auc": roc_auc_score(y_te, prob),
                "pr_auc": average_precision_score(y_te, prob),
                "f1": f1_score(y_te, pred),
                "precision": precision_score(y_te, pred, zero_division=0),
                "recall": recall_score(y_te, pred, zero_division=0),
                "acuracia": accuracy_score(y_te, pred),
                "tempo_seg": round(tempo, 3),
            }
        )

    matriz = pd.DataFrame(linhas, columns=COLUNAS_MATRIZ)
    matriz = matriz.sort_values("roc_auc", ascending=False).reset_index(drop=True)
    logger.info("Matriz de classificacao: %d modelos avaliados", len(matriz))
    return matriz


def importancia_features(
    modelo,
    X: pd.DataFrame,
    y: pd.Series,
    n_repeats: int = 10,
    seed: int = SEED,
) -> pd.Series:
    """
    Importancia por PERMUTACAO (embaralha uma coluna e mede o quanto a
    metrica cai) — funciona para qualquer modelo e mede contribuicao real,
    nao so ganância de divisao como o impurity_importance de arvores.

    Args:
        modelo: Estimador JA TREINADO (tipicamente o vencedor da matriz).
        X, y: Onde medir (idealmente o teste — mantem a honestidade).
        n_repeats: Embaralhamentos por coluna (estabilidade da medida).
        seed: Seed da permutacao.

    Returns:
        Series indexada pelas colunas de X, ordenada descendente
        (maior queda de ROC-AUC = variavel mais importante).
    """
    if X.shape[1] != len(X.columns):
        raise ValueError("X sem colunas nomeadas")
    resultado = permutation_importance(
        modelo,
        X,
        y,
        n_repeats=n_repeats,
        random_state=seed,
        scoring="roc_auc",
    )
    return pd.Series(
        resultado.importances_mean, index=X.columns
    ).sort_values(ascending=False)


def extrair_residuos_oportunidade(
    df: pd.DataFrame,
    alvo: str,
    prob: pd.Series | np.ndarray,
    limiar: float = 0.5,
    colunas: list[str] | None = None,
) -> pd.DataFrame:
    """
    Extrai os FALSOS NEGATIVOS do classificador — o produto de negocio:
    municipios com probabilidade prevista alta (perfil de bancarizado)
    mas sem presenca (alvo = 0). Sao as "oportunidades nao atendidas",
    candidatas a cruzar com o rank do IPB.

    Args:
        df: Dataset com identidade e coluna-alvo (index alinhado com prob).
        alvo: Coluna binaria observada (ex.: "flag_tem_agencia").
        prob: Probabilidade prevista da classe positiva (0 a 1).
        limiar: Corte de "probabilidade alta" (default 0.5).
        colunas: Colunas para carregar no resultado (default so o alvo);
            passe a identidade para um relatorio legivel.

    Returns:
        DataFrame filtrado (falso negativo), com a coluna extra
        `prob_prevista`, ordenado da maior para a menor probabilidade.

    Raises:
        ValueError: Se o alvo nao existir, o vetor de probabilidades nao
            se alinhar com `df` ou o limiar estiver fora de [0, 1].
    """
    if alvo not in df.columns:
        raise ValueError(f"alvo nao encontrado no dataset: {alvo}")
    if not 0.0 <= limiar <= 1.0:
        raise ValueError(f"limiar precisa estar em [0, 1]; recebido {limiar}")
    if len(prob) != len(df):
        raise ValueError("probabilidades nao alinhadas com o dataset")
    prob_serie = pd.Series(np.asarray(prob), index=df.index)
    if prob_serie.isna().any():
        raise ValueError("probabilidades com valores nulos")

    mascara = (prob_serie >= limiar) & (df[alvo] == 0)
    colunas = colunas or [alvo]
    faltantes = set(colunas) - set(df.columns)
    if faltantes:
        raise ValueError(f"colunas ausentes no dataset: {sorted(faltantes)}")

    residuos = df.loc[mascara, colunas].copy()
    residuos["prob_prevista"] = prob_serie[mascara]
    logger.info("Residuos (falsos negativos): %d municipios", len(residuos))
    return residuos.sort_values("prob_prevista", ascending=False)


def matriz_confusao(y_te: pd.Series, prob, limiar: float = 0.5) -> pd.DataFrame:
    """
    Matriz de confusao 2x2 no formato legivel (counts), a partir das
    probabilidades previstas — o notebook usa direto para o grafico.
    """
    pred = (np.asarray(prob) >= limiar).astype(int)
    classes = [0, 1]
    cm = confusion_matrix(y_te, pred, labels=classes)
    return pd.DataFrame(
        cm,
        index=["obs_negativo", "obs_positivo"],
        columns=["prev_negativo", "prev_positivo"],
    )


# ------------------------------------------------------- multiclasse
# Classificador de arquetipos: o rotulo e o proprio cluster (K-Means),
# entao o modelo e 100% baseado em dados. Serve para (1) explicar quais
# variaveis definem cada arquetipo, (2) classificar municipio novo sem
# refazer o cluster e (3) medir a solidez dos grupos (F1 macro alto =
# arquetipos bem separados; baixo = grupos se misturam, e o relatorio
# diz isso com numero).

MODELOS_MULTICLASSE = {
    "random_forest": RandomForestClassifier(
        n_estimators=300, class_weight="balanced", random_state=SEED, n_jobs=-1
    ),
    "logistica": LogisticRegression(
        max_iter=1000, class_weight="balanced", random_state=SEED
    ),
}

COLUNAS_MATRIZ_MULTICLASSE = ["modelo", "f1_macro", "acuracia", "tempo_seg"]


def treinar_multiclasse(
    X_tr: pd.DataFrame,
    y_tr: pd.Series,
    X_te: pd.DataFrame,
    y_te: pd.Series,
    modelos: dict | None = None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """
    Treina classificadores multi-classe para o rotulo de arquetipo.

    `class_weight="balanced"` compensa os tamanhos designais dos
    clusters (grupo gigante de cidades pequenas nao deve engolir os
    demais no aprendizado).

    Args:
        X_tr, y_tr: Treino (features padronizadas + rotulo do cluster).
        X_te, y_te: Teste (a prova).
        modelos: Dict {nome: estimador}; default `MODELOS_MULTICLASSE`.

    Returns:
        (matriz, confusao). `matriz` tem `COLUNAS_MATRIZ_MULTICLASSE`
        (F1 macro — a media do F1 entre classes, que pune classe esquecida);
        `confusao` e um dict {modelo: DataFrame n_classes x n_classes}
        com counts legiveis para o grafico.
    """
    if list(X_tr.columns) != list(X_te.columns):
        raise ValueError("X_treino e X_teste com colunas diferentes")
    if len(X_tr) != len(y_tr) or len(X_te) != len(y_te):
        raise ValueError("X e y com tamanhos diferentes")
    y_tr = pd.Series(y_tr)
    y_te = pd.Series(y_te)
    classes = sorted(pd.unique(y_tr))
    if len(classes) < 2:
        raise ValueError("rotulo de arquetipo precisa ter ao menos 2 classes")

    modelos = modelos or MODELOS_MULTICLASSE
    linhas, confusao = [], {}
    for nome, modelo in modelos.items():
        t0 = time.perf_counter()
        modelo.fit(X_tr, y_tr)
        tempo = time.perf_counter() - t0

        pred = modelo.predict(X_te)
        linhas.append(
            {
                "modelo": nome,
                "f1_macro": f1_score(y_te, pred, average="macro", zero_division=0),
                "acuracia": accuracy_score(y_te, pred),
                "tempo_seg": round(tempo, 3),
            }
        )
        cm = confusion_matrix(y_te, pred, labels=classes)
        confusao[nome] = pd.DataFrame(
            cm, index=[f"obs_{c}" for c in classes], columns=[f"prev_{c}" for c in classes]
        )

    matriz = (
        pd.DataFrame(linhas, columns=COLUNAS_MATRIZ_MULTICLASSE)
        .sort_values("f1_macro", ascending=False)
        .reset_index(drop=True)
    )
    logger.info("Classificador de arquetipos: %d modelos avaliados", len(matriz))
    return matriz, confusao
