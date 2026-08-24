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

O projeto é suportado por um pipeline robusto de Engenharia de Dados (Python, Pandas, Google BigQuery), dividido em camadas `raw` (bruta) e `trusted` (padronizada). 

Dê preferência para leitura de nossos guias detalhados na pasta `docs/`:

- [Guia de Execução Técnica (Pipeline & SQL)](docs/Guia_de_Execucao.md) ⚠️ *Obrigatório ler para replicar a infra e dados manuais*
- [Plano de Implementação (Fases 0 a 4)](docs/Plano_de_Implementacao.md)
- [Guia de Bases e Desenho (Indicadores)](docs/IPB_Guia_de_Bases_e_Desenho.md)

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

- [x] **Fase 1: Desenho da Arquitetura e Definição de Indicadores** (Agosto/2026)
  - Identificação das fontes abertas (IBGE, BCB, Anatel).
  - Desenho técnico do Data Lake no BigQuery (Free Tier).

- [x] **Fase 2: Engenharia de Dados (Pipelines Raw e Trusted)** (Agosto/2026)  📍 **<-- ESTAMOS AQUI**
  - Implementação do ambiente isolado (Poetry).
  - Coleta automatizada de APIs e processamento de planilhas.
  - Subida dos dados para a camada `trusted_municipios` com códigos unificados.

- [ ] **Fase 3: Analytics e Modelagem do IPB** (Previsto: Setembro/2026)
  - Limpeza estatística (tratamento de *outliers*).
  - Normalização dos indicadores (Min-Max Scaler).
  - Criação da fórmula ponderada do Índice e geração do Ranking.

- [ ] **Fase 4: Visualização e Dashboard** (Previsto: Outubro/2026)
  - Conexão do BigQuery a uma ferramenta de BI (Looker Studio ou PowerBI).
  - Construção do painel executivo com mapas interativos e filtros regionais.
