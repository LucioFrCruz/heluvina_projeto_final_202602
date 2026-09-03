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

7. **Cultura de Testes Rigorosa**:
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

**ESCOPO DA SESSÃO (próximos passos):**
- Validação de negócio dos Top 100 e escolha da versão oficial do IPB.
- Clusterização/ML (Etapa 3) e enriquecimentos (4G/5G, CNPJ/Caged, dados de visitação para a flag de turismo).
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
│   ├── Arquitetura_Tecnica.md
│   └── Guia_de_Coleta.md
├── src/
│   ├── __init__.py
│   ├── config.py                # centraliza paths, URLs, nomes de tabelas, constantes
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── ibge.py              # funções para códigos IBGE, localidades, joins
│   │   ├── bigquery.py          # cliente BigQuery, upload/download
│   │   └── storage.py           # leitura de arquivos locais (csv/xlsx)
│   ├── ingestors/               # um módulo por fonte de dados
│   │   ├── __init__.py
│   │   ├── ibge_localidades.py  # API
│   │   ├── sidra_censo_2022.py  # API
│   │   ├── ibge_cempre.py       # API (CEMPRE/SIDRA 9528, série 2022+)
│   │   ├── ibge_pib_municipios.py  # XLSX manual
│   │   ├── bcb_pix.py           # API
│   │   ├── bcb_correspondentes.py  # API OData BCB (cache idempotente)
│   │   ├── anatel_banda_larga_fixa.py  # CSV manual
│   │   ├── bcb_estban.py        # CSV manual
│   │   └── pnud_idhm.py         # XLSX manual (se disponível)
│   ├── preparacao/              # scripts de limpeza e consolidação trusted
│   │   ├── __init__.py
│   │   └── trusted_municipios.py
│   └── analytics/               # cálculo das 3 versões do IPB (V1/V2/V3)
│       ├── __init__.py
│       └── ipb.py
├── scripts/
│   └── 07_publica_ipb_bigquery.py  # publica analytics_ipb_* no BigQuery
├── data/
│   ├── raw/                     # dumps locais temporários (não commitados)
│   └── processed/               # resultados intermediários (não commitados)
├── notebooks/
│   └── 00_exploracao/           # EDA (7 notebooks, incl. 05 de comparação das abordagens)
└── tests/
    ├── unit/                    # testes pequenos para utilitários e módulos
    ├── integration/             # teste de conexão BigQuery
    └── data_quality/            # integridade da trusted e das analytics_ipb_*
