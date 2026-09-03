# Plano de Recalibração do IPB — Reduzindo o Viés para Cidades Ricas/Conectadas

> **Objetivo**: propor caminhos para transformar o IPB de um índice de "riqueza municipal" em uma métrica de **oportunidade real de expansão bancária digital**.  
> **Escopo**: análise e planejamento. Nenhuma execução de código está prevista neste documento.  
> **Branch**: `feature/etapa2-eda-e-limpeza`  
> **Data**: 2026-08-31

---

## 1. Diagnóstico do problema

### 1.1 O que está acontecendo hoje

O IPB *alpha* atual é dominado por cidades ricas, conectadas e frequentemente já bancarizadas. O Top 10 inclui Barueri, Paulínia, Ilhabela, Nova Lima, Itapema e Balneário Camboriú — cidades que qualquer análise trivial já apontaria como "boas oportunidades".

Isso acontece por 4 razões estruturais:

1. **Peso desproporcional para riqueza e conectividade**  
   Com pesos iguais entre 5 pilares, Pilares A (renda/PIB), B (Pix) e C (banda larga/Pix) somam 60% do índice. O Pilar D (gap bancário), que deveria contrabalançar, tem apenas 20%.

2. **O Pilar D não inverte completamente a lógica de riqueza**  
   Cidades ricas têm **mais agências, mais depósitos e mais crédito** do que cidades pobres. A inversão do Pilar D (quanto menor, melhor) só funciona se a cidade for rica **e** desbancarizada. Cidades ricas e bancarizadas (ex.: Barueri) continuam com score alto no Pilar D invertido porque seus valores normalizados ainda são medianos/altos após a inversão.

3. **Redundância no Pilar D amplifica o problema**  
   `agencias`, `depositos` e `credito` têm correlação 0,88–0,91. Isso dá peso implícito triplo a uma única dimensão: "presença bancária tradicional". A inversão de 3 variáveis quase iguais não cria diversificação — apenas repete o mesmo sinal.

4. **Normalização min-max dilui o efeito do gap**  
   A normalização comprime outliers. Cidades com 0 agências (2.656 municípios) ficam no valor mínimo (0 após inversão → 1 no Pilar D), mas cidades com poucas agências e alto PIB podem ter score intermediário no Pilar D e muito alto nos Pilares A/B/C, dominando o ranking.

### 1.2 Por que isso é ruim para o produto

- **Óbvio**: não gera insight acionável;
- **Injusto**: cidades médias e pequenas com adoção digital crescente e pouca concorrência ficam abaixo de metrópoles já saturadas;
- **Frágil para defesa**: qualquer avaliador pode apontar que o índice apenas replica o mapa de riqueza do Brasil;
- **Conflito com a tese**: a pergunta central é "onde expandir um banco digital", não "onde já está tudo bem servido".

---

## 2. Princípios para a nova versão do IPB

Para que o índice meça oportunidade de verdade, ele deve premiar municípios que atendam a:

1. **Demanda econômica real**: renda, PIB, emprego formal;
2. **Adoção digital acima do esperado para o nível de bancarização**: cidades que já usam muito Pix/digital apesar de pouca infra física;
3. **Baixa concorrência bancária tradicional**: poucas agências, poucos correspondentes, baixo crédito per capita;
4. **Infraestrutura digital mínima**: banda larga / 4G suficiente para operar um app;
5. **Perfil demográfico favorável**: população jovem e escolarizada.

A grande mudança conceitual é passar de:

```
IPB = riqueza × conectividade × (1 / bancarização)
```

para:

```
IPB = demanda × (adoção_digital / bancarização) × infraestrutura_mínima × perfil
```

Ou seja, a adoção digital e o gap bancário devem interagir multiplicativamente, não apenas serem somados como pilares independentes.

---

## 3. Abordagem 1 — Rápida (ajustes com dados atuais)

### 3.1 Objetivo

Reduzir o viés com **mínima alteração na arquitetura**, usando apenas os dados já disponíveis.

### 3.2 Ações propostas

#### A. Recalibração de pesos

Aplicar pesos diferenciados nos pilares:

| Pilar | Peso atual | Peso proposto | Justificativa |
|---|---|---|---|
| A — Capacidade de Consumo | 1,0 | **0,5** | Renda/PIB são importantes, mas não devem dominar |
| B — Dinamismo Econômico | 1,0 | **0,75** | Pix é proxy de atividade, mas precisa ser relativizado |
| C — Adoção Digital | 1,0 | **0,75** | Banda larga é necessária, mas não suficiente |
| D — Gap Bancário | 1,0 | **1,5** | Deve ser o diferencial do índice |
| E — Perfil Demográfico | 1,0 | **1,0** | Mantido |

