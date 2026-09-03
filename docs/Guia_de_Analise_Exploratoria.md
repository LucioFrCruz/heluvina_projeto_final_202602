# Guia de Análise Exploratória de Dados (EDA) — IPB

> **Propósito**: este documento estrutura a Etapa 2 do projeto — Análise Exploratória e Limpeza — com base nos objetivos da aula 3, no desenho técnico aprovado (`docs/Arquitetura_Tecnica.md`), na tese do índice (`docs/IPB_Guia_de_Bases_e_Desenho.md`) e no dicionário de dados (`docs/Dicionario_de_Dados.md`).
>
> **Escopo**: planejamento detalhado. A execução será feita em notebooks `.ipynb` dentro de `notebooks/00_exploracao/`, lendo diretamente das tabelas `trusted_*` e `raw_*` do BigQuery.
>
> **Público-alvo**: equipe do IPB e professor avaliador.

---

## 1. Contexto e objetivos da EDA

A Etapa 1 foi concluída: a tabela `trusted_municipios` está consolidada com **5.570 municípios** e as variáveis dos 5 pilares do IPB. A Etapa 2 deve transformar essa base em **conhecimento acionável** para responder:

> *Quais municípios brasileiros apresentam maior potencial para expansão de um banco digital?*

### 1.1 Objetivos da EDA (derivados da aula 3)

| # | Objetivo | O que isso significa para o IPB |
|---|----------|--------------------------------|
| 1 | **Avaliar a qualidade dos dados após a limpeza** | Confirmar se `trusted_municipios` está completa, tipada corretamente e sem duplicidades; medir taxa de nulos por variável. |
| 2 | **Desenvolver visão crítica sobre limitações e potencial analítico** | Documentar vintage misto, proxies (ex.: Anatel por % de internet), e municípios sem agência bancária. |
| 3 | **Compreender a estrutura geral da base e suas principais variáveis** | Perfilar cada pilar: capacidade de consumo, dinamismo econômico, adoção digital, gap bancário e perfil demográfico. |
| 4 | **Identificar padrões, tendências e anomalias** | Detectar assimetrias, concentrações regionais, cidades outliers e possíveis erros de coleta. |
| 5 | **Realizar análises estatísticas descritivas** | Calcular média, mediana, desvio padrão, quartis, assimetria e curtose para cada indicador. |
| 6 | **Investigar correlações e relações entre atributos** | Cruzar renda × Pix, banda larga × escolaridade, agências × PIB, etc. |
| 7 | **Produzir visualizações que facilitem a interpretação** | Gerar histogramas, boxplots, mapas coropléticos, scatter plots e heatmaps. |
| 8 | **Levantar hipóteses para a modelagem** | Formular proposições testáveis sobre o que explica o potencial bancário digital. |

### 1.2 Critérios de excelência (rubrica da aula 3)

- Estatísticas descritivas, visualizações, correlações e anomalias com **interpretação coerente com o problema**.
- Gráficos adequados, legíveis, bem rotulados e relacionados aos objetivos.
- Código organizado, comentado e executável (notebooks reprodutíveis).
- Documentação das fontes, problemas encontrados, tratamentos aplicados e análises realizadas.

---

## 2. Base de dados e acesso

### 2.1 Tabelas-fonte no BigQuery

| Camada | Tabela | Função na EDA |
|--------|--------|---------------|
| **Trusted** | `trusted_municipios` | Base principal da análise. Uma linha por município com todos os indicadores. |
| Raw | `raw_sidra_censo_2022` | Validação de indicadores demográficos e renda; análise de granularidade. |
| Raw | `raw_pib_municipios` | Checagem de PIB e `va_servicos` (nulo para 2023). |
| Raw | `raw_bcb_pix_transacoes` | Análise de sazonalidade e crescimento do Pix (série temporal). |
| Raw | `raw_anatel_banda_larga_fixa` | Validação do proxy de infraestrutura digital. |
| Raw | `raw_bcb_estban` | Análise do gap bancário e concentração de agências. |
| Raw | `raw_pnud_idhm` | Referência histórica de desenvolvimento humano. |
| Raw | `raw_ibge_localidades` | Base geográfica para joins e mapas. |

### 2.2 Conexão e leitura no notebook

