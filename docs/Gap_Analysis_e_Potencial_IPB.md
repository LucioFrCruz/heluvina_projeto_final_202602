# Gap Analysis e Potencial do Índice de Potencial Bancário (IPB)

> **Objetivo deste documento**: revisão de ponta a ponta do projeto IPB, identificação de gaps técnicos e de dados, avaliação da viabilidade do cálculo do índice, mapeamento de bases complementares e proposta de features.  
> **Branch**: `feature/etapa2-eda-e-limpeza`  
> **Data da análise**: 2026-08-31  
> **Base analisada**: `trusted_municipios` (5.570 municípios) + tabelas `raw_*` no BigQuery e caches locais.

---

## 1. Resumo Executivo

O projeto IPB está **tecnicamente maduro na Etapa 1**: pipeline Poetry + BigQuery funciona, a tabela-mestre cobre os 5.570 municípios, e a documentação é clara. A análise exploratória (EDA) já gerou uma versão *alpha* do índice com ranking preliminar.

No entanto, **foram identificados gaps críticos que invalidam parcialmente os resultados atuais** e precisam de correção antes de avançar para a Etapa 3 (modelagem final / ML):

1. **Bug crítico nos dados de Pix**: a tabela `raw_bcb_pix_transacoes` contém registros duplicados por `id_municipio + AnoMes`, com acumulação crescente de meses. Isso infla artificialmente `pix_total_volume_12m` e `pix_per_capita_12m` na `trusted_municipios`, contaminando o Pilar B e o ranking IPB *alpha*.
2. **Coluna `domicilios_com_internet_pct` 100% nula**: a API SIDRA Tabela 7307 permanece indisponível para `N6[all]`. A proxy `banda_larga_fixa_por_100_hab` é aceitável, mas reduz a robustez do Pilar C.
3. **`va_servicos` 100% nulo no PIB 2023**: a rubrica não foi divulgada pelo IBGE para o ano mais recente. Decisão correta foi não propagar para a trusted, mas isso elimina uma variável de stretch promissora.
4. **Vintage misto extremo**: Censo 2022, PIB 2023, Pix 2025–2026, Anatel/Estban 2026, IDHM 2010. O índice mistura estrutura, conjuntura e histórico, o que exige disclaimer forte e análise de sensibilidade.
5. **Municípios sem IDHM**: 6 municípios (0,11%) ficam sem essa variável histórica.
6. **Interpretação do ranking *alpha* questionável**: o Top 10 é dominado por cidades de SP, SC e MT, muitas delas já bancarizadas ou com efeito polo/região metropolitana. A fórmula atual pode estar premiando mais "riqueza + infraestrutura" do que "potencial de expansão bancária digital".

**Veredito geral**: o IPB é viável como produto acadêmico e como prova de conceito de pipeline de dados, mas **precisa de correção de dados, recalibração de pesos e validação de negócio** antes de ser apresentado como recomendação estratégica real.

---

## 2. Diagnóstico Atual

### 2.1 O que está funcionando

| Aspecto | Status | Evidência |
|---|---|---|
| Cobertura municipal | ✅ | 5.570 municípios na `trusted_municipios` |
| Pipeline de ingestão | ✅ | 7 ingestores implementados; cache Parquet + BigQuery |
| Documentação | ✅ | README, AGENTS.md, guias técnicos e dicionário de dados claros |
| Camada trusted consolidada | ✅ | Joins corretos; colunas padronizadas; regras de imputação definidas |
| EDA inicial | ✅ | 6 notebooks; relatório EDA; figuras versionadas |
| Cálculo alpha do IPB | ✅ | Fórmula implementada; ranking gerado; PCA exploratório |
| Testes | ⚠️ | Testes unitários para `ibge`, `storage`, `eda` e `sidra`; faltam testes de data quality e para ingestores manuais |

### 2.2 O que não está funcionando

| Aspecto | Problema | Impacto |
|---|---|---|
| Dados de Pix | Duplicados/acumulados na `raw_bcb_pix_transacoes` | **Alto** — volume Pix inflado; ranking alpha contaminado |
| Internet domiciliar | Coluna 100% nula | Médio — perda de uma variável de proxy digital |
| PIB serviços | `va_servicos` 100% nulo | Baixo — era stretch, mas elimina análise setorial |
| IDHM | 6 municípios sem dados | Baixo — variável histórica, pode ser imputada ou removida |
| Estban | 2.656 municípios sem agência (47,7%) | Esperado — imputação com 0 é correta, mas cria massa de zeros no pilar D |
| Consistência conceitual | Ranking alpha privilegia cidades ricas/conectadas | Alto — pode não refletir a tese de "desbancarização com potencial" |

