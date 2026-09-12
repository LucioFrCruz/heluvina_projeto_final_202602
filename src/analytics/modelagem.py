"""
Dataset de modelagem da Etapa 3 (ML).

Monta a base unica de modelagem a partir da trusted
(`trusted_municipios_eda.parquet`) e da analytics V3
(`analytics_ipb_v3_presenca_completa.parquet`), aplicando a selecao de
features travada em `referencias/DISCUSSAO_MODELOS_ETAPA3.md` (v2) e em
`docs/Plano_de_Implementacao_Etapa3_Modelagem.md` (secao 2).

Regras do dataset:
    - 19 features numericas (0% de nulos), listadas em `FEATURES_MODELO`;
    - alvos proxy derivados (`flag_tem_agencia`, `flag_tem_correspondente`),
      declarados como substitutos — o projeto nao possui rotulo de verdade;
    - colunas de indice (scores dos pilares, ipb, ranks, features derivadas
      da formula) NUNCA entram como feature; `ipb`/`rank` acompanham o
      dataset apenas como referencia de cruzamento;
    - chave unica `id_municipio` (7 digitos) e 5.570 municipios.

Tambem centraliza os utilitarios compartilhados pelos modelos: split
treino/teste estratificado (o "holdout": o modelo nunca ve o teste) e
padronizacao ajustada somente no treino (sem vazar a prova).
"""

from __future__ import annotations

import logging

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Seed unica da etapa (reprodutibilidade dos experimentos).
SEED = 42

# Numero oficial de municipios do projeto (Censo 2022).
N_MUNICIPIOS_ESPERADO = 5570

COLUNAS_IDENTIDADE = [
    "id_municipio",
    "nome_municipio",
    "sigla_uf",
    "nome_regiao",
    "estrato_populacional",
]

# Features oficiais de modelagem (19), por familia e vintage:
# demografia Censo 2022, PIB 2023, CEMPRE 2024, Pix 2023/24,
# Anatel/Estban 2026. Ver discussao Etapa 3, secao 3.
FEATURES_MODELO = [
    # Demografia (Censo 2022)
    "populacao_total",
    "populacao_18_35_pct",
    "populacao_urbana_pct",
    "rendimento_domiciliar_per_capita",
    "escolaridade_ensino_medio_pct",
    # Economia (PIB 2023)
    "pib_per_capita",
    # Atividade empresarial (CEMPRE 2024)
    "empregos_formais_por_1000_hab",
    "unidades_locais_por_1000_hab",
    "unidades_alojamento_alimentacao_por_1000_hab",
    # Digital (Pix 2023/24, Anatel 2026)
    "pix_per_capita_12m",
    "pix_pj_pct",
    "pix_ticket_medio",
    "banda_larga_fixa_por_100_hab",
    # Presenca bancaria (Estban/BCB 2026)
    "quantidade_agencias",
    "agencias_por_100k_hab",
    "quantidade_correspondentes",
    "correspondentes_por_100k_hab",
    "depositos_per_capita",
    "credito_per_capita",
]

# Alvos proxy (rotulos substitutos — declarado no relatorio da etapa).
ALVOS = ["flag_tem_agencia", "flag_tem_correspondente"]

# Referencia do indice para cruzamento (nao sao feature).
COLUNAS_REFERENCIA_IPB = ["ipb", "rank"]

# Selecao explicita por fonte (nada de "dropar": so entra o que foi
# aprovado na discussao).
_COLUNAS_TRUSTED = COLUNAS_IDENTIDADE + [
    "populacao_total",
    "populacao_18_35_pct",
    "populacao_urbana_pct",
    "rendimento_domiciliar_per_capita",
    "escolaridade_ensino_medio_pct",
    "pib_per_capita",
    "pix_per_capita_12m",
    "pix_pj_pct",
    "pix_ticket_medio",
    "banda_larga_fixa_por_100_hab",
    "quantidade_agencias",
    "agencias_por_100k_hab",
    "depositos_per_capita",
    "credito_per_capita",
]

_COLUNAS_V3 = ["id_municipio"] + COLUNAS_REFERENCIA_IPB + [
    "empregos_formais_por_1000_hab",
    "unidades_locais_por_1000_hab",
    "unidades_alojamento_alimentacao_por_1000_hab",
    "quantidade_correspondentes",
    "correspondentes_por_100k_hab",
]


