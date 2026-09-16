# AGENTS.md — Diretrizes e Convenções do Projeto (IPB)

> **AVISO PARA TODOS OS AGENTES DE IA**: Este documento é a fonte primária de regras e memória deste repositório. Qualquer agente (Claude, GPT, Kimi, Gemini, Antigravity, etc.) deve ler, memorizar e seguir rigorosamente estas diretrizes ao iniciar uma sessão.

---

## 0. Diretrizes Mandatórias de Comportamento para Agentes

1. **Postura Crítica e Analítica (Não seja apenas concordante)**:
   - Não seja um "yes-man". Analise criticamente todas as propostas do usuário.
   - Aponte riscos técnicos, armadilhas de engenharia de dados, impactos em custo e sugira alternativas mais eficientes sempre que pertinente.

2. **Política Estrita de Commits Pequenos e Atômicos**:
   - Faça commits estritamente modulares e pequenos (uma única alteração lógica por commit).
   - Nunca acumule arquivos de múltiplos módulos ou ingestores em um único commit gigante.
   - Mensagens de commit em português, no padrão convencional e no imperativo (`feat: ...`, `fix: ...`, `test: ...`, `docs: ...`, `chore: ...`).

3. **Gerenciador de Dependências: Poetry**:
   - O projeto utiliza **Poetry** exclusivamente para gerenciamento de dependências e ambiente virtual (`poetry.lock`).
   - Todos os comandos devem rodar via `poetry run ...` ou dentro do `poetry shell`.
   - O ambiente virtual deve residir localmente em `.venv/` (`poetry config virtualenvs.in-project true`).

4. **Premissa de Custo Zero Absoluto (Free Tier)**:
   - BigQuery configurado estritamente na localização **`US`** (multi-região padrão do Always Free / Sandbox, que não exige cartão nem conta de faturamento ativa).

5. **Segurança de Credenciais (Zero Secrets no Git)**:
   - Desenvolvimento local utiliza **Application Default Credentials (ADC)** via `gcloud auth application-default login`.
   - Nunca baixar ou armazenar chaves JSON de service account dentro da pasta do repositório.
   - Segredos e configurações de ambiente ficam exclusivamente no `.env` (ignorado no Git).

6. **Cache / Estágio Local em Parquet**:
   - Todo ingestor deve salvar dados brutos em `data/raw/<fonte>/*.parquet` antes de subir para o BigQuery (`raw_*`).
   - Isso garante idempotência, desacoplamento e evita re-execuções desnecessárias contra APIs públicas.

7. **Fontes Manuais: Estágio Obrigatório no GCS**:
   - Toda fonte obtida por **download manual** (PIB dos Municípios, Estban, Anatel) deve ser enviada ao bucket GCS do projeto (`GCS_BUCKET_NAME`, ex.: `ipb-raw-data-mba-projetc-final`, prefixos `pib/`, `estban/`, `anatel/`).
   - O download na origem é **pontual (feito uma única vez)**; a partir daí, os ingestores baixam automaticamente do GCS via `src/utils/gcs.py` (`download_file_from_gcs`).
   - **Nunca reintroduzir etapa manual no pipeline** — quem for executar o projeto não deve precisar baixar arquivo nenhum. Ao adicionar uma nova fonte manual, subir o arquivo ao GCS e registrar o prefixo neste documento (§2) e no `docs/Guia_de_Execucao.md`.

8. **AGENTS.md Sempre Atualizado (memória oficial do projeto)**:
   - **Qualquer mudança estrutural** — novo módulo, ingestor, script, notebook, tabela `raw_/trusted_/analytics_`, diretriz ou decisão de negócio — deve atualizar o AGENTS.md **no mesmo commit**.
   - Ao final de qualquer sessão de trabalho, o agente deve revisar se §1 (status), §2 (estrutura), §3 (tecnologias), §9 (decisões/gaps) e §10 (próximos passos) ainda refletem a realidade do repositório. Se divergirem, corrigir antes de encerrar.

9. **Cultura de Testes Rigorosa**:
   - Todo módulo ou parser em `src/utils/`, `src/ingestors/` e `src/analytics/` deve ter testes unitários correspondentes em `tests/unit/`.
   - Teste de conexão GCP em `tests/integration/test_bq_connection.py`.
   - Testes de integridade na camada `trusted` e nas tabelas `analytics_ipb_*` (`tests/data_quality/`) validando os 5.570 municípios.

