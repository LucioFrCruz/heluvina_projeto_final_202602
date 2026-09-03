# Plano de Implementação Técnico — EDA do IPB

> **Propósito**: documento executável para implementação da Etapa 2 (Análise Exploratória de Dados) do Índice de Potencial Bancário (IPB).
>
> **Público-alvo**: agentes de IA e desenvolvedores que vão criar os notebooks.
>
> **Pré-requisito**: a Etapa 1 está concluída e as tabelas `trusted_municipios` e `raw_*` existem no BigQuery.
>
> **Leitura complementar**: [`Guia_de_Analise_Exploratoria.md`](Guia_de_Analise_Exploratoria.md) (visão de negócio e justificativas).

---

## 1. Visão geral técnica

### 1.1 Entregáveis

1. Seis notebooks `.ipynb` em `notebooks/00_exploracao/`.
2. Módulo utilitário `src/utils/eda.py` com funções reutilizáveis.
3. Base enriquecida local: `data/processed/trusted_municipios_eda.parquet`.
4. Relatório de Data Quality: `data/processed/reports/data_quality_report.json`.
5. Figuras exportadas em `data/processed/figures/`.
6. Cálculo alpha do IPB: `data/processed/ipb_alpha.parquet`.

### 1.2 Stack tecnológica

Todas as bibliotecas já devem estar disponíveis no ambiente Poetry do projeto. Se faltar alguma, adicionar via `poetry add`.

| Biblioteca | Uso | Versão mínima |
|------------|-----|---------------|
| `pandas` | Manipulação de dados | `^2.2.0` |
| `numpy` | Cálculos numéricos | >= 1.23 |
| `matplotlib` | Gráficos estáticos | >= 3.7 |
| `seaborn` | Gráficos estatísticos | >= 0.12 |
| `plotly` | Mapas e gráficos interativos (opcional) | >= 5.18 |
| `scipy` | Estatísticas e testes | >= 1.10 |
| `scikit-learn` | Normalização, PCA, K-Means (opcional) | >= 1.3 |
| `google-cloud-bigquery` | Leitura do BigQuery | `^3.18.0` |
| `pyarrow` | Parquet | `^15.0.0` |

Verificar instalação:

```bash
poetry run python -c "import pandas, numpy, matplotlib, seaborn, scipy, sklearn, plotly; print('OK')"
```

Se `plotly` ou `scikit-learn` faltarem:

```bash
poetry add plotly scikit-learn
```

### 1.3 Padrão de execução

- Todos os notebooks rodam dentro do ambiente Poetry.
- Nunca usar `print`; usar `logging` com nível `INFO`.
- Todo notebook deve ser reprodutível: re-executar do início ao fim deve produzir os mesmos outputs.
- Saídas (Parquet, PNG, JSON) ficam em `data/processed/`; nada é gravado no BigQuery sem autorização explícita.

---

## 2. Módulo utilitário `src/utils/eda.py`

Criar este módulo antes dos notebooks. Ele centraliza funções reutilizáveis de EDA.

### 2.1 Funções obrigatórias