def montar_dataset_modelagem(
    df_trusted: pd.DataFrame,
    df_v3: pd.DataFrame,
    n_esperado: int = N_MUNICIPIOS_ESPERADO,
) -> pd.DataFrame:
    """
    Monta o dataset unico de modelagem da Etapa 3.

    Args:
        df_trusted: Base municipal (EDA) com demografia, economia,
            digital e presenca bancaria.
        df_v3: Tabela `analytics_ipb_v3_presenca_completa` (CEMPRE,
            correspondentes e referencia `ipb`/`rank`).
        n_esperado: Numero de municipios esperado apos o merge
            (default: 5.570; nos testes, o tamanho do brinquedo).

    Returns:
        DataFrame com identidade, 19 features, 2 alvos proxy e a
        referencia `ipb`/`rank`, sem nulos.

    Raises:
        ValueError: Se faltar coluna obrigatoria, houver `id_municipio`
            duplicado, o merge nao bater o tamanho esperado ou sobrar
            nulo em feature/alvo/identidade.
    """
    faltantes_t = set(_COLUNAS_TRUSTED) - set(df_trusted.columns)
    if faltantes_t:
        raise ValueError(
            f"df_trusted sem as colunas obrigatorias: {sorted(faltantes_t)}"
        )
    faltantes_v3 = set(_COLUNAS_V3) - set(df_v3.columns)
    if faltantes_v3:
        raise ValueError(f"df_v3 sem as colunas obrigatorias: {sorted(faltantes_v3)}")

    trusted = df_trusted.copy()
    v3 = df_v3.copy()
    # Normaliza a chave de join (int vs. string de 7 digitos): sem isso
    # o merge falha em silencio e a base some, como ja ocorreu no 07.
    for df in (trusted, v3):
        df["id_municipio"] = df["id_municipio"].astype(str).str.zfill(7)
    if trusted["id_municipio"].duplicated().any():
        raise ValueError("df_trusted com id_municipio duplicado")
    if v3["id_municipio"].duplicated().any():
        raise ValueError("df_v3 com id_municipio duplicado")

    base = trusted[_COLUNAS_TRUSTED].merge(
        v3[_COLUNAS_V3], on="id_municipio", how="inner", validate="one_to_one"
    )
    if len(base) != n_esperado:
        raise ValueError(
            f"merge resultou em {len(base)} municipios; esperado {n_esperado}"
        )

    base["flag_tem_agencia"] = (base["quantidade_agencias"] > 0).astype(int)
    base["flag_tem_correspondente"] = (
        base["quantidade_correspondentes"] > 0
    ).astype(int)

    obrigatorias = COLUNAS_IDENTIDADE + FEATURES_MODELO + ALVOS
    nulos = base[obrigatorias].isna().sum()
    cols_com_nulo = nulos[nulos > 0]
    if not cols_com_nulo.empty:
        raise ValueError(f"colunas com nulos apos o merge: {cols_com_nulo.to_dict()}")

    logger.info(
        "Dataset de modelagem: %d municipios, %d features, alvos %s",
        len(base),
        len(FEATURES_MODELO),
        ALVOS,
    )
    return base[obrigatorias + COLUNAS_REFERENCIA_IPB]


def dividir_treino_teste(
    df: pd.DataFrame,
    alvo: str,
    test_size: float = 0.2,
    seed: int = SEED,
    estratificar: bool = True,
):
    """
    Separa treino/teste (holdout) para um alvo do dataset.

    O teste fica de fora do treinamento ate a avaliacao final: e a
    "prova" que diz se o modelo aprendeu ou decorou. `estratificar`
    mantem a proporcao das classes nos dois lados (importante com
    desbalanceamento leve, como o 52/48 de `flag_tem_agencia`).

    Args:
        df: Dataset de modelagem (`montar_dataset_modelagem`).
        alvo: Nome da coluna-alvo (deve existir, sem nulos, com ao
            menos 2 classes quando `estratificar=True`).
        test_size: Fracao de teste (padrao 0.2 = 20%).
        seed: Seed do sorteio (reprodutibilidade).
        estratificar: Se True (padrao), split estratificado por classe.
            Use False para alvos continuos (regressao).

    Returns:
        Tupla (X_treino, X_teste, y_treino, y_teste), com X nas
        `FEATURES_MODELO`.
    """
    if alvo not in df.columns:
        raise ValueError(f"alvo nao encontrado no dataset: {alvo}")
    y = df[alvo]
    if y.isna().any():
        raise ValueError(f"alvo com valores nulos: {alvo}")
    if estratificar and y.nunique() < 2:
        raise ValueError(f"alvo precisa ter ao menos 2 classes: {alvo}")

    X = df[FEATURES_MODELO]
    return train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=seed,
        stratify=y if estratificar else None,
    )


def padronizar(
    X_treino: pd.DataFrame, X_teste: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, StandardScaler]:
    """
    Padroniza features (media 0, desvio 1) com `StandardScaler` ajustado
    SOMENTE no treino — o teste e transformado depois, sem vazar a prova.

    Args:
        X_treino: Features de treino.
        X_teste: Features de teste.

    Returns:
        (X_treino_padronizado, X_teste_padronizado, scaler). O scaler
        fica disponivel para padronizar dados novos na inferencia.
    """
    scaler = StandardScaler()
    X_treino_pad = pd.DataFrame(
        scaler.fit_transform(X_treino),
        columns=X_treino.columns,
        index=X_treino.index,
    )
    X_teste_pad = pd.DataFrame(
        scaler.transform(X_teste), columns=X_teste.columns, index=X_teste.index
    )
    return X_treino_pad, X_teste_pad, scaler