---

## 1. Objetivo e Estado do Projeto (Contexto da IA)

Esta base de código entrega o **Índice de Potencial Bancário (IPB)**.

**STATUS ATUAL:**
- **Etapa 1 (Engenharia de Dados e Ingestão): CONCLUÍDA.** Todos os ingestores implementados (Poetry, BigQuery), incluído o de **correspondentes bancários** (`src/ingestors/bcb_correspondentes.py`, fonte oficial BCB/OData, cache parquet idempotente).
- **Etapa 2 (EDA + Índice): comparação das 3 abordagens CONCLUÍDA e PUBLICADA.** As 3 versões do IPB estão em produção na camada `analytics_` do BigQuery:
  - `analytics_ipb_v1_classico` — fórmula original, pesos iguais;
  - `analytics_ipb_v2_recalibrado` — pesos diferenciados + `tensao_digital_bancaria`;
  - `analytics_ipb_v3_presenca_completa` — correspondentes por tipo + flag de turismo suave + `empregos_formais_por_1000_hab` (CEMPRE) no pilar A (ex-"Abordagem 2");
  - `analytics_ipb_comparacao` — visão larga das 3 versões lado a lado.
- Pipeline do índice: `src/analytics/ipb.py` (fórmulas, com testes unitários) + `scripts/07_publica_ipb_bigquery.py` (lê trusted + correspondentes + CEMPRE do BQ e publica). Integridade das tabelas: `tests/data_quality/test_analytics_ipb.py`. A `trusted_municipios` **não** carrega colunas de índice — IPB é produto da camada analytics.
- **Etapa 3 (Modelagem/ML): IMPLEMENTADA e PUBLICADA (2026-09-12).** Sem rótulo de verdade no projeto — modelos usam alvo proxy (declarado). Módulos testáveis em `src/analytics/` (`modelagem.py` com as constantes oficiais de features, `clustering.py`, `classificacao.py`, `regressao.py`, `anomalias.py`) + 3 notebooks executados em `notebooks/01_modelagem/`. Publicação: `scripts/08_publica_clusters_bigquery.py` → **`analytics_ipb_clusters`** (5.570 linhas: identidade, clusters K-Means/GMM com K=6, probabilidades, arquetipo, potencial latente, anomalias; integridade em `tests/data_quality/test_analytics_clusters.py`). Relatório com todos os números: `docs/Relatorio_Modelagem_Etapa3.md`. Decisões e correções metodológicas registradas: transformação `log1p` nas 14 colunas de cauda longa; classificação de presença usa só as 13 exógenas (`FEATURES_SEM_PRESENCA` — variáveis de presença vazam o alvo); alvo tem-correspondente degenerado (100% dos municípios têm correspondente).

**ESCOPO DA SESSÃO (próximos passos):**
- Validação de negócio dos Top 100 e escolha da versão oficial do IPB.
- Iteração da Etapa 3 com o grupo: **K=6 já confirmado (2026-09-14)**; falta validar os nomes dos arquétipos, a leitura dos resíduos da classificação e do Spearman potencial-latente × IPB (0,449).
- Enriquecimentos (4G/5G, CNPJ/Caged, dados de visitação para a flag de turismo).
- Manter a EDA sincronizada com as tabelas `analytics_ipb_*` (notebook 05 lê do BigQuery).

---

## 2. Estrutura de pastas