---

## 3. Gaps Críticos Identificados

### 3.1 Gap 1 — Duplicação dos dados de Pix (CRÍTICO)

**Evidência**:

```text
AnoMes  total  municipios_unicos
202507   5570               5570
202508  11140               5570   ← 2x
202509  16710               5570   ← 3x
202510  22284               5570   ← 4x
...
202606  66852               5571   ← 12x
202607  66852               5571   ← 12x
202608  66852               5571   ← 12x
```

O padrão mostra que cada mês foi inserido múltiplas vezes (1x em 202507, 2x em 202508, ..., 12x em 202606). Para o município `1100015` (Rio Branco/AC), o mês `202508` aparece 2 vezes com valores idênticos; `202509` aparece 3 vezes, e assim por diante.

**Causa provável**:
- O ingestor `bcb_pix.py` foi executado repetidamente ao longo do tempo;
- Cada execução sobrescrevia o cache Parquet local, mas em algum momento houve append acidental ou o cache local foi corrompido e reenviado ao BigQuery;
- A função `extract()` não faz `drop_duplicates` explícito por `id_municipio + AnoMes` antes de salvar.

**Impacto**: a `trusted_municipios` soma `VL_PagadorPF` e `QT_PagadorPF` agrupando por `id_municipio`. Com duplicatas, o volume anualizado está inflado em até ~6–8x para meses repetidos. O Pilar B (Dinamismo Econômico) e o Pilar C (Adoção Digital) ficam distorcidos.

**Recomendação imediata**:
1. Corrigir `bcb_pix.py` para fazer `drop_duplicates(subset=['id_municipio', 'AnoMes'])` antes de salvar;
2. Re-executar o ingestor e a consolidação trusted;
3. Adicionar teste unitário que garanta unicidade por `id_municipio + AnoMes` na raw;
4. Adicionar teste de data quality na trusted validando que `pix_total_volume_12m` não excede múltiplos plausíveis do PIB municipal.

### 3.2 Gap 2 — Ausência de proxy para internet domiciliar (ALTO)

A coluna `domicilios_com_internet_pct` está 100% nula. A API SIDRA Tabela 7307 continua retornando HTTP 500 para `N6[all]`. A proxy atual é `banda_larga_fixa_por_100_hab` (Anatel), que mede **acessos de internet fixa por 100 hab.**, não penetração domiciliar.

**Problemas**:
- Banda larga fixa é uma proxy imperfeita: cidades com muitas empresas podem ter mais acessos que domicílios; cidades pobres podem depender de internet móvel;
- Há 5 municípios com `banda_larga_fixa_por_100_hab > 100`, o que indica múltiplas linhas por residência/empresa (Alto Paraíso/PR = 158,8).

**Alternativas**:
- Usar a cobertura 4G/5G da Anatel (SNIS Móvel) como proxy complementar;
- Tentar novamente a SIDRA Tabela 7307 com throttling ou granularidade menor;
- Usar PNAD Contínua (IBGE) para estimativas regionais, embora não seja municipal.

### 3.3 Gap 3 — PIB 2023 sem valor adicionado de serviços (MÉDIO)

A coluna `va_servicos` da `raw_pib_municipios` está 100% nula. O IBGE não divulgou a rubrica para 2023 no arquivo de origem.

**Impacto**: perde-se a capacidade de medir a dependência do setor de serviços, que é relevante para bancos digitais (maior atividade de serviços → maior demanda por transações digitais).

**Alternativa**: usar o PIB 2022 (se `va_servicos` estiver disponível) como variável histórica complementar, ou descartar essa variável e manter apenas `pib_per_capita`.

### 3.4 Gap 4 — Vintage misto e interpretação causal (ALTO)

A base mistura:
- **Estrutura (Censo 2022)**: população, renda, escolaridade, urbanização;
- **Conjuntura recente (2025–2026)**: Pix, Anatel, Estban;
- **Histórico (2010)**: IDHM;
- **Meio-termo (2023)**: PIB.

