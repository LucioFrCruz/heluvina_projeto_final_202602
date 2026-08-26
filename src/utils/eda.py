"""Utilitários reutilizáveis para Análise Exploratória de Dados (EDA) do IPB."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src.config import PROCESSED_DATA_DIR

logger = logging.getLogger(__name__)

FIGURES_DIR = PROCESSED_DATA_DIR / "figures"
REPORTS_DIR = PROCESSED_DATA_DIR / "reports"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def save_figure(fig: plt.Figure, filename: str, dpi: int = 150) -> Path:
    """Salva figura em data/processed/figures/ e retorna o caminho.

    Args:
        fig: Objeto Figure do matplotlib.
        filename: Nome do arquivo (ex.: "00_dist_populacao.png").
        dpi: Resolução da imagem.

    Returns:
        Caminho absoluto do arquivo salvo.
    """
    path = FIGURES_DIR / filename
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    logger.info("Figura salva em %s", path)
    return path


def save_parquet(df: pd.DataFrame, filename: str) -> Path:
    """Salva DataFrame em data/processed/ como Parquet.

    Args:
        df: DataFrame a ser salvo.
        filename: Nome do arquivo (ex.: "trusted_municipios_eda.parquet").

    Returns:
        Caminho absoluto do arquivo salvo.
    """
    path = PROCESSED_DATA_DIR / filename
    df.to_parquet(path, index=False)
    logger.info("Parquet salvo em %s", path)
    return path


def save_json(data: dict[str, Any], filename: str) -> Path:
    """Salva dicionário em data/processed/reports/ como JSON.

    Args:
        data: Dicionário com dados serializáveis.
        filename: Nome do arquivo (ex.: "data_quality_report.json").

    Returns:
        Caminho absoluto do arquivo salvo.
    """
    path = REPORTS_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    logger.info("JSON salvo em %s", path)
    return path


def compute_null_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Retorna DataFrame com coluna, tipo, nulos absolutos e percentual.

    Args:
        df: DataFrame de entrada.

    Returns:
        DataFrame ordenado pelo percentual de nulos decrescente.
    """
    profile = pd.DataFrame({
        "coluna": df.columns,
        "tipo": df.dtypes.astype(str).values,
        "nulos": df.isnull().sum().values,
        "pct_nulos": (df.isnull().mean() * 100).round(2).values,
    })
    return profile.sort_values("pct_nulos", ascending=False)


def compute_descriptive_stats(df: pd.DataFrame, numeric_only: bool = True) -> pd.DataFrame:
    """Retorna estatísticas descritivas estendidas.

    Inclui média, desvio padrão, percentis, assimetria, curtose, IQR e
    percentual de missing values.

    Args:
        df: DataFrame de entrada.
        numeric_only: Se True, considera apenas colunas numéricas.

    Returns:
        DataFrame com estatísticas por coluna.
    """
    cols = df.select_dtypes(include=[np.number]).columns if numeric_only else df.columns
    desc = df[cols].describe(percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]).T
    desc["skewness"] = df[cols].skew()
    desc["kurtosis"] = df[cols].kurtosis()
    desc["iqr"] = desc["75%"] - desc["25%"]
    desc["missing_pct"] = (df[cols].isnull().mean() * 100).round(2)
    return desc


def detect_outliers_iqr(df: pd.DataFrame, column: str, k: float = 1.5) -> pd.DataFrame:
    """Retorna linhas consideradas outliers pela regra do IQR.

    Args:
        df: DataFrame de entrada.
        column: Coluna numérica a ser analisada.
        k: Fator multiplicador do IQR.

    Returns:
        DataFrame contendo apenas os outliers detectados.
    """
    q1 = df[column].quantile(0.25)
    q3 = df[column].quantile(0.75)
    iqr = q3 - q1
    lower = q1 - k * iqr
    upper = q3 + k * iqr
    return df[(df[column] < lower) | (df[column] > upper)].copy()


def winsorize_series(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    """Aplica winsorização nos percentis informados.

    Args:
        series: Série numérica.
        lower: Percentil inferior.
        upper: Percentil superior.

    Returns:
        Série winsorizada.
    """
    low = series.quantile(lower)
    up = series.quantile(upper)
    return series.astype(float).clip(lower=low, upper=up)


def min_max_normalize(series: pd.Series) -> pd.Series:
    """Normaliza série em [0, 1].

    Args:
        series: Série numérica.

    Returns:
        Série normalizada.
    """
    min_val = series.min()
    max_val = series.max()
    if max_val == min_val:
        return pd.Series(0.0, index=series.index)
    return (series - min_val) / (max_val - min_val)


def plot_distribution(
    df: pd.DataFrame,
    column: str,
    title: str | None = None,
    xlabel: str | None = None,
    log_scale: bool = False,
    filename: str | None = None,
) -> plt.Figure:
    """Gera histograma com KDE para uma variável numérica.

    Args:
        df: DataFrame de entrada.
        column: Coluna numérica a ser plotada.
        title: Título do gráfico.
        xlabel: Rótulo do eixo X.
        log_scale: Se True, aplica log1p nos dados.
        filename: Nome do arquivo para salvar a figura.

    Returns:
        Objeto Figure do matplotlib.
    """
    fig, ax = plt.subplots(figsize=(10, 5))
    data = np.log1p(df[column].dropna()) if log_scale else df[column].dropna()
    sns.histplot(data, kde=True, ax=ax, color="steelblue")
    ax.set_title(title or f"Distribuição de {column}")
    ax.set_xlabel(xlabel or (f"log({column} + 1)" if log_scale else column))
    ax.set_ylabel("Frequência")
    if filename:
        save_figure(fig, filename)
    return fig


def plot_boxplot_by_group(
    df: pd.DataFrame,
    column: str,
    group: str,
    title: str | None = None,
    filename: str | None = None,
) -> plt.Figure:
    """Gera boxplot de uma variável por grupo.

    Args:
        df: DataFrame de entrada.
        column: Coluna numérica.
        group: Coluna categórica.
        title: Título do gráfico.
        filename: Nome do arquivo para salvar a figura.

    Returns:
        Objeto Figure do matplotlib.
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    order = sorted(df[group].dropna().unique())
    sns.boxplot(data=df, x=group, y=column, ax=ax, order=order)
    ax.set_title(title or f"{column} por {group}")
    ax.tick_params(axis="x", rotation=45)
    if filename:
        save_figure(fig, filename)
    return fig


def plot_correlation_heatmap(
    df: pd.DataFrame,
    columns: list[str],
    method: str = "spearman",
    title: str | None = None,
    filename: str | None = None,
) -> plt.Figure:
    """Gera heatmap de correlação.

    Args:
        df: DataFrame de entrada.
        columns: Lista de colunas numéricas.
        method: Método de correlação ('pearson' ou 'spearman').
        title: Título do gráfico.
        filename: Nome do arquivo para salvar a figura.

    Returns:
        Objeto Figure do matplotlib.
    """
    corr = df[columns].corr(method=method)
    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0, ax=ax, square=True)
    ax.set_title(title or f"Matriz de Correlação ({method})")
    if filename:
        save_figure(fig, filename)
    return fig
