"""
Calculo das tres versoes do Indice de Potencial Bancario (IPB).

Versoes:
    - V1 = IPB Classico (ex-"IPB Atual"): 5 pilares com pesos iguais.
    - V2 = IPB Recalibrado (ex-"Recalibrado Rapido"): pesos 0.5/0.75/0.75/1.5/1.0
      e feature `tensao_digital_bancaria`.
    - V3 = IPB Presenca Bancaria Completa (ex-"Abordagem 2"): correspondentes
      por tipo, `penetracao_digital_relativa`, `gap_bancario_completo` e flag
      de turismo com desconto maximo de 15% no pilar B.

Esta logica e uma refatoracao fiel de `scripts/06_comparacao_tres_abordagens_ipb.py`
(fonte da verdade das formulas, validadas e publicadas em
`docs/Comparacao_Tres_Abordagens_IPB.md`). As formulas NAO foram alteradas;
apenas os nomes de colunas de saida foram padronizados (ex.: `A_atual` -> `A_v1`,
`ipb_atual` -> `ipb_v1_classico`). Os rankings foram extraidos das funcoes de
calculo para `adicionar_ranks`, que adota os prefixos oficiais `v1`, `v2`, `v3`.

A orquestracao (leitura de parquet, chamada das funcoes, publicacao no
BigQuery) fica em `scripts/07_publica_ipb_bigquery.py` (fora deste modulo).
"""

from __future__ import annotations

import datetime as dt
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Nomes oficiais das colunas de IPB de cada versao.
COL_IPB_V1 = "ipb_v1_classico"
COL_IPB_V2 = "ipb_v2_recalibrado"
COL_IPB_V3 = "ipb_v3_presenca_completa"

# Pesos dos pilares (A..E) por versao. Constantes exportadas para permitir
# testes de invariancia de escala; os valores sao os do script 06.
PESOS_V2 = {"A": 0.5, "B": 0.75, "C": 0.75, "D": 1.5, "E": 1.0}
PESOS_V3 = {"A": 0.75, "B": 1.0, "C": 0.75, "D": 1.5, "E": 1.0}

# Ponderacao dos correspondentes bancarios por tipo (V3), como no script 06.
PONDERACAO_CORRESPONDENTES = {
    "quantidade_correspondentes_posto": 1.00,
    "quantidade_correspondentes_filial": 0.70,
    "quantidade_correspondentes_sede": 0.40,
    "quantidade_correspondentes_agencia": 1.00,
}

# Mapeamento UF -> regiao (classificacao oficial do IBGE).
UF_PARA_REGIAO = {
    "AC": "Norte", "AP": "Norte", "AM": "Norte", "PA": "Norte",
    "RO": "Norte", "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste",
    "PB": "Nordeste", "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste",
    "SE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MT": "Centro-Oeste",
    "MS": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul",
}

# Limite inferior da faixa "media" do estrato populacional (inclusive).
LIMITE_ESTRATO_PEQUENA = 50_000
# Limite superior da faixa "media" do estrato populacional (inclusive).
LIMITE_ESTRATO_MEDIA = 500_000