```python
# src/utils/eda.py
from pathlib import Path
from typing import Optional
import json
import logging

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from src.config import PROCESSED_DATA_DIR

logger = logging.getLogger(__name__)

FIGURES_DIR = PROCESSED_DATA_DIR / "figures"
REPORTS_DIR = PROCESSED_DATA_DIR / "reports"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def save_figure(fig: plt.Figure, filename: str, dpi: int = 150) -> Path:
    """Salva figura em data/processed/figures/ e retorna o caminho."""
    path = FIGURES_DIR / filename
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    logger.info("Figura salva em %s", path)
    return path


def save_parquet(df: pd.DataFrame, filename: str) -> Path:
    """Salva DataFrame em data/processed/ como Parquet."""
    path = PROCESSED_DATA_DIR / filename
    df.to_parquet(path, index=False)
    logger.info("Parquet salvo em %s", path)
    return path


def save_json(data: dict, filename: str) -> Path:
    """Salva dicionário em data/processed/reports/ como JSON."""
    path = REPORTS_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    logger.info("JSON salvo em %s", path)
    return path


def compute_null_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Retorna DataFrame com coluna, tipo, nulos absolutos e percentual."""
    profile = pd.DataFrame({
        "coluna": df.columns,
        "tipo": df.dtypes.values,
        "nulos": df.isnull().sum().values,
        "pct_nulos": (df.isnull().mean() * 100).round(2).values,
    })
    return profile.sort_values("pct_nulos", ascending=False)


def compute_descriptive_stats(df: pd.DataFrame, numeric_only: bool = True) -> pd.DataFrame:
    """Retorna estatísticas descritivas estendidas."""
    cols = df.select_dtypes(include=[np.number]).columns if numeric_only else df.columns
    desc = df[cols].describe(percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]).T
    desc["skewness"] = df[cols].skew()
    desc["kurtosis"] = df[cols].kurtosis()
    desc["iqr"] = desc["75%"] - desc["25%"]
    desc["missing_pct"] = (df[cols].isnull().mean() * 100).round(2)
    return desc


def detect_outliers_iqr(df: pd.DataFrame, column: str, k: float = 1.5) -> pd.DataFrame:
    """Retorna linhas consideradas outliers pela regra do IQR."""
    q1 = df[column].quantile(0.25)
    q3 = df[column].quantile(0.75)
    iqr = q3 - q1
    lower = q1 - k * iqr
    upper = q3 + k * iqr
    return df[(df[column] < lower) | (df[column] > upper)].copy()


def winsorize_series(s: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    """Aplica winsorização nos percentis informados."""
    low = s.quantile(lower)
    up = s.quantile(upper)
    return s.clip(lower=low, upper=up)


def min_max_normalize(s: pd.Series) -> pd.Series:
    """Normaliza série em [0, 1]."""
    min_val = s.min()
    max_val = s.max()
    if max_val == min_val:
        return pd.Series(0.0, index=s.index)
    return (s - min_val) / (max_val - min_val)


def plot_distribution(
    df: pd.DataFrame,
    column: str,
    title: Optional[str] = None,
    xlabel: Optional[str] = None,
    log_scale: bool = False,
    filename: Optional[str] = None,
) -> plt.Figure:
    """Gera histograma com KDE para uma variável numérica."""
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
    title: Optional[str] = None,
    filename: Optional[str] = None,
) -> plt.Figure:
    """Gera boxplot de uma variável por grupo."""
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.boxplot(data=df, x=group, y=column, ax=ax, order=sorted(df[group].unique()))
    ax.set_title(title or f"{column} por {group}")
    ax.tick_params(axis="x", rotation=45)
    if filename:
        save_figure(fig, filename)
    return fig


def plot_correlation_heatmap(
    df: pd.DataFrame,
    columns: list[str],
    method: str = "spearman",
    title: Optional[str] = None,
    filename: Optional[str] = None,
) -> plt.Figure:
    """Gera heatmap de correlação."""
    corr = df[columns].corr(method=method)
    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0, ax=ax, square=True)
    ax.set_title(title or f"Matriz de Correlação ({method})")
    if filename:
        save_figure(fig, filename)
    return fig
```

### 2.2 Teste unitário obrigatório

Criar `tests/unit/test_eda_utils.py` com testes para `compute_null_profile`, `winsorize_series` e `min_max_normalize`.

---

## 3. Template padrão de notebook

Todo notebook deve seguir esta estrutura de células:

```markdown
# 00 — Setup e Qualidade de Dados

**Objetivo**: [descrever em uma frase]

**Inputs**: [tabelas ou arquivos]

**Outputs**: [arquivos gerados]
```

