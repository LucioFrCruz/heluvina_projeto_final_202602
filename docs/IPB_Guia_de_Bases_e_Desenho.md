# Mapa do Potencial Bancário Brasileiro
## Guia de bases de dados e desenho do Índice de Potencial Bancário (IPB)
### v2 — alinhado ao cronograma da disciplina (MBA em Engenharia de Dados)

---

## 1. Contexto e pergunta central

> **Quais municípios brasileiros apresentam maior potencial para expansão de um banco digital?**

Construiremos um **Índice de Potencial Bancário (IPB)** por município, combinando capacidade de consumo, dinamismo, adoção digital, desatendimento bancário e perfil demográfico.

**Tese central**: para um banco digital, a melhor oportunidade não é necessariamente a cidade mais rica, e sim o cruzamento **demanda × adoção digital × baixa penetração bancária tradicional**.

**Natureza do curso**: MBA de Engenharia de Dados — o projeto é avaliado como **pipeline de dados** (ingestão → limpeza → EDA → modelagem). O IPB é o produto; o pipeline é o entregável.

---

## 2. Cronograma real da disciplina (a régua do projeto)

| Data | Etapa | Entrega |
|---|---|---|
| 13/08 | Proposta validada | ✅ Entrega inicial |
| 18–25/08 | **Etapa 1 — Processamento e Ingestão** | **Entrega Etapa 1: 25/08** |
| 25/08–03/09 | **Etapa 2 — Análise Exploratória e Limpeza** | **Entrega Etapa 2: 03/09** |
| 01–15/09 | **Etapa 3 — Aplicação de ML e Modelos** | **Entrega Etapa 3: 15/09** |
| 17/09 | **Apresentação Final** | Pitch do projeto |

---

## 3. Estratégia de dados: NÚCLEO × STRETCH

Resposta à dúvida "reduzimos os dados?": **sim, com regra clara**.

- **NÚCLEO (MVP — obrigatório para as entregas)**: ~12 indicadores de coleta barata (API ou download direto). Garante o índice funcionando mesmo se nada mais der certo.
- **STRETCH (enriquecimento opcional)**: só entra depois que o núcleo estiver ingerido e consolidado.

**Corte já decidido**: microdados do **Caged** (FTP pesado, ~100 MB/mês) saem do núcleo. O pilar Dinamismo fica coberto por crescimento populacional (Censo) + **crescimento do Pix** — que é mais alinhado a banco digital e sai por API. Se sobrar tempo, o Caged volta como stretch.

**Decisões de escopo (mantidas)**:
- Coleta nacional (5.570 municípios) — custo de coleta igual ao de uma região;
- Ranking principal com corte ≥ 20 mil hab. (~1.800 municípios);
- Leitura em estratos: capitais/grandes (> 500 mil) separadas das médias (50–500 mil) — o insight de expansão mora nas médias;
- Pesos iguais na base + média geométrica dos pilares + sensibilidade.

---

## 4. Arquitetura do IPB

| Pilar | O que mede | Entra como |
|---|---|---|
| **A. Capacidade de Consumo** | Renda, população, PIB per capita | Direto |
| **B. Dinamismo Econômico** | Crescimento populacional, crescimento do Pix | Direto |
| **C. Adoção Digital** | Pix per capita, banda larga fixa, internet domiciliar | Direto |
| **D. Gap Bancário** | Agências, depósitos e crédito per capita | **Invertido** (menos atendimento = mais oportunidade) |
| **E. Perfil Demográfico** | Jovens 18–35, urbanização, IDHM (ou escolaridade se IDHM indisponível) | Direto |

```
IPB_m = (A_m × B_m × C_m × D_m × E_m)^(1/5) × 100
```
Cada variável normalizada em 0–1 (min-max, com winsorização no 1% extremo); cada pilar = média simples das suas variáveis.

**Como usar o índice (parte do entregável final)**: ranking geral e por estrato; quadrante Potencial × Gap Bancário; ficha do município; regra de decisão por ondas de expansão (Onda 1 = Top 50); mapa coroplético.

---

