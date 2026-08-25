# Guia de Coleta — IPB

Este documento contém o passo a passo para acessar cada fonte de dados do NÚCLEO do IPB.  
Inclui resultados de testes de conectividade feitos em `2026-08-22` e indica quais fontes podem ser coletadas via API e quais exigem download manual.

---

## 1. Resumo dos testes

| Fonte | Tipo | Status | Como coletar |
|---|---|---|---|
| IBGE — Localidades | API | ✅ Funciona | `GET` direto; retorna JSON com 5.570 municípios. |
| IBGE — SIDRA Censo 2022 | API | ✅ Funciona | `GET` com `localidades=N6[all]`; colchetes devem ser URL-encoded. |
| BCB — Pix por município | API | ✅ Funciona | `GET` no endpoint Olinda; exige `$filter=AnoMes eq YYYYMM`. |
| IBGE — PIB dos Municípios | XLSX | ⚠️ Download manual | Site do IBGE bloqueia requisições automatizadas; baixar pelo navegador. |
| Anatel — Banda Larga Fixa | CSV | ⚠️ Download manual | Arquivo já baixado; 5.571 registros no mês mais recente. |
| BCB — Estban | CSV | ⚠️ Download manual | Disponível no portal de dados abertos do BCB. |
| PNUD — IDHM | API | ✅ Funciona (Ipeadata) | Coletado via API do Ipeadata (`ADH_IDHM`), ano 2010. Atlas Brasil 2022 indisponível. |
| Base dos Dados | API/BigQuery | ✅ Disponível | Reservada para validação cruzada futura; não é fonte primária do pipeline. |
| Anatel — Banda Larga Móvel | CSV | ❌ Fora do escopo | Dados volumosos; baixo impacto esperado; não entra. |

---

## 2. Fontes via API

### 2.1 IBGE — Localidades (tabela-mestra)

**URL base**: `https://servicodados.ibge.gov.br/api/v1/localidades/municipios`

**Teste realizado**:

```bash
curl -s --max-time 15 "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
```

**Resultado**: `HTTP 200`, retorna array JSON com todos os municípios.

**Exemplo de retorno**:

```json
[
  {
    "id": 1100015,
    "nome": "Alta Floresta D'Oeste",
    "microrregiao": { ... },
    "regiao-imediata": { ... }
  }
]
```

**Observações**:
- O campo `id` já é o código IBGE de 7 dígitos.
- Útil para padronizar nomes de municípios e fazer joins.

---

### 2.2 IBGE — SIDRA (Censo 2022)

**URL base**: `https://servicodados.ibge.gov.br/api/v3/agregados/{id_agregado}/periodos/{ano}/variaveis/{id_variavel}?localidades=N6[all]`

**Agregado e variável testados**:
- Agregado: `9605` (População residente)
- Variável: `93` (População residente)
- Período: `2022`

**Teste realizado**:

```bash
curl -s --max-time 60 \
  "https://servicodados.ibge.gov.br/api/v3/agregados/9605/periodos/2022/variaveis/93?localidades=N6%5Ball%5D"
```

**Resultado**: `HTTP 200`, retornou **5.570 municípios**.

**Exemplo de retorno**:

```json
[
  {
    "id": "93",
    "variavel": "População residente",
    "unidade": "Pessoas",
    "resultados": [
      {
        "classificacoes": [...],
        "series": [
          {
            "localidade": {
              "id": "1100015",
              "nivel": {"id": "N6", "nome": "Município"},
              "nome": "Alta Floresta D'Oeste - RO"
            },
            "serie": {"2022": "21494"}
          }
        ]
      }
    ]
  }
]
```

**Observações importantes**:
- Os **colchetes** na URL (`N6[all]`) devem ser codificados como `%5B` e `%5D`. Sem isso a requisição falha.
- `N6[all]` retorna todos os municípios de uma só vez.
- Outras variáveis do Censo 2022 (rendimento, idade, internet, urbanização) usam agregados/variáveis diferentes, mas seguem o mesmo padrão de endpoint.