```python
# Célula 1: imports
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from src.utils.bigquery import read_table_to_dataframe, get_bigquery_client
from src.utils.eda import (
    save_figure,
    save_parquet,
    save_json,
    compute_null_profile,
    compute_descriptive_stats,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

sns.set_theme(style="whitegrid")
plt.rcParams["figure.figsize"] = (10, 6)
plt.rcParams["figure.dpi"] = 100
```

```python
# Célula 2: constantes
OUTPUT_PARQUET = "trusted_municipios_eda.parquet"
```

```python
# Célula 3: leitura dos dados
df = read_table_to_dataframe("trusted_municipios")
logger.info("Linhas: %d, Colunas: %d", df.shape[0], df.shape[1])
```

```python
# Célula 4+: análises e visualizações
```

```python
# Célula final: salvamento
save_parquet(df, OUTPUT_PARQUET)
```

---

## 4. Notebooks — especificação técnica

### 4.1 Notebook 00 — Setup e Qualidade de Dados

**Arquivo**: `notebooks/00_exploracao/00_setup_e_qualidade.ipynb`

**Objetivo**: carregar `trusted_municipios`, validar estrutura e gerar relatório de Data Quality.

**Inputs**: `trusted_municipios`

**Outputs**:
- `data/processed/reports/data_quality_report.json`
- `data/processed/figures/00_missing_values_heatmap.png`
- `data/processed/figures/00_municipios_por_uf.png`
- `data/processed/figures/00_populacao_total_distribuicao.png`

#### Células técnicas

**Célula A — Volumetria e integridade**

```python
assert df.shape[0] == 5570, f"Esperado 5570 municípios, obtido {df.shape[0]}"
assert df["id_municipio"].nunique() == df.shape[0], "id_municipio duplicado"
assert df["id_municipio"].isnull().sum() == 0, "id_municipio nulo"

logger.info("Volumetria OK: %d municípios", df.shape[0])
```

**Célula B — Perfil de nulos**

```python
null_profile = compute_null_profile(df)
display(null_profile)

fig, ax = plt.subplots(figsize=(12, 8))
sns.heatmap(df.isnull(), cbar=True, yticklabels=False, cmap="viridis", ax=ax)
ax.set_title("Mapa de Missing Values")
save_figure(fig, "00_missing_values_heatmap.png")
```

**Célula C — Estatísticas descritivas**

```python
desc = compute_descriptive_stats(df)
display(desc)
```

**Célula D — Validação de regras de negócio**

```python
rules = {
    "populacao_total_positiva": (df["populacao_total"] > 0).all(),
    "pib_per_capita_positivo": (df["pib_per_capita"] > 0).all(),
    "percentuais_entre_0_100": (
        df[["populacao_18_35_pct", "populacao_urbana_pct", "escolaridade_ensino_medio_pct"]]
        .apply(lambda s: s.between(0, 100).all())
        .all()
    ),
    "agencias_nao_negativas": (df["quantidade_agencias"].fillna(0) >= 0).all(),
}

for rule, ok in rules.items():
    logger.info("%s: %s", rule, "PASS" if ok else "FAIL")

assert all(rules.values()), "Regra de negócio falhou"
```

**Célula E — Diagnóstico de nulos conhecidos**

```python
gaps = {
    "domicilios_com_internet_pct_nulos_pct": float(df["domicilios_com_internet_pct"].isnull().mean() * 100),
    "estban_nulos_pct": float(df["quantidade_agencias"].isnull().mean() * 100),
    "idhm_vintage": "2010",
}
logger.info("Gaps conhecidos: %s", gaps)
```

**Célula F — Salvamento do relatório**

```python
report = {
    "volumetria": df.shape[0],
    "colunas": df.shape[1],
    "nulos_por_coluna": null_profile.set_index("coluna").to_dict(),
    "regras_negocio": rules,
    "gaps_conhecidos": gaps,
}
save_json(report, "data_quality_report.json")
```

#### Critérios de aceitação

- [ ] Notebook executa sem erros do início ao fim.
- [ ] `data_quality_report.json` é gerado.
- [ ] Confirmação de 5.570 municípios e `id_municipio` único.
- [ ] Regras de negócio passam.

