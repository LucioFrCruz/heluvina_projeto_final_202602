# Comparacao de Tres Abordagens do IPB

> **Objetivo**: comparar o IPB Clássico (V1), o IPB Recalibrado (V2) e o IPB Presença Bancária Completa (V3, ex-Abordagem 2).  
> **Escopo**: a V3 já foi publicada no BigQuery (tabelas `analytics_ipb_*`); este documento consolida a comparação das três versões a partir da mesma base.  
> **Data**: 2026-09-03  
> **Código-fonte das fórmulas**: `src/analytics/ipb.py`

---

## 1. Resumo Executivo

Três versões do índice foram calculadas a partir da mesma base `trusted_municipios` (com o bug do Pix corrigido):

| Versão | Conceito |
|---|---|
| **IPB Clássico (V1)** | Fórmula original: 5 pilares com pesos iguais. Premia cidades ricas, conectadas e com demanda digital, mas pune pouco cidades já bancarizadas (Pilar D usa 3 variáveis redundantes). |
| **IPB Recalibrado (V2)** | Ajuste rápido anti-viés: pesos diferenciados, Pilar D reduzido a apenas `agencias_por_100k_hab`, Pilar E sem `populacao_urbana_pct` e inclusão de `tensao_digital_bancaria` (Pix / agências). Diminui a influência da renda pura. |
| **IPB Presença Bancária Completa (V3, ex-Abordagem 2)** | Redesenho do Pilar D: agências bancárias estão em queda, então o índice passa a considerar **correspondentes bancários do BCB por tipo** (posto, filial, sede, agência) com pesos diferentes. Adiciona `penetracao_digital_relativa` (Pix / PIB) e `gap_bancario_completo`. Pilar A enriquecido com **empregos formais por 1.000 hab** (CEMPRE/IBGE), capturando formalização que o PIB per capita sub-declara. Inclui ainda uma **flag de turismo suave** (score contínuo, desconto máximo de 15% no pilar digital) para não privilegiar cidades pequenas com fluxo turístico. |

### Estatísticas gerais

| Métrica | IPB Clássico (V1) | IPB Recalibrado (V2) | IPB Presença Bancária Completa (V3) |
|---|---|---|---|
| Média | 35.85 | 40.85 | 36.64 |
| Mediana | 35.86 | 40.65 | 36.67 |
| Máximo | 82.54 | 83.85 | 73.33 |
| Mínimo | 0.0 | 0.0 | 0.0 |

---

## 2. Como cada versão funciona

### 2.1 IPB Clássico (V1)

Cinco pilares com **pesos iguais** (média geométrica):
- **A. Capacidade de consumo**: PIB per capita + rendimento domiciliar per capita.
- **B. Dinamismo econômico**: Pix per capita últimos 12 meses.
- **C. Adoção digital**: banda larga fixa por 100 habitantes.
- **D. Gap bancário**: agências, depósitos e crédito per capita (todas invertidas).
- **E. Perfil demográfico**: escolaridade, população 18-35 anos e população urbana.

**Problema**: cidades ricas já bancarizadas (Barueri, Itapema, Balneário Camboriú) lideram porque a renda e o digital pesam muito, enquanto o gap bancário é fraco.

### 2.2 IPB Recalibrado (V2)

Mesma estrutura de 5 pilares, mas com **pesos diferenciados**:
- Pilar A (renda) reduzido para 0.5.
- Pilares B (digital) e C (infra) com 0.75 cada.
- Pilar D (gap bancário) ampliado para 1.5 e simplificado para apenas agências.
- Pilar E sem `populacao_urbana_pct` (redundante com banda larga).
- Feature nova: `tensao_digital_bancaria` = Pix per capita / (agências por 100k + 1).

**Efeito**: cidades pequenas com muito Pix e pouca agência sobem no ranking. Ainda prevalecem SC e MT, mas já não é um ranking de riqueza pura.

### 2.3 IPB Presença Bancária Completa (V3, ex-Abordagem 2)