---

### 2.3 BCB — Pix por município

**URL base**: `https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/TransacoesPixPorMunicipio(DataBase=@DataBase)`

**Teste realizado**:

```bash
curl -s --max-time 60 \
  "https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/TransacoesPixPorMunicipio(DataBase=@DataBase)?\$format=json&@DataBase='202401'&\$filter=AnoMes%20eq%20202401"
```

**Resultado**: `HTTP 200`, retornou **5.569 registros** para jan/2024.

**Exemplo de retorno**:

```json
{
  "@odata.context": "...",
  "value": [
    {
      "AnoMes": 202401,
      "Municipio_Ibge": 3201803,
      "Municipio": "DIVINO DE SÃO LOURENÇO",
      "Estado_Ibge": 32,
      "Estado": "ESPÍRITO SANTO",
      "Sigla_Regiao": "SE",
      "Regiao": "SUDESTE",
      "VL_PagadorPF": 8053560.83,
      "QT_PagadorPF": 50326,
      "VL_PagadorPJ": 3248257.82,
      "QT_PagadorPJ": 3300,
      "VL_RecebedorPF": 7500024.69,
      "QT_RecebedorPF": 30653,
      "VL_RecebedorPJ": 2651048.12,
      "QT_RecebedorPJ": 10791,
      "QT_PES_PagadorPF": 2082,
      "QT_PES_PagadorPJ": 159,
      "QT_PES_RecebedorPF": 2048,
      "QT_PES_RecebedorPJ": 151
    }
  ]
}
```

**Observações importantes**:
- O parâmetro `@DataBase` é obrigatório, mas **não filtra** sozinho. Sem o `$filter`, a API retorna dados de vários meses misturados.
- Para obter apenas um mês, usar: `$filter=AnoMes eq YYYYMM`.
- A chave `Municipio_Ibge` é o código IBGE de 7 dígitos.
- Recomenda-se fazer loop pelos últimos 12–24 meses e agregar por município.

---

## 3. Fontes de download manual

### 3.1 IBGE — PIB dos Municípios