## 5. Etapa 3 sem "modelo de previsão": o ML nasce do índice

Não há target supervisionado aqui — e não precisa. Dois usos legítimos e simples de ML não supervisionado:

1. **PCA** sobre as variáveis normalizadas → verifica se os 5 pilares são dimensões realmente distintas e gera um cenário alternativo de pesos *data-driven* (alimenta a análise de sensibilidade);
2. **K-Means** sobre os pilares → agrupa municípios em **arquétipos de expansão** (ex.: "cidades médias conectadas e desatendidas" × "polos maduros saturados"). O mapa de clusters **é** o "Mapa do Potencial Bancário" do título.

Isso transforma a Etapa 3 de obrigação em argumento de venda do trabalho.

---

## 6. Dicionário de dados (núcleo em negrito)

Esforço: ⚡ rápido (API/download direto) · 🔧 médio · 🐢 pesado (evitar no núcleo)

### Pilar A — Capacidade de Consumo
| Indicador | Fonte e acesso | Esforço | Status |
|---|---|---|---|
| **População residente (total e 18+)** | Censo 2022 — IBGE/SIDRA (API ou tela) | ⚡ | NÚCLEO |
| **Rendimento domiciliar per capita** | Censo 2022 — SIDRA: variável "Rendimento domiciliar per capita, em julho de 2022 (em reais)" | ⚡ | NÚCLEO |
| **PIB municipal e PIB per capita** | IBGE — PIB dos Municípios: xlsx "Base 2010–2023" (planilha única) | ⚡ | NÚCLEO |
| Valor adicionado de serviços | Mesma planilha do PIB | ⚡ | stretch |

### Pilar B — Dinamismo Econômico
| Indicador | Fonte e acesso | Esforço | Status |
|---|---|---|---|
| **Crescimento populacional 2010→2022** | Censo 2010 e 2022 — SIDRA (duas consultas + variação %) | ⚡ | NÚCLEO |
| **Crescimento do Pix (12 meses)** | API BCB (ver pilar C) — calculado sobre a série | ⚡ | NÚCLEO |
| Saldo de empregos formais / salário de admissão | Novo Caged (MTE) — FTP `ftp://ftp.mtps.gov.br/pdet/microdados/NOVO CAGED/` | 🐢 | stretch |
| Empresas ativas | Cempre — IBGE/SIDRA | 🔧 | stretch |

### Pilar C — Adoção Digital (diferencial do trabalho)
| Indicador | Fonte e acesso | Esforço | Status |
|---|---|---|---|
| **Transações Pix PF/PJ por município** | API Olinda BCB: `.../servico/Pix_DadosAbertos/versao/v1/odata/TransacoesPixPorMunicipio(DataBase=@DataBase)?$format=json&@DataBase='202606'` (loop por mês, 12–24 meses) | ⚡/🔧 | NÚCLEO |
| **Banda larga fixa por 100 hab.** | Anatel — dados.gov.br: CSV "Densidade de acessos… por 100 habitantes" | 🔧 | NÚCLEO |
| **% domicílios com internet** | Censo 2022 — SIDRA: "Acesso à internet, existência" | ⚡ | NÚCLEO |
| Banda larga móvel por 100 hab. | Anatel — dados.gov.br | 🔧 | fora do escopo |
| Chaves Pix cadastradas | API BCB: `ChavesPix(Data='...')` | ⚡ | stretch |

### Pilar D — Gap Bancário (invertido no índice)
| Indicador | Fonte e acesso | Esforço | Status |
|---|---|---|---|
| **Agências por 100 mil hab.** | BCB — Portal de Dados Abertos / Estban | 🔧 | NÚCLEO |
| **Depósitos e crédito per capita** | BCB — Estban (Estatísticas Bancárias por Município) | 🔧 | NÚCLEO |
| Presença de cooperativas | BCB | 🔧 | stretch |

⚠️ **Único ponto de validação urgente**: confirmar o formato atual de download do Estban logo no 1º dia. Plano B: cadastro de agências no Portal de Dados Abertos do BCB (garante ao menos D1) ou IF.data por localidade.