```

**Regra de ouro**: nenhum dado bruto ou credencial entra no Git. Apenas código, SQL, documentação e configuração segura.

> **Nota sobre o desenho aprovado**: adotado cache local em Parquet (`data/raw/<fonte>/*.parquet`) como estágio intermediário seguro antes da carga no BigQuery. Isso permite persistência local temporária, idempotência e reprocessamento sem sobrecarregar as APIs.

---

## 3. Tecnologias e dependências

- **Python 3.10+**
- **Google Cloud SDK** (`gcloud`) — autenticação local opcional, mas recomendada.
- **BigQuery** via `google-cloud-bigquery` — camada de persistência.
- **Pandas / Polars** — manipulação de dados (escolher um e manter).
- **Requests** — consumo de APIs HTTP.
- **python-dotenv** — carregamento de variáveis de ambiente locais.
- **openpyxl** — leitura de arquivos Excel (.xlsx).

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

- Nunca commitar arquivos `.env`, JSON de service account ou qualquer secret.
- Criar `.env.example` com as chaves necessárias e valores fictícios.
- Autenticação local no BigQuery pode ser feita de duas formas:
  1. `gcloud auth application-default login` (recomendado para desenvolvimento local).
  2. Variável `GOOGLE_APPLICATION_CREDENTIALS` apontando para um JSON de service account fora do repo.
- Variáveis esperadas (exemplo):
  ```bash
  GCP_PROJECT_ID=meu-projeto-ipb
  BIGQUERY_DATASET=ipb_staging
  BIGQUERY_LOCATION=US
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

# 4. Rodar um ingestor específico
poetry run python -m src.ingestors.ibge_pib_municipios

# 5. Rodar a consolidação trusted
poetry run python -m src.preparacao.trusted_municipios

# 6. Publicar as 3 versões do IPB (camada analytics_)
poetry run python scripts/07_publica_ipb_bigquery.py
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
- **Estban**: Apenas ~2.900 municípios possuem agências. Os outros devem receber imputação zero para `quantidade_agencias`, `volume_depositos`, etc.
- **PIB**: A coluna `va_servicos` teve o mapeamento corrigido no ingestor `ibge_pib_municipios.py`; validar se agora vem preenchida no trusted.
- **IDHM**: Mantido como variável histórica (2010) via Ipeadata. O indicador principal de capital humano passa a ser a **escolaridade (% ensino médio completo)** do Censo 2022 (SIDRA Tabela 10061).
- **CEMPRE (IBGE, 2024)**: coletado em `raw_ibge_cempre` (unidades locais e pessoal ocupado por município e seção CNAE, via SIDRA 9528) — dimensão PJ/empresarial do potencial bancário. **Integrado à V3 desde 2026-09**: `empregos_formais_por_1000_hab` entra no pilar A (agregado por `agregar_cempre` no script 07); `unidades_alojamento_alimentacao_por_1000_hab` acompanha a tabela como validador objetivo de turismo, sem entrar na fórmula. MEIs excluídos pela fonte (limitação declarada).
- **Correspondentes (BCB/OData, posição 30/08/2026)**: cobre 5.571 municípios — inclui **Boa Esperança do Norte/MT (5101837), município extinto**, que não está no Censo 2022. O pipeline (`agregar_correspondentes_por_tipo`) usa left join a partir da trusted e o caso é coberto por teste de integridade (`tests/data_quality/test_analytics_ipb.py`).
- **Estrato populacional e região**: derivados no pipeline (`derive_estrato`/`derive_regiao`), não existem como colunas na trusted. Faixas oficiais: pequena <50k, média 50–500k, grande >500k (decisão do projeto, Relatório EDA 5.1).
- **Analytics publicadas**: `analytics_ipb_v1_classico`, `analytics_ipb_v2_recalibrado`, `analytics_ipb_v3_presenca_completa` e `analytics_ipb_comparacao` (5.570 linhas cada, integridade testada). Nomes oficiais: V1 Clássico, V2 Recalibrado, V3 Presença Bancária Completa (ex-Abordagem 2).

> **Disclaimer de vintage**: o `trusted_municipios` combina diferentes anos de referência (Censo 2022, PIB 2023, Pix 2023/2024, Anatel/Estban 2026, Correspondentes 30/08/2026, CEMPRE 2024, IDHM 2010). Esse mix é uma limitação declarada do projeto e deve ser mencionado na EDA e apresentação final.

> **Base dos Dados**: reservada para validação cruzada futura, não como fonte primária do pipeline.

---

## 10. Evolução Futura (Etapa 3 - Não focar agora)

- O cálculo do índice já foi realizado em 3 versões comparadas (seção 1). Resta:
  - **Validação de negócio** dos Top 100 e escolha da versão oficial do IPB;
  - **Sensibilidade/ajuste fino** de pesos e da flag de turismo;
  - **ML para clusterização** (arquétipos de municípios) e possível modelo residual;
  - **Enriquecimentos**: cobertura 4G/5G (pilar C), CNPJ/MEI + Caged, dados de visitação (Embratur/MTur) para a flag de turismo.

---

## 11. Modo Autônomo (Sessões com Agente)

- Ao receber um plano de implementação para EDA (Análise Exploratória), crie os scripts/notebooks sem pausar para confirmações.
- Decida sozinho técnicas de preenchimento de nulos (ex: `fillna(0)` para agências bancárias, mediana para dados demográficos).
- Não saia apagando/modificando as tabelas *Raw*; limite-se a criar visualizações, limpar a *Trusted* e gerar uma *Analytical* se julgar necessário.
- Proibido em qualquer hipótese: `rm -rf` fora de `data/`, `git push`, `git reset --hard`, `git clean`, expor conteúdo de `.env` ou credenciais.
---

*Última atualização: V3 enriquecida com empregos formais do CEMPRE no pilar A (agregado `agregar_cempre`, analytics republicadas), ingestor oficial de correspondentes bancários (BCB/OData) e testes de integridade — v6.*
