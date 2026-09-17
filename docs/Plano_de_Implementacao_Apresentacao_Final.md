# Plano de implementação: apresentação final (17/09)

> Rascunho de discussão do grupo, 14/09/2026 (v2, incorpora feedback do grupo de 14/09). Ainda não commitado.
> Baseado no material da aula 5 (Prof. Fabio) e nos documentos de discussão do projeto.
> Regras da escrita: tudo que for para a banca passa pela skill humanizer (sem cara de IA).

---

## 1. O que a avaliação pede

Leitura direta do material do professor:

- A apresentação vale 4,0 pontos. É o item mais pesado da média final, mais que qualquer etapa técnica individual.
- Formato: 10 minutos de fala + 10 minutos de perguntas. Sala Mack Graphe.
- O que ele quer ouvir: uma história de negócio guiada por dados. Não uma lista de etapas técnicas.
- O arco da história: problema → dados → tratamento e entendimento → solução → avaliação → valor.
- O slide de resultados é o mais importante. Métrica técnica tem que virar frase de negócio.
- Limitação não é vergonha. Projeto real tem limitação, e fingir perfeição é armadilha explicitamente listada por ele.
- Diferenciais que ele pontua: clareza, coerência, objetividade, visão de negócio, maturidade técnica.

Armadilhas listadas por ele que tratamos como restrição de design do deck: foco só em tecnologia, código em slide, texto demais, decisão sem justificativa, gráfico sem interpretação, etapas desconectadas, estourar o tempo.

## 2. Decisões do grupo

1. A V3 é a versão oficial da fala. V1 e V2 não saem do deck: entram como comparativo. As três concordam em cerca de 85% das posições (Spearman 0,852 entre V1 e V3), o que vira argumento de robustez.
2. Clusterização é o protagonista da fala de modelagem: qual algoritmo (K-Means + GMM), por quê, e a escolha de K=6 — sem aula de algoritmo. A classificação de presença bancária saiu do deck (feedback de que ficou "meio inútil") e ficou registrada no apêndice A4 como experimento honesto com alvo proxy.
3. Q&A não é "deixar pergunta no slide". É o professor perguntar e a gente responder. A preparação é ensaiar respostas curtas para as perguntas previsíveis e ter slides de backup com os números que sustentam cada resposta.
4. Backup de tudo. PDF estático do deck + deck 100% local (zero CDN).
5. Mapa do Brasil: só camada V3 e visão de arquétipos. Sem toggle de versão.
6. QR só no slide final.
7. Exploradora: busca lisa (sem acento, maiúscula/minúscula), filtro por UF e uma visão consolidada por UF (médias de escolaridade, Pix, agências, IPB por estado).
8. Pages ativado apontando para a branch `feature/apresentacao`, pasta `/docs`. A URL não depende da branch, então o QR pode ser gerado assim que qualquer conteúdo estiver no ar.
9. Modo de trabalho: entregas parciais que o grupo abre no navegador e valida antes da próxima etapa.

## 3. Entregáveis e ordem de execução

| # | Entregável | O que é | Prioridade |
|---|---|---|---|
| E6 | Script de exportação | Gera o JSON dos dados do site a partir dos parquet locais, 100% offline | 1 (tudo depende dele) |
| E2 | Mapa do Brasil | Coroplético dos 5.570 municípios: camada IPB V3 + visão de arquétipos | 2 |
| E1 | Deck HTML interativo | Apresentação em reveal.js, tudo vendorizado, funciona sem internet | 3 |
| E3 | Página exploradora | Busca de município + visão consolidada por UF | 4 |
| E4 | QR code | No slide final, apontando para a página exploradora | 5 |
| E5 | PDF do deck | Export estático para plano B e consulta da banca | 6 |

Entregas parciais para validação:

- Drop 1: JSON exportado + malha validada + mapa abrindo no navegador + landing placeholder.
- Drop 2: deck completo com os 14 slides e conteúdo real. Grupo valida e itera texto/figuras.
- Drop 3: exploradora + QR + PDF + ensaio.

## 4. Hospedagem: GitHub Pages

