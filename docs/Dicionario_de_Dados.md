# Dicionário de Dados — IPB (Índice de Potencial Bancário)

Este dicionário detalha os schemas e a semântica de negócios de todas as tabelas coletadas e processadas na Etapa 1. O pipeline é composto por camadas `raw_` (dados brutos extraídos diretamente das fontes) e `trusted_` (tabela mestre consolidada).

---

## 1. Camada Trusted (Consolidada)

A tabela `trusted_municipios` é o produto final da Etapa 1. Ela contém a chave primária única por município e concentra as métricas vitais para a Análise Exploratória (Etapa 2) e clusterização/modelagem (Etapa 3).

| Nome da Coluna | Tipo de Dado | Unidade | Fonte Original | Descrição / Regra de Negócio |
| :--- | :--- | :--- | :--- | :--- |
| `id_municipio` | STRING | ID | IBGE | Código identificador de 7 dígitos do município. Chave Primária (PK). |
| `nome_municipio` | STRING | Texto | IBGE | Nome oficial do município. |
| `sigla_uf` | STRING | Texto | IBGE | Sigla da Unidade Federativa (UF) contendo 2 letras. |
| `nome_regiao` | STRING | Texto | IBGE | Região demográfica do Brasil (Norte, Nordeste, Centro-Oeste, Sudeste, Sul). |
| `populacao_total` | FLOAT | Pessoas | Censo 2022 | Total de pessoas residentes no município (SIDRA Tabela 4709). |
| `populacao_18_35_pct` | FLOAT | % | Censo 2022 | Percentual da população entre 18 e 35 anos (SIDRA Tabela 9514, soma de idades granulares). |
| `populacao_urbana_pct` | FLOAT | % | Censo 2022 | Proporção de residentes em área urbana (SIDRA Tabela 10089, Var. 93, Situação do Domicílio). |
| `rendimento_domiciliar_per_capita` | FLOAT | R$ | Censo 2022 | Valor do rendimento nominal médio mensal domiciliar per capita (SIDRA Tabela 10295, Var. 13431). |
| `escolaridade_ensino_medio_pct` | FLOAT | % | Censo 2022 | Percentual de pessoas de 18 anos ou mais com ensino médio completo ou superior (SIDRA Tabela 10061, Var. 2667). |
| `domicilios_com_internet_pct` | FLOAT | % | Censo 2022 | Proporção de residências com utilização de internet (SIDRA Tabela 7307). **Nota:** API do SIDRA retorna HTTP 500 para N6[all] em agosto/2026; coluna permanece nula até normalização. Usar `banda_larga_fixa_por_100_hab` (Anatel) como proxy na EDA. |
| `pib` | FLOAT | Mil R$ | IBGE PIB | Produto Interno Bruto a preços correntes (R$ 1.000). |
| `pib_per_capita` | FLOAT | R$ | IBGE PIB | PIB absoluto (em R$) dividido pela população do ano. |
| `pix_total_volume_12m` | FLOAT | R$ | BCB Pix | Volume financeiro total transacionado em Pix (PF + PJ) nos últimos 12 meses coletados. |
| `pix_total_transacoes_12m` | FLOAT | Transações | BCB Pix | Quantidade total de transações Pix (PF + PJ) nos últimos 12 meses coletados. |
| `pix_per_capita_12m` | FLOAT | R$ / hab. | BCB Pix | `pix_total_volume_12m / populacao_total`. |
| `banda_larga_fixa_por_100_hab` | FLOAT | Acessos | Anatel | Quantidade de acessos de banda larga fixa para cada 100 moradores. |
| `quantidade_agencias` | INTEGER | Unidades | BCB Estban | Total de pontos de atendimento de bancos tradicionais ativos. |
| `agencias_por_100k_hab` | FLOAT | Agências | BCB Estban | `(quantidade_agencias / populacao_total) * 100.000`. |
| `volume_depositos` | FLOAT | R$ | BCB Estban | Volume total de depósitos (conta corrente + poupança) nas agências locais. |
| `depositos_per_capita` | FLOAT | R$ / hab. | BCB Estban | `volume_depositos / populacao_total`. |
| `volume_credito` | FLOAT | R$ | BCB Estban | Volume total da carteira de crédito ativa nas agências locais. |
| `credito_per_capita` | FLOAT | R$ / hab. | BCB Estban | `volume_credito / populacao_total`. |
| `idhm` | FLOAT | Índice | Ipeadata (PNUD/Atlas 2010) | Índice de Desenvolvimento Humano Municipal do Censo 2010. Mantido como variável histórica; o indicador principal do pilar E é a escolaridade 2022. |
| `_extracted_at` | TIMESTAMP | Timestamp| Pipeline | Carimbo de tempo do momento da consolidação. |

> **Disclaimer sobre vintage dos dados**: o `trusted_municipios` combina diferentes anos de referência por indisponibilidade de dados municipais atualizados. **Censo 2022** (população, renda, escolaridade, urbanização); **PIB IBGE** (último ano disponível, 2023); **Pix** (últimos 12 meses disponíveis, atualmente 2023/2024); **Anatel** (último mês disponível, 2026); **Estban** (último mês disponível, 2026); **IDHM** (Censo 2010). Esse mix de vintages é uma limitação declarada do projeto e será tratado como viés/assumpção na EDA e na apresentação final.

---

## 2. Camada Raw (Fontes Brutas)

Abaixo estão os dicionários das fontes individuais (ingestores) antes do processo de padronização, agregação temporal (group by) e pivotamento feito pela camada Trusted.