Redesenho mais profundo:
- **Pilar A enriquecido com empregos formais** (CEMPRE/IBGE, ano 2024): além de PIB per capita e rendimento domiciliar, o pilar inclui `empregos_formais_por_1000_hab` (pessoal ocupado com carteira assinada). Racional: folha de pagamento formal é o gancho produtivo nº 1 de banco/fintech (conta-salário, crédito consignado, PJ), e a variável captura formalização que o PIB per capita sub-declara — capitais como São Luís e Belém têm massa salarial bancarizável com PIB pc mediano. Movimento validado: 10 trocas no Top 100, todas capitais/polos formais entrando e dormitórios de baixa formalização saindo.
- **Agências sozinhas não refletem mais a realidade**: o número de agências bancárias vem caindo no Brasil. O BCB registra 216 mil **correspondentes** (lotéricas, caixas eletrônicos, correspondentes bancários). O índice passa a considerar a **presença bancária completa** = agências + correspondentes.
- **Correspondentes ponderados por tipo**: postos (peso 1.0), filiais (0.7), sedes (0.4) e agências (1.0). Postos são pontos mais simples; filiais/sedes têm capacidade maior.
- **Gap bancário completo (linear)** = 1 − min-max(winsorize(presença combinada)), com presença = agências + correspondentes ponderados por 100k. A forma hiperbólica original (`1 / (presença + 1)`) saturava em cidades pequenas com muitas lotéricas e zerava o IPB delas; o gap linear preserva a ordenação sem o efeito colapso.
- **Penetração digital relativa** = Pix per capita / PIB per capita. Premia cidades que transacionam muito proporcionalmente à sua riqueza.
- **Flag de turismo suave**: score contínuo baseado em Pix alto + PIB baixo + cidade pequena. Aplica desconto máximo de 15% no pilar digital para evitar que cidades turísticas (Arraial do Cabo, Búzios) disparem só por fluxo de visitantes. Como validador objetivo de turismo, a tabela acompanha `unidades_alojamento_alimentacao_por_1000_hab` (CEMPRE), sem entrar na fórmula.
- **Rankings separados por estrato**: pequena, média e grande.

**Efeito**: quebra o viés para cidades ricas já bancarizadas e passa a destacar municípios com alta demanda digital e baixa estrutura bancária física.

---

## 3. Top 10 por versão

### 3.1 IPB Clássico (V1)

| Rank | Município | UF | Estrato | IPB |
|---|---|---|---|---|
| 1 | Barueri | SP | media | 82.54 |
| 2 | Itapema | SC | media | 82.24 |
| 3 | Balneário Camboriú | SC | media | 81.81 |
| 4 | Paulínia | SP | media | 80.87 |
| 5 | Itajaí | SC | media | 80.05 |
| 6 | Ilhabela | SP | pequena | 79.87 |
| 7 | Nova Lima | MG | media | 79.85 |
| 8 | Itupeva | SP | media | 79.15 |
| 9 | Santa Carmem | MT | pequena | 78.93 |
| 10 | Nova Mutum | MT | media | 78.80 |

### 3.2 IPB Recalibrado (V2)

| Rank | Município | UF | Estrato | IPB |
|---|---|---|---|---|
| 1 | Bombinhas | SC | pequena | 83.85 |
| 2 | Confins | MG | pequena | 82.39 |
| 3 | Santa Rita do Trivelato | MT | pequena | 81.73 |
| 4 | Santa Carmem | MT | pequena | 80.11 |
| 5 | Alto Horizonte | GO | pequena | 77.09 |
| 6 | Nova Mutum | MT | media | 76.33 |
| 7 | Balneário Camboriú | SC | media | 75.82 |
| 8 | Itapema | SC | media | 75.21 |
| 9 | Primavera do Leste | MT | media | 74.70 |
| 10 | Itajaí | SC | media | 74.65 |

### 3.3 IPB Presença Bancária Completa (V3)

