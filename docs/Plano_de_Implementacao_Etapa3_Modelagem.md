# Plano de Implementação — Etapa 3: Modelagem (ML)

> **Status**: Rascunho para validação do grupo antes da implementação

> **Data**: 2026-09-11

> **Escopo**: Implementar a Etapa 3 (modelagem) conforme o escopo travado em `referencias/DISCUSSAO_MODELOS_ETAPA3.md` (v2): clusterização (K-Means + GMM), classificação de presença bancária (Regressão Logística + Random Forest, com KNN/Árvore como teste), classificador de arquétipos, regressão (explicar IPB + potencial latente), Isolation Forest e publicação da tabela `analytics_ipb_clusters`.

> **Fora de escopo (decidido)**: PCA, Agglomerative/dendrograma, DBSCAN, validação espacial por região, análise prescritiva. Ficam registrados como fase 2 na discussão.

---

## 1. Contexto

A Etapa 2 publicou as 3 versões do IPB (`analytics_ipb_*`, integridade testada). A Etapa 3 aplica ML sobre a mesma base com uma restrição central, declarada na discussão: **não temos rótulo de verdade** — todo alvo é *proxy* (substituto). Os modelos então servem para:

1. **Descobrir estrutura** — arquétipos de municípios (clusterização não supervisionada);
2. **Prever presença bancária observada** — e extrair oportunidades dos erros do modelo (classificação);
3. **Estimar potencial não observado** — quanto um município sem agência depositaria se tivesse banco (regressão);
4. **Apontar anomalias** para leitura humana (Isolation Forest).

Stack: **só scikit-learn** (já em `pyproject.toml`, ^1.3.0). Sem dependência nova, sem GPU, sem cloud — custo zero.

---

## 2. Fonte de dados — o dataset de modelagem

### 2.1 Origem

| Origem | Arquivo/tabela | Uso |
|---|---|---|
| Trusted | `data/processed/trusted_municipios_eda.parquet` (5.570 linhas) | Features-base e alvos |
| Analytics | `data/processed/analytics_ipb_v3_presenca_completa.parquet` | Correspondentes por tipo, CEMPRE e referência `ipb`/`rank` para cruzamento |
| Saída | `data/processed/modelagem.parquet` | Dataset único da Etapa 3 |

> Montagem local via parquet (padrão do projeto: idempotência, sem re-bater APIs). A publicação final é no BigQuery (§5.7).

### 2.2 Features de modelo (constante exportada `FEATURES_MODELO`)

19 variáveis numéricas, 0% de nulos, vintages documentados:

| Família | Variáveis |
|---|---|
| Demografia (Censo 2022) | `populacao_total`, `populacao_18_35_pct`, `populacao_urbana_pct`, `rendimento_domiciliar_per_capita`, `escolaridade_ensino_medio_pct` |
| Economia (2023) | `pib_per_capita` |
| Atividade empresarial (CEMPRE 2024) | `empregos_formais_por_1000_hab`, `unidades_locais_por_1000_hab`, `unidades_alojamento_alimentacao_por_1000_hab` |
| Digital | `pix_per_capita_12m`, `pix_pj_pct`, `pix_ticket_medio`, `banda_larga_fixa_por_100_hab` |
| Presença bancária | `quantidade_agencias`, `agencias_por_100k_hab`, `quantidade_correspondentes`, `correspondentes_por_100k_hab`, `depositos_per_capita`, `credito_per_capita` |

### 2.3 Alvos (rótulos proxy, declarados como tal)

| Alvo | Coluna derivada | Distribuição aproximada |
|---|---|---|
| Tem agência | `flag_tem_agencia = quantidade_agencias > 0` | ~52% sim / ~48% não (desbalanceamento leve) |
| Tem correspondente | `flag_tem_correspondente = quantidade_correspondentes > 0` | a medir nos experimentos |
| Arquétipo | `cluster_kmeans` / `cluster_gmm` (gerado pelo próprio cluster — 100% dados) | K definido nos experimentos |
| IPB (sanity) | `ipb` (da V3, para a regressão explicativa) | circularidade declarada no relatório |
| Depósitos per capita | `depositos_per_capita` (potencial latente) | só ~52% dos municípios têm valor |

### 2.4 Colunas de identidade e referência (NÃO são feature)

`id_municipio`, `nome_municipio`, `sigla_uf`, `nome_regiao`, `estrato_populacional` + `ipb`, `rank` (referência para cruzar os modelos com o índice — nunca entram como preditoras).