Cada notebook deve iniciar com:

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from src.utils.bigquery import read_table_to_dataframe

# Leitura direta da tabela (função já existente no projeto)
df = read_table_to_dataframe("trusted_municipios")

# Para queries customizadas, usar o cliente diretamente
from src.utils.bigquery import get_bigquery_client
client = get_bigquery_client()

def query_bq(sql: str) -> pd.DataFrame:
    return client.query(sql).to_dataframe()
```

> **Dica de custo zero**: como o volume é pequeno (~5.570 municípios), full-scans na trusted não geram custo relevante. O uso de `LIMIT` só é necessário durante a prototipagem com tabelas maiores.
>
> **Persistência**: os artefatos da EDA (DataFrames enriquecidos, figures, CSVs/Parquets) devem ficar em `data/processed/` localmente. Não é obrigatório gravar novas tabelas no BigQuery.

---

## 3. Organização dos notebooks

A EDA será dividida em **5 notebooks** na pasta `notebooks/00_exploracao/`. Cada notebook tem um objetivo claro, conjunto de análises, gráficos e entregáveis.

### 3.0 Estrutura de pastas

```
notebooks/
└── 00_exploracao/
    ├── 00_setup_e_qualidade.ipynb            # Conexão, perfil geral e data quality da trusted
    ├── 00b_auditoria_raws_e_features.ipynb   # Exploração das raws e engenharia de features
    ├── 01_perfil_demografico_e_geo.ipynb     # Pilar E + contexto geográfico
    ├── 02_economia_e_dinamismo.ipynb         # Pilares A e B
    ├── 03_infra_digital_e_gap_bancario.ipynb # Pilares C e D
    └── 04_integracao_correlacoes.ipynb       # Cruzamentos, correlações e cálculo alpha do IPB