Isso é uma limitação declarada, mas tem implicações práticas:
- Cidades que cresceram muito entre 2022 e 2026 podem ter infraestrutura subestimada;
- O IDHM de 2010 pode não refletir a realidade educacional atual (embora a escolaridade 2022 já seja o principal indicador do Pilar E).

**Recomendação**: manter o disclaimer, mas testar a robustez do ranking removendo o IDHM e usando apenas escolaridade 2022.

### 3.5 Gap 5 — Municípios sem IDHM (BAIXO)

6 municípios (0,11%) não possuem IDHM:

| id_municipio | nome_municipio | UF |
|---|---|---|
| 1504752 | Mojuí dos Campos | PA |
| 2206720 | Nazária | PI |
| 4212650 | Pescaria Brava | SC |
| 4220000 | Balneário Rincão | SC |
| 4314548 | Pinto Bandeira | RS |
| 5006275 | Paraíso das Águas | MS |

São municípios criados após o Censo 2010 ou com alterações de limites. A imputação pela média regional ou por escolaridade é trivial.

### 3.6 Gap 6 — Ranking alpha não valida bem a tese de negócio (ALTO)

O Top 10 do IPB *alpha* é:

| Rank | Município | UF | IPB Alpha |
|---|---|---|---|
| 1 | Barueri | SP | 82,50 |
| 2 | Itapema | SC | 82,23 |
| 3 | Balneário Camboriú | SC | 81,81 |
| 4 | Paulínia | SP | 80,91 |
| 5 | Itajaí | SC | 80,05 |
| 6 | Nova Lima | MG | 79,85 |
| 7 | Ilhabela | SP | 79,74 |
| 8 | Itupeva | SP | 79,20 |
| 9 | Nova Mutum | MT | 78,63 |
| 10 | Santa Carmem | MT | 78,52 |

**Problemas de interpretação**:
- Barueri, Paulínia, Nova Lima e Itupeva são cidades ricas da região metropolitana — já têm forte presença bancária digital e física;
- Itapema, Balneário Camboriú e Ilhabela são cidades turísticas — o Pix alto pode refletir sazonalidade/turismo, não necessariamente potencial de expansão bancária;
- O ranking parece premiar **riqueza + conectividade**, não **desbancarização + potencial**.

**Possíveis causas estruturais**:
- Média geométrica com pesos iguais dos 5 pilares pode estar subponderando o Gap Bancário (Pilar D);
- O Pilar D usa 3 variáveis (agências, depósitos, crédito) que são altamente correlacionadas entre si (ρ ≈ 0,88–0,91), ganhando peso implícito;
- A inversão do Pilar D pode não ser suficiente para contrabalançar a riqueza dos Pilares A, B e C.

---

## 4. Avaliação da Viabilidade do Cálculo do IPB

### 4.1 A fórmula faz sentido matematicamente?

Sim. A fórmula proposta é:

```
IPB_m = (A × B × C × D × E)^(1/5) × 100
```

onde cada pilar é a média simples de variáveis normalizadas (min-max) e winsorizadas no 1%, e o Pilar D é invertido.

**Pontos fortes**:
- Média geométrica penaliza municípios com pilares desbalanceados (zero em um pilar → IPB zero);
- Winsorização reduz efeito de outliers;
- Inversão do Pilar D traduz a ideia de "quanto menor a bancarização tradicional, maior a oportunidade".

**Pontos fracos**:
- Pesos iguais entre pilares são arbitrários; não há justificativa econômica para A ter o mesmo peso que D;
- Dentro de cada pilar, a média simples ignora a correlação entre variáveis. O Pilar D tem 3 variáveis quase colineares (agências, depósitos, crédito), ganhando peso implícito triplo;
- A normalização min-max é sensível a outliers extremos, mesmo com winsorização no 1%;
- Não há validação externa: o ranking não foi comparado com nenhuma métrica real de expansão bancária (ex: abertura de agências digitais, crescimento de contas digitais).

### 4.2 Correlações entre variáveis

Matriz de correlação de Spearman na `trusted_municipios`:

| Variável | pib_pc | pix_pc | banda_larga | agencias | depósitos | crédito | escolarid. | urbana |
|---|---|---|---|---|---|---|---|---|
| pib_per_capita | 1,00 | 0,55 | 0,48 | 0,36 | 0,32 | 0,41 | 0,53 | 0,40 |
| pix_per_capita_12m | 0,55 | 1,00 | 0,33 | 0,32 | 0,40 | 0,47 | 0,56 | 0,60 |
| banda_larga_fixa_por_100_hab | 0,48 | 0,33 | 1,00 | 0,30 | 0,34 | 0,35 | 0,45 | 0,37 |
| agencias_por_100k_hab | 0,36 | 0,32 | 0,30 | 1,00 | 0,88 | 0,89 | 0,34 | 0,33 |
| depositos_per_capita | 0,32 | 0,40 | 0,34 | 0,88 | 1,00 | 0,91 | 0,45 | 0,46 |
| credito_per_capita | 0,41 | 0,47 | 0,35 | 0,89 | 0,91 | 1,00 | 0,45 | 0,45 |
| escolaridade_ensino_medio_pct | 0,53 | 0,56 | 0,45 | 0,34 | 0,45 | 0,45 | 1,00 | 0,70 |
| populacao_urbana_pct | 0,40 | 0,60 | 0,37 | 0,33 | 0,46 | 0,45 | 0,70 | 1,00 |

**Insights**:
- `escolaridade` e `populacao_urbana_pct` têm correlação 0,70 — quase colineares. Ter ambas no Pilar E aumenta o peso de "urbanização/educação";
- `pix_per_capita` e `populacao_urbana_pct` têm correlação 0,60 — Pix é fortemente urbano;
- As 3 variáveis do Pilar D são altamente correlacionadas (0,88–0,91). Isso viola a premissa de que cada variável adiciona informação independente.

### 4.3 O IPB está medindo o que deveria?

A tese de negócio é: *cidades com demanda econômica, adoção digital e baixa concorrência física*. O ranking *alpha* atual parece medir mais **"cidades ricas e conectadas"** do que **"cidades com oportunidade de expansão bancária digital"**.

**Sugestões de recalibração**:
1. **Testar pesos diferenciados**: dar mais peso ao Pilar D (Gap Bancário) e menos ao Pilar A (Capacidade de Consumo);
2. **Reduzir redundância no Pilar D**: usar apenas uma variável (ex: `agencias_por_100k_hab`) ou fazer PCA interna;
3. **Remover ou reduzir `populacao_urbana_pct`** do Pilar E por colinearidade com escolaridade;
4. **Adicionar uma variável de "tensão"**: razão entre Pix per capita e agências por habitante — cidades com muito Pix e poucas agências são oportunidades claras;
5. **Segmentar por estrato populacional**: o ranking geral mistura cidades de 800 hab. com cidades de 11 milhões. Análise por estrato é obrigatória.

### 4.4 Robustez do ranking

Sem análise de sensibilidade formal publicada, não é possível afirmar que o Top 100 é estável a mudanças de peso. A correlação alta entre variáveis do Pilar D sugere que pequenas mudanças podem alterar posições, mas provavelmente não o conjunto geral de cidades ricas do Sudeste/Sul.

---

## 5. Bases Complementares Avaliadas

### 5.1 Critérios de avaliação

| Critério | Descrição |
|---|---|
| Granularidade | É municipal? |
| Periodicidade | Anual? Mensal? |
| Custo | Gratuito? |
| Relevância | Agrega ao potencial bancário? |
| Facilidade de integração | API/CSV? Volume gerenciável? |
| Dificuldade | Complexidade de limpeza/join |

### 5.2 Bases avaliadas