| Rank | Município | UF | Estrato | IPB |
|---|---|---|---|---|
| 1 | Bombinhas | SC | pequena | 73.33 |
| 2 | Nova Lima | MG | media | 72.41 |
| 3 | Confins | MG | pequena | 71.97 |
| 4 | Balneário Camboriú | SC | media | 71.00 |
| 5 | Eusébio | CE | media | 70.65 |
| 6 | Itapema | SC | media | 70.39 |
| 7 | Palmas | TO | media | 70.27 |
| 8 | Santana de Parnaíba | SP | media | 70.19 |
| 9 | Florianópolis | SC | grande | 68.85 |
| 10 | Santa Rita do Trivelato | MT | pequena | 68.74 |

---

## 4. Análise do Top 100

### 4.1 Movimentação geral

| Comparação | Saíram do Top 100 | Entraram no Top 100 |
|---|---|---|
| V1 -> V2 | 40 | 40 |
| V2 -> V3 | 39 | 39 |
| V1 -> V3 | 39 | 39 |

### 4.2 Cidades que saíram do Top 100 (V1 -> V3)

Cidades ricas e já bancarizadas que deixaram de figurar entre as 100 primeiras:

| Município | UF | Estrato | Rank V1 | Rank V3 |
|---|---|---|---|---|
| Fernando de Noronha | PE | pequena | 13 | 2578 |
| São José | SC | media | 28 | 198 |
| Jundiaí | SP | media | 30 | 110 |
| Porto Belo | SC | pequena | 31 | 233 |
| São Caetano do Sul | SP | media | 33 | 112 |
| Campo Novo do Parecis | MT | pequena | 40 | 142 |
| Santa Gertrudes | SP | pequena | 44 | 153 |
| Diamantino | MT | pequena | 50 | 254 |
| Cabedelo | PB | media | 52 | 299 |
| Blumenau | SC | media | 55 | 143 |
| Palhoça | SC | media | 56 | 162 |
| Atibaia | SP | media | 57 | 168 |
| Americana | SP | media | 60 | 237 |
| Toledo | PR | media | 62 | 182 |
| São José do Rio Preto | SP | media | 64 | 155 |
| Joinville | SC | grande | 65 | 125 |
| Extrema | MG | media | 66 | 175 |
| Barretos | SP | media | 67 | 132 |
| Sorocaba | SP | grande | 69 | 145 |
| Rio Verde | GO | media | 70 | 130 |
| Campo Verde | MT | pequena | 71 | 201 |
| Vera | MT | pequena | 72 | 241 |
| Maracaju | MS | pequena | 73 | 309 |
| Jaraguá do Sul | SC | media | 76 | 124 |
| São Francisco do Sul | SC | media | 77 | 282 |
| Gavião Peixoto | SP | pequena | 78 | 121 |
| Campo Grande | MS | grande | 80 | 161 |
| Dourados | MS | media | 82 | 286 |
| Navegantes | SC | media | 83 | 176 |
| Piracicaba | SP | media | 84 | 120 |
| Pedrinópolis | MG | pequena | 88 | 199 |
| Garopaba | SC | pequena | 89 | 164 |
| Canarana | MT | pequena | 92 | 135 |
| Cajamar | SP | media | 93 | 174 |
| Araucária | PR | media | 94 | 185 |
| Ilha Comprida | SP | pequena | 96 | 300 |
| Ponta Porã | MS | media | 97 | 244 |
| Nova Odessa | SP | media | 99 | 183 |
| Tapurah | MT | pequena | 100 | 406 |

### 4.3 Cidades que entraram no Top 100 (V1 -> V3)

Cidades que subiram e passaram a figurar entre as 100 primeiras oportunidades:

| Município | UF | Estrato | Rank V1 | Rank V3 |
|---|---|---|---|---|
| Brasília | DF | grande | 134 | 13 |
| São Paulo | SP | grande | 174 | 15 |
| Nova Serrana | MG | media | 131 | 22 |
| Belo Horizonte | MG | grande | 202 | 23 |
| Porto Alegre | RS | grande | 364 | 29 |
| Tibau do Sul | RN | pequena | 445 | 30 |
| Parnamirim | RN | media | 107 | 41 |
| João Pessoa | PB | grande | 194 | 43 |
| Vitória | ES | media | 258 | 44 |
| Engenheiro Coelho | SP | pequena | 191 | 45 |
| Curitiba | PR | grande | 120 | 47 |
| Aracaju | SE | grande | 239 | 50 |
| Rio de Janeiro | RJ | grande | 611 | 51 |
| Biguaçu | SC | media | 164 | 55 |
| Dumont | SP | pequena | 209 | 56 |
| Bady Bassitt | SP | pequena | 121 | 63 |
| Sarzedo | MG | pequena | 125 | 64 |
| Penha | SC | pequena | 122 | 68 |
| Araguaína | TO | media | 235 | 69 |
| São Luís | MA | grande | 366 | 70 |
| Santo André | SP | grande | 103 | 71 |
| Saltinho | SP | pequena | 170 | 72 |
| Fortaleza | CE | grande | 314 | 75 |
| Presidente Prudente | SP | media | 108 | 76 |
| Porto Velho | RO | media | 206 | 78 |
| Boa Vista | RR | media | 360 | 80 |
| Foz do Iguaçu | PR | media | 102 | 82 |
| Madre de Deus de Minas | MG | pequena | 195 | 83 |
| Araporã | MG | pequena | 186 | 84 |
| Rio Branco | AC | media | 395 | 86 |
| Taboão da Serra | SP | media | 288 | 87 |
| Governador Valadares | MG | media | 280 | 91 |
| Camboriú | SC | media | 236 | 92 |
| Montes Claros | MG | media | 488 | 93 |
| Passo de Torres | SC | pequena | 484 | 94 |
| Guarulhos | SP | grande | 140 | 95 |
| Nova Maringá | MT | pequena | 147 | 96 |
| Patos de Minas | MG | media | 149 | 97 |
| Belém | PA | grande | 542 | 99 |

---

## 5. Top 5 por Estrato Populacional

Além do ranking geral, apresentamos os líderes de cada estrato populacional nas três versões. Isso evita que cidades pequenas e grandes concorram no mesmo critério.

### Estrato: Grande

#### IPB Clássico (V1)

| Rank Geral | Rank no Estrato | Município | UF | IPB |
|---|---|---|---|---|
| 41 | 1 | Florianópolis | SC | 70.00 |
| 46 | 2 | Cuiabá | MT | 68.95 |
| 49 | 3 | Campinas | SP | 68.79 |
| 51 | 4 | Ribeirão Preto | SP | 68.68 |
| 61 | 5 | Goiânia | GO | 67.68 |

#### IPB Recalibrado (V2)

| Rank Geral | Rank no Estrato | Município | UF | IPB |
|---|---|---|---|---|
| 19 | 1 | Brasília | DF | 72.75 |
| 27 | 2 | Florianópolis | SC | 71.89 |
| 28 | 3 | Goiânia | GO | 71.76 |
| 32 | 4 | Cuiabá | MT | 71.04 |
| 47 | 5 | Uberlândia | MG | 69.47 |

#### IPB Presença Bancária Completa (V3)

| Rank Geral | Rank no Estrato | Município | UF | IPB |
|---|---|---|---|---|
| 9 | 1 | Florianópolis | SC | 68.85 |
| 11 | 2 | Goiânia | GO | 68.55 |
| 13 | 3 | Brasília | DF | 67.46 |
| 15 | 4 | São Paulo | SP | 66.52 |
| 23 | 5 | Belo Horizonte | MG | 65.17 |

### Estrato: Media

#### IPB Clássico (V1)

| Rank Geral | Rank no Estrato | Município | UF | IPB |
|---|---|---|---|---|
| 1 | 1 | Barueri | SP | 82.54 |
| 2 | 2 | Itapema | SC | 82.24 |
| 3 | 3 | Balneário Camboriú | SC | 81.81 |
| 4 | 4 | Paulínia | SP | 80.87 |
| 5 | 5 | Itajaí | SC | 80.05 |

