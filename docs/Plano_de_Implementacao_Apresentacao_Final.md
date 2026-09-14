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
2. Classificação entra por cima. Um slide, 30 segundos: tentamos prever presença bancária usando agências como alvo proxy, resultado fica como registro honesto de tentativa.
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

## 6. Roteiro do deck (10 minutos, 14 slides)

| Slide | Conteúdo | Tempo |
|---|---|---|
| 1. Capa | Nome do grupo, integrantes, tema. Frase de impacto decidida no ensaio, com calma | 20 s |
| 2. O problema | Bancos e fintechs precisam escolher onde investir (agência, correspondente, crédito, marketing) entre 5.570 cidades e não existe ranking público que una potencial econômico + digital + concorrência. Hoje a decisão é por achismo. E o escuro é real: 2.655 cidades sem agência registrada no Estban | 50 s |
| 3. O objetivo | A pergunta do IPB: onde potencial econômico, adoção digital e baixa concorrência física se encontram | 30 s |
| 4. Os dados | 9 fontes públicas, volume (216 mil vínculos de correspondentes), diagrama do pipeline. Ponto forte: tudo público, dá para refazer | 60 s |
| 5. Preparação | A história do gap em duas frases: a primeira fórmula da V3 punia com IPB zero ~119 cidades pequenas saturadas de lotérica. Testamos a sensibilidade, trocamos para gap linear, e as três versões convergiram. Lição: confiamos na fórmula só depois de testá-la | 70 s |
| 6. EDA | Os gráficos que a gente mesmo fez: escolaridade, cidades com maiores valores de Pix e de agências, correlações. Cada gráfico com uma frase do que ele mostra | 60 s |
| 7. A solução | Os 5 pilares e a média geométrica. Por que geométrica: pilar zerado zera o índice, quem não tem nada em nenhuma dimensão não entra no ranking à força | 70 s |
| 8. Três versões | V1, V2 e V3 lado a lado, o que cada uma testa, as diferenças entre elas, e por que a V3 é a oficial | 60 s |
| 9. Mapa | O coroplético dos 5.570 municípios na V3. Onde o potencial concentra: eixo sul-sudeste, litoral turístico, dormitórios industriais | 60 s |
| 10. Arquétipos | Etapa 3: 6 clusters com nome de negócio, potencial latente, anomalias. Figuras regeneradas para ficarem chamativas | 60 s |
| 11. O que tentamos | Classificação de presença bancária usando agências como alvo proxy. 30 segundos, honesto | 30 s |
| 12. Resultados | O slide principal: perfil do Top 30 (PIB pc ~R$ 111 mil contra mediana de ~R$ 30 mil), o ranking por cluster, a visão por estrato (pequena/média/grande), o experimento de tirar o pilar D e as trocas do Top 100 com história | 80 s |
| 13. Limitações e próximos passos | Vintage misto, concorrência digital invisível, alvo proxy, MEI fora do CEMPRE. Um próximo passo real por linha | 40 s |
| 14. Fechamento | QR para a página exploradora. "Cada uma das 5.570 cidades dá para consultar aqui" | 20 s |

Soma: 9 min 50 s. Espaço zero para imprevisto, então o ensaio cronometrado é obrigatório.

Slides de backup (apêndice depois do 14, não entram na fala): tabela completa V1/V2/V3, ranking completo por cluster, detalhe do K=6, métricas de classificação e regressão, construção dos pesos dos correspondentes, dicionário de fontes com ano de referência, caso a caso das trocas do Top 100.

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
