# Mapa do Potencial Bancário Brasileiro
Onde expandir um banco digital?
Análise dos municípios brasileiros por meio da construção do Índice de Potencial Bancário (IPB).

## Sobre o projeto
O projeto quer responder a seguinte pergunta: Quais municípios brasileiros apresentam maior potencial para expansão de um banco digital?

## Objetivo

Criar um Índice de Potencial Bancário (IPB) e as cidades serão rankeadas por esse índice.

Levando em consideração
- População - https://dados.gov.br/dados/conjuntos-dados/cd-censo-demografico & https://www.ibge.gov.br/estatisticas/sociais/rendimento-despesa-e-consumo/22827-censo-demografico-2022.html?edicao=35938

- crescimento populacional

- renda média - https://basedosdados.org/dataset/218ae306-29ac-4a83-836d-95bfdb9683fe?table=708098f3-aa55-41d3-9390-f35fb87faa66

- população economicamente ativa

- emprego

- escolaridade
- https://basedosdados.org/dataset/218ae306-29ac-4a83-836d-95bfdb9683fe?table=708098f3-aa55-41d3-9390-f35fb87faa66
- 
- urbanização

IPB = renda + crescimento + população + emprego + urbanização

O resultado final poderia ser um ranking:

<img width="359" height="68" alt="image" src="https://github.com/user-attachments/assets/36f880c8-dbae-439a-9e2e-19e97d8fbaa9" />


Possível continuação
Com esse rank de cidades, verificar quais tem menor presença/uso de serviços financeiros

"Onde há população e potencial econômico, mas menor presença/uso de serviços financeiros?"
adicionando informações do sistema financeiro, usando dados públicos do Banco Central do Brasil

Possível continuação
Nível de Conectividade das cidades
Numero de dispositivos móveis x população - base de estudo FGV

## Integrantes

- Hermes Augusto
- Lúcio Franchi Cruz
- Vitor Paes
- Nathalia Miranda

## Tecnologias

-- Dê preferência para tecnologias gratuitas

- Python
- SQL
- Git/GitHub

## Estrutura do Projeto e Documentação Técnica

O projeto é dividido em camadas bem definidas de Engenharia de Dados (`raw` e `trusted`), carregando e padronizando os dados de diferentes fontes no BigQuery.

Para guias passo a passo de como rodar e testar, consulte nossas documentações na pasta `docs/`:
- [Guia de Execução Técnica (Pipeline & SQL)](docs/Guia_de_Execucao.md) ⚠️ *Obrigatório ler para baixar os dados manuais*
- [Plano de Implementação (Fases 0 a 4)](docs/Plano_de_Implementacao.md)
- [Guia de Bases e Desenho (Indicadores)](docs/IPB_Guia_de_Bases_e_Desenho.md)

## Status

🚧 Projeto em desenvolvimento.

Compartilhar com o usuário fabioversolatto
