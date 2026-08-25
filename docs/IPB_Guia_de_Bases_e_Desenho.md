# Guia de Bases e Desenho do Índice de Potencial Bancário (IPB)

> **Propósito deste documento**: descrever o *design* do índice — a tese de negócio, os pilares, as variáveis e a estratégia de modelagem. Detalhes técnicos de implementação estão em [`Arquitetura_Tecnica.md`](Arquitetura_Tecnica.md); schemas completos estão em [`Dicionario_de_Dados.md`](Dicionario_de_Dados.md); cronograma e entregáveis estão em [`Plano_de_Implementacao.md`](Plano_de_Implementacao.md).

---

## 1. Pergunta central e tese

**Quais municípios brasileiros apresentam maior potencial para expansão de um banco digital?**

A melhor oportunidade não é necessariamente a cidade mais rica, e sim o cruzamento **demanda × adoção digital × baixa penetração bancária tradicional**.

> **Natureza do curso**: MBA de Engenharia de Dados — o projeto é avaliado como **pipeline de dados** (ingestão → limpeza → EDA → modelagem). O IPB é o produto; o pipeline é o entregável.

---

## 2. Estratégia de dados: NÚCLEO × STRETCH

Para garantir entrega mesmo com indisponibilidade de fontes, adotamos duas camadas de escopo:

- **NÚCLEO (MVP)**: indicadores de coleta barata (API ou download direto) que garantem o índice funcionando.
- **STRETCH**: enriquecimento opcional, só explorado depois que o núcleo estiver consolidado.

### Critérios de seleção

1. **Relevância para a tese**
   - *Anatel* mede a infraestrutura (fibra/banda larga) que viabiliza o uso do app.
   - *BCB Pix* mede a maturidade digital financeira da população.
   - *BCB Estban* mapeia a concorrência física (agências, depósitos, crédito).
2. **Confiabilidade**: fontes oficiais (IBGE, Banco Central, Anatel) com metodologia pública.
3. **Viabilidade técnica**: evitamos microdados pesados (ex: Caged) no núcleo.

### Decisões de escopo mantidas

- Coleta nacional (5.570 municípios).
- Ranking principal com corte ≥ 20 mil hab. (~1.800 municípios).
- Leitura em estratos: capitais/grandes (> 500 mil) separadas das médias (50–500 mil).
- Pesos iguais na base + média geométrica dos pilares + análise de sensibilidade.

---

## 3. Arquitetura do IPB

Cinco pilares compõem o índice. As variáveis em **negrito** fazem parte do NÚCLEO e estão disponíveis na `trusted_municipios`.

| Pilar | O que mede | Variáveis disponíveis |
|---|---|---|
| **A. Capacidade de Consumo** | Renda, população, PIB per capita | `populacao_total`, `rendimento_domiciliar_per_capita`, `pib_per_capita` |
| **B. Dinamismo Econômico** | Crescimento populacional, crescimento do Pix | `pix_per_capita_12m`, `pix_total_transacoes_12m` |
| **C. Adoção Digital** | Pix, banda larga fixa, internet domiciliar | `pix_per_capita_12m`, `banda_larga_fixa_por_100_hab` |
| **D. Gap Bancário** | Agências, depósitos e crédito per capita | `agencias_por_100k_hab`, `depositos_per_capita`, `credito_per_capita` |
| **E. Perfil Demográfico** | Jovens 18–35, urbanização, escolaridade, IDHM | `populacao_18_35_pct`, `populacao_urbana_pct`, `escolaridade_ensino_medio_pct`, `idhm` |

### Fórmula base

```
IPB_m = (A_m × B_m × C_m × D_m × E_m)^(1/5) × 100
```

Cada variável é normalizada em 0–1 (min-max, com winsorização no 1% extremo); cada pilar é a média simples das suas variáveis.

> **Gap bancário invertido**: quanto *menor* o número de agências, depósitos e crédito per capita, *maior* a oportunidade digital. Essa inversão é aplicada antes da normalização.

### Uso do índice (entregável final)

- Ranking geral e por estrato.
- Quadrante Potencial × Gap Bancário.
- Ficha do município.
- Ondas de expansão (ex: Onda 1 = Top 50).
- Mapa coroplético.

---

## 4. Indicadores do núcleo por pilar

### Pilar A — Capacidade de Consumo

| Indicador | Fonte | Status |
|---|---|---|
| **População residente** | IBGE/SIDRA Censo 2022 | NÚCLEO |
| **Rendimento domiciliar per capita** | IBGE/SIDRA Censo 2022 | NÚCLEO |
| **PIB municipal e PIB per capita** | IBGE PIB dos Municípios 2023 | NÚCLEO |
| Valor adicionado de serviços | IBGE PIB dos Municípios | STRETCH — **nulo para 2023** no arquivo de origem; mantido apenas na camada `raw`. |

