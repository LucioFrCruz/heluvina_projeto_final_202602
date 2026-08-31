"""
Comparacao de tres versoes do IPB:
  1. IPB atual (alpha original)
  2. IPB recalibrado rapido (Abordagem 1)
  3. IPB abordagem 2 (com correspondentes bancarios e features derivadas)

Tudo local, sem subir dados para o BigQuery.

Inputs:
    - data/processed/trusted_municipios_eda.parquet
    - data/raw/bcb_correspondentes/correspondentes_por_municipio.parquet

Outputs (locais):
    - data/processed/ipb_comparacao_3_abordagens.parquet
    - docs/Comparacao_Tres_Abordagens_IPB.md
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_DIR = Path("data/processed")
RAW_DIR = Path("data/raw")
DOCS_DIR = Path("docs")


def winsorize(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    return series.clip(lower=series.quantile(lower), upper=series.quantile(upper))


def normalize(series: pd.Series) -> pd.Series:
    min_val, max_val = series.min(), series.max()
    if max_val == min_val:
        return pd.Series(0.0, index=series.index)
    return (series - min_val) / (max_val - min_val)


def compute_ipb_atual(df: pd.DataFrame) -> pd.DataFrame:
    """Replica o IPB alpha atual."""
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

    df["A_atual"] = df[[f"{c}_norm" for c in vars_a]].mean(axis=1)
    df["B_atual"] = df[[f"{c}_norm" for c in vars_b]].mean(axis=1)
    df["C_atual"] = df[[f"{c}_norm" for c in vars_c]].mean(axis=1)
    df["D_atual"] = df[[f"{c}_norm" for c in vars_d]].mean(axis=1)
    df["E_atual"] = df[[f"{c}_norm" for c in vars_e]].mean(axis=1)

    df["ipb_atual"] = (
        df["A_atual"] * df["B_atual"] * df["C_atual"] * df["D_atual"] * df["E_atual"]
    ) ** (1 / 5) * 100

    df["rank_atual"] = df["ipb_atual"].rank(ascending=False, method="min").astype(int)
    return df


def compute_ipb_recalibrado_rapido(df: pd.DataFrame) -> pd.DataFrame:
    """Abordagem 1: pesos, reducao de redundancia, tensao digital-bancaria."""
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

    df["A_rec"] = df[[f"{c}_norm" for c in vars_a]].mean(axis=1)
    df["B_rec"] = df[[f"{c}_norm" for c in vars_b]].mean(axis=1)
    df["C_rec"] = df[[f"{c}_norm" for c in vars_c]].mean(axis=1)
    df["D_rec"] = df[[f"{c}_norm" for c in vars_d]].mean(axis=1)
    df["E_rec"] = df[[f"{c}_norm" for c in vars_e]].mean(axis=1)

    w_a, w_b, w_c, w_d, w_e = 0.5, 0.75, 0.75, 1.5, 1.0
    soma = w_a + w_b + w_c + w_d + w_e

    df["ipb_recalibrado"] = (
        (df["A_rec"] ** w_a)
        * (df["B_rec"] ** w_b)
        * (df["C_rec"] ** w_c)
        * (df["D_rec"] ** w_d)
        * (df["E_rec"] ** w_e)
    ) ** (1 / soma) * 100

    df["rank_recalibrado"] = (
        df["ipb_recalibrado"].rank(ascending=False, method="min").astype(int)
    )
    return df


def compute_ipb_abordagem_2(df: pd.DataFrame) -> pd.DataFrame:
    """
    Abordagem 2 refinada: inclui correspondentes bancarios por tipo,
    penalidade suave para cidades turisticas e rankings separados por estrato.

    A cobertura 4G/5G nao foi integrada nesta rodada por dificuldade de
    acesso aos dados agregados por municipio; mantemos banda larga fixa
    como proxy de infraestrutura digital.
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

    df["A_a2"] = df[[f"{c}_norm" for c in vars_a]].mean(axis=1)
    df["B_a2"] = df[[f"{c}_norm" for c in vars_b]].mean(axis=1)
    df["C_a2"] = df[[f"{c}_norm" for c in vars_c]].mean(axis=1)
    df["D_a2"] = df[[f"{c}_norm" for c in vars_d]].mean(axis=1)
    df["E_a2"] = df[[f"{c}_norm" for c in vars_e]].mean(axis=1)

    # Desconto suave de turismo no pilar B (maximo 15%)
    df["B_a2"] = df["B_a2"] * (1 - 0.15 * df["score_turismo"])

    w_a, w_b, w_c, w_d, w_e = 0.75, 1.0, 0.75, 1.5, 1.0
    soma = w_a + w_b + w_c + w_d + w_e

    df["ipb_abordagem_2"] = (
        (df["A_a2"] ** w_a)
        * (df["B_a2"] ** w_b)
        * (df["C_a2"] ** w_c)
        * (df["D_a2"] ** w_d)
        * (df["E_a2"] ** w_e)
    ) ** (1 / soma) * 100

    df["rank_abordagem_2"] = (
        df["ipb_abordagem_2"].rank(ascending=False, method="min").astype(int)
    )

    # Rankings separados por estrato populacional
    for estrato in df["estrato_populacional"].dropna().unique():
        mask = df["estrato_populacional"] == estrato
        df.loc[mask, f"rank_abordagem_2_{estrato}"] = (
            df.loc[mask, "ipb_abordagem_2"]
            .rank(ascending=False, method="min")
            .astype(int)
        )

    return df


