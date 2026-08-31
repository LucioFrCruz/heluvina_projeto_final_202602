# Comparacao de Tres Abordagens do IPB

> **Objetivo**: comparar o IPB atual, o IPB recalibrado rapido e o IPB com a Abordagem 2 (correspondentes bancarios + features derivadas).  
> **Escopo**: analise local, sem alterar dados no BigQuery.  
> **Data**: 2026-08-31  
> **Branch**: `feature/etapa2-eda-e-limpeza`

---

## 1. Resumo Executivo

Tres versoes do indice foram calculadas a partir da mesma base `trusted_municipios` (com o bug do Pix corrigido):

| Versao | Conceito |
|---|---|
| **IPB Atual** | Formula original: 5 pilares com pesos iguais, Pilar D com 3 variaveis redundantes. |
| **IPB Recalibrado (Rapido)** | Pesos diferenciados, Pilar D reduzido, Pilar E sem `populacao_urbana_pct`, inclusao de `tensao_digital_bancaria`. |
| **IPB Abordagem 2** | Inclui correspondentes bancarios do BCB, `penetracao_digital_relativa` e `gap_bancario_completo`. |

### Estatisticas gerais

| Metrica | IPB Atual | IPB Recalibrado | IPB Abordagem 2 |
|---|---|---|---|
| Media | 35.85 | 40.85 | 25.86 |
| Mediana | 35.86 | 40.65 | 25.46 |
| Maximo | 82.54 | 83.85 | 62.76 |
| Minimo | 0.0 | 0.0 | 0.0 |

---

## 2. Top 10 por versao

### 2.1 IPB Atual

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

### 2.2 IPB Recalibrado (Rapido)

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

### 2.3 IPB Abordagem 2

| Rank | Municipio | UF | Estrato | IPB |
|---|---|---|---|---|
| 1 | Engenheiro Coelho | SP | pequena | 62.76 |
| 2 | Arraial do Cabo | RJ | pequena | 60.73 |
| 3 | Armação dos Búzios | RJ | pequena | 60.66 |
| 4 | Nova Lima | MG | media | 60.61 |
| 5 | Santana de Parnaíba | SP | media | 59.24 |
| 6 | Barra dos Coqueiros | SE | pequena | 58.76 |
| 7 | Santana do Paraíso | MG | pequena | 58.55 |
| 8 | Botuverá | SC | pequena | 57.77 |
| 9 | Alumínio | SP | pequena | 57.75 |
| 10 | Mário Campos | MG | pequena | 57.34 |

---

## 3. Analise do Top 100

### 3.1 Movimentacao geral

| Comparacao | Sairam do Top 100 | Entraram no Top 100 |
|---|---|---|
| Atual -> Recalibrado | 40 | 40 |
| Recalibrado -> Abordagem 2 | 75 | 75 |
| Atual -> Abordagem 2 | 76 | 76 |

### 3.2 Cidades que sairam do Top 100 (Atual -> Abordagem 2)

Cidades ricas e ja bancarizadas que deixaram de figurar entre as 100 primeiras:

| Municipio | UF | Estrato | Rank Atual | Rank Abordagem 2 |
|---|---|---|---|---|
| Barueri | SP | media | 1 | 202 |
| Itajaí | SC | media | 5 | 400 |
| Santa Carmem | MT | pequena | 9 | 128 |
| Nova Mutum | MT | media | 10 | 144 |
| Vinhedo | SP | media | 12 | 242 |
| Fernando de Noronha | PE | pequena | 13 | 1384 |
| Xangri-lá | RS | pequena | 19 | 120 |
| Jaguariúna | SP | media | 22 | 283 |
| Campos de Júlio | MT | pequena | 24 | 248 |
| Primavera do Leste | MT | media | 27 | 398 |
| São José | SC | media | 28 | 1249 |
| Valinhos | SP | media | 29 | 279 |
| Jundiaí | SP | media | 30 | 495 |
| Porto Belo | SC | pequena | 31 | 786 |
| Sorriso | MT | media | 32 | 300 |
| São Caetano do Sul | SP | media | 33 | 498 |
| Pinhais | PR | media | 34 | 213 |
| Indaiatuba | SP | media | 35 | 129 |
| Balneário Piçarras | SC | pequena | 36 | 139 |
| Sinop | MT | media | 38 | 390 |
| Maringá | PR | media | 39 | 439 |
| Campo Novo do Parecis | MT | pequena | 40 | 295 |
| Florianópolis | SC | grande | 41 | 142 |
| Santa Gertrudes | SP | pequena | 44 | 186 |
| Catalão | GO | media | 45 | 299 |
| Cuiabá | MT | grande | 46 | 280 |
| Alto Horizonte | GO | pequena | 47 | 355 |
| Santos | SP | media | 48 | 191 |
| Campinas | SP | grande | 49 | 240 |
| Diamantino | MT | pequena | 50 | 473 |
| Ribeirão Preto | SP | grande | 51 | 329 |
| Cabedelo | PB | media | 52 | 943 |
| Gramado | RS | pequena | 54 | 352 |
| Blumenau | SC | media | 55 | 526 |
| Palhoça | SC | media | 56 | 711 |
| Atibaia | SP | media | 57 | 520 |
| Vila Velha | ES | media | 58 | 137 |
| Holambra | SP | pequena | 59 | 382 |
| Americana | SP | media | 60 | 961 |
| Goiânia | GO | grande | 61 | 126 |
| Toledo | PR | media | 62 | 901 |
| São José dos Pinhais | PR | media | 63 | 363 |
| São José do Rio Preto | SP | media | 64 | 853 |
| Joinville | SC | grande | 65 | 483 |
| Extrema | MG | media | 66 | 465 |
| Barretos | SP | media | 67 | 639 |
| Praia Grande | SP | media | 68 | 160 |
| Sorocaba | SP | grande | 69 | 431 |
| Rio Verde | GO | media | 70 | 725 |
| Campo Verde | MT | pequena | 71 | 381 |
| Vera | MT | pequena | 72 | 119 |
| Maracaju | MS | pequena | 73 | 493 |
| São José dos Campos | SP | grande | 74 | 193 |
| Uberlândia | MG | grande | 75 | 359 |
| Jaraguá do Sul | SC | media | 76 | 496 |
| São Francisco do Sul | SC | media | 77 | 200 |
| Gavião Peixoto | SP | pequena | 78 | 541 |
| Rio das Ostras | RJ | media | 79 | 113 |
| Campo Grande | MS | grande | 80 | 641 |
| Dourados | MS | media | 82 | 812 |
| Navegantes | SC | media | 83 | 293 |
| Piracicaba | SP | media | 84 | 275 |
| Araçariguama | SP | pequena | 86 | 150 |
| Águas Frias | SC | pequena | 87 | 380 |
| Pedrinópolis | MG | pequena | 88 | 308 |
| Garopaba | SC | pequena | 89 | 387 |
| Luís Eduardo Magalhães | BA | media | 90 | 357 |
| Salto | SP | media | 91 | 125 |
| Canarana | MT | pequena | 92 | 276 |
| Cajamar | SP | media | 93 | 203 |
| Araucária | PR | media | 94 | 310 |
| Capão da Canoa | RS | media | 95 | 228 |
| Ilha Comprida | SP | pequena | 96 | 436 |
| Ponta Porã | MS | media | 97 | 348 |
| Nova Odessa | SP | media | 99 | 415 |
| Tapurah | MT | pequena | 100 | 633 |

### 3.3 Cidades que entraram no Top 100 (Atual -> Abordagem 2)

Cidades que subiram e passaram a figurar entre as 100 primeiras oportunidades:

| Municipio | UF | Estrato | Rank Atual | Rank Abordagem 2 |
|---|---|---|---|---|
| Engenheiro Coelho | SP | pequena | 191 | 1 |
| Barra dos Coqueiros | SE | pequena | 291 | 6 |
| Santana do Paraíso | MG | pequena | 783 | 7 |
| Botuverá | SC | pequena | 780 | 8 |
| Mário Campos | MG | pequena | 833 | 10 |
| Nilópolis | RJ | media | 962 | 11 |
| Tremembé | SP | media | 569 | 12 |
| Nova Serrana | MG | media | 131 | 13 |
| São José de Ribamar | MA | media | 1813 | 15 |
| São Joaquim de Bicas | MG | pequena | 1312 | 16 |
| Cubatão | SP | media | 232 | 17 |
| Paço do Lumiar | MA | media | 1848 | 19 |
| Taboão da Serra | SP | media | 288 | 21 |
| Rio Acima | MG | pequena | 799 | 23 |
| Francisco Morato | SP | media | 1691 | 25 |
| Ribeirão das Neves | MG | media | 1361 | 26 |
| Sabará | MG | media | 967 | 27 |
| Rio Grande da Serra | SP | pequena | 1193 | 29 |
| Caieiras | SP | media | 471 | 30 |
| Embu das Artes | SP | media | 577 | 33 |
| Ibirité | MG | media | 1398 | 34 |
| Paraty | RJ | pequena | 343 | 35 |
| Piraquara | PR | media | 1291 | 36 |
| Passo de Torres | SC | pequena | 484 | 37 |
| São Vicente | SP | media | 618 | 38 |
| Nova Maringá | MT | pequena | 147 | 39 |
| Igaratinga | MG | pequena | 723 | 40 |
| Vespasiano | MG | media | 868 | 41 |
| Ferreira Gomes | AP | pequena | 1510 | 44 |
| Campo Magro | PR | pequena | 1331 | 45 |
| Rio de Janeiro | RJ | grande | 611 | 48 |
| Diadema | SP | media | 428 | 49 |
| Rafard | SP | pequena | 503 | 50 |
| Camaragibe | PE | media | 1730 | 51 |
| Conde | PB | pequena | 1440 | 52 |
| Mangaratiba | RJ | pequena | 128 | 53 |
| Balneário Rincão | SC | pequena | 1207 | 54 |
| Carapicuíba | SP | media | 708 | 57 |
| Santa Luzia | MG | media | 706 | 58 |
| Embu-Guaçu | SP | media | 898 | 59 |
| Brasília | DF | grande | 134 | 60 |
| Brumadinho | MG | pequena | 158 | 61 |
| Cidade Ocidental | GO | media | 1513 | 62 |
| São Cristóvão | SE | media | 1936 | 63 |
| Capim Branco | MG | pequena | 1597 | 64 |
| São Paulo | SP | grande | 174 | 65 |
| Ferraz de Vasconcelos | SP | media | 1327 | 67 |
| Balneário Arroio do Silva | SC | pequena | 996 | 68 |
| Raposos | MG | pequena | 1752 | 69 |
| Valparaíso de Goiás | GO | media | 520 | 70 |
| Mauá | SP | media | 621 | 71 |
| Senador Canedo | GO | media | 872 | 72 |
| Pescaria Brava | SC | pequena | 3222 | 73 |
| Guarujá | SP | media | 227 | 74 |
| Jandira | SP | media | 344 | 75 |
| Chalé | MG | pequena | 2207 | 76 |
| Parauapebas | PA | media | 255 | 78 |
| Manaus | AM | grande | 331 | 81 |
| Barcarena | PA | media | 1144 | 83 |
| Ubatuba | SP | media | 357 | 84 |
| Itapevi | SP | media | 806 | 85 |
| Iguaba Grande | RJ | pequena | 435 | 86 |
| Macaé | RJ | media | 247 | 87 |
| Franco da Rocha | SP | media | 958 | 88 |
| Potim | SP | pequena | 1812 | 89 |
| Paracambi | RJ | pequena | 944 | 90 |
| Piratininga | SP | pequena | 251 | 91 |
| Alvorada | RS | media | 857 | 92 |
| Delta | MG | pequena | 1780 | 93 |
| Parnamirim | RN | media | 107 | 94 |
| Salvador | BA | grande | 600 | 95 |
| Betim | MG | media | 166 | 96 |
| Balsa Nova | PR | pequena | 681 | 97 |
| Esmeraldas | MG | media | 2239 | 98 |
| Paulista | PE | media | 2132 | 99 |
| Novo Gama | GO | media | 2218 | 100 |

---

## 4. Top 5 por Estrato Populacional (Abordagem 2)

### Grande

| Rank | Municipio | UF | IPB |
|---|---|---|---|
| 48 | Rio de Janeiro | RJ | 51.63 |
| 60 | Brasília | DF | 50.30 |
| 65 | São Paulo | SP | 49.94 |
| 81 | Manaus | AM | 48.42 |
| 95 | Salvador | BA | 47.92 |

### Media

| Rank | Municipio | UF | IPB |
|---|---|---|---|
| 4 | Nova Lima | MG | 60.61 |
| 5 | Santana de Parnaíba | SP | 59.24 |
| 11 | Nilópolis | RJ | 57.03 |
| 12 | Tremembé | SP | 55.74 |
| 13 | Nova Serrana | MG | 55.65 |

### Pequena

| Rank | Municipio | UF | IPB |
|---|---|---|---|
| 1 | Engenheiro Coelho | SP | 62.76 |
| 2 | Arraial do Cabo | RJ | 60.73 |
| 3 | Armação dos Búzios | RJ | 60.66 |
| 6 | Barra dos Coqueiros | SE | 58.76 |
| 7 | Santana do Paraíso | MG | 58.55 |

