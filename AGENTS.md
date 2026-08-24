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
   - Todo módulo ou parser em `src/utils/` e `src/ingestors/` deve ter testes unitários correspondentes em `tests/unit/`.
   - Teste de conexão GCP em `tests/integration/test_bq_connection.py`.
   - Testes de integridade na camada `trusted` (`tests/data_quality/`) validando os 5.570 municípios.

---

## 1. Objetivo do Projeto

Esta branch entrega o **desenho e a estrutura de ingestão/coleta** do Índice de Potencial Bancário (IPB).

Escopo atual:
- Coletar os indicadores do **NÚCLEO** definidos em `docs/IPB_Guia_de_Bases_e_Desenho.md`.
- Persistir os dados brutos e processados no **BigQuery** (camada `raw` e `trusted`).
- Executar os scripts localmente (máquina dos integrantes) nesta primeira versão.
- Manter o projeto pronto para evoluir para orquestração via GitHub Actions no futuro.

Não sair do escopo sem aprovação: nenhum modelo de ML, EDA profunda ou dashboard entra aqui.

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
│   │   ├── ibge_pib_municipios.py  # XLSX manual
│   │   ├── bcb_pix.py           # API
│   │   ├── anatel_banda_larga_fixa.py  # CSV manual
│   │   ├── bcb_estban.py        # CSV manual
│   │   └── pnud_idhm.py         # XLSX manual (se disponível)
│   └── preparacao/              # scripts de limpeza e consolidação trusted
│       ├── __init__.py
│       └── trusted_municipios.py
├── sql/
│   └── trusted/
│       └── create_trusted_municipios.sql
├── data/
│   ├── raw/                     # dumps locais temporários (não commitados)
│   └── processed/               # resultados intermediários (não commitados)
├── notebooks/
│   └── 00_exploracao/           # EDA futura; nada aqui ainda
└── tests/
    └── unit/                    # testes pequenos para utilitários