---

### 4.2 Notebook 00b — Auditoria das Raws e Engenharia de Features

**Arquivo**: `notebooks/00_exploracao/00b_auditoria_raws_e_features.ipynb`

**Objetivo**: explorar as `raw_*` para validar a `trusted_municipios` e gerar `trusted_municipios_eda.parquet` com features derivadas.

**Inputs**: `trusted_municipios`, `raw_bcb_pix_transacoes`, `raw_bcb_estban`, `raw_anatel_banda_larga_fixa`

**Outputs**:
- `data/processed/trusted_municipios_eda.parquet`
- `data/processed/reports/features_engineering_report.json`

#### Células técnicas

**Célula A — Leitura das raws**

```python
df_raw_pix = read_table_to_dataframe("raw_bcb_pix_transacoes")
df_raw_estban = read_table_to_dataframe("raw_bcb_estban")
df_raw_anatel = read_table_to_dataframe("raw_anatel_banda_larga_fixa")
```

**Célula B — Auditoria Pix**

```python
df_pix_audit = (
    df_raw_pix.groupby("id_municipio")
    .agg(
        pix_total_volume_12m_raw=("valor_pf", "sum"),
        pix_total_transacoes_12m_raw=("transacoes_pf", "sum"),
    )
    .reset_index()
)

# Soma PF + PJ se as colunas existirem
if "valor_pj" in df_raw_pix.columns:
    df_pix_audit["pix_total_volume_12m_raw"] += df_raw_pix.groupby("id_municipio")["valor_pj"].sum().values
if "transacoes_pj" in df_raw_pix.columns:
    df_pix_audit["pix_total_transacoes_12m_raw"] += df_raw_pix.groupby("id_municipio")["transacoes_pj"].sum().values

# Cruzar com trusted para validar
df_check = df[["id_municipio", "pix_total_volume_12m", "pix_total_transacoes_12m"]].merge(
    df_pix_audit, on="id_municipio", how="left"
)

diff_volume = (df_check["pix_total_volume_12m"] - df_check["pix_total_volume_12m_raw"].fillna(0)).abs()
diff_trans = (df_check["pix_total_transacoes_12m"] - df_check["pix_total_transacoes_12m_raw"].fillna(0)).abs()

logger.info("Diferença máxima volume: %.2f", diff_volume.max())
logger.info("Diferença máxima transações: %.2f", diff_trans.max())
```

**Célula C — Features derivadas das raws**

```python
# Proporção PJ no volume Pix
if {"valor_pf", "valor_pj"}.issubset(df_raw_pix.columns):
    pix_pj = (
        df_raw_pix.groupby("id_municipio")
        .agg(valor_pf=("valor_pf", "sum"), valor_pj=("valor_pj", "sum"))
        .reset_index()
    )
    pix_pj["pix_pj_pct"] = pix_pj["valor_pj"] / (pix_pj["valor_pf"] + pix_pj["valor_pj"])
    df = df.merge(pix_pj[["id_municipio", "pix_pj_pct"]], on="id_municipio", how="left")

# Ticket médio Pix
df["pix_ticket_medio"] = df["pix_total_volume_12m"] / df["pix_total_transacoes_12m"].replace(0, np.nan)

# Flags e estratos
df["flag_sem_agencia"] = (df["quantidade_agencias"].fillna(0) == 0).astype(int)
df["estrato_populacional"] = pd.cut(
    df["populacao_total"],
    bins=[0, 50000, 500000, float("inf")],
    labels=["pequena", "media", "grande"],
)

# Features de eficiência bancária
df["depositos_por_agencia"] = df["volume_depositos"] / df["quantidade_agencias"].replace(0, np.nan)
df["credito_por_agencia"] = df["volume_credito"] / df["quantidade_agencias"].replace(0, np.nan)
```

**Célula D — Salvamento**