| Base | Fonte | Granularidade | Periodicidade | Custo | Relevância | Facilidade | Dificuldade | Potencial |
|---|---|---|---|---|---|---|---|---|
| **CNPJ / MEI por município** | Receita Federal | Municipal | Mensal | Gratuito | ⭐⭐⭐⭐⭐ Alta — densidade empresarial indica demanda por serviços bancários PJ | Média — download de grandes arquivos, necessita agregação por município | Média | **Alto** |
| **SCR.data (crédito + inadimplência)** | BCB | UF / Região (não municipal detalhado) | Mensal | Gratuito | ⭐⭐⭐⭐ Alta — indica mercado de crédito e risco | Média — API OData, mas agregação limitada | Média | **Médio** — útil como validação cruzada, não como feature principal |
| **Novo Caged (emprego formal)** | MTE | Municipal | Mensal | Gratuito | ⭐⭐⭐⭐ Alta — emprego formal é proxy de renda e demanda por crédito consignado | Média — arquivos grandes, mas existem APIs/CSV por município | Média | **Alto** |
| **PNAD Contínua (renda)** | IBGE | Regional / metropolitana (não todos os municípios) | Trimestral | Gratuito | ⭐⭐⭐ Média — já temos renda do Censo 2022 | Alta | Baixa | **Baixo** — redundante com Censo |
| **SICONFI (finanças municipais)** | STN/Tesouro | Municipal | Anual | Gratuito | ⭐⭐⭐ Média — saúde fiscal indica estabilidade econômica | Média — dados contábeis complexos | Alta | **Médio** — mais relevante para crédito público/tributário |
| **SNIS (saneamento básico)** | MCID | Municipal | Anual | Gratuito | ⭐⭐⭐ Média — proxy de infraestrutura urbana e qualidade de vida | Média — preenchimento irregular | Média | **Médio** |
| **Cobertura 4G/5G (SNIS Móvel)** | Anatel | Municipal | Anual | Gratuito | ⭐⭐⭐⭐ Alta — complementa banda larga fixa | Alta | Baixa | **Alto** |
| **Pontos de atendimento de correspondentes bancários** | BCB | Municipal | Mensal | Gratuito | ⭐⭐⭐⭐⭐ Alta — mede infraestrutura bancária alternativa (além de agências) | Alta | Baixa | **Alto** |
| **Índice de Progresso Social (IPS)** | Imazon / IPS Brasil | Municipal | Anual | Gratuito | ⭐⭐⭐ Média — substituto moderno do IDHM | Média | Baixa | **Médio** |
| **Atlas da Violência (Ipea/FBSP)** | Ipea | Municipal (com ressalvas) | Anual | Gratuito | ⭐⭐ Baixa — segurança afeta investimento, mas é indireto | Média | Média | **Baixo** — fora do escopo principal |
| **Base dos Dados** | Base dos Dados | Várias | Variada | Gratuito | ⭐⭐⭐⭐ Alta — validação cruzada de múltiplas fontes | Média | Média | **Médio** — já mencionada no AGENTS.md como reserva |

### 5.3 Recomendação de bases a integrar

**Prioridade 1 (alto impacto, baixa/média dificuldade)**:
1. **Correspondentes bancários do BCB** — complementa o Pilar D com pontos de atendimento não tradicionais (lotéricas, correspondentes);
2. **Cobertura 4G/5G da Anatel** — complementa a banda larga fixa no Pilar C;
3. **CNPJ/MEI por município** — enriquece o Pilar B com dinamismo empresarial.

**Prioridade 2 (médio impacto, média dificuldade)**:
4. **Novo Caged** — variável de emprego formal e massa salarial;
5. **IPS (Índice de Progresso Social)** — substituto moderno e mais abrangente que o IDHM 2010.

**Prioridade 3 (validação cruzada)**:
6. **SCR.data do BCB** — para validar se o ranking IPB está alinhado com mercado de crédito real.

---

## 6. Features Existentes e Propostas

### 6.1 Features já existentes

| Feature | Descrição | Pilar | Status |
|---|---|---|---|
| `populacao_total` | População residente | A | Núcleo |
| `rendimento_domiciliar_per_capita` | Renda média mensal | A | Núcleo |
| `pib_per_capita` | PIB / população | A | Núcleo |
| `pix_per_capita_12m` | Volume Pix PF / população | B / C | Núcleo |
| `pix_total_transacoes_12m` | Quantidade de transações Pix | B | Núcleo |
| `banda_larga_fixa_por_100_hab` | Acessos fixos / 100 hab. | C | Núcleo |
| `agencias_por_100k_hab` | Agências / 100 mil hab. | D | Núcleo |
| `depositos_per_capita` | Depósitos / população | D | Núcleo |
| `credito_per_capita` | Crédito / população | D | Núcleo |
| `escolaridade_ensino_medio_pct` | % 18+ com ensino médio+ | E | Núcleo |
| `populacao_18_35_pct` | % jovens 18–35 | E | Núcleo |
| `populacao_urbana_pct` | % urbana | E | Núcleo |
| `idhm` | IDHM 2010 | E | Núcleo (histórico) |

Features derivadas na EDA:

| Feature | Descrição |
|---|---|
| `pix_pj_pct` | Proporção do volume Pix de pessoas jurídicas |
| `pix_ticket_medio` | Valor médio por transação Pix |
| `flag_sem_agencia` | Indicador de município sem agência |
| `estrato_populacional` | pequena / média / grande |
| `depositos_por_agencia` | Volume de depósitos por agência |
| `credito_por_agencia` | Volume de crédito por agência |