### Pilar E — Perfil Demográfico
| Indicador | Fonte e acesso | Esforço | Status |
|---|---|---|---|
| **% população 18–35 anos** | Censo 2022 — SIDRA (grupos de idade) | ⚡ | NÚCLEO |
| **% população urbana** | Censo 2022 — SIDRA | ⚡ | NÚCLEO |
| **IDHM** | Atlas Brasil (PNUD) — xlsx por município (IDHM 2022) | ⚡ | NÚCLEO* |
| Escolaridade (% ensino médio+) | Censo 2022 — SIDRA | ⚡ | alternativa |

> *O IDHM é a primeira opção para o pilar E, mas o site do Atlas Brasil apresentou instabilidade (`HTTP 500`). Se não for possível baixar o IDHM em 24–48h, a **escolaridade (% ensino médio+)** vira indicador principal do pilar E, mantendo o núcleo funcional.

**Chave de junção (passo zero)**: código IBGE de 7 dígitos — tabela-mestra via `https://servicodados.ibge.gov.br/api/v1/localidades/municipios`. Guardar nome + UF para *fuzzy matching* (Anatel pode vir por nome).

> **Nota técnica**: cada fonte do NÚCLEO será persistida no BigQuery com o prefixo `raw_`. Os schemas sugeridos e os tratamentos de integração estão nas seções 10 e 11 deste documento.

---

## 7. Plano semana a semana (realinhado)

| Período | Etapa | O que entregar |
|---|---|---|
| **até 25/08** | Etapa 1 — Ingestão | Chave IBGE; scripts/planilhas de coleta do NÚCLEO (SIDRA, PIB xlsx, IDHM/escolaridade, API Pix, Anatel banda larga fixa, Estban); base consolidada 1 linha = 1 município; documentação das fontes |
| **até 03/09** | Etapa 2 — EDA e Limpeza | Faltantes e outliers tratados (winsorização); distribuições e correlações; primeiros mapas; decisão final das variáveis do índice |
| **até 15/09** | Etapa 3 — ML | IPB calculado (3 cenários de peso); PCA; K-Means com arquétipos; quadrante de priorização; ranking final |
| **17/09** | Apresentação | Mapa + ranking + "como usar" + 3 municípios-caso (história do pitch) |

---

## 8. Cuidados metodológicos (para a defesa)

1. **Vintage misto declarado**: estrutura (Censo 2022) + conjuntura (Pix 2025–26) = índice atualizável, por escolha;
2. **Efeito polo regional**: Pix/depósitos concentram na sede da microrregião — tratar como insight, não defeito;
3. **Winsorização** no 1% extremo antes de normalizar;
4. **Robustez**: Top 100 deve ser estável entre cenários de peso — se não for, reportar (é material de discussão).

---

## 9. Aspectos Legais e Éticos (LGPD e Viés)

Em conformidade com os requisitos do projeto, ressaltamos que **não há dados pessoais sensíveis (PII)** neste pipeline. 
- Todas as bases utilizadas (IBGE, Banco Central, Anatel) são agregadas em nível municipal (macro) e de domínio público (Open Data). A LGPD não se aplica a agregados demográficos e econômicos que não permitem identificação individual.
- **Viés (Bias) e Ética**: O índice foca em infraestrutura e volume financeiro. Não há penalização demográfica (ex: não usamos cor/raça para rankear cidades). O único risco ético é o "Efeito Polo", onde cidades-dormitório pareçam desatendidas financeiramente por transferirem seu capital para a metrópole vizinha. Isso será endereçado nas regras de negócio (Ondas de Expansão).

---

## 10. Links rápidos

| Base | Link |
|---|---|
| API Pix (BCB) | https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/aplicacao |
| Dados Abertos BCB | https://dadosabertos.bcb.gov.br |
| SIDRA (IBGE) | https://sidra.ibge.gov.br |
| API Localidades IBGE | https://servicodados.ibge.gov.br/api/v1/localidades/municipios |
| PIB dos Municípios | https://www.ibge.gov.br/estatisticas/economicas/contas-nacionais/9088-produto-interno-bruto-dos-municipios.html |
| Microdados Caged (stretch) | ftp://ftp.mtps.gov.br/pdet/microdados/ |
| Anatel — Dados Abertos | https://www.gov.br/anatel/pt-br/dados/dados-abertos · https://dados.gov.br |
| Atlas Brasil (IDHM) | https://www.atlasbrasil.org.br |