### 2.5 O que fica de fora e por quê

- **Colunas do índice** (`score_a`…`score_e`, `gap_bancario_completo`, `penetracao_digital_relativa`, `score_turismo`, `tensao_digital_bancaria`, ranks V1/V2): são *derivadas* das features-base ou da fórmula — entrar como feature criaria circularidade (o modelo decoraria o índice);
- **`domicilios_com_internet_pct`**: 100% nula (SIDRA 7307 fora do ar);
- **`depositos_por_agencia`, `credito_por_agencia`**: 48% nulos (só existem onde há agência);
- **`_extracted_at`, `_source_url`**: auditoria, não feature;
- **`idhm`**: 2010, vintage distante demais da demografia 2022 — fica fora da V1 (decisão registrada; se o grupo quiser, entra como teste opcional);
- **`pib`, `pix_total_volume_12m`, `pix_total_transacoes_12m`**: absolutos, duplicam a informação das taxas per capita e arrastam o efeito tamanho (documentado na discussão de negócio §3).

---

## 3. Arquitetura da implementação

### 3.1 Arquivos a criar/alterar

| Arquivo | Alteração |
|---|---|
| `src/config.py` | Adicionar `TABLE_ANALYTICS_IPB_CLUSTERS = "analytics_ipb_clusters"` |
| `src/analytics/modelagem.py` | **Novo.** Constantes (features, seed) + montagem do dataset + split padronizado |
| `src/analytics/clustering.py` | **Novo.** K-Means, GMM, métricas de qualidade, perfis e sugestão de nomes |
| `src/analytics/classificacao.py` | **Novo.** Treino/avaliação de classificadores (binário e multiclasse), importância, resíduos |
| `src/analytics/regressao.py` | **Novo.** Regressão explicativa do IPB + potencial latente |
| `src/analytics/anomalias.py` | **Novo.** Isolation Forest |
| `tests/unit/test_modelagem.py` | **Novo.** Testes do dataset |
| `tests/unit/test_clustering.py` | **Novo.** Testes com blobs sintéticos |
| `tests/unit/test_classificacao.py` | **Novo.** Testes de métricas e resíduos |
| `tests/unit/test_regressao.py` | **Novo.** Testes do potencial latente |
| `tests/unit/test_anomalias.py` | **Novo.** Testes do Isolation Forest |
| `tests/data_quality/test_analytics_clusters.py` | **Novo.** Integridade da tabela publicada |
| `notebooks/01_modelagem/01_dataset_e_arquetipos.ipynb` | **Novo.** Monta dataset, clusteriza, perfila e nomeia arquétipos |
| `notebooks/01_modelagem/02_classificacao_presenca.ipynb` | **Novo.** Classificação binária (2 alvos) + classificador de arquétipos |
| `notebooks/01_modelagem/03_regressao_anomalias_sintese.ipynb` | **Novo.** Regressões, anomalias, consolidação e gráficos |
| `scripts/08_publica_clusters_bigquery.py` | **Novo.** Publica `analytics_ipb_clusters` (padrão do script 07) |
| `docs/Relatorio_Modelagem_Etapa3.md` | **Novo.** Relatório final da etapa |

### 3.2 Estrutura dos módulos (assinaturas principais)