### Pilar B — Dinamismo Econômico

| Indicador | Fonte | Status |
|---|---|---|
| Crescimento populacional 2010→2022 | IBGE/SIDRA | STRETCH |
| **Volume/quantidade Pix (12 meses)** | BCB/Olinda | NÚCLEO |
| Saldo de empregos formais | Novo Caged | STRETCH |

### Pilar C — Adoção Digital

| Indicador | Fonte | Status |
|---|---|---|
| **Volume Pix per capita** | BCB/Olinda | NÚCLEO |
| **Banda larga fixa por 100 hab.** | Anatel | NÚCLEO |
| % domicílios com internet | IBGE/SIDRA Tabela 7307 | NÚCLEO/ALTERNATIVA — API instável para `N6[all]`; usa-se `banda_larga_fixa_por_100_hab` como proxy. |
| Banda larga móvel | Anatel | Fora do escopo |

### Pilar D — Gap Bancário (invertido)

| Indicador | Fonte | Status |
|---|---|---|
| **Agências por 100 mil hab.** | BCB/Estban | NÚCLEO |
| **Depósitos e crédito per capita** | BCB/Estban | NÚCLEO |

### Pilar E — Perfil Demográfico

| Indicador | Fonte | Status |
|---|---|---|
| **% população 18–35 anos** | IBGE/SIDRA Censo 2022 | NÚCLEO |
| **% população urbana** | IBGE/SIDRA Censo 2022 | NÚCLEO |
| **Escolaridade (% ensino médio+)** | IBGE/SIDRA Censo 2022 | NÚCLEO — indicador principal do pilar E. |
| IDHM | Ipeadata (PNUD/Atlas 2010) | NÚCLEO — variável histórica de referência. Atlas Brasil 2022 indisponível. |

---

## 5. Etapa 3: ML sem target supervisionado

Não há variável-alvo para previsão — e não precisa. O ML serve para estruturar o índice e criar arquétipos:

1. **PCA** sobre as variáveis normalizadas → verifica se os 5 pilares são dimensões distintas e gera cenário alternativo de pesos *data-driven*.
2. **K-Means** sobre os pilares → agrupa municípios em **arquétipos de expansão** (ex.: "cidades médias conectadas e desatendidas" vs. "polos maduros saturados").

O mapa de clusters **é** o "Mapa do Potencial Bancário" do título.

---

## 6. Cuidados metodológicos para a defesa

1. **Vintage misto declarado**: estrutura (Censo 2022) + conjuntura (Pix/Anatel/Estban 2025–26) + histórico (IDHM 2010) = índice atualizável, por escolha e por limitação de dados.
2. **Efeito polo regional**: Pix/depósitos concentram na sede da microrregião — tratar como insight, não defeito.
3. **Winsorização** no 1% extremo antes de normalizar.
4. **Robustez**: Top 100 deve ser estável entre cenários de peso; se não for, reportar.

---

## 7. Aspectos legais e éticos

Não há dados pessoais sensíveis (PII) no pipeline. Todas as bases são agregadas em nível municipal e de domínio público, não se enquadrando na LGPD.

O índice foca em infraestrutura e volume financeiro. Não usamos atributos sensíveis (cor/raça, etc.) para rankear. O principal risco ético é o "efeito polo", onde cidades-dormitório parecem desatendidas por transferirem recursos para a metrópole vizinha — isso será endereçado nas regras de ondas de expansão.

---

## 8. Links rápidos

| Documento | Para quê serve |
|---|---|
| [`README.md`](../README.md) | Visão geral, equipe e roadmap. |
| [`Plano_de_Implementacao.md`](Plano_de_Implementacao.md) | Cronograma e entregáveis por fase. |
| [`Arquitetura_Tecnica.md`](Arquitetura_Tecnica.md) | Desenho técnico, diagramas, requisitos, custos e riscos. |
| [`Guia_de_Coleta.md`](Guia_de_Coleta.md) | Como acessar cada fonte de dados (URLs, APIs, downloads). |
| [`Guia_de_Execucao.md`](Guia_de_Execucao.md) | Como instalar e rodar o pipeline localmente. |
| [`Dicionario_de_Dados.md`](Dicionario_de_Dados.md) | Schema completo das tabelas `raw_*` e `trusted_municipios`. |
| [`AGENTS.md`](../AGENTS.md) | Regras e convenções do repositório. |

---

*Documento v4 — refatorado para focar no design do índice e remover detalhes técnicos/operacionais já cobertos por outros guias.*