Fórmula adaptada:

```
IPB = (A^0.5 × B^0.75 × C^0.75 × D^1.5 × E^1.0)^(1/4.5) × 100
```

#### B. Redução de redundância no Pilar D

Manter apenas **uma** variável principal no Pilar D, por exemplo:

- `agencias_por_100k_hab` (mais direta: presença física de bancos tradicionais);
- Ou um score combinado das 3 variáveis via PCA interno.

Impacto esperado: reduzir o peso implícito da bancarização tradicional e evitar que depósitos/crédito (que crescem com riqueza) contaminem o sinal de "gap".

#### C. Remover `populacao_urbana_pct` do Pilar E

Essa variável tem correlação 0,70 com `escolaridade_ensino_medio_pct`. Manter ambas amplifica o efeito "cidade desenvolvida". O indicador principal do Pilar E deve ser a escolaridade.

#### D. Criar feature `tensao_digital_bancaria`

Nova variável híbrida que combina adoção digital e gap bancário:

```
tensao_digital_bancaria = pix_per_capita_12m / (agencias_por_100k_hab + 1)
```

Interpretação: quanto mais Pix per capita e menos agências, maior a tensão (oportunidade). Essa variável pode entrar como uma nova variável no Pilar B ou D, ou como um pilar extra.

#### E. Segmentação obrigatória por estrato

Não publicar um ranking único. Publicar rankings separados para:

- Grandes cidades (> 500 mil hab.)
- Cidades médias (50–500 mil hab.)
- Cidades pequenas (< 50 mil hab.)

Isso evita comparar diretamente Barueri com municípios de 10 mil habitantes.

### 3.3 Resultado esperado

- Cidades ricas e bancarizadas (Barueri, Paulínia) caem no ranking;
- Cidades médias com alta adoção Pix e poucas agências sobem;
- O índice fica mais alinhado à tese de expansão bancária digital.

### 3.4 Limitações

- Ainda usa dados de Pix corrigidos, mas sem contexto empresarial (PJ);
- Ainda não diferencia "cidade dormitório" de "cidade polo";
- Ainda depende de variáveis per capita que favorecem cidades pequenas ricas.

---

## 4. Abordagem 2 — Média complexidade (novas features com bases disponíveis)

### 4.1 Objetivo

Incorporar novas variáveis usando bases públicas que já existem e podem ser coletadas sem grandes mudanças no pipeline.

### 4.2 Novas bases a integrar

#### 4.2.1 Correspondentes bancários do BCB (alta prioridade)

- **Fonte**: Portal de Dados Abertos do BCB — "Pontos de Atendimento de Correspondentes";
- **Granularidade**: municipal;
- **Relevância**: mede a concorrência real no varejo. Cidades ricas têm muitas agências, mas também muitos correspondentes (lotéricas, mercados, farmácias). Uma cidade com poucas agências **e** poucos correspondentes é uma oportunidade melhor do que uma cidade com poucas agências mas muitos correspondentes;
- **Feature**: `correspondentes_por_100k_hab`;
- **Uso**: substituir ou complementar `agencias_por_100k_hab` no Pilar D.

#### 4.2.2 Cobertura 4G/5G da Anatel (alta prioridade)

- **Fonte**: Anatel — Painel de Cobertura Móvel;
- **Granularidade**: municipal;
- **Relevância**: a banda larga fixa é uma proxy limitada. A cobertura 4G/5G mede a capacidade real de usar apps bancários no celular;
- **Feature**: `cobertura_4g_5g_pct`;
- **Uso**: substituir ou complementar `banda_larga_fixa_por_100_hab` no Pilar C.

#### 4.2.3 Dados do Pix detalhados (já coletados, mas subutilizados)

A raw `raw_bcb_pix_transacoes` já contém:
- Volume e quantidade por PF/PJ;
- Volume e quantidade de recebedores;
- Quantidade de pessoas (pagadores/recebedores).

Features possíveis:

| Feature | Descrição | Uso |
|---|---|---|
| `pix_pj_pct` | % do volume Pix de Pessoa Jurídica | Identificar dinamismo empresarial |
| `pix_recebedores_per_capita` | Recebedores / população | Medir penetração comercial |
| `pix_ticket_medio` | Valor médio por transação | Comportamento de uso |
| `pix_pagadores_per_capita` | Pagadores / população | Adoção populacional real |