- Pages ativado em 14/09 apontando para a branch `feature/apresentacao`, pasta `/docs`. O commit do site vai nessa branch.
- URL: `https://luciofrcruz.github.io/heluvina_projeto_final_202602/` (a URL não muda com a branch, só o conteúdo servido).
- Estrutura dentro de `docs/`:

```
docs/
├── index.html                  # landing: botão "ver apresentação" + botão "explorar cidades"
├── apresentacao.html           # o deck
├── explorar.html               # página exploradora (alvo do QR)
├── assets/
│   ├── reveal/                 # reveal.js vendorizado
│   ├── d3/ + topojson/         # libs do mapa
│   ├── qrcodejs/               # geração do QR client-side
│   ├── malha-municipios.topojson  # geometria simplificada
│   ├── css/ e img/             # estilo e figuras
├── data/
│   └── municipios.json         # ~5.570 registros, alvo ≤ 3 MB
└── (os .md de documentação atual continuam onde estão)
```

Pontos de atenção:

- Committar o `municipios.json` é uma exceção pequena à regra de "nada de dado bruto no Git". É dado derivado, compacto, e é o que permite o site ser 100% estático. Registrar a exceção no AGENTS.md quando commitar (diretriz 0.8).
- Sem chamada ao BigQuery a partir do site. Chave não se expõe. Tudo vem do JSON.
- Limite do Pages (1 GB por site, 100 MB por arquivo) está muito longe do nosso tamanho.

Plano B de hospedagem, se o Pages der problema: Netlify Drop ou Vercel com conta de um integrante, subindo a mesma pasta estática. O QR só é gerado depois do deploy definido, para não codificar URL quebrada.

## 5. Dados do site

Script novo `scripts/09_exporta_dados_site.py` (segue a numeração 07/08), via Poetry, lendo os parquet locais de `data/processed/` e gravando `docs/data/municipios.json`.

Campos por município (proposta, ~20 colunas):

```
id_municipio, nome_municipio, sigla_uf, nome_regiao, estrato_populacional,
ipb_v1, ipb_v2, ipb_v3, rank_v1, rank_v2, rank_v3,
score_a_v3, score_b_v3, score_c_v3, score_d_v3, score_e_v3,
arquetipo, cluster, potencial_latente (resíduo), flag_anomalia,
pix_per_capita, pix_pj_pct, idhm, escolaridade_pct, pib_per_capita,
agencias_por_100k, correspondentes_por_100k
```

Checagem de qualidade do export: 5.570 linhas, `id_municipio` único e com 7 dígitos, sem nulo nos campos de identidade e de IPB. Relatório de campos que não existirem em nenhum parquet (ficam de fora e viram nota no plano).

## 6. Roteiro do deck (10 minutos, 22 slides — v3 do deck, repaginado em 16/09)

> Redesign de 16/09 incorporando o feedback do professor (15/09) e a revisão do grupo
> (16/09): gráficos quase tela cheia (a altura do plotly é ajustada ao container pelo
> próprio deck, sem transbordar texto), texto mínimo por slide, diagrama iconográfico da
> stack, comparação visual das 3 versões do IPB, clusterização como protagonista da
> modelagem (algoritmo em um slide, escolha de K em outro; arquétipos e resultados
> também em 2 slides cada, com legenda de cores no próprio slide). A classificação de
> presença bancária SAIU da fala e ficou registrada no apêndice (A4). Capa/fechamento
> em gradiente petróleo suavizado, fontes Sora/Inter vendorizadas em `assets/fonts/`.