```

### 3.1 Notebook 00 — Setup e Qualidade de Dados

**Objetivo**: carregar `trusted_municipios`, validar estrutura, identificar nulos, duplicatas e inconsistências.

#### Análises obrigatórias

1. **Volumetria e integridade**
   - Total de linhas (esperado: 5.570).
   - Contagem de `id_municipio` distintos.
   - Verificação de duplicatas na chave primária.
   - Cobertura por UF e região.

2. **Estatísticas descritivas gerais**
   - `df.describe()` para todas as variáveis numéricas.
   - Contagem de nulos por coluna (% e absoluto).
   - Tipos de dados (`df.dtypes`).

3. **Validação de regras de negócio**
   - `populacao_total > 0` para todos os municípios.
   - Percentuais (`populacao_18_35_pct`, `populacao_urbana_pct`, `escolaridade_ensino_medio_pct`) entre 0 e 100.
   - `pib_per_capita > 0`.
   - `quantidade_agencias >= 0`.

4. **Diagnóstico de nulos e gaps conhecidos**
   - `domicilios_com_internet_pct`: documentar 100% nulo (API SIDRA instável).
   - `idhm`: documentar vintage 2010.
   - `quantidade_agencias`, `volume_depositos`, `volume_credito`: documentar ~2.900 municípios com registro.

#### Gráficos sugeridos

- Tabela de missing values (heatmap de nulos).
- Mapa de cobertura por UF (contagem de municípios).
- Histograma de `populacao_total` (escala log).

#### Entregáveis

- DataFrame `df_quality` com taxa de nulos por coluna.
- Lista de flags de qualidade (ex.: `flag_sem_agencia`, `flag_internet_nula`, `flag_populacao_zero`).
- Documentação inicial dos problemas encontrados.

---

### 3.2 Notebook 00b — Auditoria das Raws e Engenharia de Features

**Objetivo**: explorar as tabelas `raw_*` para validar como a `trusted_municipios` foi construída e identificar features derivadas que podem enriquecer a análise. As saídas deste notebook ficam **locais** (`data/processed/`).

#### Análises obrigatórias

1. **Inventário das colunas nas raws**
   - Comparar schema de cada `raw_*` com as colunas correspondentes na `trusted_municipios`.
   - Listar colunas existentes nas raws que **não** foram para a trusted e avaliar se têm valor analítico.

2. **Auditoria da agregação**
   - `raw_bcb_pix_transacoes`: verificar se a soma dos 12 meses bate com `pix_total_volume_12m` e `pix_total_transacoes_12m` da trusted.
   - `raw_bcb_estban`: verificar se a contagem de agências e soma de depósitos/crédito batem com a trusted.
   - `raw_anatel_banda_larga_fixa`: verificar se o mês mais recente foi usado corretamente.

3. **Features derivadas candidatas**

   | Feature | Base de cálculo | Relevância para a tese |
   |---------|-----------------|------------------------|
   | `pix_pj_pct` | `valor_pj / (valor_pf + valor_pj)` | Maturidade digital de empresas locais. |
   | `pix_ticket_medio` | `pix_total_volume_12m / pix_total_transacoes_12m` | Quanto dinheiro circula por transação. |
   | `pix_crescimento_12m` | Variação percentual do volume Pix nos últimos 12 meses | Dinamismo recente. |
   | `depositos_por_agencia` | `volume_depositos / quantidade_agencias` | Eficiência da rede bancária tradicional. |
   | `credito_por_agencia` | `volume_credito / quantidade_agencia` | Capacidade de crédito por ponto físico. |
   | `flag_sem_agencia` | `1` se `quantidade_agencias == 0` | Indicador direto de gap bancário. |
   | `estrato_populacional` | `< 50k`, `50k–500k`, `> 500k` | Segmentação para análise e ranking. |

4. **Critério de inclusão**
   - Cada nova feature deve ser justificada com base na tese: *demanda × adoção digital × baixa penetração bancária*.
   - Não incluir feature só porque "existe no dado".

#### Entregáveis

- Tabela `data/processed/trusted_municipios_eda.parquet` com as features enriquecidas.
- Documento/lista de features candidatas aprovadas e rejeitadas, com justificativa.
- Validação cruzada entre `raw_*` e `trusted_municipios`.

---

### 3.3 Notebook 01 — Perfil Demográfico e Geográfico (Pilar E)

**Objetivo**: entender a composição demográfica e geográfica dos municípios; analisar escolaridade, urbanização e juventude.

#### Variáveis principais

- `populacao_total`
- `populacao_18_35_pct`
- `populacao_urbana_pct`
- `escolaridade_ensino_medio_pct`
- `idhm`

#### Análises obrigatórias

1. **Distribuição das variáveis demográficas**
   - Histogramas com KDE para `populacao_total`, `populacao_18_35_pct`, `populacao_urbana_pct`, `escolaridade_ensino_medio_pct`.
   - Boxplots por região.
   - Medidas de assimetria e curtose.

2. **Análise geográfica e regional**
   - Média dos indicadores por `nome_regiao` e `sigla_uf`.
   - Mapa coroplético do Brasil por `escolaridade_ensino_medio_pct`.
   - Identificação de outliers regionais.

3. **Relação entre juventude, urbanização e escolaridade**
   - Scatter plot: `populacao_18_35_pct` × `escolaridade_ensino_medio_pct`.
   - Scatter plot: `populacao_urbana_pct` × `escolaridade_ensino_medio_pct`.
   - Correlação de Spearman (dados possivelmente não normais).

4. **Comparação IDHM 2010 × escolaridade 2022**
   - Scatter plot com reta de regressão.
   - Identificar municípios com alta escolaridade e baixo IDHM histórico (oportunidades emergentes).

#### Gráficos sugeridos

- Histogramas com KDE.
- Boxplots por região.
- Mapas coropléticos (estático ou interativo com Plotly).
- Pairplot das variáveis demográficas.

#### Entregáveis

- Perfil demográfico por região (tabela resumo).
- Lista de municípios com jovens + urbanização + escolaridade acima da mediana.
- Identificação de outliers demográficos.

---

### 3.4 Notebook 02 — Capacidade de Consumo e Dinamismo Econômico (Pilares A e B)

**Objetivo**: analisar renda, PIB, volume Pix e dinamismo financeiro.

#### Variáveis principais

- `rendimento_domiciliar_per_capita`
- `pib`
- `pib_per_capita`
- `pix_total_volume_12m`
- `pix_total_transacoes_12m`
- `pix_per_capita_12m`

#### Análises obrigatórias

1. **Distribuição de renda e PIB**
   - Histogramas de `rendimento_domiciliar_per_capita` e `pib_per_capita` (escala log se necessário).
   - Boxplots por região.
   - Cálculo de Gini simplificado ou concentração (top 10% vs. bottom 10%).

2. **Análise do Pix**
   - Distribuição de `pix_per_capita_12m` (muitos zeros? assimetria?).
   - Scatter plot: `pib_per_capita` × `pix_per_capita_12m`.
   - Scatter plot: `populacao_total` × `pix_total_volume_12m`.
   - Municípios com alto volume Pix e baixo PIB per capita (adoção digital avançada em cidades menos ricas).

3. **Sazonalidade e crescimento (usar `raw_bcb_pix_transacoes`)**
   - Série temporal de transações e volume por mês.
   - Crescimento acumulado nos últimos 12 meses.
   - Comparar PF vs. PJ.

4. **Segmentação por estratos populacionais**
   - Estratos: capitais/grandes (> 500 mil), médias (50–500 mil), pequenas (< 50 mil).
   - Comparar renda, PIB e Pix entre estratos.

#### Gráficos sugeridos

- Histogramas e KDE.
- Boxplots por região e estrato.
- Scatter plots com regressão.
- Gráfico de linha para série temporal do Pix.
- Treemap ou barplot dos top 20 municípios em Pix per capita.

#### Entregáveis

- Tabela de estatísticas descritivas por estrato populacional.
- Identificação de municípios com alta adoção Pix e baixa renda.
- Insights sobre sazonalidade do Pix.

---

### 3.5 Notebook 03 — Infraestrutura Digital e Gap Bancário (Pilares C e D)

**Objetivo**: avaliar conectividade, infraestrutura digital e concorrência física dos bancos tradicionais.

#### Variáveis principais

- `banda_larga_fixa_por_100_hab` (proxy de adoção digital)
- `quantidade_agencias`
- `agencias_por_100k_hab`
- `volume_depositos`
- `depositos_per_capita`
- `volume_credito`
- `credito_per_capita`

#### Análises obrigatórias

1. **Infraestrutura digital**
   - Distribuição de `banda_larga_fixa_por_100_hab`.
   - Boxplot por região.
   - Mapa coroplético de banda larga.
   - Relação: `banda_larga_fixa_por_100_hab` × `pix_per_capita_12m`.

2. **Gap bancário — volumetria**
   - Quantos municípios têm 0 agências? (% e absoluto).
   - Distribuição de `agencias_por_100k_hab` (muitos zeros).
   - Boxplot de `depositos_per_capita` e `credito_per_capita` por região.

3. **Gap bancário — inversão para o índice**
   - Criar variáveis invertidas: `gap_agencias = 1 / (1 + agencias_por_100k_hab)`, ou `1 - min_max(agencias_por_100k_hab)`.
   - Discutir abordagem: inversão direta vs. ranking inverso.

4. **Cruzamento infraestrutura × gap bancário**
   - Scatter plot: `banda_larga_fixa_por_100_hab` × `agencias_por_100k_hab`.
   - Identificar quadrantes:
     - **Alto potencial**: alta banda larga + poucas agências.
     - **Maduro saturado**: alta banda larga + muitas agências.
     - **Desconectado**: baixa banda larga + poucas agências.
     - **Bancarizado sem infra**: baixa banda larga + muitas agências.

5. **Efeito polo regional**
   - Analisar se municípios próximos a capitais têm menor número de agências (efeito dormitório).
   - Comparar agências e depósitos entre municípios da mesma microrregião.

#### Gráficos sugeridos

- Histogramas com destaque para zero agências.
- Boxplots por região.
- Scatter plots com quadrantes.
- Mapas coropléticos de agências por 100k hab.
- Gráfico de barras dos estados com maior % de municípios sem agência.

#### Entregáveis

- Tabela de municípios sem agência bancária.
- Definição das variáveis invertidas do pilar D.
- Matriz de quadrantes (infraestrutura × gap bancário).

---

### 3.6 Notebook 04 — Integração, Correlações e Cálculo Alpha do IPB

**Objetivo**: cruzar todos os pilares, calcular correlações, detectar multicolinearidade e calcular uma primeira versão do IPB (alpha). A modelagem de ML (PCA, K-Means) é **opcional e exploratória**; o entregável principal desta etapa é o cálculo do índice e suas interpretações.

#### Análises obrigatórias

1. **Matriz de correlação**
   - Correlação de Pearson e Spearman entre todas as variáveis numéricas.
   - Heatmap com anotações.
   - Destacar correlações fortes (> 0.7 ou < -0.7).

2. **Correlações específicas da tese**
   - `rendimento_domiciliar_per_capita` × `pix_per_capita_12m`
   - `banda_larga_fixa_por_100_hab` × `pix_per_capita_12m`
   - `escolaridade_ensino_medio_pct` × `pix_per_capita_12m`
   - `pib_per_capita` × `credito_per_capita`
   - `agencias_por_100k_hab` × `depositos_per_capita`

3. **Multicolinearidade**
   - Calcular VIF (Variance Inflation Factor) para variáveis candidatas ao modelo.
   - Identificar variáveis redundantes.

4. **Distribuição conjunta e agrupamentos prévios (opcional)**
   - Pairplot das variáveis normalizadas.
   - Projeção 2D via PCA para entender se os 5 pilares formam dimensões distintas.
   - Se fizer sentido, testar K-Means para agrupar municípios em arquétipos.
   - Identificar visualmente grupos de municípios.

5. **Cálculo prévio do IPB (versão alpha)**
   - Normalizar variáveis com min-max (0–1) com winsorização no 1%.
   - Inverter variáveis do pilar D.
   - Calcular pilares como média simples das variáveis.
   - Calcular IPB = média geométrica dos 5 pilares × 100.
   - Gerar ranking inicial e comparar com expectativas de negócio.

#### Gráficos sugeridos

- Heatmap de correlação.
- Pairplot.
- Scatter plot PCA (2 componentes principais).
- Histograma do IPB alpha.
- Barplot do top 30 e bottom 30 no ranking alpha.
- Mapa coroplético do IPB alpha.

#### Entregáveis

- Matriz de correlação e insights.
- Base `df_ipb_alpha` com score prévio.
- Lista de variáveis candidatas e justificativa de exclusão (se houver).
- Primeiras hipóteses de clusters/ondas de expansão.

---

## 4. Metodologia estatística e visual

### 4.1 Medidas descritivas

Para cada variável numérica, calcular:

- N, média, mediana, desvio padrão, mínimo, máximo.
- Quartis (Q1, Q2, Q3) e IQR.
- Assimetria (`skewness`) e curtose (`kurtosis`).
- Taxa de missing values.

### 4.2 Detecção de outliers

- **Regra do IQR**: valores fora de `[Q1 - 1.5×IQR, Q3 + 1.5×IQR]`.
- **Winsorização**: truncar no percentil 1% e 99% para variáveis que entrarão no IPB.
- **Análise visual**: boxplots e scatter plots para investigar se o outlier é erro ou fenômeno real (ex.: São Paulo, Brasília).

### 4.3 Correlação

- **Pearson**: para relações lineares entre variáveis contínuas (ex.: PIB × renda).
- **Spearman**: para relações monotônicas e dados com outliers (ex.: Pix × agências).
- **Nunca interpretar correlação como causalidade** — documentar sempre como associação.

### 4.4 Escolha de gráficos por objetivo

| Objetivo | Gráfico recomendado |
|----------|---------------------|
| Ver distribuição de uma variável | Histograma + KDE |
| Comparar distribuições por grupo | Boxplot, violin plot |
| Ver relação entre duas variáveis | Scatter plot |
| Ver correlação entre várias | Heatmap |
| Ver composição geográfica | Mapa coroplético |
| Ver evolução temporal | Gráfico de linha |
| Ver ranking | Barplot horizontal |
| Ver proporções | Treemap, pizza (com cautela) |

---

## 5. Tratamento de dados: nulos, outliers e imputação

### 5.1 Nulos conhecidos e estratégia

| Variável | Situação | Estratégia sugerida |
|----------|----------|---------------------|
| `domicilios_com_internet_pct` | 100% nulo (API indisponível) | **Não imputar**. Usar `banda_larga_fixa_por_100_hab` como proxy no pilar C. Documentar como limitação. |
| `quantidade_agencias` | Nulo para ~2.600 municípios | Imputar `0` (município sem agência bancária). Consequentemente `volume_depositos = 0` e `volume_credito = 0`. |
| `depositos_per_capita` / `credito_per_capita` | Nulo quando `volume_*` é nulo | Imputar `0` após imputação de volume. |
| `idhm` | Vintage 2010; pode ter poucos nulos | Manter como variável histórica. Não usar como principal no pilar E. |

### 5.2 Outliers e winsorização

- Aplicar winsorização no percentil 1% e 99% para variáveis que alimentam o IPB.
- Justificar: evitar que cidades extremas (São Paulo, Rio, Brasília) dominem o ranking.
- Documentar quais cidades foram afetadas.

### 5.3 Variáveis a serem criadas

#### Features de contexto

- `estrato_populacional`: `pequena` (< 50k), `media` (50k–500k), `grande` (> 500k).
- `flag_sem_agencia`: 1 se `quantidade_agencias == 0`.
- `log_populacao`, `log_pib_per_capita`, `log_pix_per_capita`: para visualizações.
- `ipb_alpha`: score prévio do índice (Notebook 04).
- `rank_ipb_alpha`: ranking nacional.
- `rank_regional`: ranking dentro da região.

#### Features derivadas das raws (candidatas a serem testadas)

| Feature | Base de cálculo | Justificativa |
|---------|-----------------|---------------|
| `pix_pj_pct` | `valor_pj / (valor_pf + valor_pj)` | Representa maturidade do ecossistema de empresas locais no Pix. |
| `pix_ticket_medio` | `pix_total_volume_12m / pix_total_transacoes_12m` | Indica o porte médio das transações. |
| `pix_crescimento_12m` | Variação percentual do volume Pix no último ano | Mede dinamismo recente. |
| `depositos_por_agencia` | `volume_depositos / quantidade_agencias` | Eficiência/pressão da rede física. |
| `credito_por_agencia` | `volume_credito / quantidade_agencia` | Capacidade de crédito por ponto de atendimento. |

> **Regra**: uma feature só entra na base enriquecida se tiver interpretação clara para a tese do IPB. Caso contrário, fica apenas como análise descritiva no notebook.

---

## 6. Variáveis e métricas por pilar

### 6.1 Pilar A — Capacidade de Consumo

| Variável | Métrica | Análise principal |
|----------|---------|-------------------|
| `populacao_total` | Absoluto | Distribuição, estratos, mapa. |
| `rendimento_domiciliar_per_capita` | R$ | Correlação com Pix e PIB. |
| `pib_per_capita` | R$ | Distribuição, outliers, relação com crédito. |

### 6.2 Pilar B — Dinamismo Econômico

| Variável | Métrica | Análise principal |
|----------|---------|-------------------|
| `pix_per_capita_12m` | R$/hab | Principal medida de dinamismo financeiro digital. |
| `pix_total_transacoes_12m` | Transações | Volume de adoção do Pix. |

### 6.3 Pilar C — Adoção Digital

| Variável | Métrica | Análise principal |
|----------|---------|-------------------|
| `pix_per_capita_12m` | R$/hab | Reutilizado do pilar B (alta correlação esperada — decidir se mantém em ambos). |
| `banda_larga_fixa_por_100_hab` | Acessos/100 hab | Principal proxy de infraestrutura digital. |

### 6.4 Pilar D — Gap Bancário (invertido)

| Variável | Métrica | Análise principal |
|----------|---------|-------------------|
| `agencias_por_100k_hab` | Agências/100k | Quanto menor, maior o gap. |
| `depositos_per_capita` | R$/hab | Quanto menor, maior o gap. |
| `credito_per_capita` | R$/hab | Quanto menor, maior o gap. |

### 6.5 Pilar E — Perfil Demográfico

| Variável | Métrica | Análise principal |
|----------|---------|-------------------|
| `populacao_18_35_pct` | % | Público-alvo de banco digital. |
| `populacao_urbana_pct` | % | Facilita adoção digital. |
| `escolaridade_ensino_medio_pct` | % | Principal indicador do pilar E. |
| `idhm` | Índice | Variável histórica de referência. |

---

## 7. Checklist de validação da EDA

### 7.1 Qualidade dos dados

- [ ] `trusted_municipios` possui 5.570 linhas.
- [ ] `id_municipio` é único e sem nulos.
- [ ] Todas as variáveis percentuais estão entre 0 e 100.
- [ ] `populacao_total` e `pib_per_capita` são positivos.
- [ ] Nulos foram mapeados e justificados.
- [ ] Imputação de zeros no Estban foi aplicada corretamente.

### 7.2 Análise exploratória

- [ ] Estatísticas descritivas calculadas para todas as variáveis.
- [ ] Distribuições investigadas (histogramas + KDE).
- [ ] Outliers identificados e analisados.
- [ ] Correlações calculadas e interpretadas.
- [ ] Análises segmentadas por região e estrato populacional.
- [ ] Visualizações adequadas e bem rotuladas.

### 7.3 Documentação

- [ ] Fontes dos dados citadas.
- [ ] Problemas encontrados documentados.
- [ ] Tratamentos aplicados explicados.
- [ ] Hipóteses levantadas para a modelagem.
- [ ] Limitações e vintage dos dados declarados.

---

## 8. Entregáveis da Etapa 2

1. **5 notebooks reprodutíveis** em `notebooks/00_exploracao/`.
2. **Este guia atualizado** com eventuais ajustes feitos durante a execução.
3. **Relatório de Data Quality** com taxa de nulos, outliers e inconsistências.
4. **Base enriquecida local** (`data/processed/trusted_municipios_eda.parquet` ou `.csv`) contendo flags, estratos, features derivadas e IPB alpha. Não é obrigatório subir para o BigQuery; pode permanecer local para consumo dos notebooks seguintes.
5. **Lista de insights e hipóteses** para a Etapa 3 — que pode ser apenas o cálculo final do IPB ou, se fizer sentido, clusterização/ML exploratório.
6. **Conjunto de visualizações exportadas** em `data/processed/figures/` (PNG/SVG).

---

## 9. Cronograma sugerido

| Dia | Atividade | Notebook |
|-----|-----------|----------|
| 1 | Leitura da base e validação de qualidade | 00 |
| 2 | Perfil demográfico e geográfico | 01 |
| 3 | Capacidade de consumo e dinamismo Pix | 02 |
| 4 | Infraestrutura digital e gap bancário | 03 |
| 5 | Integração, correlações e IPB alpha | 04 |
| 6 | Revisão, documentação e ajustes | Todos |
| 7 | Entrega e apresentação dos primeiros insights | — |

---

## 10. Riscos e cuidados metodológicos

1. **Vintage misto de dados**: Censo 2022 + PIB 2023 + Pix 2023/2024 + Anatel/Estban 2026 + IDHM 2010. Sempre declarar isso nas análises e na apresentação final.
2. **Efeito polo regional**: municípios próximos a grandes cidades podem parecer desatendidos porque recursos financeiros fluem para o polo. Tratar como insight, não defeito.
3. **Correlação ≠ causalidade**: evitar afirmações do tipo "banda larga causa maior uso de Pix" sem validação estatística.
4. **Outliers dom inantes**: São Paulo, Rio de Janeiro e Brasília podem distorcer médias e rankings. Usar medianas, winsorização e análise por estrato.
5. **Variáveis altamente correlacionadas**: `pix_total_volume_12m` e `pix_per_capita_12m` têm alta correlação com `populacao_total`. Decidir se ambas entram no modelo.
6. **Não modificar tabelas raw**: a limpeza deve gerar novas tabelas (`trusted_municipios_eda` ou `analytics_*`) sem apagar os dados brutos.

---

## 11. Referências internas

- [`IPB_Guia_de_Bases_e_Desenho.md`](IPB_Guia_de_Bases_e_Desenho.md) — tese, pilares e fórmula.
- [`Arquitetura_Tecnica.md`](Arquitetura_Tecnica.md) — desenho técnico e fontes.
- [`Dicionario_de_Dados.md`](Dicionario_de_Dados.md) — schema completo das tabelas.
- [`Plano_de_Implementacao.md`](Plano_de_Implementacao.md) — cronograma e entregáveis.
- [`../AGENTS.md`](../AGENTS.md) — regras e convenções do repositório.
- `referencias/aula3-analise_exploratoria.pdf` — objetivos e rubrica da Etapa 2.

---

*Documento v1 — planejamento da EDA do IPB.*