```
heluvina_projeto_final_202602/
├── README.md
├── AGENTS.md
├── .env.example                 # template de variáveis de ambiente (sem secrets)
├── .gitignore                   # deve ignorar .env, credenciais, caches e outputs locais
├── docs/
│   ├── IPB_Guia_de_Bases_e_Desenho.md
│   ├── Arquitetura_Tecnica.md        # desenho da Etapa 1 (arquivado)
│   ├── Guia_de_Coleta.md             # fontes e contratos de coleta (Etapa 1)
│   ├── Dicionario_de_Dados.md        # schemas de todas as tabelas raw_/trusted_/analytics_
│   ├── Relatorio_EDA.md              # achados da EDA + comparação V1/V2/V3
│   ├── Comparacao_Tres_Abordagens_IPB.md  # gerado pelo script 07
│   ├── Guia_de_Analise_Exploratoria.md / Plano_de_Implementacao_EDA.md  # planejamento Etapa 2
│   ├── Relatorio_Modelagem_Etapa3.md # resultados da Etapa 3 (clusters, classificação, anomalias)
│   ├── Arquetipos_Municipais.md      # perfis dos 6 arquétipos
│   ├── Plano_de_Implementacao_Etapa3_Modelagem.md
│   ├── Plano_de_Implementacao_Apresentacao_Final.md  # plano do site/deck da apresentação de 17/09
│   ├── Apresentacao_Final_IPB.pptx  # versão offline com gráficos nativos e pipeline iconográfica
│   ├── index.html / mapa.html / apresentacao.html / apendice.html  # site estático (GitHub Pages, branch feature/apresentacao)
│   ├── assets/                    # libs vendorizadas, malha IBGE 2022, figuras, pipeline SVG e JS do mapa
│   └── data/municipios.json       # export derivado (script 09) consumido pelo site
├── src/
│   ├── __init__.py
│   ├── config.py                # centraliza paths, nomes de tabelas, dataset, bucket GCS
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── ibge.py              # funções para códigos IBGE, localidades, joins
│   │   ├── bigquery.py          # cliente BigQuery, upload/download
│   │   ├── storage.py           # leitura de arquivos locais (csv/xlsx)
│   │   ├── gcs.py               # download de arquivos das fontes manuais a partir do bucket GCS
│   │   └── eda.py               # utilitários de EDA (figuras, parquet, JSON, outliers)
│   ├── ingestors/               # um módulo por fonte de dados
│   │   ├── __init__.py
│   │   ├── ibge_localidades.py  # API
│   │   ├── sidra_censo_2022.py  # API
│   │   ├── ibge_cempre.py       # API (CEMPRE/SIDRA 9528, série 2022+)
│   │   ├── ibge_pib_municipios.py  # XLSX via GCS (upload pontual, ver Diretriz 0.7)
│   │   ├── bcb_pix.py           # API
│   │   ├── bcb_correspondentes.py  # API OData BCB (cache idempotente)
│   │   ├── anatel_banda_larga_fixa.py  # CSV via GCS
│   │   ├── bcb_estban.py        # CSV via GCS
│   │   └── pnud_idhm.py         # API Ipeadata (OData)
│   ├── preparacao/              # scripts de limpeza e consolidação trusted
│   │   ├── __init__.py
│   │   └── trusted_municipios.py
│   └── analytics/               # índice (V1/V2/V3) + modelagem da Etapa 3
│       ├── __init__.py
│       ├── ipb.py               # fórmulas V1/V2/V3, agregações, gerador da comparação
│       ├── modelagem.py         # constantes oficiais de features (19; 13 exógenas), log1p, split
│       ├── clustering.py        # K-Means/GMM, avaliação de K, regras de nomeação de arquétipos
│       ├── classificacao.py     # presença bancária (alvo proxy)
│       ├── regressao.py         # potencial latente + explicação do IPB
│       └── anomalias.py         # Isolation Forest
├── scripts/
│   ├── 07_publica_ipb_bigquery.py      # publica analytics_ipb_* (V1/V2/V3 + comparação)
│   ├── 08_publica_clusters_bigquery.py # publica analytics_ipb_clusters (Etapa 3)
│   ├── 09_exporta_dados_site.py        # exporta docs/data/municipios.json (só parquet local, sem BigQuery)
│   ├── 10_gera_figuras_apresentacao.py # figuras estáticas (matplotlib) da rodada 1 do deck
│   └── 11_gera_figuras_interativas.py  # figuras interativas (plotly → JSON) do deck atual
├── data/
│   ├── raw/                     # dumps locais temporários (não commitados)
│   └── processed/               # resultados intermediários (não commitados)
├── notebooks/
│   ├── 00_exploracao/           # EDA (7 notebooks, incl. 05 de comparação das abordagens)
│   └── 01_modelagem/            # Etapa 3 (3 notebooks: dataset/arquétipos, classificação, regressão+anomalias)
└── tests/
    ├── unit/                    # testes de utils, ingestores, ipb.py e módulos de modelagem
    ├── integration/             # teste de conexão BigQuery
    └── data_quality/            # integridade da trusted e das analytics_ipb_* (V1/V2/V3 e clusters)
```

**Regra de ouro**: nenhum dado bruto ou credencial entra no Git. Apenas código, SQL, documentação e configuração segura.