```python
save_parquet(df, "trusted_municipios_eda.parquet")

features_report = {
    "features_adicionadas": [
        "pix_pj_pct",
        "pix_ticket_medio",
        "flag_sem_agencia",
        "estrato_populacional",
        "depositos_por_agencia",
        "credito_por_agencia",
    ],
    "nulos_pix_pj_pct": float(df["pix_pj_pct"].isnull().mean() * 100),
    "municipios_sem_agencia": int(df["flag_sem_agencia"].sum()),
}
save_json(features_report, "features_engineering_report.json")
```

#### Critérios de aceitação

- [ ] Diferenças entre agregações raw e trusted são próximas de zero (tolerar arredondamento).
- [ ] `trusted_municipios_eda.parquet` é gerado com as novas colunas.
- [ ] Documentação das features aprovadas/rejeitadas no notebook.

---

### 4.3 Notebook 01 — Perfil Demográfico e Geográfico

**Arquivo**: `notebooks/00_exploracao/01_perfil_demografico_e_geo.ipynb`

**Objetivo**: analisar distribuição das variáveis demográficas e geográficas.

**Inputs**: `data/processed/trusted_municipios_eda.parquet`

**Outputs**:
- Figuras: histogramas, boxplots, mapas das variáveis demográficas.
- `data/processed/reports/perfil_demografico.json`

#### Variáveis

`populacao_total`, `populacao_18_35_pct`, `populacao_urbana_pct`, `escolaridade_ensino_medio_pct`, `idhm`

#### Células técnicas

**Célula A — Leitura local**

```python
df = pd.read_parquet(PROCESSED_DATA_DIR / "trusted_municipios_eda.parquet")
```

**Célula B — Distribuições**

```python
for col in ["populacao_total", "populacao_18_35_pct", "populacao_urbana_pct", "escolaridade_ensino_medio_pct"]:
    log_scale = col == "populacao_total"
    plot_distribution(df, col, log_scale=log_scale, filename=f"01_dist_{col}.png")
```

**Célula C — Boxplots por região**

```python
for col in ["escolaridade_ensino_medio_pct", "populacao_18_35_pct"]:
    plot_boxplot_by_group(df, col, "nome_regiao", filename=f"01_boxplot_{col}_regiao.png")
```

**Célula D — Mapa coroplético (Plotly)**

```python
import plotly.express as px

fig = px.choropleth_mapbox(
    df,
    geojson="https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson",
    locations="sigla_uf",
    color="escolaridade_ensino_medio_pct",
    color_continuous_scale="Blues",
    mapbox_style="carto-positron",
    zoom=2,
    center={"lat": -14.235, "lon": -51.925},
    opacity=0.7,
    title="Escolaridade média por UF",
)
fig.write_html(FIGURES_DIR / "01_mapa_escolaridade_uf.html")
```

> Nota: mapa municipal requer GeoJSON municipal. Se não houver, usar mapa por UF ou scatter plot geográfico.

**Célula E — Correlações demográficas**

```python
plot_correlation_heatmap(
    df,
    ["populacao_18_35_pct", "populacao_urbana_pct", "escolaridade_ensino_medio_pct", "idhm"],
    method="spearman",
    filename="01_correlacao_demografica.png",
)
```

#### Critérios de aceitação

- [ ] Todas as distribuições demográficas plotadas.
- [ ] Comparação por região gerada.
- [ ] Mapa ou visualização geográfica salva.

---

### 4.4 Notebook 02 — Capacidade de Consumo e Dinamismo

**Arquivo**: `notebooks/00_exploracao/02_economia_e_dinamismo.ipynb`

**Objetivo**: analisar renda, PIB e Pix.

**Inputs**: `data/processed/trusted_municipios_eda.parquet`, `raw_bcb_pix_transacoes`

**Outputs**: figuras e tabela de estatísticas por estrato.

#### Células técnicas

**Célula A — Distribuição de renda e PIB**

```python
for col in ["rendimento_domiciliar_per_capita", "pib_per_capita"]:
    plot_distribution(df, col, log_scale=True, filename=f"02_dist_log_{col}.png")
```