**URL de acesso**: [https://www.ibge.gov.br/estatisticas/economicas/contas-nacionais/9088-produto-interno-bruto-dos-municipios.html](https://www.ibge.gov.br/estatisticas/economicas/contas-nacionais/9088-produto-interno-bruto-dos-municipios.html)

**Status do teste**: `HTTP 403` ao tentar acessar via `curl`. O site bloqueia requisições automatizadas.

**Passo a passo**:
1. Acessar a URL acima em um navegador.
2. Localizar a seção de downloads (geralmente "Downloads" ou "Resultados").
3. Baixar o arquivo compactado da "Base de dados 2010–2023" (formato XLSX ou ZIP).
4. Extrair e identificar a planilha principal (geralmente `base_de_dados_2010_2023_xls.xlsx` ou similar).
5. Salvar o arquivo em `data/raw/ibge_pib_municipios/` para processamento posterior.

**Observações**:
- O arquivo contém séries anuais de 2010 a 2023.
- Colunas esperadas: código IBGE, nome do município, ano, PIB, PIB per capita, valor adicionado por setor.

---

### 3.2 Anatel — Banda Larga Fixa

**URL de acesso**: [https://www.gov.br/anatel/pt-br/dados/dados-abertos](https://www.gov.br/anatel/pt-br/dados/dados-abertos)

**Status do teste**: Página acessível (`HTTP 200`). Download direto depende do dataset específico.

**Passo a passo**:
1. Acessar a URL acima.
2. Navegar até o conjunto "Acessos - Banda Larga Fixa".
3. Baixar o CSV mais recente (mensal) de densidade de acessos por 100 habitantes.
4. Recomenda-se também consultar o painel: [https://informacoes.anatel.gov.br/paineis/acessos/banda-larga-fixa](https://informacoes.anatel.gov.br/paineis/acessos/banda-larga-fixa)
5. Salvar em `data/raw/anatel_banda_larga/`.

**URL alternativa do inventário** (funciona via `curl`):

```bash
curl -s --max-time 15 \
  "https://www.anatel.gov.br/dadosabertos/PDA/Bases_Publicadas/Inventario_de_Bases_de_Dados.csv"
```

Esse CSV lista todos os conjuntos de dados e links para o dados.gov.br.

**Observações**:
- O arquivo já validado possui a coluna `Código IBGE` preenchida para registros de nível `Municipio`.
- **Banda larga móvel está fora do escopo** (dados volumosos, baixo impacto esperado).

---

### 3.3 BCB — Estban (Estatísticas Bancárias por Município)

**URL de acesso**: [https://www.bcb.gov.br/estatisticas/estatisticabancariamunicipios](https://www.bcb.gov.br/estatisticas/estatisticabancariamunicipios)

**Portal de Dados Abertos**: [https://dadosabertos.bcb.gov.br](https://dadosabertos.bcb.gov.br)

**Status do teste**: Página acessível (`HTTP 200`), mas o conteúdo é carregado dinamicamente.

**Passo a passo**:
1. Acessar a URL `https://www.bcb.gov.br/estatisticas/estatisticabancariamunicipios`.
2. Localizar o link para download do CSV mensal ("Saldos Estban por município").
3. Baixar o arquivo mais recente.
4. Salvar em `data/raw/bcb_estban/`.

**Observações**:
- Esta é a fonte de maior risco de mudança de formato. Validar imediatamente ao começar a implementação.
- Colunas esperadas: código IBGE, mês/ano, agências, depósitos, operações de crédito.
- Plano B: se o Estban não estiver disponível, usar o cadastro de agências no Portal de Dados Abertos do BCB.

---

### 3.4 PNUD — IDHM (via Ipeadata)

**Fonte oficial**: Atlas Brasil / PNUD — indisponível no momento (`HTTP 500`).

**Fonte adotada**: Ipeadata (`http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='ADH_IDHM')`)

**Status do teste**:
- Atlas Brasil: `HTTP 500` (instável).
- UNDP: `HTTP 403` ao tentar via `curl` (bloqueio de bot).
- Ipeadata: `HTTP 200`, série `ADH_IDHM` disponível para 1991, 2000 e 2010.

**Passo a passo**:
1. O ingestor `src/ingestors/pnud_idhm.py` consome a API do Ipeadata.
2. Filtra automaticamente o ano 2010 (último Censo disponível na série).
3. Padroniza o código IBGE para 7 dígitos.
4. Salva em `data/raw/pnud_idhm/` e sobe para `raw_pnud_idhm`.

**Observações**:
- O IDHM utilizado é do **Censo 2010**. Ele é mantido como variável histórica de referência.
- O indicador principal do pilar E passa a ser a **escolaridade (% ensino médio+) do Censo 2022**, coletada via SIDRA Tabela 10061.
- A **Base dos Dados** está reservada para validação cruzada futura, não como fonte primária.

---

## 4. Checklist de validação por fonte

Antes de considerar uma fonte como "coletada", verificar:

- [ ] **IBGE Localidades**: 5.570 municípios, código IBGE de 7 dígitos presente.
- [ ] **SIDRA Censo 2022**: resposta HTTP 200, colchetes codificados, valores preenchidos.
- [ ] **BCB Pix**: `$filter` funcionando, retorno com código IBGE e campos de valor/quantidade.
- [ ] **PIB dos Municípios**: arquivo XLSX baixado e legível.
- [ ] **Anatel Banda Larga Fixa**: CSV baixado, com colunas de município/UF e densidade de acessos.
- [ ] **Estban**: CSV mensal baixado, com colunas de agências, depósitos e crédito.
- [x] **IDHM**: coletado via API Ipeadata (`ADH_IDHM`, ano 2010). Escolaridade 2022 (SIDRA) é o indicador principal do pilar E.

---

## 5. Problemas conhecidos e workarounds

| Problema | Fonte | Workaround |
|---|---|---|
| Colchetes na URL causam erro | SIDRA | Usar `N6%5Ball%5D` ao invés de `N6[all]`. |
| `@DataBase` não filtra o mês | BCB Pix | Sempre adicionar `$filter=AnoMes eq YYYYMM`. |
| Site bloqueia `curl`/bots | IBGE, UNDP | Fazer download manual pelo navegador. |
| Site fora do ar | Atlas Brasil | Tentar novamente mais tarde ou usar página do UNDP. |
| Município sem código IBGE | Anatel | Fuzzy matching controlado com a tabela-mestra do IBGE. |

---

## 6. Resultado da validação dos arquivos baixados

Validação realizada em `2026-08-23` sobre os arquivos presentes em `data/raw/`.

### 6.1 IBGE — PIB dos Municípios

- **Arquivo**: `data/raw/ibge_pib_municipios/PIB dos Municípios - base de dados 2010-2023.xlsx`
- **Status**: ✅ OK
- **Detalhes**:
  - 2 abas: `PIB dos Municípios` (dados) e `Notas`.
  - 43 colunas, incluindo `Produto Interno Bruto per capita` e `Valor adicionado bruto dos Serviços`.
  - Anos 2010 a 2023.
  - 5.570 municípios únicos.
  - Coluna `Código do Município` com 7 dígitos.

### 6.2 Anatel — Densidade de Banda Larga Fixa

- **Arquivo**: `data/raw/anatel_banda_larga/Densidade_Banda_Larga_Fixa.csv`
- **Status**: ✅ OK
- **Detalhes**:
  - Encoding UTF-8 BOM, delimitador `;`, separador decimal `,`.
  - Colunas: `Ano`, `Mês`, `UF`, `Município`, `Código IBGE`, `Densidade`, `Nível Geográfico Densidade`.
  - 5.571 registros no mês mais recente (2026-06).
  - Código IBGE preenchido para registros de nível `Municipio`.
  - **Banda larga móvel está fora do escopo**.

### 6.3 BCB — Estban

- **Arquivo**: `data/raw/bcb_estaban/202603_ESTBAN.CSV`
- **Status**: ✅ OK
- **Detalhes**:
  - Encoding `latin1`, delimitador `;`.
  - 7.972 linhas de dados (uma por instituição/município).
  - Coluna `CODMUN_IBGE` com código IBGE completo.
  - 2.915 municípios únicos — apenas municípios com presença bancária.
  - Muitos verbetes financeiros disponíveis (depósitos, crédito, agências processadas/esperadas).

### 6.4 PNUD — IDHM

- **Arquivo/Fonte**: API Ipeadata (`ADH_IDHM`)
- **Status**: ✅ OK (IDHM 2010)
- **Detalhes**:
  - 5.564 dos 5.571 municípios preenchidos.
  - Atlas Brasil 2022 indisponível (`HTTP 500`); UNDP bloqueia bots (`HTTP 403`).
  - IDHM 2010 mantido como variável histórica; escolaridade 2022 (SIDRA) é o indicador principal do pilar E.

> **Disclaimer de vintage**: o pipeline combina diferentes anos de referência por indisponibilidade de dados municipais atualizados. Ver `Dicionario_de_Dados.md` para detalhes completos.

---

## 7. Próximos passos de coleta

1. ✅ IDHM obtido via Ipeadata (2010) + escolaridade 2022 via SIDRA.
2. ✅ Ingestores de APIs implementados (IBGE Localidades, SIDRA, Pix, Ipeadata).
3. ✅ Ingestores de arquivos manuais via GCS implementados (PIB, Anatel, Estban).
4. Próximo: validação cruzada com Base dos Dados e início da EDA (Etapa 2).

---

*Documento atualizado após testes de conectividade (2026-08-22) e validação dos arquivos baixados (2026-08-23).*