> **Nota sobre o desenho aprovado**: adotado cache local em Parquet (`data/raw/<fonte>/*.parquet`) como estágio intermediário seguro antes da carga no BigQuery. Isso permite persistência local temporária, idempotência e reprocessamento sem sobrecarregar as APIs.

---

## 3. Tecnologias e dependências

- **Python 3.10+**
- **Google Cloud SDK** (`gcloud`) — autenticação local via ADC (recomendado).
- **BigQuery** via `google-cloud-bigquery` — camada de persistência (raw/trusted/analytics).
- **Google Cloud Storage** via `google-cloud-storage` — estágio obrigatório das fontes manuais (Diretriz 0.7): bucket `GCS_BUCKET_NAME` com prefixos `pib/`, `estban/`, `anatel/`.
- **Pandas** — manipulação de dados (padrão do projeto; não usar Polars).
- **scikit-learn / scipy** — Etapa 3: clusters (K-Means/GMM), classificação, regressão e anomalias.
- **matplotlib / seaborn / plotly** — EDA e figuras dos relatórios.
- **Requests** — consumo de APIs HTTP.
- **python-dotenv** — carregamento de variáveis de ambiente locais.
- **openpyxl** — leitura de arquivos Excel (.xlsx).
- **pre-commit** (dev) — bloqueio de credenciais e chaves privadas no commit (Diretriz 0.5).

Todas as dependências devem ser declaradas em `pyproject.toml` e travadas em `poetry.lock` (ver Diretriz 0.3 — Poetry exclusivamente; não usar `requirements.txt`).

---

## 4. Padrões de código

### Python

- PEP 8 como base.
- Docstrings no formato Google para funções públicas.
- Funções pequenas e testáveis; cada `ingestor` deve ter uma função principal `coletar()` ou `run()`.
- Logs via `logging` (não `print`). Nível padrão: `INFO`.
- Tratamento explícito de erros: APIs podem falhar; capturar, logar e, quando possível, retentar.

### SQL

- Identificadores em snake_case.
- Comentários em português quando explicam regra de negócio.
- Prefixos de camada obrigatórios:
  - `raw_` — dados brutos, o mais próximo possível da fonte.
  - `trusted_` — dados limpos, tipados e enriquecidos com chaves padronizadas.
  - `analytics_` — agregações e tabelas prontas para consumo (usar no futuro).

### Commits e branches

- Branch sugerida para novos trabalhos: `feature/etapa2-eda-e-limpeza`.
- Commits em português, no imperativo (`feat: adiciona script de imputacao de nulos`).
- Um commit por mudança lógica. Evite commits gigantes.

---

## 5. Credenciais e ambiente

- Nunca commitar arquivos `.env`, JSON de service account ou qualquer secret. O repositório tem **pre-commit** (`.pre-commit-config.yaml`) que bloqueia chaves privadas e JSONs de service account nos commits — mantenha-o instalado com `poetry run pre-commit install`.
- Criar `.env.example` com as chaves necessárias e valores fictícios (o exemplo deve espelhar as variáveis lidas por `src/config.py`).
- Autenticação local no BigQuery pode ser feita de duas formas:
  1. `gcloud auth application-default login` (recomendado para desenvolvimento local).
  2. Variável `GOOGLE_APPLICATION_CREDENTIALS` apontando para um JSON de service account **fora do repo**.
- Variáveis esperadas (exemplo):
  ```bash
  GCP_PROJECT_ID=meu-projeto-ipb
  BIGQUERY_DATASET=ipb_staging
  BIGQUERY_LOCATION=US
  GCS_BUCKET_NAME=ipb-raw-data-mba-projetc-final
  ```

---

## 6. Convenções de tabelas no BigQuery

Dataset padrão: `ipb_staging` (ajustável via `.env`).

| Camada | Prefixo | Exemplo | Conteúdo |
|--------|---------|---------|----------|
| Raw | `raw_` | `raw_sidra_censo_2022` | Dados coletados quase sem alteração. |
| Trusted | `trusted_` | `trusted_municipios` | Dados limpos, com código IBGE padronizado e tipos corretos. |
| Analytics | `analytics_` | `analytics_ipb_v3_presenca_completa` | Produtos finais do IPB (V1/V2/V3 + comparação), publicados por `scripts/07_publica_ipb_bigquery.py`. |