```python
# src/analytics/modelagem.py
SEED = 42
FEATURES_MODELO: list[str]          # 19 features da §2.2
COLUNAS_IDENTIDADE: list[str]

def montar_dataset_modelagem(df_trusted: pd.DataFrame,
                             df_v3: pd.DataFrame) -> pd.DataFrame:
    """Junta trusted + analytics V3, deriva os alvos (flags), exclui
    colunas de índice/auditoria e devolve o dataset único da Etapa 3."""

def dividir_treino_teste(df: pd.DataFrame, alvo: str,
                         test_size: float = 0.2, seed: int = SEED):
    """Split estratificado (holdout = prova: o modelo nunca vê o teste).
    Retorna X_treino, X_teste, y_treino, y_teste."""

def padronizar(X_treino, X_teste):
    """StandardScaler ajustado SÓ no treino (sem vazar a prova)."""

# src/analytics/clustering.py
def avaliar_k(df, features, ks=range(3, 11), seed=SEED) -> pd.DataFrame:
    """Roda K-Means e GMM para cada K; retorna tabela com silhouette,
    Davies-Bouldin, Calinski-Harabasz (K-Means) e BIC (GMM)."""

def ajustar_kmeans(df, features, k, seed=SEED) -> tuple[modelo, labels]
def ajustar_gmm(df, features, k, seed=SEED) -> tuple[modelo, labels, probs]
def perfis_clusters(df, features, labels) -> pd.DataFrame:
    """Médias (e desvios) das variáveis por cluster = retrato do arquétipo."""
def sugerir_nomes_perfis(df_perfis) -> dict[int, str]:
    """Sugere nome a partir DOS DADOS (ex.: alojamento/1000 no p90 ->
    'turismo'; pix_pj alto -> 'polo empresarial'). Rótulo nunca é manual:
    vem de thresholds calculados no próprio perfil."""

# src/analytics/classificacao.py
MODELOS = {"logistica": ..., "random_forest": ..., "knn": ..., "arvore": ...}

def treinar_classificadores(X_tr, y_tr, X_te, y_te,
                            modelos=MODELOS) -> pd.DataFrame:
    """Treina cada modelo e devolve a matriz de comparação: ROC-AUC,
    PR-AUC, F1, precision, recall (no teste) + tempo de treino."""
def importancia_features(modelo, features) -> pd.Series
def extrair_residuos_oportunidade(df, y_te, prob_te,
                                  limiar=0.5) -> pd.DataFrame:
    """Falsos negativos (prob prevista alta, sem agência) = lista de
    oportunidade para cruzar com o rank V3."""
def treinar_classificador_arquetipo(X_tr, y_tr, X_te, y_te):
    """Multiclasse: rótulo = cluster do K-Means. Métrica F1 macro +
    matriz de confusão (mede a solidez dos arquétipos)."""

# src/analytics/regressao.py
def treinar_regressores(X_tr, y_tr, X_te, y_te) -> pd.DataFrame:
    """Ridge, Lasso e RF; retorna MAE, RMSE, R² por modelo."""
def explicar_ipb(df, features, col_ipb="ipb") -> pd.DataFrame:
    """Regressão alvo=IPB com ressalva de circularidade impressa no
    relatório; produto = importância ordenada das variáveis."""
def estimar_potencial_latente(df, features_sem_presenca,
                              seed=SEED) -> pd.Series:
    """Treina SÓ em municípios com agência: log1p(depositos_pc) ~
    features socioeconômicas+digitais (SEM variáveis de presença).
    Prevê nos SEM agência = depósitos esperados se tivessem banco."""

# src/analytics/anomalias.py
def detectar_anomalias(df, features, n_top=30,
                       seed=SEED) -> pd.DataFrame:
    """Isolation Forest; retorna score (quanto maior, mais atípico),
    flag top-N e o subset narrável para leitura humana."""
```

Convenções: docstrings Google, `logging` (não print), snake_case, seed única `SEED` exportada (reprodutibilidade).

### 3.3 Notebooks (orquestração fina + visualização)

| Notebook | Conteúdo | Saídas |
|---|---|---|
| `01_dataset_e_arquetipos.ipynb` | Monta `modelagem.parquet`; tabela K × métricas (K=3..10); gráficos de silhuette; perfis dos clusters; **boxplot do IPB por cluster**; proposta de nomes | `modelagem.parquet`, figuras, escolha de K registrada |
| `02_classificacao_presenca.ipynb` | Tuning (GridSearchCV pequeno, 5-fold) de RF e Logística; matriz de comparação dos 4 classificadores × 2 alvos; ROC/PR, matriz de confusão, learning curve; importância; resíduos × rank V3; classificador de arquétipos | tabelas de métricas, figuras |
| `03_regressao_anomalias_sintese.ipynb` | Regressão do IPB (circularidade declarada); potencial latente (previsto × observado, resíduos, Spearman × IPB V3); anomalias Top 30; **consolida `modelagem_resultados.parquet`** | `modelagem_resultados.parquet`, figuras |

> Toda decisão (K escolhido, transformação log, hiperparâmetros) fica registrada em célula markdown do notebook — é a trilha de auditoria da etapa.

---

## 4. Detalhamento por entrega

### 4.1 Dataset de modelagem

- Ler os dois parquets, merge em `id_municipio` (string 7 dígitos, `zfill` — mesmo cuidado do script 07);
- Derivar `flag_tem_agencia`, `flag_tem_correspondente`;
- Validar: 5.570 linhas, chave única, 0 nulos nas 19 features, nenhuma coluna de índice presente;
- Gravar `data/processed/modelagem.parquet`.

