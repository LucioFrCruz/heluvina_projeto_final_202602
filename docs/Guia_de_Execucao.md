# Guia de Execução Técnica do Pipeline (IPB)

Este documento detalha o passo a passo para configurar o ambiente, garantir a presença das bases manuais, executar os scripts de ingestão e validar os dados no BigQuery.

---

## 1. Pré-requisitos e Configuração de Ambiente

O projeto utiliza **Poetry** para gerenciamento de dependências e requer Python 3.10+. 

1. **Instale as dependências:**
   ```bash
   poetry config virtualenvs.in-project true
   poetry install
   ```

2. **Autenticação GCP:**
   O projeto requer acesso ao Google Cloud Platform (BigQuery).
   - Copie o arquivo `.env.example` para `.env`
   - Preencha o `GCP_PROJECT_ID` e aponte o `GOOGLE_APPLICATION_CREDENTIALS` para o seu arquivo JSON de Service Account (que deve estar obrigatoriamente ignorado no git, ex: na pasta `credentials/`).

---

## 2. Bases Manuais agora no Data Lake (GCS) ☁️

Anteriormente, era necessário baixar manualmente arquivos pesados (CSV e XLSX) para a pasta `data/raw/`. Para melhorar a reprodutibilidade, todas as bases manuais foram migradas para um **Bucket no Google Cloud Storage (GCS)** (`ipb-raw-data-mba-projetc-final`).

- **IBGE PIB dos Municípios**
- **BCB Estban (Estatística Bancária)**
- **Anatel Banda Larga Fixa**

> **Nota:** Todos os dados, sejam APIs ou arquivos estáticos, são consumidos automaticamente do Data Lake no GCS ou de endpoints públicos. Nenhuma ação manual de download é necessária por parte dos engenheiros.

---

## 3. Ordem de Execução do Pipeline

Com o ambiente configurado, execute os ingestores na seguinte ordem (do nível fundacional até a consolidação). Todos os scripts fazem *replace* na tabela de destino e baixam seus dados automaticamente.

```bash
# 1. Base Mestra de Localidades (API)
poetry run python -m src.ingestors.ibge_localidades

# 2. Demografia e Escolaridade (SIDRA Censo 2022)
poetry run python -m src.ingestors.sidra_censo_2022

# 3. Transações Pix (API)
poetry run python -m src.ingestors.bcb_pix

# 4. Dados Baixados via GCS Data Lake
poetry run python -m src.ingestors.ibge_pib_municipios
poetry run python -m src.ingestors.bcb_estban
poetry run python -m src.ingestors.anatel_banda_larga_fixa

# 5. IDHM histórico (API Ipeadata — Censo 2010)
poetry run python -m src.ingestors.pnud_idhm

# 6. Correspondentes bancários (API OData BCB — cache idempotente)
poetry run python -m src.ingestors.bcb_correspondentes

# 6.1 CEMPRE — empregos formais por município (API SIDRA, tabela 9528)
poetry run python -m src.ingestors.ibge_cempre

# 7. Consolidação (Camada Trusted)
poetry run python -m src.preparacao.trusted_municipios

# 8. Publicação das 3 versões do IPB (Camada Analytics)
#    Lê trusted + correspondentes + CEMPRE do BQ, calcula V1/V2/V3,
#    sobe analytics_ipb_* e regenera docs/Comparacao_Tres_Abordagens_IPB.md
poetry run python scripts/07_publica_ipb_bigquery.py
```

---

## 4. Validação e Consultas no BigQuery

Após a execução, os dados estarão no dataset `ipb_staging`. Abaixo estão as consultas recomendadas para homologar os dados com a sua equipe.

> **Disclaimer de vintage**: o `trusted_municipios` combina diferentes anos de referência (Censo 2022, PIB 2023, Pix 2023/2024, Anatel/Estban 2026, IDHM 2010). Esse mix é uma limitação declarada do projeto e deve ser mencionado na EDA e apresentação final.

