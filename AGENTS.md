# AGENTS.md — Ingestão e Coleta de Dados (IPB)

## 1. Objetivo desta branch

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
│   └── Arquitetura_Tecnica.md
├── src/
│   ├── __init__.py
│   ├── config.py                # centraliza paths, URLs, nomes de tabelas, constantes
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── ibge.py              # funções para códigos IBGE, localidades, joins
│   │   ├── bigquery.py          # cliente BigQuery, upload/download
│   │   └── storage.py           # salvamento local temporário (parquet/csv)
│   ├── ingestors/               # um módulo por fonte de dados
│   │   ├── __init__.py
│   │   ├── ibge_localidades.py
│   │   ├── sidra_censo_2022.py
│   │   ├── ibge_pib_municipios.py
│   │   ├── bcb_pix.py
│   │   ├── anatel_banda_larga.py
│   │   ├── bcb_estban.py
│   │   └── pnud_idhm.py
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

---

## 3. Tecnologias e dependências

- **Python 3.11+**
- **Google Cloud SDK** (`gcloud`) — autenticação local opcional, mas recomendada.
- **BigQuery** via `google-cloud-bigquery` — camada de persistência.
- **Pandas / Polars** — manipulação de dados (escolher um e manter; Polars é mais rápido para grandes volumes).
- **Requests** — consumo de APIs HTTP.
- **python-dotenv** — carregamento de variáveis de ambiente locais.
- **PyArrow / fastparquet** — cache local em Parquet.

Todas as dependências devem ser listadas em `requirements.txt` (a ser criado na fase de implementação).

---

## 4. Padrões de código

### Python

- PEP 8 como base.
- Docstrings no formato Google para funções públicas.
- Funções pequenas e testáveis; cada `ingestor` deve ter uma função principal `coletar()` ou `run()`.
- Logs via `logging` (não `print`). Nível padrão: `INFO`.
- Tratamento explícito de erros: APIs podem falhar; capturar, logar e, quando possível, retentar.
- Cache local em Parquet para evitar re-downloads durante desenvolvimento.

### SQL

- Identificadores em snake_case.
- Comentários em português quando explicam regra de negócio.
- Prefixos de camada obrigatórios:
  - `raw_` — dados brutos, o mais próximo possível da fonte.
  - `trusted_` — dados limpos, tipados e enriquecidos com chaves padronizadas.
  - `analytics_` — agregações e tabelas prontas para consumo (usar no futuro).

### Commits e branches

- Branch atual: `ingestao-coleta` (ou nome acordado pelo time).
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
  BIGQUERY_LOCATION=southamerica-east1
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

## 9. Evolução futura (não implementar agora)

- Orquestração via GitHub Actions usando `.github/workflows/ingestao.yml`.
- Workload Identity ou service account key no GitHub Secret para autenticação no BigQuery.
- Agendamento mensal para fontes como Pix e Estban.
- Testes automatizados com `pytest`.

---

*Última atualização: branch de ingestão e coleta — v1.*