### 4.3 Novas features derivadas

#### 4.3.1 `penetracao_digital_relativa`

```
penetracao_digital_relativa = pix_per_capita_12m / pib_per_capita
```

Interpretação: quanto de Pix a cidade transaciona **em relação à sua renda**. Cidades pobres com adoção digital acima do esperado sobem no ranking.

#### 4.3.2 `gap_bancario_completo`

Combinar agências e correspondentes:

```
gap_bancario_completo = 1 / (agencias_por_100k_hab + correspondentes_por_100k_hab + 1)
```

Interpretação: presença bancária total (tradicional + correspondentes). Cidades ricas com muitas lotéricas deixam de parecer "desbancarizadas".

> **ATUALIZAÇÃO (2026-09) — fórmula recalibrada.** A forma hiperbólica acima saturava: como correspondentes chegam a centenas por 100k hab em cidades pequenas, o gap colapsava e o IPB de ~119 municípios zerava. A implementação atual (`src/analytics/ipb.py`) usa **gap linear** = `1 − min-max(winsorize(presença combinada))`, mesmo padrão dos pilares D da V1/V2.

#### 4.3.3 `oportunidade_relativa`

```
oportunidade_relativa = (pix_per_capita_percentil) / (presenca_bancaria_percentil + 1)
```

Interpretação: cidades com adoção digital no percentil 90 e presença bancária no percentil 10 são oportunidades extremas.

### 4.4 Nova estrutura sugerida de pilares

| Pilar | Variáveis | Peso |
|---|---|---|
| A — Demanda Econômica | `pib_per_capita`, `rendimento_domiciliar_per_capita` | 0,75 |
| B — Dinamismo Digital-Financeiro | `pix_per_capita_12m`, `pix_pj_pct`, `penetracao_digital_relativa` | 1,0 |
| C — Infraestrutura Digital | `banda_larga_fixa_por_100_hab`, `cobertura_4g_5g_pct` | 0,75 |
| D — Concorrência Bancária (invertido) | `gap_bancario_completo` (agências + correspondentes) | 1,5 |
| E — Perfil Demográfico | `escolaridade_ensino_medio_pct`, `populacao_18_35_pct` | 1,0 |

### 4.5 Resultado esperado

- Redução significativa do viés para cidades ricas já bancarizadas;
- Surgimento de cidades médias do interior com alta adoção Pix e pouca concorrência;
- Melhor discriminação entre "cidade rica saturada" e "cidade em ascensão digital".

### 4.6 Limitações

- Correspondentes bancários e cobertura 4G/5G ainda precisam ser coletados e integrados;
- Ainda não resolve completamente o efeito "cidade dormitório";
- Ainda não há validação externa com dados reais de expansão bancária.

---

## 5. Abordagem 3 — Complexa (redesenho com novos dados e modelagem)

### 5.1 Objetivo

Redesenhar o IPB como um **modelo de potencial residual**: comparar o que a cidade *deveria* transacionar em Pix/digital dado sua renda, escolaridade e infraestrutura com o que ela *realmente* transaciona. O potencial está nas cidades que transacionam **mais do que o esperado** para o nível de bancarização, ou que transacionam **menos do que o esperado** para o nível de renda (oportunidade não realizada).

### 5.2 Novas bases necessárias

#### 5.2.1 CNPJ / MEI por município (Receita Federal)