**Célula B — Quadrantes Pix × renda (alta adoção Pix)** *(atualizado em 2026-09: o scatter Pix×PIB planejado aqui foi descartado na revisão da EDA — não continha informação. Foi substituído pelo quadrante Pix per capita × rendimento domiciliar per capita com destaque dos municípios de alta adoção Pix, figura `02_quadrante_pix_renda.png`)*

```python
# Scatter Pix per capita × rendimento domiciliar per capita (log),
# linhas nas medianas, quadrante "Pix alto + renda baixa" destacado.
# Implementado no notebook 02; ver docs/Relatorio_EDA.md seção 5.
```

**Célula C — Sazonalidade do Pix**

```python
df_pix = read_table_to_dataframe("raw_bcb_pix_transacoes")
df_pix["ano_mes"] = pd.to_datetime(df_pix["data_base"].astype(str), format="%Y-%m-%d").dt.to_period("M")
serie = df_pix.groupby("ano_mes").agg(
    valor_pf=("valor_pf", "sum"),
    valor_pj=("valor_pj", "sum"),
).reset_index()
serie["ano_mes"] = serie["ano_mes"].astype(str)

fig, ax = plt.subplots(figsize=(12, 6))
serie.plot(x="ano_mes", y=["valor_pf", "valor_pj"], ax=ax)
ax.set_title("Evolução do volume Pix (PF vs PJ)")
ax.tick_params(axis="x", rotation=45)
save_figure(fig, "02_serie_pix.png")
```

**Célula D — Estatísticas por estrato**

```python
stats = df.groupby("estrato_populacional").agg({
    "rendimento_domiciliar_per_capita": ["mean", "median"],
    "pib_per_capita": ["mean", "median"],
    "pix_per_capita_12m": ["mean", "median"],
}).round(2)
display(stats)
```

#### Critérios de aceitação

- [ ] Distribuições de renda e PIB plotadas.
- [ ] Relação Pix × PIB analisada.
- [ ] Série temporal do Pix gerada.

---

### 4.5 Notebook 03 — Infraestrutura Digital e Gap Bancário

**Arquivo**: `notebooks/00_exploracao/03_infra_digital_e_gap_bancario.ipynb`

**Objetivo**: analisar banda larga, agências, depósitos e crédito.

**Inputs**: `data/processed/trusted_municipios_eda.parquet`

**Outputs**: figuras e matriz de quadrantes.

#### Células técnicas

**Célula A — Municípios sem agência**

```python
sem_agencia = df["flag_sem_agencia"].sum()
logger.info("Municípios sem agência: %d (%.2f%%)", sem_agencia, sem_agencia / len(df) * 100)
```

**Célula B — Quadrantes infraestrutura × gap bancário**

```python
mediana_banda = df["banda_larga_fixa_por_100_hab"].median()
mediana_agencias = df["agencias_por_100k_hab"].fillna(0).median()

df["quadrante"] = "desconectado"
df.loc[
    (df["banda_larga_fixa_por_100_hab"] >= mediana_banda) & (df["agencias_por_100k_hab"].fillna(0) < mediana_agencias),
    "quadrante",
] = "alto_potencial"
df.loc[
    (df["banda_larga_fixa_por_100_hab"] >= mediana_banda) & (df["agencias_por_100k_hab"].fillna(0) >= mediana_agencias),
    "quadrante",
] = "maduro_saturado"
df.loc[
    (df["banda_larga_fixa_por_100_hab"] < mediana_banda) & (df["agencias_por_100k_hab"].fillna(0) >= mediana_agencias),
    "quadrante",
] = "bancarizado_sem_infra"

logger.info("Distribuição dos quadrantes:\n%s", df["quadrante"].value_counts())
```

**Célula C — Scatter plot de quadrantes**