### 2.1 `raw_ibge_localidades`
| Coluna | Tipo | Unidade | Descrição |
| :--- | :--- | :--- | :--- |
| `id_municipio` | STRING | ID | Código IBGE de 7 dígitos. Usado como chave de JOIN universal. |
| `nome_municipio` | STRING | Texto | Nome oficial do município. |
| `sigla_uf` | STRING | Texto | UF (ex: SP, RJ). |
| `nome_uf` | STRING | Texto | Nome da UF (ex: São Paulo). |
| `nome_regiao` | STRING | Texto | Região geográfica (Norte, Sul, etc). |

### 2.2 `raw_sidra_censo_2022`
| Coluna | Tipo | Unidade | Descrição |
| :--- | :--- | :--- | :--- |
| `id_municipio` | STRING | ID | Código IBGE. |
| `populacao_total` | FLOAT | Pessoas | População residente (Censo 2022 - Tabela 4709, Var. 93). |
| `populacao_18_35_pct` | FLOAT | % | Percentual da população entre 18 e 35 anos (Tabela 9514, Var. 93, idades granulares). |
| `populacao_urbana_pct` | FLOAT | % | Percentual da população residente em área urbana (Tabela 10089, Var. 93). |
| `rendimento_domiciliar_per_capita` | FLOAT | R$ | Rendimento nominal médio mensal domiciliar per capita (Tabela 10295, Var. 13431). |
| `escolaridade_ensino_medio_pct` | FLOAT | % | Percentual de pessoas 18+ com ensino médio completo ou superior (Tabela 10061, Var. 2667). |
| `domicilios_com_internet_pct` | FLOAT | % | Percentual de domicílios com utilização de internet (Tabela 7307, Var. 9784). Nulo quando a API do SIDRA está indisponível para N6. |

### 2.3 `raw_pib_municipios`
| Coluna | Tipo | Unidade | Descrição |
| :--- | :--- | :--- | :--- |
| `id_municipio` | STRING | ID | Código IBGE. |
| `ano` | INTEGER | Ano | Ano de referência da série do PIB (filtrado apenas o mais recente). |
| `pib` | FLOAT | Mil R$ | PIB a preços correntes (R$ 1.000). |
| `pib_per_capita` | FLOAT | R$ | PIB absoluto (em R$) dividido pela população do ano. |
| `va_servicos` | FLOAT | Mil R$ | Valor adicionado bruto do setor de serviços. **Atualmente nulo para 2023** — o IBGE não divulgou essa rubrica para o ano mais recente do arquivo de origem. |

### 2.4 `raw_bcb_pix_transacoes`
| Coluna | Tipo | Unidade | Descrição |
| :--- | :--- | :--- | :--- |
| `id_municipio` | STRING | ID | Código IBGE. |
| `data_base` | DATE | Mês/Ano | Mês do lote de transações. Série mensal de 12 a 24 meses. |
| `transacoes_pf` | INTEGER | Transações| Contagem absoluta de transferências de origem Pessoa Física. |
| `transacoes_pj` | INTEGER | Transações| Contagem absoluta de transferências de origem Pessoa Jurídica. |
| `valor_pf` | FLOAT | R$ | Volume bruto monetário enviado por Pessoas Físicas. |
| `valor_pj` | FLOAT | R$ | Volume bruto monetário enviado por Pessoas Jurídicas. |

### 2.5 `raw_anatel_banda_larga_fixa`
| Coluna | Tipo | Unidade | Descrição |
| :--- | :--- | :--- | :--- |
| `id_municipio` | STRING | ID | Código IBGE. |
| `nome_municipio` | STRING | Texto | Nome de origem do CSV da Anatel (não utilizado após JOIN na Trusted). |
| `sigla_uf` | STRING | Texto | Estado de origem do CSV. |
| `data_base` | DATE | Mês/Ano | Safra dos dados (filtrado apenas mês/ano mais recente). |
| `densidade` | FLOAT | Acessos | Contratos de internet física residencial/empresarial por 100 hab. Renomeado para `banda_larga_fixa_por_100_hab` na Trusted. |

### 2.6 `raw_bcb_estban`
| Coluna | Tipo | Unidade | Descrição |
| :--- | :--- | :--- | :--- |
| `id_municipio` | STRING | ID | Código IBGE. |
| `data_base` | DATE | Mês/Ano | Data do balancete (Doc 4500). Filtrado pelo lote do bucket GCS. |
| `quantidade_agencias` | INTEGER | Unidades | Total de pontos de atendimento de bancos tradicionais ativos. |
| `volume_depositos` | FLOAT | R$ | Soma de conta corrente e poupança nas agências locais (Verbete 420). |
| `volume_credito` | FLOAT | R$ | Operações de empréstimos/financiamentos cedidos (Verbete 160). |

### 2.7 `raw_pnud_idhm`
| Coluna | Tipo | Unidade | Descrição |
| :--- | :--- | :--- | :--- |
| `id_municipio` | STRING | ID | Código IBGE. |
| `ano` | INTEGER | Ano | Ano de referência (2010). |
| `idhm` | FLOAT | Índice | Índice de Desenvolvimento Humano Municipal. |
| `_source_url` | STRING | URL | URL da API do Ipeadata. |
| `_extracted_at` | TIMESTAMP | Timestamp | Data/hora da extração. |

*(Nota Geral: Todas as tabelas `raw_` contém as colunas técnicas `_source_url` informando a proveniência dos dados, e `_extracted_at` com o carimbo de data e hora em que a rotina do ingestor foi disparada).*
