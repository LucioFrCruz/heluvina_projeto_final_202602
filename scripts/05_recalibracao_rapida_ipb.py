"""
Análise local de recalibração rápida do IPB.

Objetivo: testar ajustes anti-vies (Abordagem 1 do Plano de Recalibração)
sem subir dados para o BigQuery.

Inputs:
    - data/processed/trusted_municipios_eda.parquet

Outputs (locais, nao versionados):
    - data/processed/ipb_recalibrado_rapido.parquet
    - data/processed/reports/comparacao_ipb_recalibrado.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = PROCESSED_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def winsorize(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    """Winsoriza serie nos percentis informados."""
    low = series.quantile(lower)
    up = series.quantile(upper)
    return series.clip(lower=low, upper=up)


def min_max_normalize(series: pd.Series) -> pd.Series:
    """Normaliza serie em [0, 1]."""
    min_val = series.min()
    max_val = series.max()
    if max_val == min_val:
        return pd.Series(0.0, index=series.index)
    return (series - min_val) / (max_val - min_val)


def compute_ipb_atual(df: pd.DataFrame) -> pd.DataFrame:
    """
    Replica o IPB alpha atual (mesma formula do notebook 04).
    Pilares com pesos iguais e todas as variaveis originais.
    """
    df = df.copy()

    # Variaveis por pilar
    vars_a = ["pib_per_capita", "rendimento_domiciliar_per_capita"]
    vars_b = ["pix_per_capita_12m"]
    vars_c = ["banda_larga_fixa_por_100_hab"]
    vars_d = ["agencias_por_100k_hab", "depositos_per_capita", "credito_per_capita"]
    vars_e = ["escolaridade_ensino_medio_pct", "populacao_18_35_pct", "populacao_urbana_pct"]

    for col in vars_a + vars_b + vars_c + vars_d + vars_e:
        df[f"{col}_norm"] = min_max_normalize(winsorize(df[col]))

    # Pilar D invertido
    for col in vars_d:
        df[f"{col}_norm"] = 1 - df[f"{col}_norm"]

    df["A_capacidade_consumo"] = df[[f"{c}_norm" for c in vars_a]].mean(axis=1)
    df["B_dinamismo"] = df[[f"{c}_norm" for c in vars_b]].mean(axis=1)
    df["C_adocao_digital"] = df[[f"{c}_norm" for c in vars_c]].mean(axis=1)
    df["D_gap_bancario"] = df[[f"{c}_norm" for c in vars_d]].mean(axis=1)
    df["E_perfil_demografico"] = df[[f"{c}_norm" for c in vars_e]].mean(axis=1)

    # Media geometrica com pesos iguais
    df["ipb_atual"] = (
        df["A_capacidade_consumo"]
        * df["B_dinamismo"]
        * df["C_adocao_digital"]
        * df["D_gap_bancario"]
        * df["E_perfil_demografico"]
    ) ** (1 / 5) * 100

    df["rank_ipb_atual"] = df["ipb_atual"].rank(ascending=False, method="min").astype(int)

    return df


def compute_ipb_recalibrado(df: pd.DataFrame) -> pd.DataFrame:
    """
    IPB recalibrado com a Abordagem 1 (rapida):
    - Pesos diferenciados;
    - Pilar D com apenas agencias_por_100k_hab;
    - Pilar E sem populacao_urbana_pct;
    - Inclui tensao_digital_bancaria.
    """
    df = df.copy()

    # Feature nova: tensao digital vs bancaria
    df["tensao_digital_bancaria"] = df["pix_per_capita_12m"] / (df["agencias_por_100k_hab"] + 1)

    # Variaveis por pilar
    vars_a = ["pib_per_capita", "rendimento_domiciliar_per_capita"]
    vars_b = ["pix_per_capita_12m", "tensao_digital_bancaria"]
    vars_c = ["banda_larga_fixa_por_100_hab"]
    vars_d = ["agencias_por_100k_hab"]  # reduzido
    vars_e = ["escolaridade_ensino_medio_pct", "populacao_18_35_pct"]  # sem urbana

    for col in vars_a + vars_b + vars_c + vars_d + vars_e:
        df[f"{col}_norm"] = min_max_normalize(winsorize(df[col]))

    # Pilar D invertido
    for col in vars_d:
        df[f"{col}_norm"] = 1 - df[f"{col}_norm"]

    df["A_capacidade_consumo_v2"] = df[[f"{c}_norm" for c in vars_a]].mean(axis=1)
    df["B_dinamismo_v2"] = df[[f"{c}_norm" for c in vars_b]].mean(axis=1)
    df["C_adocao_digital_v2"] = df[[f"{c}_norm" for c in vars_c]].mean(axis=1)
    df["D_gap_bancario_v2"] = df[[f"{c}_norm" for c in vars_d]].mean(axis=1)
    df["E_perfil_demografico_v2"] = df[[f"{c}_norm" for c in vars_e]].mean(axis=1)

    # Pesos
    w_a, w_b, w_c, w_d, w_e = 0.5, 0.75, 0.75, 1.5, 1.0
    soma_pesos = w_a + w_b + w_c + w_d + w_e

    df["ipb_recalibrado"] = (
        (df["A_capacidade_consumo_v2"] ** w_a)
        * (df["B_dinamismo_v2"] ** w_b)
        * (df["C_adocao_digital_v2"] ** w_c)
        * (df["D_gap_bancario_v2"] ** w_d)
        * (df["E_perfil_demografico_v2"] ** w_e)
    ) ** (1 / soma_pesos) * 100

    df["rank_ipb_recalibrado"] = (
        df["ipb_recalibrado"].rank(ascending=False, method="min").astype(int)
    )

    return df


def comparar_rankings(df: pd.DataFrame) -> dict:
    """Gera comparativos entre IPB atual e recalibrado."""
    comparacao = {}

    comparacao["estatisticas_gerais"] = {
        "ipb_atual": {
            "media": round(df["ipb_atual"].mean(), 2),
            "mediana": round(df["ipb_atual"].median(), 2),
            "max": round(df["ipb_atual"].max(), 2),
            "min": round(df["ipb_atual"].min(), 2),
        },
        "ipb_recalibrado": {
            "media": round(df["ipb_recalibrado"].mean(), 2),
            "mediana": round(df["ipb_recalibrado"].median(), 2),
            "max": round(df["ipb_recalibrado"].max(), 2),
            "min": round(df["ipb_recalibrado"].min(), 2),
        },
    }

    # Top 10 atual
    comparacao["top10_atual"] = (
        df.nsmallest(10, "rank_ipb_atual")[
            ["rank_ipb_atual", "nome_municipio", "sigla_uf", "estrato_populacional", "ipb_atual"]
        ]
        .rename(columns={"rank_ipb_atual": "rank"})
        .to_dict(orient="records")
    )

    # Top 10 recalibrado
    comparacao["top10_recalibrado"] = (
        df.nsmallest(10, "rank_ipb_recalibrado")[
            ["rank_ipb_recalibrado", "nome_municipio", "sigla_uf", "estrato_populacional", "ipb_recalibrado"]
        ]
        .rename(columns={"rank_ipb_recalibrado": "rank"})
        .to_dict(orient="records")
    )

    # Movimentacao geral
    df["delta_rank"] = df["rank_ipb_atual"] - df["rank_ipb_recalibrado"]

    comparacao["maiores_subidas"] = (
        df.nlargest(15, "delta_rank")[
            ["nome_municipio", "sigla_uf", "estrato_populacional", "rank_ipb_atual", "rank_ipb_recalibrado", "delta_rank", "ipb_recalibrado"]
        ]
        .to_dict(orient="records")
    )

    comparacao["maiores_quedas"] = (
        df.nsmallest(15, "delta_rank")[
            ["nome_municipio", "sigla_uf", "estrato_populacional", "rank_ipb_atual", "rank_ipb_recalibrado", "delta_rank", "ipb_atual"]
        ]
        .to_dict(orient="records")
    )

    # Quem saiu/entrou no Top 100
    top100_atual = set(df.nsmallest(100, "rank_ipb_atual")["id_municipio"])
    top100_novo = set(df.nsmallest(100, "rank_ipb_recalibrado")["id_municipio"])

    comparacao["sairam_top100"] = (
        df[df["id_municipio"].isin(top100_atual - top100_novo)][
            ["nome_municipio", "sigla_uf", "estrato_populacional", "rank_ipb_atual", "rank_ipb_recalibrado"]
        ]
        .to_dict(orient="records")
    )

    comparacao["entraram_top100"] = (
        df[df["id_municipio"].isin(top100_novo - top100_atual)][
            ["nome_municipio", "sigla_uf", "estrato_populacional", "rank_ipb_atual", "rank_ipb_recalibrado"]
        ]
        .to_dict(orient="records")
    )

    # Analise por estrato
    comparacao["por_estrato"] = {}
    for estrato in df["estrato_populacional"].dropna().unique():
        sub = df[df["estrato_populacional"] == estrato]
        top5_atual = sub.nsmallest(5, "rank_ipb_atual")[
            ["rank_ipb_atual", "nome_municipio", "sigla_uf", "ipb_atual"]
        ].rename(columns={"rank_ipb_atual": "rank", "ipb_atual": "ipb"}).to_dict(orient="records")
        top5_novo = sub.nsmallest(5, "rank_ipb_recalibrado")[
            ["rank_ipb_recalibrado", "nome_municipio", "sigla_uf", "ipb_recalibrado"]
        ].rename(columns={"rank_ipb_recalibrado": "rank", "ipb_recalibrado": "ipb"}).to_dict(orient="records")
        comparacao["por_estrato"][estrato] = {
            "quantidade": int(len(sub)),
            "top5_atual": top5_atual,
            "top5_recalibrado": top5_novo,
        }

    return comparacao


def main() -> None:
    logger.info("Carregando base enriquecida local...")
    df = pd.read_parquet(PROCESSED_DIR / "trusted_municipios_eda.parquet")
    logger.info("Base: %d municípios, %d colunas", len(df), len(df.columns))

    logger.info("Calculando IPB atual (referencia)...")
    df = compute_ipb_atual(df)

    logger.info("Calculando IPB recalibrado (Abordagem 1)...")
    df = compute_ipb_recalibrado(df)

    logger.info("Gerando comparativos...")
    comparacao = comparar_rankings(df)

    # Salva resultados locais
    output_parquet = PROCESSED_DIR / "ipb_recalibrado_rapido.parquet"
    df.to_parquet(output_parquet, index=False)
    logger.info("Resultado salvo em: %s", output_parquet)

    output_json = REPORTS_DIR / "comparacao_ipb_recalibrado.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(comparacao, f, indent=2, ensure_ascii=False, default=str)
    logger.info("Comparacao salva em: %s", output_json)

    # Print resumido no terminal
    print("\n" + "=" * 70)
    print("COMPARACAO: IPB ATUAL vs IPB RECALIBRADO (RAPIDO)")
    print("=" * 70)

    stats = comparacao["estatisticas_gerais"]
    print(f"\nMédia IPB atual:        {stats['ipb_atual']['media']}")
    print(f"Média IPB recalibrado:  {stats['ipb_recalibrado']['media']}")
    print(f"Mediana IPB atual:      {stats['ipb_atual']['mediana']}")
    print(f"Mediana IPB recalibrado:{stats['ipb_recalibrado']['mediana']}")
    print(f"Max IPB atual:          {stats['ipb_atual']['max']}")
    print(f"Max IPB recalibrado:    {stats['ipb_recalibrado']['max']}")

    print("\n--- TOP 10 ATUAL ---")
    for r in comparacao["top10_atual"]:
        print(f"  {r['rank']:2d}. {r['nome_municipio']}-{r['sigla_uf']} ({r['estrato_populacional']}) -> {r['ipb_atual']:.2f}")

    print("\n--- TOP 10 RECALIBRADO ---")
    for r in comparacao["top10_recalibrado"]:
        print(f"  {r['rank']:2d}. {r['nome_municipio']}-{r['sigla_uf']} ({r['estrato_populacional']}) -> {r['ipb_recalibrado']:.2f}")

    print(f"\n--- MAIOR MOVIMENTACAO NO TOP 100 ---")
    print(f"Sairam do Top 100: {len(comparacao['sairam_top100'])}")
    for r in comparacao["sairam_top100"]:
        print(f"  {r['nome_municipio']}-{r['sigla_uf']}: {r['rank_ipb_atual']} -> {r['rank_ipb_recalibrado']}")
    print(f"Entraram no Top 100: {len(comparacao['entraram_top100'])}")
    for r in comparacao["entraram_top100"]:
        print(f"  {r['nome_municipio']}-{r['sigla_uf']}: {r['rank_ipb_atual']} -> {r['rank_ipb_recalibrado']}")

    print("\n--- TOP 5 POR ESTRATO (RECALIBRADO) ---")
    for estrato, dados in comparacao["por_estrato"].items():
        print(f"\nEstrato: {estrato} ({dados['quantidade']} municípios)")
        for r in dados["top5_recalibrado"]:
            print(f"  {r['rank']:2d}. {r['nome_municipio']}-{r['sigla_uf']} -> {r['ipb']:.2f}")

    print("\n" + "=" * 70)
    print("Analise concluida. Arquivos salvos localmente em data/processed/.")
    print("=" * 70)


if __name__ == "__main__":
    main()