#### IPB Recalibrado (V2)

| Rank Geral | Rank no Estrato | Município | UF | IPB |
|---|---|---|---|---|
| 6 | 1 | Nova Mutum | MT | 76.33 |
| 7 | 2 | Balneário Camboriú | SC | 75.82 |
| 8 | 3 | Itapema | SC | 75.21 |
| 9 | 4 | Primavera do Leste | MT | 74.70 |
| 10 | 5 | Itajaí | SC | 74.65 |

#### IPB Presença Bancária Completa (V3)

| Rank Geral | Rank no Estrato | Município | UF | IPB |
|---|---|---|---|---|
| 2 | 1 | Nova Lima | MG | 72.41 |
| 4 | 2 | Balneário Camboriú | SC | 71.00 |
| 5 | 3 | Eusébio | CE | 70.65 |
| 6 | 4 | Itapema | SC | 70.39 |
| 7 | 5 | Palmas | TO | 70.27 |

### Estrato: Pequena

#### IPB Clássico (V1)

| Rank Geral | Rank no Estrato | Município | UF | IPB |
|---|---|---|---|---|
| 6 | 1 | Ilhabela | SP | 79.87 |
| 9 | 2 | Santa Carmem | MT | 78.93 |
| 11 | 3 | Santa Rita do Trivelato | MT | 78.31 |
| 13 | 4 | Fernando de Noronha | PE | 78.08 |
| 17 | 5 | Armação dos Búzios | RJ | 76.77 |

#### IPB Recalibrado (V2)

| Rank Geral | Rank no Estrato | Município | UF | IPB |
|---|---|---|---|---|
| 1 | 1 | Bombinhas | SC | 83.85 |
| 2 | 2 | Confins | MG | 82.39 |
| 3 | 3 | Santa Rita do Trivelato | MT | 81.73 |
| 4 | 4 | Santa Carmem | MT | 80.11 |
| 5 | 5 | Alto Horizonte | GO | 77.09 |

#### IPB Presença Bancária Completa (V3)

| Rank Geral | Rank no Estrato | Município | UF | IPB |
|---|---|---|---|---|
| 1 | 1 | Bombinhas | SC | 73.33 |
| 3 | 2 | Confins | MG | 71.97 |
| 10 | 3 | Santa Rita do Trivelato | MT | 68.74 |
| 12 | 4 | Armação dos Búzios | RJ | 68.09 |
| 18 | 5 | Alumínio | SP | 65.77 |

---

## 6. Distribuição Regional no Top 100

Quantidade de municípios por região entre os 100 primeiros de cada versão:

| Região | IPB Clássico (V1) | IPB Recalibrado (V2) | IPB Presença Bancária Completa (V3) |
|---|---|---|---|
| Centro-Oeste | 22 | 20 | 13 |
| Nordeste | 4 | 3 | 8 |
| Norte | 2 | 1 | 7 |
| Sudeste | 48 | 51 | 52 |
| Sul | 24 | 25 | 20 |

---

## 7. Interpretação dos Resultados

### 7.1 IPB Clássico (V1)
- Fortemente enviesado para cidades ricas e conectadas do Sudeste/Sul;
- Top 10 com Barueri, Paulínia, Ilhabela, Nova Lima;
- Pilar D redundante e com peso insuficiente para contrabalançar riqueza.

### 7.2 IPB Recalibrado (V2)
- Reduziu o peso da renda e aumentou o gap bancário;
- Cidades pequenas com alta tensão digital-bancária subiram;
- Ainda prevalecem cidades de SC e MT no topo, mas já não é um ranking de riqueza pura.

### 7.3 IPB Presença Bancária Completa (V3)
- Redesenhou o Pilar D: agências sozinhas perdem relevância, então o índice passa a considerar a presença bancária completa (agências + correspondentes por tipo);
- `penetracao_digital_relativa` premia cidades que transacionam muito Pix proporcionalmente à renda;
- Flag de turismo suave reduz o impacto de cidades pequenas com fluxo de visitantes;
- Top 100 ficou mais distribuído regionalmente e por estrato;
- Reduziu ainda mais a dominância de cidades obviamente ricas.