---

## 5. Distribuicao Regional no Top 100

Quantidade de municipios por regiao entre os 100 primeiros de cada versao:

| Regiao | IPB Atual | IPB Recalibrado | IPB Abordagem 2 |
|---|---|---|---|
| Centro-Oeste | 22 | 20 | 7 |
| Nordeste | 4 | 3 | 10 |
| Norte | 2 | 1 | 6 |
| Sudeste | 48 | 51 | 65 |
| Sul | 24 | 25 | 12 |

---

## 6. Interpretacao dos Resultados

### 6.1 IPB Atual
- Fortemente enviesado para cidades ricas e conectadas do Sudeste/Sul;
- Top 10 com Barueri, Paulínia, Ilhabela, Nova Lima;
- Pilar D redundante e com peso insuficiente para contrabalançar riqueza.

### 6.2 IPB Recalibrado (Rapido)
- Reduziu o peso da renda e aumentou o gap bancario;
- Cidades pequenas com alta tensao digital-bancaria subiram;
- Ainda prevalecem cidades de SC e MT no topo, mas ja nao e um ranking de riqueza pura.

### 6.3 IPB Abordagem 2
- Incorporou correspondentes bancarios, o que pune cidades ricas com alta presenca de lotericas/correspondentes;
- `penetracao_digital_relativa` premia cidades que transacionam muito Pix proporcionalmente a renda;
- Top 100 ficou mais distribuido regionalmente e por estrato;
- Reduziu ainda mais a dominancia de cidades obviamente ricas.

---

## 7. Alertas importantes para discussao do grupo

### 7.1 Abordagem 2 ainda privilegia cidades pequenas com eventos especiais

O Top 10 da Abordagem 2 traz:
- Engenheiro Coelho-SP (pequena)
- Arraial do Cabo-RJ (pequena)
- Armacao dos Buzios-RJ (pequena)
- Barra dos Coqueiros-SE (pequena)

Essas cidades provavelmente tem Pix alto por **turismo**, nao por atividade economica residente. A normalizacao per capita amplifica esse efeito.

### 7.2 Distribuicao regional no Top 100

| Regiao | IPB Atual | IPB Recalibrado | IPB Abordagem 2 |
|---|---|---|---|
| Centro-Oeste | 22 | 20 | 7 |
| Nordeste | 4 | 3 | 10 |
| Norte | 2 | 1 | 6 |
| Sudeste | 48 | 51 | 65 |
| Sul | 24 | 25 | 12 |

A Abordagem 2 concentrou **65% do Top 100 no Sudeste**. Isso nao e necessariamente ruim (e a regiao mais populosa), mas precisa ser analisado: sao cidades dormitorio da metropole? Sao cidades turisticas? Sao polos regionais reais?

### 7.3 Grandes cidades no ranking da Abordagem 2

Entraram no Top 100: Rio de Janeiro, Sao Paulo, Brasilia, Manaus, Salvador.

Isso e positivo: mostra que o indice nao exclui grandes cidades automaticamente, mas tambem levanta a questao: essas cidades realmente sao oportunidades de expansao bancaria digital? Ou ja estao saturadas?

### 7.4 O que falta para decidir

- **Validacao de negocio**: o grupo precisa olhar o Top 100 e dizer "faz sentido" ou "isso aqui esta estranho";
- **Filtro por populacao minima**: talvez publicar rankings separados por estrato seja obrigatorio;
- **Identificar cidades turisticas**: criar uma flag para cidades com eventos sazonais fortes;
- **Validacao externa**: comparar com expansao real de bancos digitais, se houver dados.

---

## 8. Limitacoes e proximos passos

### Limitacoes desta analise
- A cobertura 4G/5G nao foi integrada nesta rodada por dificuldade de acesso a dados agregados por municipio. A banda larga fixa continua como proxy;
- Nao houve validacao externa com dados reais de expansao bancaria;
- Variaveis per capita ainda favorecem cidades pequenas com eventos especiais (turismo, comercio de fronteira).

### Proximos passos recomendados
1. Validar os Top 100 da Abordagem 2 com conhecimento de negocio;
2. Testar segmentacao por estrato como ranking oficial;
3. Coletar cobertura 4G/5G (painel STEL/Anatel) para enriquecer o Pilar C;
4. Coletar CNPJ/MEI e Caged para a Abordagem 3 (modelo residual).

---

*Documento gerado automaticamente por scripts/06_comparacao_tres_abordagens_ipb.py*
