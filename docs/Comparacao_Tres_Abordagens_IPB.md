# Comparacao de Tres Abordagens do IPB

> **Objetivo**: comparar o IPB atual, o IPB recalibrado rapido e o IPB com a Abordagem 2 (correspondentes bancarios por tipo + ajuste suave para turismo + segmentacao por estrato).  
> **Escopo**: analise local, sem alterar dados no BigQuery.  
> **Data**: 2026-08-31  
> **Branch**: `feature/etapa2-eda-e-limpeza`

---

## 1. Resumo Executivo

Tres versoes do indice foram calculadas a partir da mesma base `trusted_municipios` (com o bug do Pix corrigido):

| Versao | Conceito |
|---|---|
| **IPB Atual** | Formula original: 5 pilares com pesos iguais. Premia cidades ricas, conectadas e com demanda digital, mas pune pouco cidades ja bancarizadas (Pilar D usa 3 variaveis redundantes). |
| **IPB Recalibrado (Rapido)** | Ajuste rapido anti-vies: pesos diferenciados, Pilar D reduzido a apenas `agencias_por_100k_hab`, Pilar E sem `populacao_urbana_pct` e inclusao de `tensao_digital_bancaria` (Pix / agencias). Diminui a influencia da renda pura. |
| **IPB Abordagem 2** | Redesenho do Pilar D: agencias bancarias estao em queda, entao o indice passa a considerar **correspondentes bancarios do BCB por tipo** (posto, filial, sede, agencia) com pesos diferentes. Adiciona `penetracao_digital_relativa` (Pix / PIB) e `gap_bancario_completo`. Inclui ainda uma **flag de turismo suave** (score continuo, desconto maximo de 15% no pilar digital) para nao privilegiar cidades pequenas com fluxo turistico. |

### Estatisticas gerais

| Metrica | IPB Atual | IPB Recalibrado | IPB Abordagem 2 |
|---|---|---|---|
| Media | 35.85 | 40.85 | 25.63 |
| Mediana | 35.86 | 40.65 | 25.23 |
| Maximo | 82.54 | 83.85 | 61.38 |
| Minimo | 0.0 | 0.0 | 0.0 |

---

## 2. Como cada versao funciona

### 2.1 IPB Atual

Cinco pilares com **pesos iguais** (media geometrica):
- **A. Capacidade de consumo**: PIB per capita + rendimento domiciliar per capita.
- **B. Dinamismo economico**: Pix per capita ultimos 12 meses.
- **C. Adocao digital**: banda larga fixa por 100 habitantes.
- **D. Gap bancario**: agencias, depositos e credito per capita (todas invertidas).
- **E. Perfil demografico**: escolaridade, populacao 18-35 anos e populacao urbana.

**Problema**: cidades ricas ja bancarizadas (Barueri, Itapema, Balneario Camboriu) lideram porque a renda e o digital pesam muito, enquanto o gap bancario e fraco.

### 2.2 IPB Recalibrado (Rapido)

Mesma estrutura de 5 pilares, mas com **pesos diferenciados**:
- Pilar A (renda) reduzido para 0.5.
- Pilares B (digital) e C (infra) com 0.75 cada.
- Pilar D (gap bancario) ampliado para 1.5 e simplificado para apenas agencias.
- Pilar E sem `populacao_urbana_pct` (redundante com banda larga).
- Feature nova: `tensao_digital_bancaria` = Pix per capita / (agencias por 100k + 1).

**Efeito**: cidades pequenas com muito Pix e pouca agencia sobem no ranking. Ainda prevalecem SC e MT, mas ja nao e um ranking de riqueza pura.

### 2.3 IPB Abordagem 2