### 4.2 Clusterização — escolha do K (decisão em grupo, nos experimentos)

1. Padronizar as 19 features (`StandardScaler`);
2. Rodar `avaliar_k` para K = 3…10;
3. Decisão combinando: silhouette (maior melhor), BIC do GMM (menor melhor) e **legibilidade de negócio** (cada cluster se explica em uma frase pelos dados). O grupo itera sobre a tabela — não decidimos K agora no escuro;
4. Se silhouette < 0,2 para todo K: reportar honestamente (estrutura fraca; talvez seja o caso de projetar em menos variáveis na fase 2);
5. Fixar os modelos vencedores e gerar labels + probabilidades GMM para os 5.570 municípios.

### 4.3 Classificação binária — 2 alvos

1. Split estratificado 80/20 (seed 42), padronização ajustada só no treino;
2. Tuning com `GridSearchCV` (5-fold) no treino: RF (`n_estimators`, `max_depth`), Logística (`C`, `class_weight`), KNN (`n_neighbors`), Árvore (`max_depth`); grids **pequenos e justificados** (a aula pede tuning, não exaustão);
3. Métricas no **teste** (a prova): ROC-AUC, PR-AUC, F1, precision, recall + tempo de treino → matriz de comparação;
4. Gráficos: ROC, PR, matriz de confusão (normalizada), learning curve, importância (RF), distribuição de probabilidade;
5. Extrair resíduos: falso negativo (prob alta + sem agência) = oportunidade; cruzar com `rank` do IPB V3 (scatter/Spearman);
6. Repetir para o alvo "tem correspondente".

### 4.4 Classificador de arquétipos (multiclasse)

1. Rótulo = cluster do K-Means escolhido em 4.2 (dados, não manual);
2. Mesmo protocolo de split/tuning com RF + Logística;
3. F1 macro + matriz de confusão por classe: acerto alto → arquétipos sólidos; erro alto → grupos se misturam (dito no relatório).

### 4.5 Regressão

**(a) Explicar o IPB:** alvo `ipb`, preditoras = 19 features. Espera-se R² alto — declarado como circular (as variáveis já estão na fórmula). Produto: importância ordenada ("o que pesa no índice?"). Ridge/Lasso + RF.

**(b) Potencial latente:** preditoras = features socioeconômicas + digitais **excluindo as 6 de presença bancária** (agências, correspondentes, depósitos, crédito); alvo `log1p(depositos_per_capita)`; treino só em municípios **com** agência; previsão nos **sem** agência. Produto: `potencial_latente_depositos_pc` + Spearman contra IPB V3 (validação cruzada do índice por via independente).

Métricas: MAE, RMSE, R² + gráficos previsto × observado e resíduos.

### 4.6 Anomalias

Isolation Forest sobre as 19 features padronizadas; 
score por município; Top 30 narrável (identidade + features + score + posição no rank V3).
Leitura qualitativa no relatório.

### 4.7 Publicação — `analytics_ipb_clusters`

Script `scripts/08_publica_clusters_bigquery.py`, 
seguindo o padrão do 07 (lê parquet local consolidado, valida, sobe com `upload_dataframe_to_raw`, carga `WRITE_TRUNCATE`):

| Coluna | Origem |
|---|---|
| `id_municipio`, `nome_municipio`, `sigla_uf`, `nome_regiao`, `estrato_populacional` | identidade |
| `cluster_kmeans`, `cluster_gmm`, `prob_cluster_gmm` | clusterização |
| `arquetipo` | sugestão dos dados (§3.2), validada pelo grupo |
| `prob_tem_agencia_rf`, `pred_tem_agencia_rf`, `prob_tem_correspondente_rf` | classificação |
| `potencial_latente_depositos_pc` | regressão (nulo onde tem agência — não se estima o que já se observa) |
| `score_anomalia`, `flag_anomalia_top30` | anomalias |
| `ipb`, `rank` | referência V3 para cruzamento (não são feature) |
| `_extracted_at` | auditoria (padrão AGENTS.md) |

### 4.8 Relatório

`docs/Relatorio_Modelagem_Etapa3.md`: 
1) contexto e restrição do rótulo proxy;
2) dataset (features, alvos, exclusões); 
3) arquétipos (tabela de perfis + narrativa + boxplot IPB por cluster);
4) classificação (matriz comparativa, resíduos × IPB);
5) regressão (importância no IPB, potencial latente, Spearman);
6) anomalias Top 30;
7) síntese — o que cada modelo responde da pergunta do projeto;
8) limitações (proxy, circularidade, vintage, IPB=0) e melhorias futuras (fase 2).

