# Arquétipos Municipais — documentação dos 6 clusters

> **Data:** 2026-09-13 · **Método:** K-Means com K=6 sobre as 19 features da Etapa 3
> **Código:** `src/analytics/clustering.py` (clusterização + regras de nome) · **Notebook:** `notebooks/01_modelagem/01_dataset_e_arquetipos.ipynb` (execução com figuras)
> **Status:** nomes são **sugestão por regra sobre os dados** — validação do grupo **pendente** (este doc é a base pra decisão).

---

## 1. Os arquétipos são baseados em quê?

Em **nada que tenha sido decidido na mão**. A cadeia é:

1. **Dados:** as 19 variáveis aprovadas na discussão (renda, PIB, Pix, banda larga, agências, correspondentes, CEMPRE... — lista em `src/analytics/modelagem.py`, `FEATURES_MODELO`).
2. **Transformação:** `log1p` nas 14 colunas de cauda longa + padronização.
3. **Agrupamento:** K-Means com K=6 (como o K foi escolhido: §3 abaixo). Nenhum rótulo humano entra aqui — o algoritmo só calcula distâncias entre as 5.570 cidades nas 19 dimensões.
4. **Perfil:** para cada grupo, calculamos a média de cada variável (a "cidade média" do grupo). É essa tabela que aparece abaixo — **a narrativa nasce dela**.
5. **Nome:** regra automática (`sugerir_nomes_perfis`) compara cada média ao **perfil nacional ponderado**: alojamento-alimentação muito acima → *Turismo*; Pix PJ acima → *Polo empresarial*; agências ~zero → *Sem rede bancária*... Se um nome repete, um **discriminador** separa o par (ex.: os dois "Turismo" viraram *Turismo - com rede* e *Turismo - sem banco*). Regras e discriminadores são baseadas em dados.

**Solidez dos grupos (número):** dá para reconhecer o arquétipo de uma cidade olhando **só** as 13 variáveis socioeconômicas + digitais (sem nada de banco): F1 macro = **0,826** (`notebooks/01_modelagem/02_classificacao_presenca.ipynb`, seção 3). Ou seja: o arquétipo é uma propriedade da cidade, não um acidente da rede bancária instalada.

**Quão "típico" cada município é (GMM):** o GMM acompanha o K-Means e entrega a **probabilidade de pertencimento** de cada cidade ao seu grupo (`prob_cluster_gmm`). Resultado (notebook 01, seção 4.1): 4.855 municípios típicos (>90% de confiança), 705 predominantes e só 10 "mestiços" (<50%) — todos cidades pequenas do interior do Nordeste na fronteira entre os perfis de baixa renda, candidatas a transição entre arquétipos.

## 2. Tabela de perfis (valores reais, não log)

Média de cada variável dentro do grupo (fonte: notebook 01, seção 4):

| Arquétipo (sugestão) | n | Pop. média | PIB pc (R$) | Renda dom. pc (R$) | Pix pc (R$) | Pix PJ (%) | Empregos formais /1000 | Alojamento aliment. /1000 | Agências /100k | Corresp. /100k | IPB médio | % sem agência |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Turismo - com rede** | 740 | 180.726 | 67.376 | 1.731 | 70.560 | 51% | 370 | 3,3 | 7,8 | 125 | 51,2 | 0% |
| **Sem rede bancária - renda baixa** | 1.278 | 9.986 | 16.550 | 716 | 38.500 | 18% | 103 | 0,4 | 0,0 | 143 | 28,6 | **100%** |
| **Intermediário - empresarial** | 1.248 | 14.390 | 54.255 | 1.517 | 54.746 | 42% | 269 | 2,3 | 15,4 | 144 | 37,3 | 0% |
| **Intermediário - tradicional** | 919 | 34.370 | 20.821 | 810 | 43.430 | 25% | 128 | 0,8 | 7,4 | 94 | 32,6 | 0% |
| **Turismo - sem banco** | 653 | 6.089 | 60.688 | 1.442 | 52.542 | 42% | 308 | 2,5 | 0,0 | 163 | 43,0 | **100%** |
| **Sem rede bancária - renda alta** | 732 | 4.181 | 37.192 | 1.330 | 46.426 | 29% | 167 | 1,0 | 0,2 | 175 | 34,3 | 99% |