### 6.2 Features propostas

| Feature | Descrição | Pilar | Viabilidade | Impacto |
|---|---|---|---|---|
| `pix_razao_pib` | `pix_per_capita / pib_per_capita` | B/C | Alta | Alto — mede penetração digital relativa à renda |
| `tensao_digital_bancaria` | `pix_per_capita / (agencias_por_100k_hab + 1)` | B/D | Alta | Alto — oportunidade = adoção digital / infra física |
| `correspondentes_por_100k_hab` | Correspondentes bancários / 100 mil hab. | D | Alta | Alto — concorrência real no varejo |
| `cobertura_4g_pct` | % população com cobertura 4G | C | Alta | Alto — complementa banda larga fixa |
| `empresas_per_capita` | CNPJs ativos / população | B | Média | Alto — demanda PJ |
| `mei_per_capita` | MEIs / população | B | Média | Alto — microempreendedores como público-alvo |
| `saldo_empregos_formais_12m` | Saldo Caged anualizado | B | Média | Médio/Alto — dinamismo econômico |
| `massa_salarial_per_capita` | Empregos × salário médio / população | A/B | Média | Alto — renda real via folha |
| `ips_2024` | Índice de Progresso Social | E | Média | Médio — substitui IDHM 2010 |
| `gini_renda` | Desigualdade de renda (Censo 2022) | A | Média | Médio — cidades mais igualitárias podem ter demanda mais ampla |
| `percentual_servicos_no_pib_2022` | VA serviços / PIB (ano anterior) | A | Média | Médio — setor de serviços consome mais serviços bancários |
| `crescimento_pix_12m` | Variação % do Pix vs. meses anteriores | B | Média | Médio — momentum |
| `distancia_capital_km` | Distância até a capital do estado | Contexto | Média | Baixo — efeito polo |
| `populacao_18_35_absoluta` | População jovem absoluta | E | Alta | Médio — tamanho do mercado jovem |

### 6.3 Sugestão de nova arquitetura de features

**Pilar A — Capacidade de Consumo**:
- `pib_per_capita` (manter)
- `rendimento_domiciliar_per_capita` (manter)
- `populacao_total` (manter, talvez em log)
- *(novo)* `massa_salarial_per_capita` (Caged)

**Pilar B — Dinamismo Econômico**:
- `pix_per_capita_12m` (manter, após correção do bug)
- *(novo)* `empresas_per_capita` (CNPJ)
- *(novo)* `saldo_empregos_formais_12m` (Caged)

**Pilar C — Adoção Digital**:
- `banda_larga_fixa_por_100_hab` (manter)
- *(novo)* `cobertura_4g_pct` (Anatel)
- *(novo)* `pix_razao_pib` ou `pix_ticket_medio`

**Pilar D — Gap Bancário**:
- `agencias_por_100k_hab` (manter)
- *(novo)* `correspondentes_por_100k_hab` (BCB)
- Remover ou reduzir `depositos_per_capita` e `credito_per_capita` por alta correlação

**Pilar E — Perfil Demográfico**:
- `escolaridade_ensino_medio_pct` (manter como principal)
- `populacao_18_35_pct` (manter)
- Remover `populacao_urbana_pct` (colinearidade 0,70 com escolaridade)
- Substituir `idhm` por `ips_2024` ou mantê-lo apenas como referência histórica

---

## 7. Recomendações Priorizadas

### Curto prazo (até 03/09 — entrega da Etapa 2)

1. **Corrigir o bug de duplicação do Pix** em `bcb_pix.py` e reprocessar `trusted_municipios`;
2. **Regerar a EDA e o IPB *alpha*** com os dados corrigidos;
3. **Adicionar testes de data quality** para:
   - Unicidade por `id_municipio + AnoMes` na `raw_bcb_pix_transacoes`;
   - Volumetria exata de 5.570 municípios na trusted;
   - Faixas de valores percentuais (0–100);
   - Verificação de outliers absurdos (ex: pix_per_capita > 10x o PIB per capita).
4. **Documentar o bug e a correção** no `Relatorio_EDA.md`;
5. **Imputar os 6 municípios sem IDHM** pela média regional ou remover o IDHM do cálculo principal.

### Médio prazo (até 15/09 — Etapa 3)