---

## 11. Detalhes técnicos de implementação

### 12.1 Autenticação e armazenamento

- **BigQuery**: projeto GCP a ser criado; autenticação local via `gcloud auth application-default login` ou variável `GOOGLE_APPLICATION_CREDENTIALS`.
- **Dataset padrão**: `ipb_staging` (ajustável em `.env`).
- **Localização**: `US` (multi-região padrão do BigQuery Sandbox / Free Tier, sem custos).
- **Credenciais**: nunca commitar `.env` nem JSON de service account.

### 12.2 Endpoints e métodos de coleta

| Fonte | Endpoint / URL | Método | Autenticação |
|---|---|---|---|
| IBGE Localidades | `https://servicodados.ibge.gov.br/api/v1/localidades/municipios` | GET | Nenhuma |
| SIDRA Censo 2022 | `https://servicodados.ibge.gov.br/api/v3/agregados/{id}/periodos/2022/variaveis/{vars}/localidades/N6[{municipio}]` | GET | Nenhuma |
| PIB dos Municípios | `https://www.ibge.gov.br/estatisticas/economicas/contas-nacionais/9088-produto-interno-bruto-dos-municipios.html` | Download XLSX | Nenhuma |
| BCB Pix (Olinda) | `https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/TransacoesPixPorMunicipio(DataBase=@DataBase)?$format=json&@DataBase='YYYYMM'` | GET | Nenhuma |
| Anatel | `https://www.gov.br/anatel/pt-br/dados/dados-abertos` | Download CSV | Nenhuma |
| BCB Estban | Portal de Dados Abertos do BCB / `https://dadosabertos.bcb.gov.br` | Download CSV | Nenhuma |
| PNUD IDHM | `https://www.atlasbrasil.org.br` | Download XLSX | Nenhuma |

### 11.3 Pré-Processamento e Transformações (Justificativas)

Durante a fase de ingestão (Etapa 1), as seguintes abordagens de pré-processamento estrutural foram aplicadas aos *Raw Datasets* antes da consolidação na camada *Trusted*:

1. **Padronização da Chave Primária (`id_municipio`)**:
   - **Técnica**: Cast para STRING, remoção de `.0` (float issues do pandas), preenchimento com zeros à esquerda (`zfill(7)`) e substring para garantir exatamente 7 dígitos (excluindo o dígito verificador quando as fontes enviavam 6 dígitos).
   - **Justificativa**: Fontes heterogêneas lidam com o código IBGE de formas diferentes (int, float, string, 6 ou 7 dígitos). Sem uma chave unificada e perfeitamente padronizada, o *JOIN* falharia, comprometendo a integridade referencial.
2. **Seleção de Recorte Temporal (Ano mais recente)**:
   - **Técnica**: Filtro `max(ano)` / `max(mes)` para planilhas históricas (PIB e Anatel).
   - **Justificativa**: Como o IPB é uma fotografia do cenário atual para decisão de expansão, séries temporais passadas apenas geram ruído na consolidação.
3. **Agregação em Série Temporal (Pix)**:
   - **Técnica**: Soma (`groupby.sum()`) das transações e valores (PF e PJ) dos últimos 12 meses disponíveis.
   - **Justificativa**: O Pix possui forte sazonalidade mensal (ex: picos em dezembro e dias úteis). Utilizar a janela de 12 meses dilui sazonalidades e reflete o dinamismo real.
4. **Tratamento Inicial de Metadados (Estban)**:
   - **Técnica**: Descarte de linhas de cabeçalho administrativo (`skiprows=2`) e drop de registros sem código IBGE.
   - **Justificativa**: Garantir que o *parser* carregue os tipos corretamente sem poluir a tabela com strings de metadados do BCB.