---

## 8. Alertas importantes para discussão do grupo

### 8.1 V3 ainda privilegia cidades pequenas com eventos especiais

O Top 10 da V3 ainda traz cidades pequenas como Engenheiro Coelho-SP, Arraial do Cabo-RJ, Armação dos Búzios-RJ e Barra dos Coqueiros-SE. Essas cidades provavelmente têm Pix alto por turismo ou por atividade econômica não residente. A flag de turismo suave mitiga, mas não elimina o efeito.

### 8.2 Distribuição regional no Top 100

A V3 concentra grande parte do Top 100 no Sudeste. Isso não é necessariamente ruim (é a região mais populosa), mas precisa ser analisado: são cidades-dormitório da metrópole? São cidades turísticas? São polos regionais reais?

### 8.3 Grandes cidades no ranking da V3

Entraram no Top 100 (estratos grandes): Florianópolis, Goiânia, Brasília, São Paulo, Belo Horizonte, Cuiabá, Porto Alegre, Ribeirão Preto, João Pessoa, Curitiba, Campinas, Aracaju, Rio de Janeiro, Uberlândia, São Luís, Santo André, Fortaleza, São José dos Campos, Guarulhos, Belém. Isso é positivo porque mostra que o índice não exclui grandes cidades automaticamente. Mas também levanta a questão: essas cidades realmente são oportunidades de expansão bancária digital ou já estão saturadas?

### 8.4 Correspondentes bancários como proxy de acesso

O BCB classifica correspondentes em sede, filial, posto e agência. A ponderação usada (posto=1.0, filial=0.7, sede=0.4, agência=1.0) é uma primeira aproximação. O grupo precisa validar se essa hierarquia faz sentido de negócio.

---

## 9. Limitações e próximos passos

### Limitações desta análise
- A cobertura 4G/5G não foi integrada nesta rodada por dificuldade de acesso a dados agregados por município. A banda larga fixa continua como proxy;
- **Empates em IPB = 0**: por construção (normalização min-max + média geométrica), os municípios nos extremos de qualquer pilar recebem score 0 e o IPB zera. Isso ocorre nas três versões na mesma magnitude (V1: ~120, V2: ~126, V3: ~119 municípios). Na V3, a maioria deles é o percentil de maior presença bancária combinada — uma afirmação defensável ("sem gap"), não um artefato de escala;
- **CEMPRE exclui MEIs** (critério da pesquisa): a taxa de empregos formais sub-declara o mercado de micro-PJ exatamente nas cidades pequenas, onde o segmento nativo-digital mais cresce;
- Não houve validação externa com dados reais de expansão bancária;
- A flag de turismo é uma heurística (Pix alto + PIB baixo + cidade pequena). Sem dados de visitação, é um ajuste pragmático — mitigada pelo validador objetivo `unidades_alojamento_alimentacao_por_1000_hab` (CEMPRE), que acompanha a tabela sem entrar na fórmula;
- Variáveis per capita ainda favorecem cidades pequenas com eventos especiais (turismo, comércio de fronteira).

### Próximos passos recomendados
1. Validar os Top 100 da V3 com conhecimento de negócio;
2. Publicar rankings oficiais separados por estrato populacional;
3. Coletar cobertura 4G/5G (painel STEL/Anatel) para enriquecer o Pilar C;
4. Enriquecer o CEMPRE com CNPJ/MEI e Caged (o CEMPRE exclui MEIs — justamente o segmento nativo-digital — e não mede saldos de vagas);
5. Refinar a flag de turismo com dados reais de visitação/turismo (Embratur, MTur) se disponíveis.

---

*Documento gerado automaticamente a partir de `src/analytics/ipb.py` (orquestração: `scripts/07_publica_ipb_bigquery.py`)*