6. **Testar cenários de pesos** para o IPB:
   - Pesos iguais (atual);
   - Pilar D com peso 1,5× ou 2×;
   - Pesos derivados de PCA;
   - Pilar E reduzido (sem `populacao_urbana_pct` e sem `idhm`).
7. **Incorporar 1–2 novas bases de prioridade 1**:
   - Correspondentes bancários do BCB;
   - Cobertura 4G/5G da Anatel.
8. **Criar feature `tensao_digital_bancaria`** e incluir como variável de negócio no Pilar D/B;
9. **Segmentar o ranking por estrato populacional** e por região, evitando comparar diretamente cidades de tamanhos muito distintos;
10. **Validar o ranking com análise de sensibilidade**: o Top 100 deve ser razoavelmente estável entre cenários de peso.

### Longo prazo (pós-entrega do MBA)

11. **Incorporar CNPJ/MEI e Caged** para enriquecer os pilares A e B;
12. **Construir um dashboard interativo** (Streamlit / Looker Studio) para exploração do ranking;
13. **Publicar metodologia** e comparar com outras iniciativas (ex: rankings de potencial de mercado);
14. **Automatizar pipeline** em GitHub Actions, substituindo fontes manuais por APIs quando possível.

---

## 8. Riscos e Limitações

### Riscos técnicos

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| API SIDRA continuar indisponível para internet | Alta | Médio | Manter proxy Anatel; tentar novamente com retry/backoff |
| BCB alterar formato da API Pix | Baixa | Alto | Isolar lógica de parse no ingestor; testes robustos |
| Estban mudar rubricas contábeis | Média | Alto | Validar colunas esperadas antes de agregar |
| Duplicação recorrente de dados | Média | Alto | Adicionar `drop_duplicates` e testes de unicidade |

### Riscos metodológicos

| Risco | Impacto | Mitigação |
|---|---|---|
| Ranking reflete riqueza, não oportunidade | Alto | Recalibração de pesos; validação por estrato |
| Vintage misto distorce comparações | Médio | Disclaimer claro; análise de sensibilidade |
| Efeito polo regional | Médio | Analisar microrregiões; não recomendar cidades-dormitório isoladamente |
| Ausência de target/validação externa | Alto | Usar SCR.data e expansão real de correspondentes como validação cruzada |

### Limitações declaradas

- O IPB é um índice composto com pesos arbitrários; não é um modelo preditivo;
- Não há variável-alvo de expansão bancária real para validar o ranking;
- A granularidade municipal esconde desigualdades intra-municipais;
- Dados de Pix incluem transações PJ, o que pode distorcer a "adoção digital da população".

---

## 9. Próximos Passos Concretos

1. **Corrigir `src/ingestors/bcb_pix.py`**:
   - Adicionar `df = df.drop_duplicates(subset=['id_municipio', 'AnoMes'])`;
   - Opcionalmente limitar a 12 meses mais recentes sem sobreposição.

2. **Reprocessar**:
   ```bash
   poetry run python -m src.ingestors.bcb_pix
   poetry run python -m src.preparacao.trusted_municipios
   ```

3. **Adicionar testes em `tests/data_quality/test_trusted_quality.py`**:
   - Unicidade por município + mês no Pix;
   - Check de outliers (ex: `pix_per_capita_12m < 5 * pib_per_capita`);
   - Volumetria e completude das colunas.

4. **Regerar notebooks de EDA** com dados corrigidos.

5. **Experimentar novos pesos e features** em `notebooks/00_exploracao/04_integracao_correlacoes.ipynb`.

6. **Documentar lições aprendidas** em `docs/Relatorio_EDA.md` e neste `Gap_Analysis_e_Potencial_IPB.md`.

---

## 10. Conclusão

O IPB tem base técnica sólida, mas **a correção do bug de duplicação do Pix é pré-requisito para qualquer conclusão confiável**. Após essa correção, o projeto deve:

- Recalibrar pesos para refletir melhor a tese de "oportunidade de expansão bancária digital";
- Reduzir redundância no Pilar D;
- Incorporar 1–2 novas bases de alta relevância (correspondentes bancários e 4G/5G);
- Validar o ranking por estrato populacional e região.

Com esses ajustes, o IPB passa de um índice de "riqueza municipal" para uma ferramenta mais alinhada à pergunta de negócio original: **onde um banco digital deveria expandir?**

---

*Documento gerado automaticamente a partir de análise de ponta a ponta do projeto IPB.*