- **Fonte**: [Dados Abertos da Receita Federal](https://www.gov.br/receitafazenda/pt-br/acesso-a-informacao/dados-abertos) / [CNPJ Store](https://www.cnpjstore.com/);
- **Granularidade**: endereço do CNPJ (agregável por município);
- **Relevância**: densidade empresarial é um indicador de demanda por serviços bancários PJ. Uma cidade com muitos CNPJs per capita e pouca presença bancária é oportunidade clara;
- **Features**: `cnpjs_ativos_per_capita`, `mei_per_capita`, `empresas_servicos_per_capita`;
- **Dificuldade**: média — arquivos grandes, mas existem agregados prontos.

#### 5.2.2 Novo Caged (emprego formal)

- **Fonte**: Ministério do Trabalho e Emprego;
- **Granularidade**: municipal;
- **Relevância**: massa salarial real e empregos formais são proxies de renda e demanda por crédito consignado/pessoal;
- **Features**: `empregos_formais_per_capita`, `massa_salarial_per_capita`, `saldo_empregos_12m`;
- **Dificuldade**: média — dados públicos, mas volumosos.

#### 5.2.3 SCR.data / dados de crédito do BCB

- **Fonte**: [Portal de Dados Abertos do BCB — SCR.data](https://dadosabertos.bcb.gov.br/dataset/scr_data);
- **Granularidade**: regional/UF (dados municipais detalhados são restritos);
- **Relevância**: permite validar se o ranking IPB está alinhado com mercado de crédito real;
- **Uso**: validação cruzada, não feature principal (por limitação de granularidade).

#### 5.2.4 Índice de Progresso Social (IPS)

- **Fonte**: [IPS Brasil](https://www.ipsbrasil.org.br/);
- **Granularidade**: municipal;
- **Relevância**: substituto moderno e mais abrangente que o IDHM 2010. Mede necessidades humanas básicas, fundamentos do bem-estar e oportunidades;
- **Feature**: `ips_2024`;
- **Dificuldade**: baixa — dados disponíveis em planilha.

#### 5.2.5 SICONFI (finanças municipais)

- **Fonte**: Tesouro Nacional / STN;
- **Granularidade**: municipal;
- **Relevância**: saúde fiscal do município indica estabilidade econômica e capacidade de parcerias;
- **Features**: `receita_per_capita`, `despesa_per_capita`, `capacidade_pagamento`;
- **Dificuldade**: alta — dados contábeis complexos.

### 5.3 Modelagem proposta

#### 5.3.1 Modelo de potencial residual (recomendado)

Passos:

1. **Modelar Pix per capita esperado** a partir de variáveis estruturais:
   ```
   log(pix_per_capita_esperado) = f(renda, escolaridade, urbanização, emprego formal, empresas_per_capita)
   ```
   Usar regressão linear, Random Forest ou XGBoost.

2. **Calcular resíduo**:
   ```
   residuo_pix = pix_per_capita_real - pix_per_capita_esperado
   ```

3. **Interpretar**:
   - `residuo_pix > 0`: cidade transaciona mais Pix do que o esperado → adoção digital avançada;
   - `residuo_pix < 0`: cidade transaciona menos do que o esperado → oportunidade não realizada.

4. **Combinar com gap bancário**:
   ```
   IPB_v2 = (residuo_pix_positivo) × (1 / presenca_bancaria_total) × infraestrutura_digital
   ```

Isso separa claramente:
- Cidades ricas que já usam muito digital (resíduo alto, mas bancarizadas → oportunidade média);
- Cidades médias que usam muito digital apesar da pouca renda (resíduo alto, desbancarizadas → oportunidade alta);
- Cidades ricas que ainda usam pouco digital (resíduo baixo → oportunidade futura, mas não prioritária).

#### 5.3.2 Análise de Envoltória de Dados (DEA)

A DEA identifica municípios "eficientes" em converter insumos (renda, escolaridade, infraestrutura) em adoção digital, dado um nível de bancarização. Municípios eficientes e com baixa bancarização são oportunidades.

#### 5.3.3 Clusterização (K-Means) com perfis de expansão

Agrupar municípios em arquétipos:

| Arquétipo | Características | Estratégia |
|---|---|---|
| **Oportunidade clara** | Alto Pix, baixa bancarização, infra digital OK | Expansão imediata |
| **Mercado maduro** | Alto Pix, alta bancarização | Manutenção / pouca ação |
| **Potencial dormido** | Baixo Pix, baixa bancarização, renda crescendo | Ações educativas / campanhas |
| **Conectividade fraca** | Baixa infra digital | Não priorizar |
| **Polo regional** | Alto Pix, poucas agências, mas influencia microrregião | Analisar com cuidado |

### 5.4 Nova estrutura de pilares (v2)

| Pilar | Variáveis | Peso |
|---|---|---|
| A — Demanda Estrutural | `rendimento_domiciliar_per_capita`, `massa_salarial_per_capita`, `empresas_per_capita` | 1,0 |
| B — Potencial Digital Residual | `residuo_pix` (real vs. esperado) | 1,5 |
| C — Infraestrutura Digital | `banda_larga_fixa_por_100_hab`, `cobertura_4g_5g_pct` | 0,75 |
| D — Concorrência Bancária (invertido) | `gap_bancario_completo` (agências + correspondentes) | 1,5 |
| E — Perfil Humano | `escolaridade_ensino_medio_pct`, `populacao_18_35_pct`, `ips_2024` | 1,0 |

### 5.5 Resultado esperado

- Eliminação prática do viés para cidades ricas trivialmente óbvias;
- Identificação de cidades médias e pequenas com potencial real de expansão;
- Justificativa metodológica robusta para defesa ("o índice mede potencial residual, não riqueza");
- Base para um produto acadêmico e eventualmente comercial mais sério.

### 5.6 Limitações e riscos

- **Maior complexidade**: exige coleta de mais bases e modelagem;
- **Risco de overfitting**: o modelo residual pode capturar ruído se as variáveis estruturais forem mal escolhidas;
- **Interpretação**: mais difícil de explicar para um público não técnico;
- **Prazo**: pode não caber no cronograma atual do MBA (entrega em 17/09).

---

## 6. Comparação das abordagens

| Critério | Abordagem 1 (Rápida) | Abordagem 2 (Média) | Abordagem 3 (Complexa) |
|---|---|---|---|
| Esforço de implementação | Baixo | Médio | Alto |
| Novas bases necessárias | Nenhuma | 2 (correspondentes, 4G/5G) | 4+ (CNPJ, Caged, IPS, SICONFI) |
| Redução do viés para cidades ricas | Moderada | Significativa | Muito alta |
| Robustez metodológica | Baixa/Média | Média/Alta | Alta |
| Facilidade de defesa | Média | Alta | Muito alta |
| Prazo para entrega do MBA | Viável | Viável com esforço | Arriscado |
| Manutenção futura | Simples | Média | Complexa |

---

## 7. Recomendação do autor

**Recomendo executar as Abordagens 1 e 2 em sequência**, e deixar a Abordagem 3 como evolução futura ou como capítulo avançado do trabalho acadêmico.

### Por quê?

- A Abordagem 1 resolve 60–70% do problema com pouco esforço;
- A Abordagem 2 resolve mais 20–25% e já incorpora dados públicos disponíveis;
- A Abordagem 3 é ideal, mas pode comprometer a entrega do MBA se iniciada agora.

### Sequência sugerida

1. **Semana 1**: implementar Abordagem 1 (pesos, redução de redundância, `tensao_digital_bancaria`, segmentação por estrato);
2. **Semana 2**: coletar e integrar correspondentes bancários + cobertura 4G/5G (Abordagem 2);
3. **Semana 3**: testar combinações, gerar ranking final e documentar metodologia;
4. **Pós-MBA**: evoluir para modelo residual (Abordagem 3) se houver interesse comercial.

---

## 8. Próximos passos concretos (para execução futura)

### Abordagem 1

- [ ] Implementar pesos diferenciados no notebook `04_integracao_correlacoes.ipynb`;
- [ ] Reduzir Pilar D para 1 variável ou PCA interno;
- [ ] Remover `populacao_urbana_pct` do Pilar E;
- [ ] Criar feature `tensao_digital_bancaria`;
- [ ] Gerar ranking por estrato populacional;
- [ ] Comparar Top 100 antes/depois.

### Abordagem 2

- [ ] Criar ingestor para correspondentes bancários do BCB;
- [ ] Criar ingestor para cobertura 4G/5G da Anatel;
- [ ] Criar features `pix_pj_pct`, `penetracao_digital_relativa`, `gap_bancario_completo`;
- [ ] Recalcular IPB com nova estrutura de pilares;
- [ ] Validar ranking com análise de sensibilidade.

### Abordagem 3

- [ ] Mapear URLs e formatos das bases (CNPJ, Caged, IPS, SICONFI);
- [ ] Prototipar modelo residual de Pix per capita;
- [ ] Calcular resíduos e integrar ao IPB;
- [ ] Aplicar K-Means para arquétipos de expansão;
- [ ] Documentar metodologia completa.

---

## 9. Conclusão

O viés do IPB para cidades ricas/conectadas é **real, identificável e corrigível**. Não é "over" resolver isso — é o próprio propósito do índice. Se o IPB apenas replicar o mapa de riqueza do Brasil, ele falha como ferramenta de decisão.

A boa notícia é que existe um caminho evolutivo claro: ajustes rápidos já melhoram bastante, novas features públicas resolvem a maior parte do problema, e uma remodelagem mais sofisticada pode ser feita como evolução futura.

**O mais importante**: o índice deve passar a medir **oportunidade relativa**, não riqueza absoluta.

---

*Documento gerado para análise e planejamento. Nenhum código foi executado.*