```python
fig, ax = plt.subplots(figsize=(12, 8))
sns.scatterplot(
    data=df,
    x="banda_larga_fixa_por_100_hab",
    y="agencias_por_100k_hab",
    hue="quadrante",
    alpha=0.7,
    ax=ax,
)
ax.axvline(mediana_banda, color="gray", linestyle="--")
ax.axhline(mediana_agencias, color="gray", linestyle="--")
ax.set_title("Infraestrutura Digital vs Gap Bancário")
save_figure(fig, "03_quadrantes_infra_gap.png")
```

#### Critérios de aceitação

- [ ] Distribuição de municípios sem agência calculada.
- [ ] Quadrantes definidos e visualizados.
- [ ] Mapa ou barplot de agências por região gerado.

---

### 4.6 Notebook 04 — Integração, Correlações e Cálculo Alpha do IPB

**Arquivo**: `notebooks/00_exploracao/04_integracao_correlacoes.ipynb`

**Objetivo**: cruzar pilares, calcular correlações e gerar o IPB alpha.

**Inputs**: `data/processed/trusted_municipios_eda.parquet`

**Outputs**:
- `data/processed/ipb_alpha.parquet`
- `data/processed/reports/ipb_alpha_report.json`
- Figuras de correlação e ranking.

#### Células técnicas

**Célula A — Seleção de variáveis para o IPB alpha**

```python
variaveis_ipb = {
    "A_capacidade_consumo": ["rendimento_domiciliar_per_capita", "pib_per_capita"],
    "B_dinamismo": ["pix_per_capita_12m"],
    "C_adocao_digital": ["banda_larga_fixa_por_100_hab"],
    "D_gap_bancario": ["agencias_por_100k_hab", "depositos_per_capita", "credito_per_capita"],
    "E_perfil_demografico": ["populacao_18_35_pct", "populacao_urbana_pct", "escolaridade_ensino_medio_pct"],
}
```

**Célula B — Winsorização e normalização**

```python
from src.utils.eda import winsorize_series, min_max_normalize

df_ipb = df[["id_municipio", "nome_municipio", "sigla_uf", "nome_regiao", "populacao_total"]].copy()

for pilar, vars_list in variaveis_ipb.items():
    for var in vars_list:
        col_norm = f"{var}_norm"
        df_ipb[col_norm] = min_max_normalize(winsorize_series(df[var]))
```

**Célula C — Inversão do pilar D**

```python
for var in variaveis_ipb["D_gap_bancario"]:
    df_ipb[f"{var}_norm"] = 1 - df_ipb[f"{var}_norm"]
```

**Célula D — Cálculo dos pilares e IPB**

```python
for pilar, vars_list in variaveis_ipb.items():
    cols = [f"{var}_norm" for var in vars_list]
    df_ipb[pilar] = df_ipb[cols].mean(axis=1)

# Média geométrica dos 5 pilares
df_ipb["ipb_alpha"] = (df_ipb[list(variaveis_ipb.keys())].prod(axis=1)) ** (1 / 5) * 100
df_ipb["rank_ipb_alpha"] = df_ipb["ipb_alpha"].rank(ascending=False, method="min").astype(int)
```

**Célula E — Correlação entre pilares**

```python
plot_correlation_heatmap(
    df_ipb,
    list(variaveis_ipb.keys()),
    method="spearman",
    title="Correlação entre Pilares",
    filename="04_correlacao_pilares.png",
)
```

**Célula F — Top e bottom ranking**

```python
top30 = df_ipb.nsmallest(30, "rank_ipb_alpha")[["nome_municipio", "sigla_uf", "ipb_alpha", "rank_ipb_alpha"]]
bottom30 = df_ipb.nlargest(30, "rank_ipb_alpha")[["nome_municipio", "sigla_uf", "ipb_alpha", "rank_ipb_alpha"]]
display(top30)
display(bottom30)
```

**Célula G — Salvamento**