```

**Regra de ouro**: nenhum dado bruto ou credencial entra no Git. Apenas código, SQL, documentação e configuração segura.

> **Nota sobre o desenho aprovado**: adotado cache local em Parquet (`data/raw/<fonte>/*.parquet`) como estágio intermediário seguro antes da carga no BigQuery. Isso permite persistência local temporária, idempotência e reprocessamento sem sobrecarregar as APIs.

---

## 3. Tecnologias e dependências

- **Python 3.11+**
- **Google Cloud SDK** (`gcloud`) — autenticação local opcional, mas recomendada.
- **BigQuery** via `google-cloud-bigquery` — camada de persistência.
- **Pandas / Polars** — manipulação de dados (escolher um e manter).
- **Requests** — consumo de APIs HTTP.
- **python-dotenv** — carregamento de variáveis de ambiente locais.
- **openpyxl** — leitura de arquivos Excel (.xlsx).

Todas as dependências devem ser listadas em `requirements.txt` (a ser criado na fase de implementação).

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

- Branch atual: `feature/etapa1-processamento-ingestao` (ou nome acordado pelo time).
- Commits em português, no imperativo:
  - `feat: adiciona ingestor do PIB municipal`
  - `docs: atualiza schema do BigQuery`
  - `fix: corrige parsing de código IBGE no SIDRA`
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
| Analytics | `analytics_` | `analytics_ipb_ranking` | Agregações e produtos finais (futuro). |

Regras:
- Sempre incluir colunas de auditoria: `_extracted_at`, `_source_url`.
- Chave primária lógica em tabelas municipais: `id_municipio` (código IBGE de 7 dígitos).

---

## 7. Execução local

Fluxo sugerido para rodar a ingestão na máquina:

```bash
# 1. Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate

# 2. Instalar dependências (quando existir)
pip install -r requirements.txt

# 3. Configurar variáveis de ambiente
cp .env.example .env
# editar .env com seus valores

# 4. Autenticar no GCP (se necessário)
gcloud auth application-default login

# 5. Rodar um ingestor específico
python -m src.ingestors.ibge_pib_municipios

# 6. Rodar a consolidação trusted
python -m src.preparacao.trusted_municipios
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

## 9. Validação das bases baixadas manualmente

Resultado da validação realizada em `2026-08-23`:

| Fonte | Arquivo | Status | Observações |
|---|---|---|---|
| IBGE — PIB dos Municípios | `data/raw/ibge_pib_municipios/PIB dos Municípios - base de dados 2010-2023.xlsx` | ✅ OK | 43 colunas, anos 2010–2023, 5.570 municípios únicos, colunas de PIB e PIB per capita presentes. |
| BCB — Estban | `data/raw/bcb_estaban/202603_ESTBAN.CSV` | ✅ OK | Encoding `latin1`, delimitador `;`, 7.972 linhas, coluna `CODMUN_IBGE` com código IBGE completo, 2.915 municípios únicos (apenas municípios com presença bancária). |
| Anatel — Densidade Banda Larga Fixa | `data/raw/anatel_banda_larga/Densidade_Banda_Larga_Fixa.csv` | ✅ OK | UTF-8 BOM, delimitador `;`, 5.571 registros no mês mais recente (2026-06), coluna `Código IBGE` preenchida. Banda larga móvel fora do escopo. |
| PNUD — IDHM | — | ❌ Indisponível | Atlas Brasil retornou HTTP 500 no momento do teste; download não realizado. Ver alternativas na seção 10. |

**Implicações para o pipeline**:
- O **IDHM** é o único indicador do NÚCLEO ainda pendente. Se não for possível baixar em 24–48h, usar **escolaridade (% ensino médio+)** do Censo 2022 (SIDRA) como substituto no pilar E.
- O **Estban** cobre apenas ~2.900 municípios. Os demais serão tratados como missing na `trusted_municipios` e imputados/analisados na Etapa 2.
- A **Anatel** fornece apenas banda larga fixa no arquivo baixado; banda larga móvel está fora do escopo.

---

## 10. Alternativas para o IDHM

A fonte original (`Atlas Brasil`) apresentou instabilidade (`HTTP 500`) no momento da validação. Opções:

1. Tentar novamente pelo Atlas Brasil: `https://www.atlasbrasil.org.br`.
2. Página do PNUD/UNDP: `https://www.undp.org/pt/brazil/atlas-dos-municipios`.
3. Base dos Dados: `https://basedosdados.org/dataset/cbfc7253-089b-44e2-8825-755e1419efc8`.
4. **Substituir o IDHM por escolaridade** (`% ensino médio+` ou `anos de estudo`) do Censo 2022 — mantém o pilar E funcional sem depender do Atlas.

---

## 11. Evolução futura (não implementar agora)

- Orquestração via GitHub Actions usando `.github/workflows/ingestao.yml`.
- Workload Identity ou service account key no GitHub Secret para autenticação no BigQuery.
- Agendamento mensal para fontes como Pix e Estban.
- Testes automatizados com `pytest`.

## 12. Modo Autônomo (Sessões com Agente)

- Ao receber um plano de implementação, execute-o do início ao fim **sem pausar para confirmações**.
- Decida sozinho detalhes de implementação não especificados (nomes internos, estrutura de funções, libs auxiliares).
- Se algo falhar, diagnostique, corrija e tente novamente até 3x antes de desistir.
- Ao final de cada fase, rode os testes correspondentes antes de avançar e dê um resumo do que foi feito.
- **Só pare para perguntar se**: faltar credencial, uma API pública estiver fora do ar, ou o plano se contradizer.
- Proibido em qualquer hipótese: `rm -rf` fora de `data/`, `git push`, `git reset --hard`, `git clean`, expor conteúdo de `.env` ou credenciais, instalar dependências fora do Poetry.
---

*Última atualização: branch de ingestão e coleta — v2.*