| Slide | Conteúdo | Tempo |
|---|---|---|
| 1. Capa | Tema, grupo e a pergunta central | 15 s |
| 2. O problema | 2.656 cidades sem agência (47,7% do território, 19,8 mi de pessoas) e a falta de visão integrada | 35 s |
| 3. O objetivo | Índice 0–100 para os 5.570 municípios, dados públicos, pipeline reproduzível | 15 s |
| 4. Arquitetura e stack | Diagrama iconográfico: fontes (APIs + manuais→GCS) → ingestores Python/Pandas → Parquet → BigQuery (raw/trusted/analytics) → site | 45 s |
| 5. Nove bases, nove safras | Grid das 8 fontes com ano; o problema de engenharia é 2010–2026 convivendo; tratamentos e testes | 35 s |
| 6. EDA — escolaridade I | Histograma grande; cidade média tem só 39,4% com ensino médio | 30 s |
| 7. EDA — escolaridade II | Box por região; Sul/Sudeste acima, Norte/Nordeste embaixo | 30 s |
| 8. EDA — Pix I | Top 15 Pix per capita com legenda de região; Pacaraima (fronteira) + cidades do agro | 30 s |
| 9. EDA — Pix II | Mediana por UF com legenda; DF é um único município; leitura do agro é correlação, não causalidade | 30 s |
| 10. Três versões, três perguntas | Texto: V1 "onde já tem dinheiro" (ranking de riqueza) → V2 "onde falta banco" (exagerou no déficit) → V3 "onde falta banco E tem mercado" (correspondentes + CEMPRE) | 30 s |
| 11. O Top 100 trocou | Texto: 39 posições novas; saíram as ricas bancarizadas (Noronha 13→2.578) e entraram capitais/polos (Brasília 134→13); Norte 2→7, Nordeste 4→8 | 20 s |
| 12. Metodologia V3 | 5 pilares — D é INVERTIDO (menos banco = mais pontos, 30%) — e média geométrica como seguro | 40 s |
| 13. Mapa ao vivo | Coroplético interativo (IPB V3 e arquétipos), rodando no site | 30 s |
| 14. Clusterização — algoritmo | K-Means + GMM e por quê; sem rótulo de verdade; 4.855 cidades >90% de um arquétipo | 25 s |
| 15. Por que K=6 | Figura silhouette × elbow; K=3 separa porte; queda desacelera entre 5 e 6 | 25 s |
| 16. Arquétipos — os grupos | Barras + grid dos 6 grupos; o achado "Turismo sem banco" (653 cidades, 100% sem agência) | 30 s |
| 17. Arquétipos — o mapa | Scatter sem eixos: cada ponto é uma cidade, perto = perfil parecido; legenda de cores | 15 s |
| 18. Anomalias — Isolation Forest | Qual algoritmo e por quê (sem rótulo de anomalia); Top 30 atípicas, Noronha #1, grupo com 5× agências; gerador de hipótese | 25 s |
| 19. Resultados — Top 15 | Stats (PIB pc R$ 93 mil × R$ 30 mil; PJ 0,57 × 0,19; 39 trocas) + Top 15 com legenda de porte | 30 s |
| 20. Resultados — arquétipos no índice | Distribuição do IPB por arquétipo com legenda; turismo alto, interior sem rede embaixo | 25 s |
| 21. Limitações | Vintage misto, concorrência digital invisível, alvo proxy, fontes fora da coleta — cada uma com o próximo passo | 25 s |
| 22. Fechamento | QR para a exploradora; "5.570 cidades consultáveis agora" | 15 s |

Soma: 10 min 0 s. Ensaio cronometrado continua obrigatório.

Slides de backup (apêndice, fora da fala): A1 top 10 nas três versões, A2 ranking por
arquétipo, A3 por que K=6, A4 métricas da Etapa 3 (classificação + regressão + potencial
latente com Spearman 0,449), A5 pesos dos correspondentes, A6 fontes com ano/URL,
A7 trocas do Top 100 com o CEMPRE, A8 rede paralela (agências × correspondentes).

## 7. Mapa do Brasil

- Geometria: malha municipal simplificada em topojson, alvo de 2 a 5 MB, baixada de repositório público e vendored em `assets/`, sem CDN.
- Join com os dados pela chave de 7 dígitos do IBGE. Critério de aceite: 5.570 de 5.570 municípios com polígono.
- Camadas: IPB V3 em escala contínua e visão de arquétipos com 6 cores. Tooltip com nome, UF, IPB, rank e arquétipo. Clique no município abre a página dele no explorador.
- Renderização em SVG via D3 + topojson-client. Se travar em hardware fraco, cai para canvas.
- Interpretação no slide, não só o desenho: legenda com 2 ou 3 leituras prontas.
- Fallback se a malha falhar: mapa de estados com top cidades.

## 8. Página exploradora (alvo do QR)