def build_document(df: pd.DataFrame) -> str:
    """Gera documento Markdown comparando as tres abordagens."""

    stats = {
        "atual": {
            "media": round(df["ipb_atual"].mean(), 2),
            "mediana": round(df["ipb_atual"].median(), 2),
            "max": round(df["ipb_atual"].max(), 2),
            "min": round(df["ipb_atual"].min(), 2),
        },
        "recalibrado": {
            "media": round(df["ipb_recalibrado"].mean(), 2),
            "mediana": round(df["ipb_recalibrado"].median(), 2),
            "max": round(df["ipb_recalibrado"].max(), 2),
            "min": round(df["ipb_recalibrado"].min(), 2),
        },
        "abordagem_2": {
            "media": round(df["ipb_abordagem_2"].mean(), 2),
            "mediana": round(df["ipb_abordagem_2"].median(), 2),
            "max": round(df["ipb_abordagem_2"].max(), 2),
            "min": round(df["ipb_abordagem_2"].min(), 2),
        },
    }

    top10_atual = df.nsmallest(10, "rank_atual")[
        ["rank_atual", "nome_municipio", "sigla_uf", "estrato_populacional", "ipb_atual"]
    ].rename(columns={"rank_atual": "rank", "ipb_atual": "ipb"})

    top10_rec = df.nsmallest(10, "rank_recalibrado")[
        ["rank_recalibrado", "nome_municipio", "sigla_uf", "estrato_populacional", "ipb_recalibrado"]
    ].rename(columns={"rank_recalibrado": "rank", "ipb_recalibrado": "ipb"})

    top10_a2 = df.nsmallest(10, "rank_abordagem_2")[
        ["rank_abordagem_2", "nome_municipio", "sigla_uf", "estrato_populacional", "ipb_abordagem_2"]
    ].rename(columns={"rank_abordagem_2": "rank", "ipb_abordagem_2": "ipb"})

    # Movimentacao no Top 100
    top100_atual = set(df.nsmallest(100, "rank_atual")["id_municipio"])
    top100_rec = set(df.nsmallest(100, "rank_recalibrado")["id_municipio"])
    top100_a2 = set(df.nsmallest(100, "rank_abordagem_2")["id_municipio"])

    def format_mun(row):
        return f"{row['nome_municipio']}-{row['sigla_uf']}"

    md = f"""# Comparacao de Tres Abordagens do IPB

> **Objetivo**: comparar o IPB atual, o IPB recalibrado rapido e o IPB com a Abordagem 2 (correspondentes bancarios por tipo + ajuste suave para turismo + segmentacao por estrato).  
> **Escopo**: analise local, sem alterar dados no BigQuery.  
> **Data**: 2026-08-31  
> **Branch**: `feature/etapa2-eda-e-limpeza`

---

## 1. Resumo Executivo

Tres versoes do indice foram calculadas a partir da mesma base `trusted_municipios` (com o bug do Pix corrigido):

| Versao | Conceito |
|---|---|
| **IPB Atual** | Formula original: 5 pilares com pesos iguais. Premia cidades ricas, conectadas e com demanda digital, mas pune pouco cidades ja bancarizadas (Pilar D usa 3 variaveis redundantes). |
| **IPB Recalibrado (Rapido)** | Ajuste rapido anti-vies: pesos diferenciados, Pilar D reduzido a apenas `agencias_por_100k_hab`, Pilar E sem `populacao_urbana_pct` e inclusao de `tensao_digital_bancaria` (Pix / agencias). Diminui a influencia da renda pura. |
| **IPB Abordagem 2** | Redesenho do Pilar D: agencias bancarias estao em queda, entao o indice passa a considerar **correspondentes bancarios do BCB por tipo** (posto, filial, sede, agencia) com pesos diferentes. Adiciona `penetracao_digital_relativa` (Pix / PIB) e `gap_bancario_completo`. Inclui ainda uma **flag de turismo suave** (score continuo, desconto maximo de 15% no pilar digital) para nao privilegiar cidades pequenas com fluxo turistico. |

### Estatisticas gerais

| Metrica | IPB Atual | IPB Recalibrado | IPB Abordagem 2 |
|---|---|---|---|
| Media | {stats['atual']['media']} | {stats['recalibrado']['media']} | {stats['abordagem_2']['media']} |
| Mediana | {stats['atual']['mediana']} | {stats['recalibrado']['mediana']} | {stats['abordagem_2']['mediana']} |
| Maximo | {stats['atual']['max']} | {stats['recalibrado']['max']} | {stats['abordagem_2']['max']} |
| Minimo | {stats['atual']['min']} | {stats['recalibrado']['min']} | {stats['abordagem_2']['min']} |

---

## 2. Como cada versao funciona

### 2.1 IPB Atual

Cinco pilares com **pesos iguais** (media geometrica):
- **A. Capacidade de consumo**: PIB per capita + rendimento domiciliar per capita.
- **B. Dinamismo economico**: Pix per capita ultimos 12 meses.
- **C. Adocao digital**: banda larga fixa por 100 habitantes.
- **D. Gap bancario**: agencias, depositos e credito per capita (todas invertidas).
- **E. Perfil demografico**: escolaridade, populacao 18-35 anos e populacao urbana.

**Problema**: cidades ricas ja bancarizadas (Barueri, Itapema, Balneario Camboriu) lideram porque a renda e o digital pesam muito, enquanto o gap bancario e fraco.

### 2.2 IPB Recalibrado (Rapido)

Mesma estrutura de 5 pilares, mas com **pesos diferenciados**:
- Pilar A (renda) reduzido para 0.5.
- Pilares B (digital) e C (infra) com 0.75 cada.
- Pilar D (gap bancario) ampliado para 1.5 e simplificado para apenas agencias.
- Pilar E sem `populacao_urbana_pct` (redundante com banda larga).
- Feature nova: `tensao_digital_bancaria` = Pix per capita / (agencias por 100k + 1).

**Efeito**: cidades pequenas com muito Pix e pouca agencia sobem no ranking. Ainda prevalecem SC e MT, mas ja nao e um ranking de riqueza pura.

### 2.3 IPB Abordagem 2

Redesenho mais profundo, principalmente no Pilar D:
- **Agencias sozinhas nao refletem mais a realidade**: o numero de agencias bancarias vem caindo no Brasil. O BCB registra 216 mil **correspondentes** (lotericas, caixas eletronicos, correspondentes bancarios). O indice passa a considerar a **presenca bancaria completa** = agencias + correspondentes.
- **Correspondentes ponderados por tipo**: postos (peso 1.0), filiais (0.7), sedes (0.4) e agencias (1.0). Postos sao pontos mais simples; filiais/sedes tem capacidade maior.
- **Gap bancario completo** = 1 / (agencias + correspondentes ponderados por 100k + 1).
- **Penetracao digital relativa** = Pix per capita / PIB per capita. Premia cidades que transacionam muito proporcionalmente a sua riqueza.
- **Flag de turismo suave**: score continuo baseado em Pix alto + PIB baixo + cidade pequena. Aplica desconto maximo de 15% no pilar digital para evitar que cidades turisticas (Arraial do Cabo, Buzios) disparem so por fluxo de visitantes.
- **Rankings separados por estrato**: pequena, media e grande.

**Efeito**: quebra o vies para cidades ricas ja bancarizadas e passa a destacar municipios com alta demanda digital e baixa estrutura bancaria fisica.

---

## 3. Top 10 por versao

### 3.1 IPB Atual

| Rank | Municipio | UF | Estrato | IPB |
|---|---|---|---|---|
"""
    for _, r in top10_atual.iterrows():
        md += f"| {int(r['rank'])} | {r['nome_municipio']} | {r['sigla_uf']} | {r['estrato_populacional']} | {r['ipb']:.2f} |\n"

    md += """
### 3.2 IPB Recalibrado (Rapido)

| Rank | Municipio | UF | Estrato | IPB |
|---|---|---|---|---|
"""
    for _, r in top10_rec.iterrows():
        md += f"| {int(r['rank'])} | {r['nome_municipio']} | {r['sigla_uf']} | {r['estrato_populacional']} | {r['ipb']:.2f} |\n"

    md += """
### 3.3 IPB Abordagem 2

| Rank | Municipio | UF | Estrato | IPB |
|---|---|---|---|---|
"""
    for _, r in top10_a2.iterrows():
        md += f"| {int(r['rank'])} | {r['nome_municipio']} | {r['sigla_uf']} | {r['estrato_populacional']} | {r['ipb']:.2f} |\n"

    md += """
---

## 4. Analise do Top 100

### 4.1 Movimentacao geral

| Comparacao | Sairam do Top 100 | Entraram no Top 100 |
|---|---|---|
"""
    md += f"| Atual -> Recalibrado | {len(top100_atual - top100_rec)} | {len(top100_rec - top100_atual)} |\n"
    md += f"| Recalibrado -> Abordagem 2 | {len(top100_rec - top100_a2)} | {len(top100_a2 - top100_rec)} |\n"
    md += f"| Atual -> Abordagem 2 | {len(top100_atual - top100_a2)} | {len(top100_a2 - top100_atual)} |\n"

    md += """
### 4.2 Cidades que sairam do Top 100 (Atual -> Abordagem 2)

Cidades ricas e ja bancarizadas que deixaram de figurar entre as 100 primeiras:

| Municipio | UF | Estrato | Rank Atual | Rank Abordagem 2 |
|---|---|---|---|---|
"""
    sairam = df[df["id_municipio"].isin(top100_atual - top100_a2)][
        ["nome_municipio", "sigla_uf", "estrato_populacional", "rank_atual", "rank_abordagem_2"]
    ].sort_values("rank_atual")
    for _, r in sairam.iterrows():
        md += f"| {r['nome_municipio']} | {r['sigla_uf']} | {r['estrato_populacional']} | {int(r['rank_atual'])} | {int(r['rank_abordagem_2'])} |\n"

    md += """
### 4.3 Cidades que entraram no Top 100 (Atual -> Abordagem 2)

Cidades que subiram e passaram a figurar entre as 100 primeiras oportunidades:

| Municipio | UF | Estrato | Rank Atual | Rank Abordagem 2 |
|---|---|---|---|---|
"""
    entraram = df[df["id_municipio"].isin(top100_a2 - top100_atual)][
        ["nome_municipio", "sigla_uf", "estrato_populacional", "rank_atual", "rank_abordagem_2"]
    ].sort_values("rank_abordagem_2")
    for _, r in entraram.iterrows():
        md += f"| {r['nome_municipio']} | {r['sigla_uf']} | {r['estrato_populacional']} | {int(r['rank_atual'])} | {int(r['rank_abordagem_2'])} |\n"

    # Top 5 por estrato - todas as versoes
    md += """
---

## 5. Top 5 por Estrato Populacional

Alem do ranking geral, apresentamos os lideres de cada estrato populacional nas tres versoes. Isso evita que cidades pequenas e grandes concorram no mesmo criterio.

"""
    for estrato in ["grande", "media", "pequena"]:
        md += f"### Estrato: {estrato.capitalize()}\n\n"
        sub = df[df["estrato_populacional"] == estrato]

        for col_rank, col_rank_estrato, col_ipb, label in [
            ("rank_atual", f"rank_atual_{estrato}", "ipb_atual", "IPB Atual"),
            ("rank_recalibrado", f"rank_recalibrado_{estrato}", "ipb_recalibrado", "IPB Recalibrado"),
            ("rank_abordagem_2", f"rank_abordagem_2_{estrato}", "ipb_abordagem_2", "IPB Abordagem 2"),
        ]:
            top5 = sub.nsmallest(5, col_rank)[[col_rank, col_rank_estrato, "nome_municipio", "sigla_uf", col_ipb]].rename(
                columns={col_rank: "rank_geral", col_rank_estrato: "rank_estrato", col_ipb: "ipb"}
            )
            md += f"#### {label}\n\n| Rank Geral | Rank no Estrato | Municipio | UF | IPB |\n|---|---|---|---|---|---|\n"
            for _, r in top5.iterrows():
                md += f"| {int(r['rank_geral'])} | {int(r['rank_estrato'])} | {r['nome_municipio']} | {r['sigla_uf']} | {r['ipb']:.2f} |\n"
            md += "\n"

    # Distribuicao regional
    md += """---

## 6. Distribuicao Regional no Top 100

Quantidade de municipios por regiao entre os 100 primeiros de cada versao:

| Regiao | IPB Atual | IPB Recalibrado | IPB Abordagem 2 |
|---|---|---|---|
"""
    regioes = sorted(df["nome_regiao"].dropna().unique())
    for reg in regioes:
        c_atual = len(df[(df["nome_regiao"] == reg) & (df["rank_atual"] <= 100)])
        c_rec = len(df[(df["nome_regiao"] == reg) & (df["rank_recalibrado"] <= 100)])
        c_a2 = len(df[(df["nome_regiao"] == reg) & (df["rank_abordagem_2"] <= 100)])
        md += f"| {reg} | {c_atual} | {c_rec} | {c_a2} |\n"

    md += """
---

## 7. Interpretacao dos Resultados

### 7.1 IPB Atual
- Fortemente enviesado para cidades ricas e conectadas do Sudeste/Sul;
- Top 10 com Barueri, Paulínia, Ilhabela, Nova Lima;
- Pilar D redundante e com peso insuficiente para contrabalançar riqueza.

### 7.2 IPB Recalibrado (Rapido)
- Reduziu o peso da renda e aumentou o gap bancario;
- Cidades pequenas com alta tensao digital-bancaria subiram;
- Ainda prevalecem cidades de SC e MT no topo, mas ja nao e um ranking de riqueza pura.

### 7.3 IPB Abordagem 2
- Redesenhou o Pilar D: agencias sozinhas perdem relevancia, entao o indice passa a considerar a presenca bancaria completa (agencias + correspondentes por tipo);
- `penetracao_digital_relativa` premia cidades que transacionam muito Pix proporcionalmente a renda;
- Flag de turismo suave reduz o impacto de cidades pequenas com fluxo de visitantes;
- Top 100 ficou mais distribuido regionalmente e por estrato;
- Reduziu ainda mais a dominancia de cidades obviamente ricas.

---

## 7. Alertas importantes para discussao do grupo

### 7.1 Abordagem 2 ainda privilegia cidades pequenas com eventos especiais

O Top 10 da Abordagem 2 ainda traz cidades pequenas como Engenheiro Coelho-SP, Arraial do Cabo-RJ, Armacao dos Buzios-RJ e Barra dos Coqueiros-SE. Essas cidades provavelmente tem Pix alto por turismo ou por atividade econômica nao residente. A flag de turismo suave mitiga, mas nao elimina o efeito.

### 7.2 Distribuicao regional no Top 100

A Abordagem 2 concentra grande parte do Top 100 no Sudeste. Isso nao e necessariamente ruim (e a regiao mais populosa), mas precisa ser analisado: sao cidades-dormitorio da metropole? Sao cidades turisticas? Sao polos regionais reais?

### 7.3 Grandes cidades no ranking da Abordagem 2

Entraram no Top 100: Rio de Janeiro, Sao Paulo, Brasilia, Manaus, Salvador. Isso e positivo porque mostra que o indice nao exclui grandes cidades automaticamente. Mas tambem levanta a questao: essas cidades realmente sao oportunidades de expansao bancaria digital ou ja estao saturadas?

### 7.4 Correspondentes bancarios como proxy de acesso

O BCB classifica correspondentes em sede, filial, posto e agencia. A ponderacao usada (posto=1.0, filial=0.7, sede=0.4, agencia=1.0) e uma primeira aproximacao. O grupo precisa validar se essa hierarquia faz sentido de negocio.

---

## 8. Limitacoes e proximos passos

### Limitacoes desta analise
- A cobertura 4G/5G nao foi integrada nesta rodada por dificuldade de acesso a dados agregados por municipio. A banda larga fixa continua como proxy;
- Nao houve validacao externa com dados reais de expansao bancaria;
- A flag de turismo e uma heuristica (Pix alto + PIB baixo + cidade pequena). Sem dados de visitacao, e um ajuste pragmatico;
- Variaveis per capita ainda favorecem cidades pequenas com eventos especiais (turismo, comercio de fronteira).

### Proximos passos recomendados
1. Validar os Top 100 da Abordagem 2 com conhecimento de negocio;
2. Publicar rankings oficiais separados por estrato populacional;
3. Coletar cobertura 4G/5G (painel STEL/Anatel) para enriquecer o Pilar C;
4. Coletar CNPJ/MEI e Caged para a Abordagem 3 (modelo residual);
5. Refinar a flag de turismo com dados reais de visitacao/turismo (Embratur, MTur) se disponiveis.

---

*Documento gerado automaticamente por scripts/06_comparacao_tres_abordagens_ipb.py*
"""
    return md


