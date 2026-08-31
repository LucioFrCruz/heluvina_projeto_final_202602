# Relatório de Análise Exploratória de Dados — IPB

> **Projeto**: Índice de Potencial Bancário (IPB)  
> **Etapa**: 2 — Análise Exploratória e Limpeza  
> **Base**: `trusted_municipios` (5.570 municípios)  
> **Período de referência**: Censo 2022, PIB 2023, Pix jul/2025–jun/2026, Anatel/Estban 2026, IDHM 2010  
> **Gerado em**: 2026-08-26

---

## 1. Objetivo

Este relatório consolida os principais achados da análise exploratória de dados (EDA) do IPB. A EDA teve como propósito:

- Avaliar a qualidade da base `trusted_municipios`.
- Explorar as tabelas `raw_*` para validar a construção da camada trusted.
- Identificar padrões, outliers e correlações entre os 5 pilares do índice.
- Calcular uma versão alpha do IPB e gerar um ranking inicial de municípios.

---

## 2. Base de dados e método

A análise foi conduzida em 6 notebooks reprodutíveis localizados em `notebooks/00_exploracao/`:

| Notebook | Propósito |
|----------|-----------|
| `00_setup_e_qualidade.ipynb` | Validação de qualidade da `trusted_municipios`. |
| `00b_auditoria_raws_e_features.ipynb` | Auditoria das tabelas `raw_*` e engenharia de features. |
| `01_perfil_demografico_e_geo.ipynb` | Análise do pilar E (perfil demográfico). |
| `02_economia_e_dinamismo.ipynb` | Análise dos pilares A e B (renda, PIB, Pix). |
| `03_infra_digital_e_gap_bancario.ipynb` | Análise dos pilares C e D (banda larga, agências). |
| `04_integracao_correlacoes.ipynb` | Correlações, PCA e cálculo alpha do IPB. |

Os outputs de dados (parquet e relatórios JSON) foram salvos em `data/processed/`.  
As figuras geradas pela EDA foram salvas em `docs/assets/figures/` para ficarem versionadas junto com este relatório.

### 2.1 Correção e recálculo do Pix

Durante a análise de ponta a ponta do projeto, identificou-se um **bug crítico de duplicação** na tabela `raw_bcb_pix_transacoes`: cada mês aparecia múltiplas vezes (ex.: o mês `202606` aparecia 12 vezes), inflando artificialmente o volume Pix anualizado em aproximadamente **87%**.

A causa foi a ausência de `drop_duplicates` no ingestor `bcb_pix.py`, combinada a execuções sucessivas da rotina. O bug foi corrigido adicionando:

```python
df = df.drop_duplicates(subset=["id_municipio", "AnoMes"])
```

Após a correção, o ingestor foi re-executado para os **12 meses mais recentes** (ago/2025 a jul/2026), resultando em **72.421 registros** brutos únicos. A `trusted_municipios` e o IPB *alpha* foram recalculados com a série corrigida.

**Impacto nos dados**:

| Métrica | Antes da correção | Depois da correção | Redução |
|---|---|---|---|
| Pix total volume 12m (soma) | R$ 107,97 trilhões | R$ 13,84 trilhões | **87,2%** |
| Pix per capita médio | R$ 389.821 | R$ 49.901 | **87,2%** |
| Registros brutos na raw | 568.236 | 72.421 | **87,3%** |

---

## 3. Qualidade dos dados

A base `trusted_municipios` possui **5.570 municípios** e **26 colunas**, com `id_municipio` como chave primária única.

### 3.1 Nulos e gaps conhecidos

| Coluna | % Nulos | Observação |
|--------|---------|------------|
| `domicilios_com_internet_pct` | 100% | API do SIDRA indisponível para `N6[all]`; usa-se `banda_larga_fixa_por_100_hab` como proxy. |
| `idhm` | 0,11% | Vintage 2010; mantido como referência histórica. |
| `quantidade_agencias` | 0% | Municípios sem agência foram imputados com 0. |

Todas as regras de negócio validadas passaram:

- `populacao_total > 0` ✅
- `pib_per_capita > 0` ✅
- Percentuais entre 0 e 100 ✅
- `quantidade_agencias >= 0` ✅

### 3.2 Figuras relevantes

![Mapa de missing values](assets/figures/00_missing_values_heatmap.png)

![Distribuição da população total](assets/figures/00_populacao_total_distribuicao.png)

![Quantidade de municípios por UF](assets/figures/00_municipios_por_uf.png)

---

## 4. Perfil demográfico e geográfico (Pilar E)

### 4.1 Principais achados