---

## 5. Fluxo de execução

```bash
# 1. Módulos + testes unitários
poetry run pytest tests/unit -v

# 2. Notebooks (ordem)
notebooks/01_modelagem/01_dataset_e_arquetipos.ipynb      # dataset + clusters + K
notebooks/01_modelagem/02_classificacao_presenca.ipynb    # classificação
notebooks/01_modelagem/03_regressao_anomalias_sintese.ipynb  # regressão + anomalias + consolidação

# 3. Publicação
poetry run python scripts/08_publica_clusters_bigquery.py

# 4. Integridade da tabela publicada
poetry run pytest tests/data_quality/test_analytics_clusters.py -v
```

---

## 6. Validações esperadas (checklist)

- [ ] `modelagem.parquet`: 5.570 linhas, 1 linha por `id_municipio`, 0 nulos nas 19 features, nenhuma coluna de índice;
- [ ] Clusterização: todo município tem cluster K-Means e GMM; probabilidades GMM somam 1; tabela K × métricas gerada;
- [ ] Classificação: métricas calculadas no **teste** (nunca no treino); matriz de comparação completa; resíduos extraídos;
- [ ] Potencial latente: só municípios sem agência recebem estimativa;
- [ ] `analytics_ipb_clusters`: 5.570 linhas, chave única, probabilidades em [0, 1], sem nulos fora `potencial_latente_depositos_pc`;
- [ ] Testes unitários verdes (blobs sintéticos com 2 grupos conhecidos recuperam estrutura; métricas/resíduos/potencial respondem como o esperado em dados de brinquedo);
- [ ] Relatório com as ressalvas da §4.8 impressas.

---

## 7. Ordem sugerida de commits (pequenos e atômicos, em português)

1. `feat: adiciona dataset de modelagem da etapa 3` — `modelagem.py`, `test_modelagem.py`, constante no `config.py`;
2. `feat: adiciona clusterizacao k-means e gmm com metricas e perfis` — `clustering.py`, `test_clustering.py`;
3. `feat: adiciona classificacao de presenca bancaria com metricas completas` — `classificacao.py` (binário), `test_classificacao.py`;
4. `feat: adiciona classificador de arquetipos multiclasse` — função no mesmo módulo + teste;
5. `feat: adiciona regressao do ipb e potencial latente` — `regressao.py`, `test_regressao.py`;
6. `feat: adiciona deteccao de anomalias com isolation forest` — `anomalias.py`, `test_anomalias.py`;
7. `feat: adiciona notebooks de modelagem da etapa 3` — `notebooks/01_modelagem/`;
8. `feat: adiciona publicacao da tabela analytics_ipb_clusters` — `scripts/08_publica_clusters_bigquery.py`, `tests/data_quality/test_analytics_clusters.py`;
9. `docs: adiciona relatorio da etapa 3 de modelagem` — `docs/Relatorio_Modelagem_Etapa3.md` + atualização do `AGENTS.md` (seção 1).

---

## 8. Riscos e fallbacks

| Cenário | Ação |
|---|---|
| Silhouette baixa (< 0,2) para todo K | Reportar como resultado honesto; fase 2 avalia menos variáveis/PCA |
| GMM com convergência ruim | Aumentar `reg_covar`, ajustar `max_iter`, documentar |
| Variáveis de cauda longa (Pix pc, depósitos pc) distorcendo distâncias | Avaliar `log1p` por variável no notebook; decisão registrada |
| Métricas de classificação fracas (ROC-AUC ~ 0,5) | Também é resultado: presença bancária pouco explicada pelas features → discussão no relatório |
| Cluster com mais de um "rosto" | Subir/descer K; legibilidade manda na decisão final |

---

## 9. Pós-escopo (fase 2, registrado sem compromisso)

PCA como validação do índice, Agglomerative/dendrograma, validação espacial por região (treina em 4, testa na 5ª), mais tuning, `idhm` como feature opcional.

---

*Baseado em `referencias/DISCUSSAO_MODELOS_ETAPA3.md` (v2, escopo travado em 2026-09-11). Convenções do projeto: Poetry, scikit-learn apenas, testes por módulo, tabelas `analytics_*` com auditoria, commits pequenos e atômicos.*
