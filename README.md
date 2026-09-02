# Mapa do Potencial Bancário Brasileiro (IPB)

**Onde expandir um banco digital no Brasil?** 
Este projeto realiza uma análise avançada dos 5.570 municípios brasileiros por meio da criação do **Índice de Potencial Bancário (IPB)**.

---

## 🎯 Sobre o Projeto e Objetivo

O mercado financeiro digital está em constante expansão. No entanto, a estratégia de alocação de esforços (como campanhas de marketing, concessão de crédito e expansão de serviços) exige precisão geográfica. 

O objetivo deste projeto é responder: **Quais municípios brasileiros apresentam a melhor relação entre potencial econômico, adoção digital e oportunidade de mercado (baixa concorrência física)?**

Para responder a essa pergunta, estamos construindo o IPB. As cidades são rankeadas a partir de uma combinação matemática de 5 pilares fundamentais de dados públicos:

1. **Pilar Demográfico e Educacional (IBGE / Censo 2022):** População total e nível de escolaridade.
2. **Pilar Econômico (IBGE):** PIB per capita e força do setor de serviços.
3. **Pilar de Dinamismo Financeiro (BCB - Pix):** Adoção e volume transacionado no Pix.
4. **Pilar de Infraestrutura Digital (Anatel):** Densidade de banda larga fixa instalada.
5. **Pilar de Desbancarização Física (BCB - Estban):** Quantidade de agências físicas (concorrência tradicional) versus depósitos em poupança.

**IPB = Oportunidade Financeira + Infraestrutura Digital - Concorrência Física**

<img width="359" height="68" alt="Exemplo de Ranking" src="https://github.com/user-attachments/assets/36f880c8-dbae-439a-9e2e-19e97d8fbaa9" />

---

## 🏗️ Estrutura do Projeto e Documentação Técnica

O projeto é suportado por um pipeline robusto de Engenharia de Dados (Python, Pandas, Google BigQuery), dividido em camadas `raw` (bruta), `trusted` (padronizada) e `analytics` (3 versões do IPB publicadas). 

Dê preferência para leitura de nossos guias detalhados na pasta `docs/`:

- [Relatório de EDA (inclui a comparação das 3 versões do IPB)](docs/Relatorio_EDA.md) 📊 *Achados da EDA, qualidade dos dados e comparação V1/V2/V3*
- [Comparação das Três Abordagens do IPB](docs/Comparacao_Tres_Abordagens_IPB.md) ⚖️ *Rankings, movimentação do Top 100 e alertas por versão*
- [Guia de Execução Técnica (Pipeline & SQL)](docs/Guia_de_Execucao.md) 💻 *Instruções de setup e queries SQL (100% automatizado)*
- [Plano de Implementação (Fases 0 a 4)](docs/Plano_de_Implementacao.md)
- [Guia de Bases e Desenho (Tese, Pilares e Fórmula do IPB)](docs/IPB_Guia_de_Bases_e_Desenho.md)

---

## 👥 Integrantes

- Hermes Augusto
- Lúcio Franchi Cruz
- Vitor Paes
- Nathalia Miranda

*(Compartilhar resultados com o professor fabioversolatto)*

---

## 🚀 Status e Roadmap do Projeto

Estamos desenvolvendo o projeto em etapas ágeis. Acompanhe nosso progresso:

- [x] **Proposta Validada** (Concluído - 13/08)
  - Definição da arquitetura, tese e pilares do índice.

- [x] **Etapa 1: Processamento e Ingestão** (Concluída)
  - Implementação do Data Lake (BigQuery + GCS).
  - Coleta automatizada de APIs (Pix, IBGE, Correspondentes BCB) e Data Lake centralizado para arquivos manuais (Estban, Anatel).
  - Tabela consolidadora `trusted_municipios`.

- [x] **Etapa 2: Análise Exploratória (EDA) e Índice** (EDA concluída) 📍 **<-- ESTAMOS AQUI**
  - Tratamento de outliers e dados faltantes, correlações entre os pilares.
  - **3 versões do IPB publicadas no BigQuery** (`analytics_ipb_v1_classico`, `analytics_ipb_v2_recalibrado`, `analytics_ipb_v3_presenca_completa` + visão `analytics_ipb_comparacao`): Clássico, Recalibrado e Presença Bancária Completa, com comparação documentada no Relatório de EDA.

- [ ] **Etapa 3: Refinamento e ML** (Prazo: 15/09)
  - Validação de negócio dos Top 100 e escolha da versão oficial do IPB.
  - Aplicação de técnicas de Machine Learning para *clustering* das cidades.

- [ ] **Apresentação Final** (Pitch: 17/09)
  - Dashboard executivo e entrega final do projeto.