### 4.1. Visão Completa (Camada Trusted)
*Os 10 municípios com maior volume transacionado no Pix (e seus PIBs).*
```sql
SELECT 
    sigla_uf,
    nome_municipio,
    FORMAT("%'d", CAST(populacao_total AS INT64)) AS populacao,
    ROUND(pix_total_volume_12m / 1000000, 2) AS volume_pix_milhoes,
    ROUND(pib_per_capita, 2) AS pib_per_capita_reais,
    quantidade_agencias
FROM 
    `mba-projetc-final.ipb_staging.trusted_municipios`
WHERE 
    pix_total_volume_12m > 0
ORDER BY 
    pix_total_volume_12m DESC
LIMIT 10;
```

### 4.2. Infraestrutura Digital (Anatel)
*Top 5 municípios com maior densidade de Banda Larga por Região.*  
A tabela `raw_anatel_banda_larga_fixa` utiliza a coluna `densidade` (acessos por 100 hab.).
```sql
WITH Ranked AS (
  SELECT 
    t.nome_regiao,
    t.nome_municipio,
    a.densidade AS densidade_banda_larga,
    ROW_NUMBER() OVER(PARTITION BY t.nome_regiao ORDER BY a.densidade DESC) as rank
  FROM 
    `mba-projetc-final.ipb_staging.raw_anatel_banda_larga_fixa` a
  JOIN 
    `mba-projetc-final.ipb_staging.trusted_municipios` t
    ON a.id_municipio = t.id_municipio
  WHERE t.nome_regiao IS NOT NULL
)
SELECT * FROM Ranked WHERE rank <= 5 ORDER BY nome_regiao, rank;
```

### 4.3. Presença Bancária Física (Estban)
*Municípios desbancarizados fisicamente mas com alto volume de depósitos.*
```sql
SELECT 
    t.nome_municipio,
    t.sigla_uf,
    e.quantidade_agencias,
    ROUND(e.volume_depositos / 1000000, 2) AS volume_depositos_milhoes
FROM 
    `mba-projetc-final.ipb_staging.raw_bcb_estban` e
JOIN 
    `mba-projetc-final.ipb_staging.trusted_municipios` t 
    ON e.id_municipio = t.id_municipio
WHERE 
    e.quantidade_agencias < 5
ORDER BY 
    e.volume_depositos DESC
LIMIT 15;
```

### 4.4. Setor de Serviços (PIB IBGE)
*Municípios com economias historicamente dependentes de serviços.*  
A coluna `va_servicos` existe apenas na `raw_pib_municipios` e mapeia o "Valor adicionado bruto dos Serviços" do XLSX do IBGE. **Nota:** a rubrica está nula para 2023 no arquivo de origem; por isso não foi propagada para a `trusted_municipios`.
```sql
SELECT 
    id_municipio,
    pib,
    va_servicos,
    ROUND((va_servicos / NULLIF(pib, 0)) * 100, 2) AS pct_servicos_no_pib
FROM 
    `mba-projetc-final.ipb_staging.raw_pib_municipios`
WHERE 
    pib > 0
    AND va_servicos IS NOT NULL
ORDER BY 
    pct_servicos_no_pib DESC
LIMIT 10;
```

### 4.5. Índice de Potencial Bancário (Camada Analytics)
*Top 10 oportunidades da V3 (IPB Presença Bancária Completa), com os ranks nas outras versões para comparação.*  
As tabelas `analytics_ipb_*` são publicadas por `scripts/07_publica_ipb_bigquery.py`; integridade validada por `tests/data_quality/test_analytics_ipb.py`.
```sql
SELECT 
    c.nome_municipio,
    c.sigla_uf,
    c.estrato_populacional,
    ROUND(v3.ipb, 2) AS ipb_v3,
    c.rank_v1,
    c.rank_v2,
    c.rank_v3
FROM 
    `mba-projetc-final.ipb_staging.analytics_ipb_v3_presenca_completa` v3
JOIN 
    `mba-projetc-final.ipb_staging.analytics_ipb_comparacao` c
    ON v3.id_municipio = c.id_municipio
ORDER BY 
    v3.rank
LIMIT 10;
```