def main() -> None:
    logger.info("Carregando base enriquecida...")
    df = pd.read_parquet(PROCESSED_DIR / "trusted_municipios_eda.parquet")

    logger.info("Carregando correspondentes bancarios por tipo...")
    corr_raw = pd.read_parquet(
        RAW_DIR / "bcb_correspondentes" / "bcb_correspondentes.parquet"
    )
    corr_raw = corr_raw.rename(columns={"MunicipioIBGE": "id_municipio"})

    # Agrega correspondentes por tipo
    corr_por_tipo = (
        corr_raw.groupby(["id_municipio", "Tipo"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    for tipo in ["Posto", "Filial", "Sede", "Agência"]:
        if tipo not in corr_por_tipo.columns:
            corr_por_tipo[tipo] = 0

    corr_total = corr_por_tipo.copy()
    corr_total["quantidade_correspondentes"] = (
        corr_total["Posto"] + corr_total["Filial"] + corr_total["Sede"] + corr_total["Agência"]
    )

    # Junta no dataframe principal
    df = df.merge(corr_total, on="id_municipio", how="left")
    df["quantidade_correspondentes"] = df["quantidade_correspondentes"].fillna(0).astype(int)
    df["quantidade_correspondentes_posto"] = df["Posto"].fillna(0).astype(int)
    df["quantidade_correspondentes_filial"] = df["Filial"].fillna(0).astype(int)
    df["quantidade_correspondentes_sede"] = df["Sede"].fillna(0).astype(int)
    df["quantidade_correspondentes_agencia"] = df["Agência"].fillna(0).astype(int)
    df["correspondentes_por_100k_hab"] = (
        df["quantidade_correspondentes"] / df["populacao_total"]
    ) * 100_000

    logger.info("Calculando IPB atual...")
    df = compute_ipb_atual(df)

    logger.info("Calculando IPB recalibrado rapido...")
    df = compute_ipb_recalibrado_rapido(df)

    logger.info("Calculando IPB abordagem 2...")
    df = compute_ipb_abordagem_2(df)

    # Rankings separados por estrato para todas as versoes
    logger.info("Calculando rankings por estrato...")
    for estrato in df["estrato_populacional"].dropna().unique():
        mask = df["estrato_populacional"] == estrato
        df.loc[mask, f"rank_atual_{estrato}"] = (
            df.loc[mask, "ipb_atual"].rank(ascending=False, method="min").astype(int)
        )
        df.loc[mask, f"rank_recalibrado_{estrato}"] = (
            df.loc[mask, "ipb_recalibrado"].rank(ascending=False, method="min").astype(int)
        )

    logger.info("Salvando resultados...")
    df.to_parquet(PROCESSED_DIR / "ipb_comparacao_3_abordagens.parquet", index=False)

    logger.info("Gerando documento comparativo...")
    doc = build_document(df)
    doc_path = DOCS_DIR / "Comparacao_Tres_Abordagens_IPB.md"
    doc_path.write_text(doc, encoding="utf-8")
    logger.info("Documento salvo em: %s", doc_path)

    # Print resumo no terminal
    print("\n" + "=" * 70)
    print("COMPARACAO DAS TRES ABORDAGENS CONCLUIDA")
    print("=" * 70)
    print(f"\nTop 5 IPB Atual:")
    for _, r in df.nsmallest(5, "rank_atual").iterrows():
        print(f"  {r['rank_atual']:.0f}. {r['nome_municipio']}-{r['sigla_uf']} -> {r['ipb_atual']:.2f}")
    print(f"\nTop 5 IPB Recalibrado:")
    for _, r in df.nsmallest(5, "rank_recalibrado").iterrows():
        print(f"  {r['rank_recalibrado']:.0f}. {r['nome_municipio']}-{r['sigla_uf']} -> {r['ipb_recalibrado']:.2f}")
    print(f"\nTop 5 IPB Abordagem 2:")
    for _, r in df.nsmallest(5, "rank_abordagem_2").iterrows():
        print(f"  {r['rank_abordagem_2']:.0f}. {r['nome_municipio']}-{r['sigla_uf']} -> {r['ipb_abordagem_2']:.2f}")

    top100_atual = set(df.nsmallest(100, "rank_atual")["id_municipio"])
    top100_a2 = set(df.nsmallest(100, "rank_abordagem_2")["id_municipio"])
    print(f"\nMunicipios que sairam do Top 100 (Atual -> A2): {len(top100_atual - top100_a2)}")
    print(f"Municipios que entraram no Top 100 (Atual -> A2): {len(top100_a2 - top100_atual)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