Regras:
- Sempre incluir colunas de auditoria: `_extracted_at`, `_source_url`.
- Chave primária lógica em tabelas municipais: `id_municipio` (código IBGE de 7 dígitos).
- Tabelas `analytics_ipb_*` obrigatórias: identidade (`id_municipio`, `nome_municipio`, `sigla_uf`, `nome_regiao`, `estrato_populacional`), `score_a`…`score_e`, `ipb` (em [0,100]), `rank` e `rank_estrato` (método `min`; empates compartilham posição).
- A camada `trusted_` **nunca** carrega colunas de índice (IPB, scores, ranks) — índice é produto da camada `analytics_`. Features derivadas por abordagem ficam na tabela `analytics_` correspondente.

---

## 7. Execução local

Fluxo sugerido para rodar a ingestão na máquina:

```bash
# 1. Instalar dependências e ambiente (Poetry, ambiente local em .venv/)
poetry config virtualenvs.in-project true
poetry install

# 2. Configurar variáveis de ambiente
cp .env.example .env
# editar .env com seus valores

# 3. Autenticar no GCP (se necessário)
gcloud auth application-default login

# 3.1 Instalar o pre-commit (bloqueio de credenciais — Diretriz 0.5)
poetry run pre-commit install

# 4. (PONTUAL, uma única vez) Subir os arquivos das fontes manuais ao GCS —
#     depois disso os ingestores baixam sozinhos (Diretriz 0.7):
#   gcloud storage cp pib_municipios_2010_2023.xlsx gs://$GCS_BUCKET_NAME/pib/
#   gcloud storage cp 202603_ESTBAN.CSV          gs://$GCS_BUCKET_NAME/estban/
#   gcloud storage cp Densidade_Banda_Larga_Fixa.csv gs://$GCS_BUCKET_NAME/anatel/

# 5. Rodar um ingestor específico
poetry run python -m src.ingestors.ibge_pib_municipios

# 6. Rodar a consolidação trusted
poetry run python -m src.preparacao.trusted_municipios

# 7. Publicar as 3 versões do IPB (camada analytics_)
poetry run python scripts/07_publica_ipb_bigquery.py

# 8. Etapa 3: executar os 3 notebooks de notebooks/01_modelagem/ (01→02→03)
#    e publicar os clusters
poetry run python scripts/08_publica_clusters_bigquery.py
```

---

## 8. Critérios de qualidade da ingestão

Antes de marcar uma fonte como "coletada", verificar:

- [ ] Quantidade de municípios próxima a 5.570 (ou ao esperado para a fonte).
- [ ] Código IBGE de 7 dígitos presente e válido.
- [ ] Tipos de dados corretos (numérico, data, string).
- [ ] Não há duplicatas por `id_municipio` + chave temporal (quando aplicável).
- [ ] Registro de origem (`_source_url`) preenchido.
- [ ] Upload para BigQuery concluído sem erros.

---

## 9. Status da Consolidação (Trusted) e Analytics

A tabela `trusted_municipios` possui os 5.570 municípios. Principais *gaps* e decisões conhecidas:
- **Internet (Censo 2022)**: A tabela 7307 do SIDRA retorna HTTP 500 para `N6[all]` desde agosto/2026. A coluna `domicilios_com_internet_pct` permanece nula; usar `banda_larga_fixa_por_100_hab` (Anatel) como proxy na EDA.
- **Estban**: 2.915 municípios possuem registro (presença bancária). Os demais 2.655 recebem imputação zero para `quantidade_agencias`, `volume_depositos`, etc. (decisão declarada no Relatório EDA).
- **PIB**: a rubrica `va_servicos` **não é divulgada pelo IBGE para 2023** no arquivo de origem. Decisão registrada (2026-09-14): a coluna fica **somente na `raw_pib_municipios`** e não é propagada para a trusted; o VA de serviços não compõe o índice. Não há pendência de validação.
- **IDHM**: Mantido como variável histórica (2010) via Ipeadata. O indicador principal de capital humano passa a ser a **escolaridade (% ensino médio completo)** do Censo 2022 (SIDRA Tabela 10061).
- **CEMPRE (IBGE, 2024)**: coletado em `raw_ibge_cempre` (unidades locais e pessoal ocupado por município e seção CNAE, via SIDRA 9528) — dimensão PJ/empresarial do potencial bancário. **Integrado à V3 desde 2026-09**: `empregos_formais_por_1000_hab` entra no pilar A (agregado por `agregar_cempre` no script 07); `unidades_alojamento_alimentacao_por_1000_hab` acompanha a tabela como validador objetivo de turismo, sem entrar na fórmula. MEIs excluídos pela fonte (limitação declarada).
- **Correspondentes (BCB/OData, posição 30/08/2026)**: cobre 5.571 municípios — inclui **Boa Esperança do Norte/MT (5101837), município extinto**, que não está no Censo 2022. O pipeline (`agregar_correspondentes_por_tipo`) usa left join a partir da trusted e o caso é coberto por teste de integridade (`tests/data_quality/test_analytics_ipb.py`).
- **Estrato populacional e região**: derivados no pipeline (`derive_estrato`/`derive_regiao`), não existem como colunas na trusted. Faixas oficiais: pequena <50k, média 50–500k, grande >500k (decisão do projeto, Relatório EDA 5.1).
- **Analytics publicadas**: `analytics_ipb_v1_classico`, `analytics_ipb_v2_recalibrado`, `analytics_ipb_v3_presenca_completa` e `analytics_ipb_comparacao` (5.570 linhas cada, integridade testada). Nomes oficiais: V1 Clássico, V2 Recalibrado, V3 Presença Bancária Completa (ex-Abordagem 2).