Redesenho mais profundo, principalmente no Pilar D:
- **Agencias sozinhas nao refletem mais a realidade**: o numero de agencias bancarias vem caindo no Brasil. O BCB registra 216 mil **correspondentes** (lotericas, caixas eletronicos, correspondentes bancarios). O indice passa a considerar a **presenca bancaria completa** = agencias + correspondentes.
- **Correspondentes ponderados por tipo**: postos (peso 1.0), filiais (0.7), sedes (0.4) e agencias (1.0). Postos sao pontos mais simples; filiais/sedes tem capacidade maior.
- **Gap bancario completo** = 1 / (agencias + correspondentes ponderados por 100k + 1).
- **Penetracao digital relativa** = Pix per capita / PIB per capita. Premia cidades que transacionam muito proporcionalmente a sua riqueza.
- **Flag de turismo suave**: score continuo baseado em Pix alto + PIB baixo + cidade pequena. Aplica desconto maximo de 15% no pilar digital para evitar que cidades turisticas (Arraial do Cabo, Buzios) disparem so por fluxo de visitantes.
- **Rankings separados por estrato**: pequena, media e grande.

**Efeito**: quebra o vies para cidades ricas ja bancarizadas e passa a destacar municipios com alta demanda digital e baixa estrutura bancaria fisica.

---

## 3. Top 10 por versao

### 3.1 IPB Atual

| Rank | Municipio | UF | Estrato | IPB |
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

### 3.2 IPB Recalibrado (Rapido)

| Rank | Municipio | UF | Estrato | IPB |
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

### 3.3 IPB Abordagem 2

| Rank | Municipio | UF | Estrato | IPB |
|---|---|---|---|---|
| 1 | Engenheiro Coelho | SP | pequena | 61.38 |
| 2 | Mário Campos | MG | pequena | 59.92 |
| 3 | Alumínio | SP | pequena | 58.53 |
| 4 | Nova Lima | MG | media | 58.40 |
| 5 | Santana do Paraíso | MG | pequena | 58.33 |
| 6 | Santana de Parnaíba | SP | media | 57.70 |
| 7 | Arraial do Cabo | RJ | pequena | 56.96 |
| 8 | Confins | MG | pequena | 56.85 |
| 9 | Botuverá | SC | pequena | 55.07 |
| 10 | Passo de Torres | SC | pequena | 55.02 |

---

## 4. Analise do Top 100

### 4.1 Movimentacao geral

| Comparacao | Sairam do Top 100 | Entraram no Top 100 |
|---|---|---|
| Atual -> Recalibrado | 40 | 40 |
| Recalibrado -> Abordagem 2 | 74 | 74 |
| Atual -> Abordagem 2 | 77 | 77 |

### 4.2 Cidades que sairam do Top 100 (Atual -> Abordagem 2)

Cidades ricas e ja bancarizadas que deixaram de figurar entre as 100 primeiras:

| Municipio | UF | Estrato | Rank Atual | Rank Abordagem 2 |
|---|---|---|---|---|
| Barueri | SP | media | 1 | 246 |
| Balneário Camboriú | SC | media | 3 | 119 |
| Itajaí | SC | media | 5 | 432 |
| Santa Carmem | MT | pequena | 9 | 204 |
| Nova Mutum | MT | media | 10 | 176 |
| Vinhedo | SP | media | 12 | 321 |
| Fernando de Noronha | PE | pequena | 13 | 4228 |
| Xangri-lá | RS | pequena | 19 | 166 |
| Jaguariúna | SP | media | 22 | 410 |
| Campos de Júlio | MT | pequena | 24 | 307 |
| Primavera do Leste | MT | media | 27 | 482 |
| São José | SC | media | 28 | 1153 |
| Valinhos | SP | media | 29 | 345 |
| Jundiaí | SP | media | 30 | 499 |
| Porto Belo | SC | pequena | 31 | 878 |
| Sorriso | MT | media | 32 | 286 |
| São Caetano do Sul | SP | media | 33 | 588 |
| Pinhais | PR | media | 34 | 213 |
| Indaiatuba | SP | media | 35 | 149 |
| Balneário Piçarras | SC | pequena | 36 | 229 |
| Sinop | MT | media | 38 | 435 |
| Maringá | PR | media | 39 | 426 |
| Campo Novo do Parecis | MT | pequena | 40 | 374 |
| Florianópolis | SC | grande | 41 | 185 |
| Palmas | TO | media | 42 | 111 |
| Santa Gertrudes | SP | pequena | 44 | 369 |
| Catalão | GO | media | 45 | 298 |
| Cuiabá | MT | grande | 46 | 265 |
| Alto Horizonte | GO | pequena | 47 | 322 |
| Santos | SP | media | 48 | 267 |
| Campinas | SP | grande | 49 | 276 |
| Diamantino | MT | pequena | 50 | 824 |
| Ribeirão Preto | SP | grande | 51 | 346 |
| Cabedelo | PB | media | 52 | 978 |
| Gramado | RS | pequena | 54 | 462 |
| Blumenau | SC | media | 55 | 640 |
| Palhoça | SC | media | 56 | 617 |
| Atibaia | SP | media | 57 | 590 |
| Vila Velha | ES | media | 58 | 117 |
| Holambra | SP | pequena | 59 | 567 |
| Americana | SP | media | 60 | 911 |
| Goiânia | GO | grande | 61 | 121 |
| Toledo | PR | media | 62 | 790 |
| São José dos Pinhais | PR | media | 63 | 288 |
| São José do Rio Preto | SP | media | 64 | 785 |
| Joinville | SC | grande | 65 | 451 |
| Extrema | MG | media | 66 | 383 |
| Barretos | SP | media | 67 | 643 |
| Praia Grande | SP | media | 68 | 168 |
| Sorocaba | SP | grande | 69 | 421 |
| Rio Verde | GO | media | 70 | 652 |
| Campo Verde | MT | pequena | 71 | 480 |
| Vera | MT | pequena | 72 | 196 |
| Maracaju | MS | pequena | 73 | 834 |
| São José dos Campos | SP | grande | 74 | 201 |
| Uberlândia | MG | grande | 75 | 375 |
| Jaraguá do Sul | SC | media | 76 | 457 |
| São Francisco do Sul | SC | media | 77 | 273 |
| Gavião Peixoto | SP | pequena | 78 | 506 |
| Campo Grande | MS | grande | 80 | 710 |
| Dourados | MS | media | 82 | 932 |
| Navegantes | SC | media | 83 | 285 |
| Piracicaba | SP | media | 84 | 315 |
| Araçariguama | SP | pequena | 86 | 219 |
| Águas Frias | SC | pequena | 87 | 195 |
| Pedrinópolis | MG | pequena | 88 | 306 |
| Garopaba | SC | pequena | 89 | 490 |
| Luís Eduardo Magalhães | BA | media | 90 | 381 |
| Salto | SP | media | 91 | 113 |
| Canarana | MT | pequena | 92 | 326 |
| Cajamar | SP | media | 93 | 248 |
| Araucária | PR | media | 94 | 249 |
| Capão da Canoa | RS | media | 95 | 294 |
| Ilha Comprida | SP | pequena | 96 | 349 |
| Ponta Porã | MS | media | 97 | 520 |
| Nova Odessa | SP | media | 99 | 430 |
| Tapurah | MT | pequena | 100 | 1007 |

### 4.3 Cidades que entraram no Top 100 (Atual -> Abordagem 2)

Cidades que subiram e passaram a figurar entre as 100 primeiras oportunidades:

| Municipio | UF | Estrato | Rank Atual | Rank Abordagem 2 |
|---|---|---|---|---|
| Engenheiro Coelho | SP | pequena | 191 | 1 |
| Mário Campos | MG | pequena | 833 | 2 |
| Santana do Paraíso | MG | pequena | 783 | 5 |
| Botuverá | SC | pequena | 780 | 9 |
| Passo de Torres | SC | pequena | 484 | 10 |
| Nilópolis | RJ | media | 962 | 12 |
| São Joaquim de Bicas | MG | pequena | 1312 | 14 |
| Barra dos Coqueiros | SE | pequena | 291 | 15 |
| São José de Ribamar | MA | media | 1813 | 16 |
| Paço do Lumiar | MA | media | 1848 | 17 |
| Nova Serrana | MG | media | 131 | 18 |
| Ribeirão das Neves | MG | media | 1361 | 19 |
| Igaratinga | MG | pequena | 723 | 20 |
| Rio Grande da Serra | SP | pequena | 1193 | 21 |
| Rio Acima | MG | pequena | 799 | 22 |
| Balneário Rincão | SC | pequena | 1207 | 24 |
| Ferreira Gomes | AP | pequena | 1510 | 25 |
| Ibirité | MG | media | 1398 | 26 |
| Nova Maringá | MT | pequena | 147 | 27 |
| Taboão da Serra | SP | media | 288 | 30 |
| Campo Magro | PR | pequena | 1331 | 31 |
| Francisco Morato | SP | media | 1691 | 32 |
| Conde | PB | pequena | 1440 | 33 |
| Tremembé | SP | media | 569 | 34 |
| Embu das Artes | SP | media | 577 | 35 |
| Sabará | MG | media | 967 | 37 |
| Raposos | MG | pequena | 1752 | 38 |
| Vespasiano | MG | media | 868 | 40 |
| Caieiras | SP | media | 471 | 41 |
| Piraquara | PR | media | 1291 | 42 |
| Carapicuíba | SP | media | 708 | 43 |
| São Vicente | SP | media | 618 | 44 |
| Rafard | SP | pequena | 503 | 46 |
| Cubatão | SP | media | 232 | 47 |
| Cidade Ocidental | GO | media | 1513 | 49 |
| Rio de Janeiro | RJ | grande | 611 | 51 |
| Camaragibe | PE | media | 1730 | 52 |
| Brasília | DF | grande | 134 | 53 |
| Diadema | SP | media | 428 | 54 |
| São Cristóvão | SE | media | 1936 | 56 |
| Santa Luzia | MG | media | 706 | 58 |
| Madre de Deus de Minas | MG | pequena | 195 | 59 |
| Mangaratiba | RJ | pequena | 128 | 60 |
| Senador Canedo | GO | media | 872 | 62 |
| Pescaria Brava | SC | pequena | 3222 | 63 |
| Oratórios | MG | pequena | 2413 | 64 |
| Mauá | SP | media | 621 | 65 |
| Valparaíso de Goiás | GO | media | 520 | 66 |
| Chalé | MG | pequena | 2207 | 67 |
| Pirapora do Bom Jesus | SP | pequena | 1389 | 68 |
| Capim Branco | MG | pequena | 1597 | 69 |
| Maricá | RJ | media | 163 | 70 |
| Japaraíba | MG | pequena | 2228 | 72 |
| Tibau do Sul | RN | pequena | 445 | 73 |
| Barra de São Miguel | AL | pequena | 1807 | 75 |
| Ferraz de Vasconcelos | SP | media | 1327 | 76 |
| São Paulo | SP | grande | 174 | 77 |
| São José da Lapa | MG | pequena | 624 | 78 |
| São Pedro de Alcântara | SC | pequena | 908 | 79 |
| Paraty | RJ | pequena | 343 | 80 |
| Iguaba Grande | RJ | pequena | 435 | 82 |
| Betim | MG | media | 166 | 83 |
| Araricá | RS | pequena | 980 | 84 |
| Couto de Magalhães de Minas | MG | pequena | 2324 | 85 |
| Manaus | AM | grande | 331 | 86 |
| Guarujá | SP | media | 227 | 88 |
| Itaara | RS | pequena | 829 | 89 |
| Jandira | SP | media | 344 | 90 |
| Parnamirim | RN | media | 107 | 91 |
| Piratininga | SP | pequena | 251 | 93 |
| Paulista | PE | media | 2132 | 94 |
| Aguiarnópolis | TO | pequena | 1219 | 95 |
| Biguaçu | SC | media | 164 | 96 |
| Alto Paraíso de Goiás | GO | pequena | 755 | 97 |
| Camboriú | SC | media | 236 | 98 |
| Esmeraldas | MG | media | 2239 | 99 |
| Alvorada | RS | media | 857 | 100 |

---

## 5. Top 5 por Estrato Populacional

Alem do ranking geral, apresentamos os lideres de cada estrato populacional nas tres versoes. Isso evita que cidades pequenas e grandes concorram no mesmo criterio.

### Estrato: Grande

#### IPB Atual

| Rank Geral | Rank no Estrato | Municipio | UF | IPB |
|---|---|---|---|---|---|
| 41 | 1 | Florianópolis | SC | 70.00 |
| 46 | 2 | Cuiabá | MT | 68.95 |
| 49 | 3 | Campinas | SP | 68.79 |
| 51 | 4 | Ribeirão Preto | SP | 68.68 |
| 61 | 5 | Goiânia | GO | 67.68 |