5. **Decisão sobre *Missing Values* (Nulos)**:
   - **Técnica**: Preservar campos faltantes como `NULL` na camada *Trusted* (ex: dados da amostra do Censo 2022).
   - **Justificativa**: A imputação prematura no ETL esconde a distribuição real dos dados. O tratamento estatístico (média, mediana, exclusão) é uma tarefa analítica e ocorrerá na Etapa 2 (EDA).

### 12.4 Camadas no BigQuery

| Camada | Prefixo | Exemplo | Responsabilidade |
|---|---|---|---|
| Raw | `raw_` | `raw_sidra_censo_2022` | Dados coletados, com auditoria mínima. |
| Trusted | `trusted_` | `trusted_municipios` | Dados limpos, tipados e unificados por município. |
| Analytics | `analytics_` | `analytics_ipb_ranking` | Produtos finais (Etapa 3). |

---

## 12. Dicionário de Dados e Schemas

### 12.1 `raw_ibge_localidades`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id_municipio` | STRING | Código IBGE de 7 dígitos |
| `nome_municipio` | STRING | Nome oficial do município |
| `sigla_uf` | STRING | UF (2 letras) |
| `nome_uf` | STRING | Nome da UF |
| `nome_regiao` | STRING | Região geográfica |
| `_source_url` | STRING | URL da API |
| `_extracted_at` | TIMESTAMP | Data/hora da extração |

### 12.2 `raw_sidra_censo_2022`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id_municipio` | STRING | Código IBGE de 7 dígitos |
| `populacao_total` | FLOAT | População residente total |
| `populacao_18_35` | FLOAT | População entre 18 e 35 anos |
| `rendimento_domiciliar_per_capita` | FLOAT | Rendimento domiciliar per capita (R$) |
| `domicilios_com_internet_pct` | FLOAT | % de domicílios com acesso à internet |
| `populacao_urbana_pct` | FLOAT | % da população residente em área urbana |
| `_source_url` | STRING | URL da consulta SIDRA |
| `_extracted_at` | TIMESTAMP | Data/hora da extração |

> 🐘 **"O Elefante na Sala" (Censo 2022)**: O IBGE divulgou a População Total em granularidade municipal, mas os dados da amostra do Censo 2022 (Rendimento, Escolaridade e Acesso à Internet por município) **ainda não foram liberados** publicamente até o fechamento da Etapa 1. Para manter a autenticidade dos dados, essas colunas estão vindo nulas (`None`) direto da API do SIDRA. A imputação de dados faltantes ou fallback para o Censo 2010 deverá ser endereçada na **Etapa 2 (Exploração e Limpeza)**.

### 12.3 `raw_pib_municipios`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id_municipio` | STRING | Código IBGE de 7 dígitos |
| `ano` | INTEGER | Ano de referência |
| `pib` | FLOAT | PIB a preços correntes (R$ 1.000) |
| `pib_per_capita` | FLOAT | PIB per capita (R$) |
| `valor_adicionado_servicos` | FLOAT | Valor adicionado do setor de serviços (R$ 1.000) |
| `_source_url` | STRING | URL do download |
| `_extracted_at` | TIMESTAMP | Data/hora da extração |

### 12.4 `raw_bcb_pix_transacoes`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id_municipio` | STRING | Código IBGE de 7 dígitos |
| `data_base` | DATE | Mês de referência (YYYY-MM-01) |
| `transacoes_pf` | INTEGER | Quantidade de transações Pix PF |
| `transacoes_pj` | INTEGER | Quantidade de transações Pix PJ |
| `valor_pf` | FLOAT | Valor transacionado Pix PF (R$) |
| `valor_pj` | FLOAT | Valor transacionado Pix PJ (R$) |
| `_source_url` | STRING | URL da consulta Olinda |
| `_extracted_at` | TIMESTAMP | Data/hora da extração |

