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
| `rendimento_domiciliar_per_capita` | FLOAT | R$ | Censo 2022 | Valor do rendimento nominal médio mensal domiciliar per capita (SIDRA Tabela 10295, Var. 13431). |
| `pib_per_capita` | FLOAT | R$ | IBGE PIB | Divisão do Produto Interno Bruto pelo total de habitantes daquele município. |
| `domicilios_com_internet_pct` | FLOAT | % | Censo 2022 | Proporção de residências com utilização de internet (SIDRA Tabela 7307). **Nota:** API do SIDRA retorna HTTP 500 para N6[all] em agosto/2026; coluna permanece nula até normalização. Usar `banda_larga_densidade` (Anatel) como proxy na EDA. |
| `populacao_urbana_pct` | FLOAT | % | Censo 2022 | Proporção de residentes em área urbana (SIDRA Tabela 10089, Var. 93, Situação do Domicílio). |
| `escolaridade_ensino_medio_pct` | FLOAT | % | Censo 2022 | Percentual de pessoas de 18 anos ou mais com ensino médio completo ou superior (SIDRA Tabela 10061, Var. 2667). |
| `pix_per_capita_12m` | FLOAT | Transações | BCB Pix | Razão entre a soma de transferências Pix PF+PJ (últimos 12 meses) e a população. |
| `crescimento_pix_12m_pct` | FLOAT | % | BCB Pix | Variação percentual do volume financeiro (R$) transacionado em Pix ano-contra-ano. |
| `banda_larga_fixa_por_100_hab` | FLOAT | Acessos | Anatel | Quantidade de acessos de banda larga fixa (fibra/cabo) para cada 100 moradores. |
| `agencias_por_100k_hab` | FLOAT | Agências | BCB Estban | Número de dependências bancárias tradicionais ativas normalizadas por 100 mil habitantes. |
| `depositos_per_capita` | FLOAT | R$ | BCB Estban | Volume total de depósitos à vista e poupança mantidos nas agências do município dividido pela população. |
| `credito_per_capita` | FLOAT | R$ | BCB Estban | Volume total da carteira de crédito ativa nas agências do município dividido pela população. |
| `_extracted_at` | TIMESTAMP | Timestamp| Pipeline | Carimbo de tempo do momento da consolidação. |

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
| `populacao_18_35_pct` | FLOAT | % | Percentual da população entre 18 e 35 anos (Tabela 9514, Var. 93). |
| `populacao_urbana_pct` | FLOAT | % | Percentual da população residente em área urbana (Tabela 10089, Var. 93). |
| `rendimento_domiciliar_per_capita` | FLOAT | R$ | Rendimento nominal médio mensal domiciliar per capita (Tabela 10295, Var. 13431). |
| `escolaridade_ensino_medio_pct` | FLOAT | % | Percentual de pessoas 18+ com ensino médio completo ou superior (Tabela 10061, Var. 2667). |
| `domicilios_com_internet_pct` | FLOAT | % | Percentual de domicílios com utilização de internet (Tabela 7307, Var. 9784). Nulo quando a API do SIDRA está indisponível para N6. |

### 2.3 `raw_pib_municipios`
| Coluna | Tipo | Unidade | Descrição |
| :--- | :--- | :--- | :--- |
| `id_municipio` | STRING | ID | Código IBGE. |
| `ano` | INTEGER | Ano | Ano de referência da série do PIB (filtrado apenas o mais recente). |
| `pib` | FLOAT | Milhares de R$| PIB a preços correntes (fator multiplicador x1000). |
| `pib_per_capita` | FLOAT | R$ | PIB absoluto (em R$) dividido pela população do ano. |
| `valor_adicionado_servicos` | FLOAT | Milhares de R$| Riqueza gerada exclusiva do setor terciário/serviços. |

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
| `densidade_banda_larga_fixa` | FLOAT | Acessos | Contratos de internet física residencial/empresarial por 100 hab. |

### 2.6 `raw_bcb_estban`
| Coluna | Tipo | Unidade | Descrição |
| :--- | :--- | :--- | :--- |
| `id_municipio` | STRING | ID | Código IBGE. |
| `data_base` | DATE | Mês/Ano | Data do balancete (Doc 4500). Filtrado pelo lote do bucket GCS. |
| `quantidade_agencias` | INTEGER | Unidades | Total de pontos de atendimento de bancos tradicionais ativos. |
| `depositos` | FLOAT | R$ | Soma de conta corrente e poupança nas agências locais (Verbete 420). |
| `credito` | FLOAT | R$ | Operações de empréstimos/financiamentos cedidos (Verbete 160). |

*(Nota Geral: Todas as tabelas `raw_` contém as colunas técnicas `_source_url` informando a proveniência dos dados, e `_extracted_at` com o carimbo de data e hora em que a rotina do ingestor foi disparada).*