Leituras de negócio de cada grupo:

- **Turismo - com rede (740):** destinos turísticos grandes/populosos e ricos, **já atendidos** por agências. PIB pc alto + alojamento 3,3/1000 hab (≈8× a média). *Jogada típica: concorrida, o IPB não precisa "descobrir" — é mercado maduro.*
- **Sem rede bancária - renda baixa (1.278):** o interior pobre — ~10 mil hab, baixa renda e formalização, **100% sem agência** (o maior grupo do país). Correspondentes existem (143/100k). *Jogada típica: só digital/correspondente, ticket baixo.*
- **Intermediário - empresarial (1.248):** cidades pequenas com **PIB pc alto, Pix PJ 42% e empregos formais altos** — atividade empresarial forte. Agências presentes (15/100k). *Jogada típica: conta PJ, folha, consignado.*
- **Intermediário - tradicional (919):** cidades médias de renda mediana, perfil "comum do interior". *Jogada típica: varejo padrão.*
- **Turismo - sem banco (653):** **o achado do projeto** — destinos turísticos **pequenos** (~6 mil hab) e **ricos** (PIB pc R$ 60,7 mil), 100% sem agência, correspondência alta (163/100k). Bombinhas está aqui (e é o rank 1 do IPB V3). *Jogada típica: oportunidade clara de primeiro banco físico.*
- **Sem rede bancária - renda alta (732):** cidades **muito pequenas** (~4 mil hab) com renda acima da média, 99% sem agência, correspondência altíssima (175/100k). *Jogada típica: digital com correspondente de apoio.*

## 3. Como o K foi escolhido (e como opinar)

Tabela de métricas (notebook 01, seção 3 — detalhe de cada métrica no guia de conceitos):

| K | silhouette K-Means | BIC do GMM | Comentário |
|---|---|---|---|
| 3 | **0,252** | −1.515 | Melhor silhouette, mas os grupos viram "porte da cidade" (sinônimo do estrato populacional que já temos) — empobrece a narrativa |
| 5 | 0,222 | −18.905 | Alternativa válida |
| **6** | 0,200 | −20.591 | **Adotado**: perde 0,05 de silhouette e ganha 6 histórias distintas; clusters equilibrados (653–1.278) |
| 8 | 0,171 | −24.013 | Fragmenta: grupos começam a se dividir sem ganhar legibilidade |

**Recomendação (pra não ficar só "opção sua"):** manter **K=6**. Argumentos: (1) a diferença de silhouette entre 5 e 6 é pequena e nenhuma das duas é "excelente" — o que decide é o que a banca consegue ouvir; (2) com 6, cada grupo tem uma jogada de negócio diferente (tabela acima), com 3 seriam só "grande/média/pequena"; (3) a solidez está medida: F1 macro 0,826 — os grupos não são artefato. Se na apresentação 6 parecer muito, K=5 é o plano B registrado (troca de uma constante e reexecuta os 3 notebooks; ~5 minutos).

**Como opinar sobre os nomes:** olhe a tabela da §2 e pergunte "eu conto essa cidade em uma frase pra alguém de fora?". Sugestões de renomeação são bem-vindas — basta editar `K_ESCOLHIDO`/nomes no notebook 01 (ou trocar a regra em `sugerir_nomes_perfis`) e reexecutar. Nomes melhores que os atuais, baseados nos dados da tabela: *Turismo urbano atendido*, *Interior de baixa renda*, *Polo empresarial do interior*, *Cidade média comum*, *Destino turístico rico sem banco*, *Pequena rica de fronteira agro*.

## 4. Onde isso mora

| Produto | Onde |
|---|---|
| Labels por município + nome do arquétipo | tabela `analytics_ipb_clusters` no BigQuery (colunas `cluster_kmeans`, `arquetipo`, `prob_cluster_gmm`) |
| Regras de nome e discriminadores | `src/analytics/clustering.py` (`_REGRAS_NOME`, `_DESAMBIGUACAO`) |
| Perfis e figuras | notebook 01 (seções 3–4) e figuras em `docs/assets/figures/01_*.png` |
| Distribuição do IPB por arquétipo | boxplot `01_ipb_por_cluster.png` e ranking `01_ranking_ipb_arquetipos.png` |