- **Escolaridade**: Sudeste lidera com 44,35% da população 18+ com ensino médio completo; Nordeste tem o menor índice (33,95%).
- **Urbanização**: Sudeste (78,94%) e Centro-Oeste (76,2%) são as regiões mais urbanizadas; Nordeste (60,98%) e Norte (62,83%) são as menos urbanizadas.
- **População jovem (18–35)**: Norte tem a maior proporção (27,81%), seguido do Nordeste (26,85%).
- **1.098 municípios** apresentam perfil simultaneamente jovem, urbano e escolarizado acima da mediana.
- **Correlações**: as variáveis demográficas são relativamente independentes entre si, exceto pelo par `idhm` × `escolaridade_ensino_medio_pct` (0,78) e `populacao_urbana_pct` × `escolaridade_ensino_medio_pct` (0,70), indicando que municípios mais urbanos e com maior IDHM tendem a ser mais escolarizados. `populacao_18_35_pct` tem correlação fraca com as demais, o que é bom para o índice — significa que os pilares não estão todos medindo a mesma coisa.

### 4.2 Figuras relevantes

![Distribuição da escolaridade (% ensino médio completo)](assets/figures/01_dist_escolaridade_ensino_medio_pct.png)

![Escolaridade por região](assets/figures/01_boxplot_escolaridade_ensino_medio_pct_regiao.png)

![Correlação entre variáveis demográficas](assets/figures/01_correlacao_demografica.png)

---

## 5. Capacidade de consumo e dinamismo (Pilares A e B)

### 5.1 Principais achados

- **Renda e PIB**: cidades grandes apresentam renda domiciliar per capita mediana de R$ 2.079,68 e PIB per capita de R$ 56.227,29; cidades pequenas ficam com R$ 1.145,36 e R$ 28.216,86, respectivamente. As distribuições de renda e PIB usam escala log porque ambas são fortemente assimétricas: poucos municípios concentram valores muito altos.
- **Pix per capita (12 meses)**: cresce conforme o estrato populacional — pequenas R$ 348.814, médias R$ 478.673, grandes R$ 645.788. A estratificação populacional segue o critério: pequena (< 50 mil hab.), média (50 mil–500 mil hab.) e grande (> 500 mil hab.).
- **Outlier no estrato pequeno**: Pacaraima (RR), com população de ~19 mil habitantes, registra R$ 4,1 milhões de Pix per capita — provavelmente efeito do comércio de fronteira.
- **859 municípios** apresentam alta adoção Pix (acima da mediana) e renda abaixo da mediana, indicando potencial de inclusão financeira digital.
- A série temporal do Pix mostra concentração crescente de volume em meses recentes. O volume é apresentado em trilhões de reais (R$) e separado entre Pessoa Física (PF) e Pessoa Jurídica (PJ). Os dados brutos do BCB já contêm PJ, mas a camada `trusted` do IPB utiliza apenas PF como proxy de adoção digital no pilar B.
- **Pix vs PIB**: os eixos estão em escala log. A linha tracejada representa a tendência geral. Municípios acima da linha têm mais Pix per capita do que seu PIB per capita preveria, sugerindo alta penetração digital relativa à renda.

### 5.2 Figuras relevantes

![Distribuição do log do rendimento domiciliar per capita](assets/figures/02_dist_log_rendimento_domiciliar_per_capita.png)

![Pix per capita vs PIB per capita](assets/figures/02_pix_vs_pib.png)

![Série temporal do Pix](assets/figures/02_serie_pix.png)

![Pix per capita (12 meses) por estrato populacional](assets/figures/02_boxplot_pix_per_capita_12m_estrato.png)

---

## 6. Infraestrutura digital e gap bancário (Pilares C e D)

### 6.1 Principais achados

- **Municípios sem agência bancária**: **2.656 municípios (47,68%)** não possuem agência bancária ativa.
- **UFs com maior gap**: Piauí (82,1%), Tocantins (80,6%), Paraíba (79,8%), Rio Grande do Norte (77,2%) e Roraima (66,7%).
- **Banda larga fixa**: a variável `banda_larga_fixa_por_100_hab` mede o número de acessos de banda larga fixa a cada 100 habitantes (taxa de penetração), não a velocidade em Mbps. Valores acima de 100 são possíveis quando há mais de uma linha por residência/empresa.
- **Quadrantes (banda larga × agências)**:
  - **Alto potencial**: 1.050 municípios (banda larga alta + poucas agências).
  - **Maduro saturado**: 1.735 municípios (banda larga alta + muitas agências).
  - **Desconectado**: 1.735 municípios (banda larga baixa + poucas agências).
  - **Bancarizado sem infra**: 1.050 municípios (banda larga baixa + muitas agências).

### 6.2 Figuras relevantes

![Quadrantes de infraestrutura digital e gap bancário](assets/figures/03_quadrantes_infra_gap.png)

![Percentual de municípios sem agência por UF](assets/figures/03_pct_sem_agencia_uf.png)

![Banda larga fixa por 100 hab. por região](assets/figures/03_boxplot_banda_larga_fixa_por_100_hab_regiao.png)

---

## 7. Integração e cálculo alpha do IPB

### 7.1 Metodologia do IPB alpha

Para cada pilar, as variáveis foram:

1. **Winsorizadas** no percentil 1% e 99%.
2. **Normalizadas** para [0, 1] via min-max.
3. As variáveis do pilar D (gap bancário) foram **invertidas** (quanto menor a infraestrutura bancária tradicional, maior o potencial).