#### IPB Recalibrado

| Rank Geral | Rank no Estrato | Municipio | UF | IPB |
|---|---|---|---|---|---|
| 19 | 1 | Brasília | DF | 72.75 |
| 27 | 2 | Florianópolis | SC | 71.89 |
| 28 | 3 | Goiânia | GO | 71.76 |
| 32 | 4 | Cuiabá | MT | 71.04 |
| 47 | 5 | Uberlândia | MG | 69.47 |

#### IPB Abordagem 2

| Rank Geral | Rank no Estrato | Municipio | UF | IPB |
|---|---|---|---|---|---|
| 51 | 1 | Rio de Janeiro | RJ | 49.33 |
| 53 | 2 | Brasília | DF | 49.18 |
| 77 | 3 | São Paulo | SP | 47.70 |
| 86 | 4 | Manaus | AM | 47.20 |
| 118 | 5 | Guarulhos | SP | 45.92 |

### Estrato: Media

#### IPB Atual

| Rank Geral | Rank no Estrato | Municipio | UF | IPB |
|---|---|---|---|---|---|
| 1 | 1 | Barueri | SP | 82.54 |
| 2 | 2 | Itapema | SC | 82.24 |
| 3 | 3 | Balneário Camboriú | SC | 81.81 |
| 4 | 4 | Paulínia | SP | 80.87 |
| 5 | 5 | Itajaí | SC | 80.05 |

#### IPB Recalibrado

| Rank Geral | Rank no Estrato | Municipio | UF | IPB |
|---|---|---|---|---|---|
| 6 | 1 | Nova Mutum | MT | 76.33 |
| 7 | 2 | Balneário Camboriú | SC | 75.82 |
| 8 | 3 | Itapema | SC | 75.21 |
| 9 | 4 | Primavera do Leste | MT | 74.70 |
| 10 | 5 | Itajaí | SC | 74.65 |

#### IPB Abordagem 2

| Rank Geral | Rank no Estrato | Municipio | UF | IPB |
|---|---|---|---|---|---|
| 4 | 1 | Nova Lima | MG | 58.40 |
| 6 | 2 | Santana de Parnaíba | SP | 57.70 |
| 12 | 3 | Nilópolis | RJ | 54.66 |
| 16 | 4 | São José de Ribamar | MA | 53.89 |
| 17 | 5 | Paço do Lumiar | MA | 53.85 |

### Estrato: Pequena

#### IPB Atual

| Rank Geral | Rank no Estrato | Municipio | UF | IPB |
|---|---|---|---|---|---|
| 6 | 1 | Ilhabela | SP | 79.87 |
| 9 | 2 | Santa Carmem | MT | 78.93 |
| 11 | 3 | Santa Rita do Trivelato | MT | 78.31 |
| 13 | 4 | Fernando de Noronha | PE | 78.08 |
| 17 | 5 | Armação dos Búzios | RJ | 76.77 |

#### IPB Recalibrado

| Rank Geral | Rank no Estrato | Municipio | UF | IPB |
|---|---|---|---|---|---|
| 1 | 1 | Bombinhas | SC | 83.85 |
| 2 | 2 | Confins | MG | 82.39 |
| 3 | 3 | Santa Rita do Trivelato | MT | 81.73 |
| 4 | 4 | Santa Carmem | MT | 80.11 |
| 5 | 5 | Alto Horizonte | GO | 77.09 |

#### IPB Abordagem 2

| Rank Geral | Rank no Estrato | Municipio | UF | IPB |
|---|---|---|---|---|---|
| 1 | 1 | Engenheiro Coelho | SP | 61.38 |
| 2 | 2 | Mário Campos | MG | 59.92 |
| 3 | 3 | Alumínio | SP | 58.53 |
| 5 | 4 | Santana do Paraíso | MG | 58.33 |
| 7 | 5 | Arraial do Cabo | RJ | 56.96 |

---

## 6. Distribuicao Regional no Top 100

Quantidade de municipios por regiao entre os 100 primeiros de cada versao:

| Regiao | IPB Atual | IPB Recalibrado | IPB Abordagem 2 |
|---|---|---|---|
| Centro-Oeste | 22 | 20 | 7 |
| Nordeste | 4 | 3 | 11 |
| Norte | 2 | 1 | 4 |
| Sudeste | 48 | 51 | 64 |
| Sul | 24 | 25 | 14 |

---

## 7. Interpretacao dos Resultados

### 7.1 IPB Atual
- Fortemente enviesado para cidades ricas e conectadas do Sudeste/Sul;
- Top 10 com Barueri, Paulínia, Ilhabela, Nova Lima;
- Pilar D redundante e com peso insuficiente para contrabalançar riqueza.

### 7.2 IPB Recalibrado (Rapido)
- Reduziu o peso da renda e aumentou o gap bancario;
- Cidades pequenas com alta tensao digital-bancaria subiram;
- Ainda prevalecem cidades de SC e MT no topo, mas ja nao e um ranking de riqueza pura.

### 7.3 IPB Abordagem 2
- Redesenhou o Pilar D: agencias sozinhas perdem relevancia, entao o indice passa a considerar a presenca bancaria completa (agencias + correspondentes por tipo);
- `penetracao_digital_relativa` premia cidades que transacionam muito Pix proporcionalmente a renda;
- Flag de turismo suave reduz o impacto de cidades pequenas com fluxo de visitantes;
- Top 100 ficou mais distribuido regionalmente e por estrato;
- Reduziu ainda mais a dominancia de cidades obviamente ricas.

---

## 7. Alertas importantes para discussao do grupo

### 7.1 Abordagem 2 ainda privilegia cidades pequenas com eventos especiais

O Top 10 da Abordagem 2 ainda traz cidades pequenas como Engenheiro Coelho-SP, Arraial do Cabo-RJ, Armacao dos Buzios-RJ e Barra dos Coqueiros-SE. Essas cidades provavelmente tem Pix alto por turismo ou por atividade econômica nao residente. A flag de turismo suave mitiga, mas nao elimina o efeito.

### 7.2 Distribuicao regional no Top 100

A Abordagem 2 concentra grande parte do Top 100 no Sudeste. Isso nao e necessariamente ruim (e a regiao mais populosa), mas precisa ser analisado: sao cidades-dormitorio da metropole? Sao cidades turisticas? Sao polos regionais reais?

### 7.3 Grandes cidades no ranking da Abordagem 2

Entraram no Top 100: Rio de Janeiro, Sao Paulo, Brasilia, Manaus, Salvador. Isso e positivo porque mostra que o indice nao exclui grandes cidades automaticamente. Mas tambem levanta a questao: essas cidades realmente sao oportunidades de expansao bancaria digital ou ja estao saturadas?

### 7.4 Correspondentes bancarios como proxy de acesso

O BCB classifica correspondentes em sede, filial, posto e agencia. A ponderacao usada (posto=1.0, filial=0.7, sede=0.4, agencia=1.0) e uma primeira aproximacao. O grupo precisa validar se essa hierarquia faz sentido de negocio.

---

## 8. Limitacoes e proximos passos

### Limitacoes desta analise
- A cobertura 4G/5G nao foi integrada nesta rodada por dificuldade de acesso a dados agregados por municipio. A banda larga fixa continua como proxy;
- Nao houve validacao externa com dados reais de expansao bancaria;
- A flag de turismo e uma heuristica (Pix alto + PIB baixo + cidade pequena). Sem dados de visitacao, e um ajuste pragmatico;
- Variaveis per capita ainda favorecem cidades pequenas com eventos especiais (turismo, comercio de fronteira).

### Proximos passos recomendados
1. Validar os Top 100 da Abordagem 2 com conhecimento de negocio;
2. Publicar rankings oficiais separados por estrato populacional;
3. Coletar cobertura 4G/5G (painel STEL/Anatel) para enriquecer o Pilar C;
4. Coletar CNPJ/MEI e Caged para a Abordagem 3 (modelo residual);
5. Refinar a flag de turismo com dados reais de visitacao/turismo (Embratur, MTur) se disponiveis.

---

*Documento gerado automaticamente por scripts/06_comparacao_tres_abordagens_ipb.py*