### 12.5 `raw_anatel_banda_larga_fixa`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id_municipio` | STRING | Código IBGE de 7 dígitos (já presente no arquivo) |
| `nome_municipio` | STRING | Nome do município (origem Anatel) |
| `sigla_uf` | STRING | UF |
| `data_base` | DATE | Mês de referência |
| `densidade_banda_larga_fixa` | FLOAT | Acessos de banda larga fixa por 100 hab. |
| `_source_url` | STRING | URL do download |
| `_extracted_at` | TIMESTAMP | Data/hora da extração |

> Nota: banda larga móvel está fora do escopo.

### 12.6 `raw_bcb_estban`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id_municipio` | STRING | Código IBGE de 7 dígitos |
| `data_base` | DATE | Mês de referência |
| `quantidade_agencias` | INTEGER | Número de agências bancárias |
| `depositos` | FLOAT | Total de depósitos (R$) |
| `credito` | FLOAT | Total de operações de crédito (R$) |
| `_source_url` | STRING | URL do download |
| `_extracted_at` | TIMESTAMP | Data/hora da extração |

### 12.7 `raw_pnud_idhm`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id_municipio` | STRING | Código IBGE de 7 dígitos |
| `ano` | INTEGER | Ano de referência |
| `idhm` | FLOAT | Índice de Desenvolvimento Humano Municipal |
| `idhm_renda` | FLOAT | Componente renda do IDHM |
| `idhm_longevidade` | FLOAT | Componente longevidade do IDHM |
| `idhm_educacao` | FLOAT | Componente educação do IDHM |
| `_source_url` | STRING | URL do download |
| `_extracted_at` | TIMESTAMP | Data/hora da extração |

### 12.8 `trusted_municipios`

Tabela consolidada, 1 linha por município.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id_municipio` | STRING PK | Código IBGE de 7 dígitos |
| `nome_municipio` | STRING | Nome oficial |
| `sigla_uf` | STRING | UF |
| `nome_regiao` | STRING | Região |
| `populacao_total` | FLOAT | População total (Censo 2022) |
| `populacao_18_35_pct` | FLOAT | % população 18–35 anos |
| `crescimento_populacional_2010_2022_pct` | FLOAT | Variação populacional 2010→2022 |
| `rendimento_domiciliar_per_capita` | FLOAT | R$ per capita |
| `pib_per_capita` | FLOAT | R$ per capita |
| `domicilios_com_internet_pct` | FLOAT | % domicílios com internet |
| `populacao_urbana_pct` | FLOAT | % população urbana |
| `pix_per_capita_12m` | FLOAT | Transações Pix PF+PJ / população (últimos 12 meses) |
| `crescimento_pix_12m_pct` | FLOAT | Crescimento do valor Pix vs. 12 meses anteriores |
| `banda_larga_fixa_por_100_hab` | FLOAT | Acessos de banda larga fixa por 100 hab. |
| `agencias_por_100k_hab` | FLOAT | Agências bancárias por 100 mil hab. |
| `depositos_per_capita` | FLOAT | Depósitos / população |
| `credito_per_capita` | FLOAT | Crédito / população |
| `idhm` | FLOAT | IDHM 2022 |
| `escolaridade_pct` | FLOAT | % população com ensino médio completo (alternativa ao IDHM) |
| `_extracted_at` | TIMESTAMP | Data/hora da geração |

---

## 13. Checklist de validação da Etapa 1

Antes de considerar a ingestão concluída, verificar:

- [ ] Tabela `raw_ibge_localidades` com ~5.570 municípios e códigos IBGE válidos.
- [ ] Todas as tabelas `raw_*` do NÚCLEO carregadas no BigQuery.
- [ ] Tabela `trusted_municipios` gerada com 1 linha por município.
- [ ] Nenhuma duplicata por `id_municipio` na `trusted_municipios`.
- [ ] Colunas `_source_url` e `_extracted_at` preenchidas em todas as tabelas.
- [ ] Municípios com dados faltantes documentados (não imputados).
- [ ] `AGENTS.md` e `docs/Arquitetura_Tecnica.md` revisados e consistentes.

---

*v3 — revisada com detalhes técnicos de implementação, schemas de tabelas e camadas no BigQuery.*