Cada pilar foi calculado como a média simples das variáveis normalizadas. O IPB alpha é a média geométrica dos 5 pilares × 100:

```
IPB_alpha = (A × B × C × D × E)^(1/5) × 100
```

### 7.2 Resultados

- **Média do IPB alpha**: 35,85
- **Mediana do IPB alpha**: 35,86
- **Variância explicada pelos 2 primeiros componentes PCA**: 70,45%

#### Top 10 municípios no ranking alpha

| Rank | Município | UF | IPB Alpha |
|------|-----------|----|-----------|
| 1 | Barueri | SP | 82,54 |
| 2 | Itapema | SC | 82,24 |
| 3 | Balneário Camboriú | SC | 81,81 |
| 4 | Paulínia | SP | 80,87 |
| 5 | Itajaí | SC | 80,05 |
| 6 | Ilhabela | SP | 79,87 |
| 7 | Nova Lima | MG | 79,85 |
| 8 | Itupeva | SP | 79,15 |
| 9 | Santa Carmem | MT | 78,93 |
| 10 | Nova Mutum | MT | 78,80 |

#### Bottom 10

Municípios com IPB alpha igual a 0 estão majoritariamente em Alagoas e Acre. Esses casos indicam municípios com dados zerados em pelo menos um pilar após winsorização (geralmente Pix ou Estban).

#### Impacto da correção do Pix no ranking

Apesar da redução de **87%** no volume Pix, a média e a mediana do IPB *alpha* praticamente não se alteraram (35,83 → 35,85). Isso ocorre porque a normalização min-max comprime a escala e os outros pilares compensam parcialmente a queda do Pilar B/C.

No entanto, houve movimentação significativa em posições individuais:

- **Maior subida**: Piau (MG) subiu **209 posições** (3.353 → 3.144);
- **Maior queda**: Tigrinhos (SC) caiu **256 posições** (3.635 → 3.891);
- **Top 100**: apenas 1 município saiu (Foz do Iguaçu/PR) e 1 entrou (Tapurah/MT).

O Top 10 permaneceu bastante estável, com pequenas trocas de posição. A correção tornou o ranking mais confiável, embora a estrutura geral ainda reflita cidades ricas e conectadas.

### 7.3 Figuras relevantes

![Correlação entre pilares do IPB](assets/figures/04_correlacao_pilares.png)

![Distribuição do IPB alpha](assets/figures/04_dist_ipb_alpha.png)

![Top 30 municípios no ranking IPB alpha](assets/figures/04_top30_ipb_alpha.png)

![PCA dos pilares do IPB](assets/figures/04_pca_pilares.png)

---

## 8. Features adicionais criadas

A partir das tabelas `raw_*`, foram criadas as seguintes features na base enriquecida `trusted_municipios_eda.parquet`:

| Feature | Descrição |
|---------|-----------|
| `pix_pj_pct` | Proporção do volume Pix de pessoas jurídicas. |
| `pix_ticket_medio` | Valor médio por transação Pix. |
| `flag_sem_agencia` | Indicador de município sem agência bancária. |
| `estrato_populacional` | pequena (< 50k), média (50k–500k), grande (> 500k). |
| `depositos_por_agencia` | Volume de depósitos por agência. |
| `credito_por_agencia` | Volume de crédito por agência. |

---

## 9. Limitações e ressalvas

1. **Vintage misto**: a base combina Censo 2022, PIB 2023, Pix 2025–2026, Anatel/Estban 2026 e IDHM 2010. Isso deve ser declarado na apresentação final.
2. **Internet domiciliar**: a coluna `domicilios_com_internet_pct` está 100% nula; usamos banda larga fixa como proxy.
3. **Pix**: os dados brutos do BCB incluem PF e PJ, mas o cálculo da `trusted_municipios` utiliza apenas `VL_PagadorPF`/`QT_PagadorPF` como proxy de adoção digital. Uma versão futura pode testar incluir PJ e/ou variáveis de recebedores.
4. **Efeito polo regional**: municípios dormitório podem parecer desatendidos porque recursos financeiros fluem para cidades próximas.
5. **Municípios com IPB zero**: indicam ausência de dados em algum pilar; devem ser analisados caso a caso.

---

## 10. Próximos passos

1. **Refinar a fórmula do IPB**: testar cenários de pesos e sensibilidade do ranking.
2. **Explorar clusterização (opcional)**: aplicar K-Means nos pilares para criar arquétipos de municípios.
3. **Construir visualizações executivas**: mapas, quadrantes e fichas de municípios.
4. **Definir ondas de expansão**: Top 50, Top 100, etc.

---

## 11. Como reproduzir

```bash
# 1. Re-executar o Pix (12 meses)
poetry run python -m src.ingestors.bcb_pix

# 2. Re-executar a trusted
poetry run python -m src.preparacao.trusted_municipios

# 3. Executar os notebooks
poetry run jupyter nbconvert --to notebook --execute notebooks/00_exploracao/*.ipynb
```

---

*Relatório gerado automaticamente a partir dos notebooks de EDA do IPB.*