```python
save_parquet(df_ipb, "ipb_alpha.parquet")

ipb_report = {
    "media_ipb_alpha": float(df_ipb["ipb_alpha"].mean()),
    "mediana_ipb_alpha": float(df_ipb["ipb_alpha"].median()),
    "top_10": top30.head(10).to_dict(orient="records"),
}
save_json(ipb_report, "ipb_alpha_report.json")
```

#### Critérios de aceitação

- [ ] IPB alpha calculado para todos os 5.570 municípios.
- [ ] Ranking top/bottom gerado e interpretado.
- [ ] Matriz de correlação entre pilares salva.
- [ ] Arquivos `ipb_alpha.parquet` e `ipb_alpha_report.json` gerados.

---

## 5. Ordem de execução

```bash
# 1. Criar/utilizar utilitários de EDA
poetry run python -m pytest tests/unit/test_eda_utils.py  # após criar

# 2. Executar notebooks em ordem
poetry run jupyter notebook notebooks/00_exploracao/00_setup_e_qualidade.ipynb
poetry run jupyter notebook notebooks/00_exploracao/00b_auditoria_raws_e_features.ipynb
poetry run jupyter notebook notebooks/00_exploracao/01_perfil_demografico_e_geo.ipynb
poetry run jupyter notebook notebooks/00_exploracao/02_economia_e_dinamismo.ipynb
poetry run jupyter notebook notebooks/00_exploracao/03_infra_digital_e_gap_bancario.ipynb
poetry run jupyter notebook notebooks/00_exploracao/04_integracao_correlacoes.ipynb
```

Dependências entre notebooks:
- `00b` depende de `00` (embora leia a trusted diretamente do BQ, o report de quality é contextual).
- `01`, `02`, `03` dependem de `00b` (usam `trusted_municipios_eda.parquet`).
- `04` depende de `00b` e `03` (usam a base enriquecida e quadrantes).

---

## 6. Testes e validação

### 6.1 Testes unitários

Criar `tests/unit/test_eda_utils.py`:

```python
import pandas as pd
import numpy as np
import pytest

from src.utils.eda import compute_null_profile, winsorize_series, min_max_normalize


def test_compute_null_profile():
    df = pd.DataFrame({"a": [1, 2, np.nan], "b": [np.nan, np.nan, np.nan]})
    profile = compute_null_profile(df)
    assert profile.loc[profile["coluna"] == "b", "pct_nulos"].values[0] == 100.0


def test_winsorize_series():
    s = pd.Series([1, 2, 3, 100, 200])
    w = winsorize_series(s, lower=0.0, upper=0.8)
    assert w.max() <= s.quantile(0.8)


def test_min_max_normalize():
    s = pd.Series([0, 5, 10])
    n = min_max_normalize(s)
    assert n.min() == 0.0
    assert n.max() == 1.0
```

### 6.2 Validação manual dos notebooks

Antes de marcar cada notebook como concluído, executar:

```bash
poetry run jupyter nbconvert --to notebook --execute notebooks/00_exploracao/00_setup_e_qualidade.ipynb --output /tmp/test_00.ipynb
```

Se passar sem erro, o notebook é reprodutível.

---

## 7. Convenções de código

- Usar `snake_case` para variáveis e colunas.
- Toda função pública deve ter docstring no formato Google.
- Toda célula de notebook deve ter um comentário Markdown explicando o objetivo.
- Nomes de figuras devem seguir padrão: `{numero_notebook}_{descricao_curta}.{png|html}`.
- Nomes de parquet devem seguir padrão: `{descricao}.parquet`.

---

## 8. Referências

- [`Guia_de_Analise_Exploratoria.md`](Guia_de_Analise_Exploratoria.md) — visão de negócio e justificativas.
- [`IPB_Guia_de_Bases_e_Desenho.md`](IPB_Guia_de_Bases_e_Desenho.md) — tese e pilares.
- [`Dicionario_de_Dados.md`](Dicionario_de_Dados.md) — schema das tabelas.
- [`../AGENTS.md`](../AGENTS.md) — regras do repositório.

---

*Documento v1 — plano técnico de implementação da EDA do IPB.*