- Busca lisa: sem acento, maiúscula ou minúscula, filtro por UF.
- Card da cidade: IPB nas três versões, rank, arquétipo, potencial latente, flag de anomalia, Pix per capita e participação PJ, IDH(m), escolaridade, PIB per capita, agências e correspondentes por 100 mil hab.
- Visão consolidada por UF: médias de IPB, escolaridade, Pix, agências e correspondentes por estado, com ranking dos estados.
- Modo tabela com ordenação por qualquer coluna, para fuçar o ranking inteiro.
- 100% estático: lê o `municipios.json`, sem backend.
- O QR é gerado no próprio slide pelo qrcodejs (lib vendored), apontando para a URL do Pages. Sem lib nova no Python.

## 9. Preparação para as perguntas (10 minutos de banca)

Lógica: a pergunta vem do professor, a resposta a gente já ensaiou. Para cada pergunta previsível, uma resposta de 2 a 3 frases e o slide de backup que sustenta.

| Pergunta provável | Resposta ensaiada (resumo) | Backup |
|---|---|---|
| Por que média geométrica? | Pilar zero zera o índice. Município sem nada em uma dimensão não pode compensar com excesso em outra | 7 |
| Por que ~119 cidades com IPB=0? | Propriedade do método (min-max do pior 1%), não erro. Lista disponível | 7 |
| Como validam sem rótulo de verdade? | Proxy declarado + validações objetivas: CEMPRE, alojamento/turismo, estabilidade entre versões | 12 |
| Por que K=6? | Cotovelo, estabilidade e leitura de negócio. K=6 confirmado com o grupo | 10 |
| Lotérica conta como banco? | Correspondentes entram ponderados por tipo; peso do posto é limitação assumida | apêndice de pesos |
| Por que capitais sobem na V3? | Efeito denominador da densidade per capita. Declarado como ponto de atenção | 8 |
| Quanto a concorrência importa no índice? | Experimento sem pilar D: Spearman 0,894, mas o Top 100 perde 32 cidades. O pilar dá identidade ao objetivo | 12 |
| Por que misturar dados de 2010 e 2026? | Vintage misto é limitação declarada; cada fonte tem o ano mais recente disponível | 13 |
| O que as anomalias acharam? | Casos com potencial alto e presença baixa (e o contrário), listados para investigação | 10 |
| O site roda de onde? | JSON estático exportado do pipeline, GitHub Pages. Sem custo | 14 |

## 10. Cronograma até dia 17

**14/09 (hoje):**
- JSON exportado e validado
- Malha municipal baixada, join 5.570/5.570 validado
- Mapa abrindo no navegador (página de teste, fora do deck)
- Landing placeholder no ar para testar o pipeline do Pages

**15/09:**
- Deck v1 com os 14 slides e conteúdo real
- Grupo valida no navegador, itera texto e figuras

**16/09:**
- Ajustes do deck, exploradora com busca e visão por UF
- QR no slide final (depois do deploy), PDF de backup
- Dois ensaios cronometrados, divisão da fala (4 pessoas, ~2,5 min cada)
- Push na `feature/apresentacao`, site verificado no celular

**17/09:**
- Apresentar. Deck local como plano A, site no ar para o QR do público

## 11. Riscos e pendências

| Risco | Chance | Mitigação |
|---|---|---|
| Pages com delay no deploy | média | ativar e testar hoje com placeholder; plano B Netlify Drop |
| Malha municipal pesada ou com código divergente | média | topojson simplificado; critério de aceite no join; fallback mapa de estados |
| Mapa travando no notebook da apresentação | baixa | ensaio no hardware real; canvas como plano B; PDF estático sempre disponível |
| Estourar os 10 min | alta sem ensaio | cortar slides 6 ou 11 primeiro; ensaio cronometrado terça |
| QR depender da rede do público | baixa | o QR é bônus, a nota não depende dele |
| Internet da sala falhar | baixa | deck 100% local, nenhum CDN; abrir o arquivo no navegador |

Pendências do grupo:
1. Aprovar este plano v2 (marcar o que corta, se cortar algo)
2. Confirmar que o Pages está servindo a `feature/apresentacao` /docs
3. Definir quem fala qual bloco
4. Escolher a frase de impacto da capa (no ensaio, com calma)