> **Disclaimer de vintage**: o `trusted_municipios` combina diferentes anos de referência (Censo 2022, PIB 2023, Pix ago/2025–ago/2026, Anatel/Estban 2026, Correspondentes 30/08/2026, CEMPRE 2024, IDHM 2010). Esse mix é uma limitação declarada do projeto e deve ser mencionado na EDA e apresentação final.

> **Base dos Dados**: reservada para validação cruzada futura, não como fonte primária do pipeline.

---

## 10. Evolução Futura (pós-Etapa 3)

- O cálculo do índice já foi realizado em 3 versões comparadas (seção 1) e a modelagem da Etapa 3 está implementada e publicada. Resta:
  - **Validação de negócio** dos Top 100 e escolha da versão oficial do IPB;
  - **Iteração da Etapa 3 com o grupo**: **K=6 confirmado (2026-09-14)**; falta validar os nomes dos arquétipos (sugestões por regra sobre os dados), a leitura dos resíduos da classificação e do Spearman potencial-latente × IPB (0,449);
  - **Fase 2 da Etapa 3** (registrada no relatório): validação espacial por região, PCA como validação do índice, Agglomerative/dendrograma, `idhm` como feature opcional, discussão de pesos do IPB à luz da importância (banda larga + correspondentes + Pix concentram 0,64+0,29+0,17 da queda de R²);
  - **Enriquecimentos**: cobertura 4G/5G (pilar C), CNPJ/MEI + Caged, dados de visitação (Embratur/MTur) para a flag de turismo.
- **Site da apresentação final (17/09)**: deck HTML interativo (reveal.js), mapa coroplético municipal (D3 + malha IBGE 2022) e apêndice de backup, tudo em `docs/` na branch `feature/apresentacao` e servido via GitHub Pages; dados exportados por `scripts/09` e figuras por `scripts/11`. Plano em `docs/Plano_de_Implementacao_Apresentacao_Final.md`.

---

## 11. Modo Autônomo (Sessões com Agente)

- Ao receber um plano de implementação para EDA (Análise Exploratória), crie os scripts/notebooks sem pausar para confirmações.
- Decida sozinho técnicas de preenchimento de nulos (ex: `fillna(0)` para agências bancárias, mediana para dados demográficos).
- Não saia apagando/modificando as tabelas *Raw*; limite-se a criar visualizações, limpar a *Trusted* e gerar uma *Analytical* se julgar necessário.
- Proibido em qualquer hipótese: `rm -rf` fora de `data/`, `git push`, `git reset --hard`, `git clean`, expor conteúdo de `.env` ou credenciais.
---

*Última atualização (2026-09-14, v7): sincronização pós-Etapa 3 — estrutura de pastas ampliada (módulos de modelagem, script 08, notebooks/01_modelagem), Diretriz 0.7 (fontes manuais com estágio obrigatório no GCS) e Diretriz 0.8 (AGENTS.md sempre atualizado), tecnologias (GCS, scikit-learn, pre-commit), §9 com decisões registradas (Estban 2.915, `va_servicos` descartada da trusted) e K=6 confirmado.*