def winsorize(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    """Clipa a serie nos quantis `lower` e `upper` (padrao 1%/99%)."""
    return series.clip(lower=series.quantile(lower), upper=series.quantile(upper))


def normalize(series: pd.Series) -> pd.Series:
    """Normaliza a serie para [0, 1]; serie constante vira zeros."""
    min_val, max_val = series.min(), series.max()
    if max_val == min_val:
        return pd.Series(0.0, index=series.index)
    return (series - min_val) / (max_val - min_val)


def derive_estrato(populacao: pd.Series) -> pd.Series:
    """
    Classifica a populacao em estratos oficiais do projeto.

    Faixas (decisao do projeto, ver Relatorio EDA secao 5.1 — nao e uma
    classificacao de fonte externa):
        - "pequena": populacao < 50.000
        - "media": 50.000 <= populacao <= 500.000
        - "grande": populacao > 500.000

    Args:
        populacao: Serie com a populacao total do municipio.

    Returns:
        Serie de strings com o estrato ("pequena", "media" ou "grande").
    """
    return pd.cut(
        populacao,
        bins=[-np.inf, LIMITE_ESTRATO_PEQUENA - 1, LIMITE_ESTRATO_MEDIA, np.inf],
        labels=["pequena", "media", "grande"],
    ).astype(str)


def derive_regiao(sigla_uf: pd.Series) -> pd.Series:
    """
    Mapeia a sigla da UF para o nome da regiao (Norte/Nordeste/
    Centro-Oeste/Sudeste/Sul).

    Args:
        sigla_uf: Serie com as siglas de UF (ex.: "SP", "mg").

    Returns:
        Serie de strings com o nome da regiao; UFs desconhecidas viram NaN.
    """
    return sigla_uf.str.upper().map(UF_PARA_REGIAO)


def agregar_correspondentes_por_tipo(
    df_raw: pd.DataFrame, df_enriquecido: pd.DataFrame
) -> pd.DataFrame:
    """
    Agrega correspondentes bancarios por tipo e junta no DF enriquecido.

    Replica a logica do `main()` do script 06: groupby `id_municipio` x
    `Tipo` (unstack), contagem por tipo em `quantidade_correspondentes_posto/
    filial/sede/agencia`, total em `quantidade_correspondentes` e taxa
    `correspondentes_por_100k_hab`.

    Args:
        df_raw: Dados brutos dos correspondentes (BCB), com as colunas
            `id_municipio` e `Tipo` (valores "Posto", "Filial", "Sede" e
            "Agência" — com acento).
        df_enriquecido: Base municipal ja enriquecida. Pre-requisitos:
            colunas `id_municipio` e `populacao_total` (esta usada para a
            taxa por 100 mil habitantes).

    Returns:
        `df_enriquecido` enriquecido com as colunas de correspondentes.
        Municipios sem correspondente recebem 0 (merge externo, `how="left"`).
    """
    faltantes = {"id_municipio", "Tipo"} - set(df_raw.columns)
    if faltantes:
        raise ValueError(f"df_raw sem as colunas obrigatorias: {sorted(faltantes)}")

    corr_por_tipo = (
        df_raw.groupby(["id_municipio", "Tipo"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    for tipo in ["Posto", "Filial", "Sede", "Agência"]:
        if tipo not in corr_por_tipo.columns:
            corr_por_tipo[tipo] = 0

    renomeacao = {
        "Posto": "quantidade_correspondentes_posto",
        "Filial": "quantidade_correspondentes_filial",
        "Sede": "quantidade_correspondentes_sede",
        "Agência": "quantidade_correspondentes_agencia",
    }
    corr_agg = corr_por_tipo.rename(columns=renomeacao)[
        ["id_municipio"] + list(renomeacao.values())
    ]
    corr_agg["quantidade_correspondentes"] = (
        corr_agg["quantidade_correspondentes_posto"]
        + corr_agg["quantidade_correspondentes_filial"]
        + corr_agg["quantidade_correspondentes_sede"]
        + corr_agg["quantidade_correspondentes_agencia"]
    )

    if "populacao_total" not in df_enriquecido.columns:
        raise ValueError(
            "df_enriquecido precisa da coluna 'populacao_total' para "
            "calcular correspondentes_por_100k_hab"
        )

    df = df_enriquecido.merge(corr_agg, on="id_municipio", how="left")
    for col in renomeacao.values():
        df[col] = df[col].fillna(0).astype(int)
    df["quantidade_correspondentes"] = (
        df["quantidade_correspondentes"].fillna(0).astype(int)
    )
    df["correspondentes_por_100k_hab"] = (
        df["quantidade_correspondentes"] / df["populacao_total"]
    ) * 100_000
    return df


def computar_ipb_v1_classico(df: pd.DataFrame) -> pd.DataFrame:
    """
    V1 = IPB Classico (ex-"IPB Atual"): 5 pilares com pesos iguais.

    Replica `compute_ipb_atual` do script 06. Requer as colunas:
    `pib_per_capita`, `rendimento_domiciliar_per_capita`, `pix_per_capita_12m`,
    `banda_larga_fixa_por_100_hab`, `agencias_por_100k_hab`,
    `depositos_per_capita`, `credito_per_capita`,
    `escolaridade_ensino_medio_pct`, `populacao_18_35_pct` e
    `populacao_urbana_pct`. O pilar D e invertido (1 - norm).

    Returns:
        O DF de entrada enriquecido com colunas `_norm`, pilares `A_v1`..`E_v1`
        e `ipb_v1_classico`. Rankings sao calculados separadamente por
        `adicionar_ranks`.
    """
    df = df.copy()

    vars_a = ["pib_per_capita", "rendimento_domiciliar_per_capita"]
    vars_b = ["pix_per_capita_12m"]
    vars_c = ["banda_larga_fixa_por_100_hab"]
    vars_d = ["agencias_por_100k_hab", "depositos_per_capita", "credito_per_capita"]
    vars_e = ["escolaridade_ensino_medio_pct", "populacao_18_35_pct", "populacao_urbana_pct"]

    for col in vars_a + vars_b + vars_c + vars_d + vars_e:
        df[f"{col}_norm"] = normalize(winsorize(df[col]))

    for col in vars_d:
        df[f"{col}_norm"] = 1 - df[f"{col}_norm"]

    df["A_v1"] = df[[f"{c}_norm" for c in vars_a]].mean(axis=1)
    df["B_v1"] = df[[f"{c}_norm" for c in vars_b]].mean(axis=1)
    df["C_v1"] = df[[f"{c}_norm" for c in vars_c]].mean(axis=1)
    df["D_v1"] = df[[f"{c}_norm" for c in vars_d]].mean(axis=1)
    df["E_v1"] = df[[f"{c}_norm" for c in vars_e]].mean(axis=1)

    df[COL_IPB_V1] = (
        df["A_v1"] * df["B_v1"] * df["C_v1"] * df["D_v1"] * df["E_v1"]
    ) ** (1 / 5) * 100

    return df


def computar_ipb_v2_recalibrado(df: pd.DataFrame) -> pd.DataFrame:
    """
    V2 = IPB Recalibrado (ex-"Recalibrado Rapido").

    Replica `compute_ipb_recalibrado_rapido` do script 06: pesos
    0.5/0.75/0.75/1.5/1.0, Pilar D reduzido a `agencias_por_100k_hab` (in-
    vertido), Pilar E sem `populacao_urbana_pct` e feature nova
    `tensao_digital_bancaria` = Pix per capita / (agencias por 100k + 1).
    Pesos exportados em `PESOS_V2`.

    Returns:
        O DF de entrada enriquecido com `tensao_digital_bancaria`, colunas
        `_norm`, pilares `A_v2`..`E_v2` e `ipb_v2_recalibrado`. Rankings em
        `adicionar_ranks`.
    """
    df = df.copy()

    df["tensao_digital_bancaria"] = df["pix_per_capita_12m"] / (df["agencias_por_100k_hab"] + 1)

    vars_a = ["pib_per_capita", "rendimento_domiciliar_per_capita"]
    vars_b = ["pix_per_capita_12m", "tensao_digital_bancaria"]
    vars_c = ["banda_larga_fixa_por_100_hab"]
    vars_d = ["agencias_por_100k_hab"]
    vars_e = ["escolaridade_ensino_medio_pct", "populacao_18_35_pct"]

    for col in vars_a + vars_b + vars_c + vars_d + vars_e:
        df[f"{col}_norm"] = normalize(winsorize(df[col]))

    for col in vars_d:
        df[f"{col}_norm"] = 1 - df[f"{col}_norm"]

    df["A_v2"] = df[[f"{c}_norm" for c in vars_a]].mean(axis=1)
    df["B_v2"] = df[[f"{c}_norm" for c in vars_b]].mean(axis=1)
    df["C_v2"] = df[[f"{c}_norm" for c in vars_c]].mean(axis=1)
    df["D_v2"] = df[[f"{c}_norm" for c in vars_d]].mean(axis=1)
    df["E_v2"] = df[[f"{c}_norm" for c in vars_e]].mean(axis=1)

    w_a, w_b, w_c, w_d, w_e = (PESOS_V2[p] for p in ["A", "B", "C", "D", "E"])
    soma = w_a + w_b + w_c + w_d + w_e

    df[COL_IPB_V2] = (
        (df["A_v2"] ** w_a)
        * (df["B_v2"] ** w_b)
        * (df["C_v2"] ** w_c)
        * (df["D_v2"] ** w_d)
        * (df["E_v2"] ** w_e)
    ) ** (1 / soma) * 100

    return df


def computar_ipb_v3_presenca_completa(df: pd.DataFrame) -> pd.DataFrame:
    """
    V3 = IPB Presenca Bancaria Completa (ex-"Abordagem 2").

    Replica `compute_ipb_abordagem_2` do script 06: correspondentes bancarios
    ponderados por tipo (posto=1.0, filial=0.7, sede=0.4, agencia=1.0),
    `penetracao_digital_relativa` = Pix per capita / PIB per capita,
    `gap_bancario_completo` = 1 / (agencias + correspondentes ponderados por
    100k + 1) e flag de turismo suave (score continuo [0, 1], desconto maximo
    de 15% no pilar B). Pesos exportados em `PESOS_V3`.

    Pre-requisitos alem das variaveis base: colunas
    `quantidade_correspondentes_{posto,filial,sede,agencia}` (municipios sem
    correspondente recebem 0 via `agregar_correspondentes_por_tipo`),
    `populacao_total` e `estrato_populacional` (ver `derive_estrato`).

    A cobertura 4G/5G nao foi integrada nesta rodada por dificuldade de
    acesso aos dados agregados por municipio; mantemos banda larga fixa
    como proxy de infraestrutura digital.

    Returns:
        O DF de entrada enriquecido com as features derivadas, colunas
        `_norm`, pilares `A_v3`..`E_v3` (B_v3 ja com desconto de turismo),
        `score_turismo` e `ipb_v3_presenca_completa`. Rankings em
        `adicionar_ranks`.
    """
    df = df.copy()

    # Presenca bancaria ponderada por tipo de correspondente
    # Postos sao pontos basicos; filiais e sedes tem capacidade maior.
    df["correspondentes_ponderados"] = (
        1.00 * df["quantidade_correspondentes_posto"].fillna(0)
        + 0.70 * df["quantidade_correspondentes_filial"].fillna(0)
        + 0.40 * df["quantidade_correspondentes_sede"].fillna(0)
        + 1.00 * df["quantidade_correspondentes_agencia"].fillna(0)
    )
    df["correspondentes_ponderados_por_100k_hab"] = (
        df["correspondentes_ponderados"] / df["populacao_total"]
    ) * 100_000

    # Features derivadas
    df["tensao_digital_bancaria"] = df["pix_per_capita_12m"] / (df["agencias_por_100k_hab"] + 1)
    df["penetracao_digital_relativa"] = df["pix_per_capita_12m"] / df["pib_per_capita"]
    df["gap_bancario_completo"] = 1 / (
        df["agencias_por_100k_hab"]
        + df["correspondentes_ponderados_por_100k_hab"]
        + 1
    )

    # Flag de turismo suave: alto Pix per capita combinado com PIB per capita
    # abaixo da mediana e populacao pequena. Usamos um score continuo [0, 1]
    # e aplicamos um desconto leve (max 15%) no pilar B.
    pix_alto = df["pix_per_capita_12m"] >= df["pix_per_capita_12m"].quantile(0.90)
    pib_baixo = df["pib_per_capita"] <= df["pib_per_capita"].median()
    pequena = df["estrato_populacional"] == "pequena"
    df["score_turismo"] = (
        pix_alto.astype(int) * 0.5
        + pib_baixo.astype(int) * 0.3
        + pequena.astype(int) * 0.2
    )

    # Evita infinitos
    df["penetracao_digital_relativa"] = df["penetracao_digital_relativa"].replace([np.inf, -np.inf], np.nan)
    df["penetracao_digital_relativa"] = df["penetracao_digital_relativa"].fillna(0)

    vars_a = ["pib_per_capita", "rendimento_domiciliar_per_capita"]
    vars_b = ["pix_per_capita_12m", "tensao_digital_bancaria", "penetracao_digital_relativa"]
    vars_c = ["banda_larga_fixa_por_100_hab"]
    vars_d = ["gap_bancario_completo"]
    vars_e = ["escolaridade_ensino_medio_pct", "populacao_18_35_pct"]

    for col in vars_a + vars_b + vars_c + vars_d + vars_e:
        df[f"{col}_norm"] = normalize(winsorize(df[col]))

    # Pilar D ja esta construido como inverso (gap = 1 / presenca bancaria)
    # Normalizamos e usamos diretamente

    df["A_v3"] = df[[f"{c}_norm" for c in vars_a]].mean(axis=1)
    df["B_v3"] = df[[f"{c}_norm" for c in vars_b]].mean(axis=1)
    df["C_v3"] = df[[f"{c}_norm" for c in vars_c]].mean(axis=1)
    df["D_v3"] = df[[f"{c}_norm" for c in vars_d]].mean(axis=1)
    df["E_v3"] = df[[f"{c}_norm" for c in vars_e]].mean(axis=1)

    # Desconto suave de turismo no pilar B (maximo 15%)
    df["B_v3"] = df["B_v3"] * (1 - 0.15 * df["score_turismo"])

    w_a, w_b, w_c, w_d, w_e = (PESOS_V3[p] for p in ["A", "B", "C", "D", "E"])
    soma = w_a + w_b + w_c + w_d + w_e

    df[COL_IPB_V3] = (
        (df["A_v3"] ** w_a)
        * (df["B_v3"] ** w_b)
        * (df["C_v3"] ** w_c)
        * (df["D_v3"] ** w_d)
        * (df["E_v3"] ** w_e)
    ) ** (1 / soma) * 100

    return df


def adicionar_ranks(df: pd.DataFrame, prefixo: str, col_ipb: str) -> pd.DataFrame:
    """
    Adiciona rankings geral e por estrato populacional.

    Args:
        df: DF com a coluna `col_ipb` e `estrato_populacional` (ver
            `derive_estrato`).
        prefixo: Prefixo oficial da versao ("v1", "v2" ou "v3").
        col_ipb: Nome da coluna do IPB (ex.: `ipb_v1_classico`).

    Returns:
        O DF enriquecido com `rank_{prefixo}` (ranking geral, metodo `min`,
        descendente) e `rank_{prefixo}_estrato` (ranking dentro de cada
        estrato populacional, reiniciando em 1).
    """
    if col_ipb not in df.columns:
        raise ValueError(f"coluna de IPB nao encontrada: {col_ipb}")
    if "estrato_populacional" not in df.columns:
        raise ValueError("df precisa da coluna 'estrato_populacional'")

    df = df.copy()
    df[f"rank_{prefixo}"] = df[col_ipb].rank(ascending=False, method="min").astype(int)
    df[f"rank_{prefixo}_estrato"] = (
        df.groupby("estrato_populacional")[col_ipb]
        .rank(ascending=False, method="min")
        .astype(int)
    )
    return df


def gerar_documento_comparacao(df: pd.DataFrame) -> str:
    """
    Gera documento Markdown comparando as tres versoes do IPB.

    Espera o DF final com as colunas `ipb_v1_classico`, `ipb_v2_recalibrado`,
    `ipb_v3_presenca_completa`, `rank_v1`, `rank_v2`, `rank_v3`,
    `rank_v1_estrato`, `rank_v2_estrato`, `rank_v3_estrato`,
    `id_municipio`, `nome_municipio`, `sigla_uf`, `estrato_populacional` e
    `nome_regiao` (ver `derive_regiao`).
    """

    stats = {
        "v1": {
            "media": round(df[COL_IPB_V1].mean(), 2),
            "mediana": round(df[COL_IPB_V1].median(), 2),
            "max": round(df[COL_IPB_V1].max(), 2),
            "min": round(df[COL_IPB_V1].min(), 2),
        },
        "v2": {
            "media": round(df[COL_IPB_V2].mean(), 2),
            "mediana": round(df[COL_IPB_V2].median(), 2),
            "max": round(df[COL_IPB_V2].max(), 2),
            "min": round(df[COL_IPB_V2].min(), 2),
        },
        "v3": {
            "media": round(df[COL_IPB_V3].mean(), 2),
            "mediana": round(df[COL_IPB_V3].median(), 2),
            "max": round(df[COL_IPB_V3].max(), 2),
            "min": round(df[COL_IPB_V3].min(), 2),
        },
    }

    top10_v1 = df.nsmallest(10, "rank_v1")[
        ["rank_v1", "nome_municipio", "sigla_uf", "estrato_populacional", COL_IPB_V1]
    ].rename(columns={"rank_v1": "rank", COL_IPB_V1: "ipb"})

    top10_v2 = df.nsmallest(10, "rank_v2")[
        ["rank_v2", "nome_municipio", "sigla_uf", "estrato_populacional", COL_IPB_V2]
    ].rename(columns={"rank_v2": "rank", COL_IPB_V2: "ipb"})

    top10_v3 = df.nsmallest(10, "rank_v3")[
        ["rank_v3", "nome_municipio", "sigla_uf", "estrato_populacional", COL_IPB_V3]
    ].rename(columns={"rank_v3": "rank", COL_IPB_V3: "ipb"})

    # Movimentacao no Top 100
    top100_v1 = set(df.nsmallest(100, "rank_v1")["id_municipio"])
    top100_v2 = set(df.nsmallest(100, "rank_v2")["id_municipio"])
    top100_v3 = set(df.nsmallest(100, "rank_v3")["id_municipio"])

    md = f"""# Comparacao de Tres Abordagens do IPB

> **Objetivo**: comparar o IPB Clássico (V1), o IPB Recalibrado (V2) e o IPB Presença Bancária Completa (V3, ex-Abordagem 2).  
> **Escopo**: a V3 já foi publicada no BigQuery (tabelas `analytics_ipb_*`); este documento consolida a comparação das três versões a partir da mesma base.  
> **Data**: {dt.date.today().isoformat()}  
> **Código-fonte das fórmulas**: `src/analytics/ipb.py`

---

## 1. Resumo Executivo

Três versões do índice foram calculadas a partir da mesma base `trusted_municipios` (com o bug do Pix corrigido):

| Versão | Conceito |
|---|---|
| **IPB Clássico (V1)** | Fórmula original: 5 pilares com pesos iguais. Premia cidades ricas, conectadas e com demanda digital, mas pune pouco cidades já bancarizadas (Pilar D usa 3 variáveis redundantes). |
| **IPB Recalibrado (V2)** | Ajuste rápido anti-viés: pesos diferenciados, Pilar D reduzido a apenas `agencias_por_100k_hab`, Pilar E sem `populacao_urbana_pct` e inclusão de `tensao_digital_bancaria` (Pix / agências). Diminui a influência da renda pura. |
| **IPB Presença Bancária Completa (V3, ex-Abordagem 2)** | Redesenho do Pilar D: agências bancárias estão em queda, então o índice passa a considerar **correspondentes bancários do BCB por tipo** (posto, filial, sede, agência) com pesos diferentes. Adiciona `penetracao_digital_relativa` (Pix / PIB) e `gap_bancario_completo`. Inclui ainda uma **flag de turismo suave** (score contínuo, desconto máximo de 15% no pilar digital) para não privilegiar cidades pequenas com fluxo turístico. |

### Estatísticas gerais

| Métrica | IPB Clássico (V1) | IPB Recalibrado (V2) | IPB Presença Bancária Completa (V3) |
|---|---|---|---|
| Média | {stats['v1']['media']} | {stats['v2']['media']} | {stats['v3']['media']} |
| Mediana | {stats['v1']['mediana']} | {stats['v2']['mediana']} | {stats['v3']['mediana']} |
| Máximo | {stats['v1']['max']} | {stats['v2']['max']} | {stats['v3']['max']} |
| Mínimo | {stats['v1']['min']} | {stats['v2']['min']} | {stats['v3']['min']} |

---

## 2. Como cada versão funciona

### 2.1 IPB Clássico (V1)

Cinco pilares com **pesos iguais** (média geométrica):
- **A. Capacidade de consumo**: PIB per capita + rendimento domiciliar per capita.
- **B. Dinamismo econômico**: Pix per capita últimos 12 meses.
- **C. Adoção digital**: banda larga fixa por 100 habitantes.
- **D. Gap bancário**: agências, depósitos e crédito per capita (todas invertidas).
- **E. Perfil demográfico**: escolaridade, população 18-35 anos e população urbana.

**Problema**: cidades ricas já bancarizadas (Barueri, Itapema, Balneário Camboriú) lideram porque a renda e o digital pesam muito, enquanto o gap bancário é fraco.

### 2.2 IPB Recalibrado (V2)

Mesma estrutura de 5 pilares, mas com **pesos diferenciados**:
- Pilar A (renda) reduzido para 0.5.
- Pilares B (digital) e C (infra) com 0.75 cada.
- Pilar D (gap bancário) ampliado para 1.5 e simplificado para apenas agências.
- Pilar E sem `populacao_urbana_pct` (redundante com banda larga).
- Feature nova: `tensao_digital_bancaria` = Pix per capita / (agências por 100k + 1).

**Efeito**: cidades pequenas com muito Pix e pouca agência sobem no ranking. Ainda prevalecem SC e MT, mas já não é um ranking de riqueza pura.

### 2.3 IPB Presença Bancária Completa (V3, ex-Abordagem 2)

Redesenho mais profundo, principalmente no Pilar D:
- **Agências sozinhas não refletem mais a realidade**: o número de agências bancárias vem caindo no Brasil. O BCB registra 216 mil **correspondentes** (lotéricas, caixas eletrônicos, correspondentes bancários). O índice passa a considerar a **presença bancária completa** = agências + correspondentes.
- **Correspondentes ponderados por tipo**: postos (peso 1.0), filiais (0.7), sedes (0.4) e agências (1.0). Postos são pontos mais simples; filiais/sedes têm capacidade maior.
- **Gap bancário completo** = 1 / (agências + correspondentes ponderados por 100k + 1).
- **Penetração digital relativa** = Pix per capita / PIB per capita. Premia cidades que transacionam muito proporcionalmente à sua riqueza.
- **Flag de turismo suave**: score contínuo baseado em Pix alto + PIB baixo + cidade pequena. Aplica desconto máximo de 15% no pilar digital para evitar que cidades turísticas (Arraial do Cabo, Búzios) disparem só por fluxo de visitantes.
- **Rankings separados por estrato**: pequena, média e grande.

**Efeito**: quebra o viés para cidades ricas já bancarizadas e passa a destacar municípios com alta demanda digital e baixa estrutura bancária física.

---

## 3. Top 10 por versão

### 3.1 IPB Clássico (V1)

| Rank | Município | UF | Estrato | IPB |
|---|---|---|---|---|
"""
    for _, r in top10_v1.iterrows():
        md += f"| {int(r['rank'])} | {r['nome_municipio']} | {r['sigla_uf']} | {r['estrato_populacional']} | {r['ipb']:.2f} |\n"

    md += """
### 3.2 IPB Recalibrado (V2)

| Rank | Município | UF | Estrato | IPB |
|---|---|---|---|---|
"""
    for _, r in top10_v2.iterrows():
        md += f"| {int(r['rank'])} | {r['nome_municipio']} | {r['sigla_uf']} | {r['estrato_populacional']} | {r['ipb']:.2f} |\n"

    md += """
### 3.3 IPB Presença Bancária Completa (V3)

| Rank | Município | UF | Estrato | IPB |
|---|---|---|---|---|
"""
    for _, r in top10_v3.iterrows():
        md += f"| {int(r['rank'])} | {r['nome_municipio']} | {r['sigla_uf']} | {r['estrato_populacional']} | {r['ipb']:.2f} |\n"

    md += """
---

## 4. Análise do Top 100

### 4.1 Movimentação geral

| Comparação | Saíram do Top 100 | Entraram no Top 100 |
|---|---|---|
"""
    md += f"| V1 -> V2 | {len(top100_v1 - top100_v2)} | {len(top100_v2 - top100_v1)} |\n"
    md += f"| V2 -> V3 | {len(top100_v2 - top100_v3)} | {len(top100_v3 - top100_v2)} |\n"
    md += f"| V1 -> V3 | {len(top100_v1 - top100_v3)} | {len(top100_v3 - top100_v1)} |\n"

    md += """
### 4.2 Cidades que saíram do Top 100 (V1 -> V3)

Cidades ricas e já bancarizadas que deixaram de figurar entre as 100 primeiras:

| Município | UF | Estrato | Rank V1 | Rank V3 |
|---|---|---|---|---|
"""
    sairam = df[df["id_municipio"].isin(top100_v1 - top100_v3)][
        ["nome_municipio", "sigla_uf", "estrato_populacional", "rank_v1", "rank_v3"]
    ].sort_values("rank_v1")
    for _, r in sairam.iterrows():
        md += f"| {r['nome_municipio']} | {r['sigla_uf']} | {r['estrato_populacional']} | {int(r['rank_v1'])} | {int(r['rank_v3'])} |\n"

    md += """
### 4.3 Cidades que entraram no Top 100 (V1 -> V3)

Cidades que subiram e passaram a figurar entre as 100 primeiras oportunidades:

| Município | UF | Estrato | Rank V1 | Rank V3 |
|---|---|---|---|---|
"""
    entraram = df[df["id_municipio"].isin(top100_v3 - top100_v1)][
        ["nome_municipio", "sigla_uf", "estrato_populacional", "rank_v1", "rank_v3"]
    ].sort_values("rank_v3")
    for _, r in entraram.iterrows():
        md += f"| {r['nome_municipio']} | {r['sigla_uf']} | {r['estrato_populacional']} | {int(r['rank_v1'])} | {int(r['rank_v3'])} |\n"

    # Top 5 por estrato - todas as versoes
    md += """
---

## 5. Top 5 por Estrato Populacional

Além do ranking geral, apresentamos os líderes de cada estrato populacional nas três versões. Isso evita que cidades pequenas e grandes concorram no mesmo critério.

"""
    for estrato in ["grande", "media", "pequena"]:
        md += f"### Estrato: {estrato.capitalize()}\n\n"
        sub = df[df["estrato_populacional"] == estrato]

        for col_rank, col_rank_estrato, col_ipb, label in [
            ("rank_v1", "rank_v1_estrato", COL_IPB_V1, "IPB Clássico (V1)"),
            ("rank_v2", "rank_v2_estrato", COL_IPB_V2, "IPB Recalibrado (V2)"),
            ("rank_v3", "rank_v3_estrato", COL_IPB_V3, "IPB Presença Bancária Completa (V3)"),
        ]:
            top5 = sub.nsmallest(5, col_rank)[[col_rank, col_rank_estrato, "nome_municipio", "sigla_uf", col_ipb]].rename(
                columns={col_rank: "rank_geral", col_rank_estrato: "rank_estrato", col_ipb: "ipb"}
            )
            md += f"#### {label}\n\n| Rank Geral | Rank no Estrato | Município | UF | IPB |\n|---|---|---|---|---|\n"
            for _, r in top5.iterrows():
                md += f"| {int(r['rank_geral'])} | {int(r['rank_estrato'])} | {r['nome_municipio']} | {r['sigla_uf']} | {r['ipb']:.2f} |\n"
            md += "\n"

    # Distribuicao regional
    md += """---

## 6. Distribuição Regional no Top 100

Quantidade de municípios por região entre os 100 primeiros de cada versão:

| Região | IPB Clássico (V1) | IPB Recalibrado (V2) | IPB Presença Bancária Completa (V3) |
|---|---|---|---|
"""
    regioes = sorted(df["nome_regiao"].dropna().unique())
    for reg in regioes:
        c_v1 = len(df[(df["nome_regiao"] == reg) & (df["rank_v1"] <= 100)])
        c_v2 = len(df[(df["nome_regiao"] == reg) & (df["rank_v2"] <= 100)])
        c_v3 = len(df[(df["nome_regiao"] == reg) & (df["rank_v3"] <= 100)])
        md += f"| {reg} | {c_v1} | {c_v2} | {c_v3} |\n"

    md += """
---

## 7. Interpretação dos Resultados

### 7.1 IPB Clássico (V1)
- Fortemente enviesado para cidades ricas e conectadas do Sudeste/Sul;
- Top 10 com Barueri, Paulínia, Ilhabela, Nova Lima;
- Pilar D redundante e com peso insuficiente para contrabalançar riqueza.

### 7.2 IPB Recalibrado (V2)
- Reduziu o peso da renda e aumentou o gap bancário;
- Cidades pequenas com alta tensão digital-bancária subiram;
- Ainda prevalecem cidades de SC e MT no topo, mas já não é um ranking de riqueza pura.

### 7.3 IPB Presença Bancária Completa (V3)
- Redesenhou o Pilar D: agências sozinhas perdem relevância, então o índice passa a considerar a presença bancária completa (agências + correspondentes por tipo);
- `penetracao_digital_relativa` premia cidades que transacionam muito Pix proporcionalmente à renda;
- Flag de turismo suave reduz o impacto de cidades pequenas com fluxo de visitantes;
- Top 100 ficou mais distribuído regionalmente e por estrato;
- Reduziu ainda mais a dominância de cidades obviamente ricas.

---

## 8. Alertas importantes para discussão do grupo

### 8.1 V3 ainda privilegia cidades pequenas com eventos especiais

O Top 10 da V3 ainda traz cidades pequenas como Engenheiro Coelho-SP, Arraial do Cabo-RJ, Armação dos Búzios-RJ e Barra dos Coqueiros-SE. Essas cidades provavelmente têm Pix alto por turismo ou por atividade econômica não residente. A flag de turismo suave mitiga, mas não elimina o efeito.

### 8.2 Distribuição regional no Top 100

A V3 concentra grande parte do Top 100 no Sudeste. Isso não é necessariamente ruim (é a região mais populosa), mas precisa ser analisado: são cidades-dormitório da metrópole? São cidades turísticas? São polos regionais reais?

### 8.3 Grandes cidades no ranking da V3

Entraram no Top 100: Rio de Janeiro, São Paulo, Brasília, Manaus, Salvador. Isso é positivo porque mostra que o índice não exclui grandes cidades automaticamente. Mas também levanta a questão: essas cidades realmente são oportunidades de expansão bancária digital ou já estão saturadas?

### 8.4 Correspondentes bancários como proxy de acesso

O BCB classifica correspondentes em sede, filial, posto e agência. A ponderação usada (posto=1.0, filial=0.7, sede=0.4, agência=1.0) é uma primeira aproximação. O grupo precisa validar se essa hierarquia faz sentido de negócio.

---

## 9. Limitações e próximos passos

### Limitações desta análise
- A cobertura 4G/5G não foi integrada nesta rodada por dificuldade de acesso a dados agregados por município. A banda larga fixa continua como proxy;
- Não houve validação externa com dados reais de expansão bancária;
- A flag de turismo é uma heurística (Pix alto + PIB baixo + cidade pequena). Sem dados de visitação, é um ajuste pragmático;
- Variáveis per capita ainda favorecem cidades pequenas com eventos especiais (turismo, comércio de fronteira).

### Próximos passos recomendados
1. Validar os Top 100 da V3 com conhecimento de negócio;
2. Publicar rankings oficiais separados por estrato populacional;
3. Coletar cobertura 4G/5G (painel STEL/Anatel) para enriquecer o Pilar C;
4. Coletar CNPJ/MEI e Caged para a Abordagem 3 (modelo residual);
5. Refinar a flag de turismo com dados reais de visitação/turismo (Embratur, MTur) se disponíveis.

---

*Documento gerado automaticamente a partir de `src/analytics/ipb.py` (orquestração: `scripts/07_publica_ipb_bigquery.py`)*
"""
    return md
