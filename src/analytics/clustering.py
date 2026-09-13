"""
Clusterizacao de municipios (Etapa 3): K-Means e GMM.

Descobre os arquétipos de municipios a partir das FEATURES (nunca de
rotulo manual): roda K-Means e GMM para uma faixa de K, compara a
qualidade dos agrupamentos (silhouette, Davies-Bouldin, Calinski-Harabasz
e BIC) e perfila cada cluster (medias por variavel) para sustentar a
narrativa de negocio. Ver `referencias/DISCUSSAO_MODELOS_ETAPA3.md` (v2)
e o plano da Etapa 3 (secao 4.2).

Padronizacao (media 0, desvio 1) e obrigatoria para ambos os algoritmos
e feita aqui de forma isolada: a clusterizacao e descritiva e usa todo
o dataset (nao ha holdout). O scaler e retornado para reutilizacao na
inferencia (classificar municipio novo).
"""

from __future__ import annotations

import logging
import time

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.preprocessing import StandardScaler

from src.analytics.modelagem import SEED

logger = logging.getLogger(__name__)

# Contrato da tabela de avaliacao de K (uma linha por K testado).
COLUNAS_AVALIACAO_K = [
    "k",
    "silhouette_kmeans",
    "silhouette_gmm",
    "davies_bouldin_kmeans",
    "calinski_harabasz_kmeans",
    "bic_gmm",
    "tempo_seg_kmeans",
    "tempo_seg_gmm",
]

# Nome sugerido quando nenhuma regra de perfil dispara.
NOME_PADRAO_PERFIL = "Perfil intermediario"


def _X_padronizado(
    df: pd.DataFrame, features: list[str]
) -> tuple[pd.DataFrame, StandardScaler]:
    """Valida as features e retorna X padronizado (com o scaler)."""
    faltantes = set(features) - set(df.columns)
    if faltantes:
        raise ValueError(f"features ausentes no dataset: {sorted(faltantes)}")
    scaler = StandardScaler()
    X_pad = pd.DataFrame(
        scaler.fit_transform(df[features]),
        columns=features,
        index=df.index,
    )
    return X_pad, scaler


def avaliar_k(
    df: pd.DataFrame,
    features: list[str],
    ks=range(3, 11),
    seed: int = SEED,
    n_init: int = 10,
) -> pd.DataFrame:
    """
    Compara K-Means e GMM para cada K candidato (o "grid" da escolha do
    numero de arquetipos).

    Para cada K: ajusta os dois modelos nos mesmos dados padronizados e
    mede a qualidade dos agrupamentos — silhouette (quanto maior melhor,
    escala -1 a 1), Davies-Bouldin (menor melhor), Calinski-Harabasz
    (maior melhor) para o K-Means; BIC (menor melhor) e silhouette para
    o GMM. Tambem registra o tempo de treino (a rubrica pede comparacao
    de custo computacional).

    Args:
        df: Dataset de modelagem.
        features: Colunas usadas no agrupamento (ja validadas).
        ks: Iterable com os K candidatos (todos >= 2).
        seed: Seed dos modelos (reprodutibilidade).
        n_init: Reinicios do K-Means (estabilidade entre versoes do sklearn).

    Returns:
        DataFrame com `COLUNAS_AVALIACAO_K`, uma linha por K.

    Raises:
        ValueError: Se `ks` estiver vazio ou tiver algum K < 2, ou se
            faltar feature no dataset.
    """
    ks = list(ks)
    if not ks or min(ks) < 2:
        raise ValueError("ks precisa conter ao menos um k >= 2")
    X_pad, _ = _X_padronizado(df, features)

    linhas = []
    for k in ks:
        t0 = time.perf_counter()
        km = KMeans(n_clusters=k, n_init=n_init, random_state=seed)
        labels_km = km.fit_predict(X_pad)
        t_km = time.perf_counter() - t0

        t0 = time.perf_counter()
        gmm = GaussianMixture(n_components=k, random_state=seed)
        labels_gmm = gmm.fit_predict(X_pad)
        t_gmm = time.perf_counter() - t0

        linhas.append(
            {
                "k": k,
                "silhouette_kmeans": silhouette_score(X_pad, labels_km),
                "silhouette_gmm": silhouette_score(X_pad, labels_gmm),
                "davies_bouldin_kmeans": davies_bouldin_score(X_pad, labels_km),
                "calinski_harabasz_kmeans": calinski_harabasz_score(
                    X_pad, labels_km
                ),
                "bic_gmm": gmm.bic(X_pad),
                "tempo_seg_kmeans": round(t_km, 3),
                "tempo_seg_gmm": round(t_gmm, 3),
            }
        )

    resultado = pd.DataFrame(linhas, columns=COLUNAS_AVALIACAO_K)
    logger.info("Avaliacao de K concluida: %s", list(ks))
    return resultado


def ajustar_kmeans(
    df: pd.DataFrame,
    features: list[str],
    k: int,
    seed: int = SEED,
    n_init: int = 10,
) -> tuple[KMeans, pd.Series, StandardScaler]:
    """
    Ajusta o K-Means final com K escolhido (nos experimentos de
    `avaliar_k` + legibilidade de negocio).

    Returns:
        (modelo, labels, scaler). `labels` e uma Series indexada como
        `df` (nome `cluster_kmeans`); o scaler padroniza dados novos na
        inferencia.
    """
    if k < 2:
        raise ValueError(f"k precisa ser >= 2; recebido {k}")
    X_pad, scaler = _X_padronizado(df, features)
    modelo = KMeans(n_clusters=k, n_init=n_init, random_state=seed)
    labels = pd.Series(
        modelo.fit_predict(X_pad), index=df.index, name="cluster_kmeans"
    )
    logger.info("K-Means ajustado com k=%d", k)
    return modelo, labels, scaler


def ajustar_gmm(
    df: pd.DataFrame,
    features: list[str],
    k: int,
    seed: int = SEED,
    reg_covar: float = 1e-6,
) -> tuple[GaussianMixture, pd.Series, pd.DataFrame, StandardScaler]:
    """
    Ajusta o GMM final com K escolhido. Diferente do K-Means, entrega a
    probabilidade de pertencimento de cada municipio a cada cluster
    ("municipio X e 83% arquetipo A, 17% B").

    Args:
        reg_covar: Regularizacao da covariancia (sobe se o GMM nao
            convergir — fallback documentado no plano, secao 8).

    Returns:
        (modelo, labels, probs, scaler). `labels` (nome `cluster_gmm`) e
        `probs` (colunas `prob_cluster_0`...) sao indexadas como `df`;
        as probabilidades somam 1 por municipio.
    """
    if k < 2:
        raise ValueError(f"k precisa ser >= 2; recebido {k}")
    X_pad, scaler = _X_padronizado(df, features)
    modelo = GaussianMixture(
        n_components=k, random_state=seed, reg_covar=reg_covar
    )
    labels = pd.Series(
        modelo.fit_predict(X_pad), index=df.index, name="cluster_gmm"
    )
    probs = pd.DataFrame(
        modelo.predict_proba(X_pad),
        columns=[f"prob_cluster_{i}" for i in range(k)],
        index=df.index,
    )
    logger.info("GMM ajustado com k=%d", k)
    return modelo, labels, probs, scaler


def perfis_clusters(
    df: pd.DataFrame, features: list[str], labels: pd.Series
) -> pd.DataFrame:
    """
    Retrato de cada cluster: tamanho, percentual do total e media/desvio
    das variaveis. E a tabela que sustenta a narrativa do arquetipo —
    cada cluster precisa se explicar em uma frase a partir daqui.

    Returns:
        DataFrame indexado pelo cluster, com `n_municipios`,
        `pct_municipios`, `<feature>_media` e `<feature>_desvio`.
    """
    faltantes = set(features) - set(df.columns)
    if faltantes:
        raise ValueError(f"features ausentes no dataset: {sorted(faltantes)}")
    if len(labels) != len(df):
        raise ValueError("labels com tamanho diferente do dataset")

    base = df[features].copy()
    base["cluster"] = np.asarray(labels)
    grupo = base.groupby("cluster")
    tamanho = grupo.size().rename("n_municipios")
    pct = (grupo.size() / len(base) * 100).rename("pct_municipios")

    return pd.concat(
        [
            tamanho,
            pct,
            grupo[features].mean().add_suffix("_media"),
            grupo[features].std().add_suffix("_desvio"),
        ],
        axis=1,
    )


# Regras de nomeacao, SEMPRE relativas ao perfil medio nacional (media
# ponderada pelos tamanhos dos clusters, calculada dentro da funcao) —
# nunca a valores absolutos chutados. A ordem importa: a primeira regra
# que dispara define o nome (de caracteristica de negocio forte para
# infraestrutura bancaria).
_LIMIAR_FORTE = 1.5  # media do cluster >= 1,5x a media nacional
_LIMIAR_AUSENTE = 0.2  # media do cluster <= 0,2x a media nacional
_REGRAS_NOME: list[tuple[str, str, str, float]] = [
    (
        "unidades_alojamento_alimentacao_por_1000_hab",
        "Turismo",
        "acima",
        _LIMIAR_FORTE,
    ),
    ("pix_pj_pct", "Polo empresarial", "acima", _LIMIAR_FORTE),
    ("empregos_formais_por_1000_hab", "Polo formalizado", "acima", _LIMIAR_FORTE),
    ("agencias_por_100k_hab", "Sem rede bancaria", "abaixo", _LIMIAR_AUSENTE),
    (
        "correspondentes_por_100k_hab",
        "Coberta por correspondentes",
        "acima",
        _LIMIAR_FORTE,
    ),
]

# Desambiguacao de nomes repetidos (sempre dados): quando dois ou mais
# clusters recebem o mesmo nome, uma variavel discriminadora separa o
# grupo — os de valor acima ganham um sufixo, os de baixo outro. Sem
# isso, nomes iguais impedem a leitura ("qual dos dois Turismo?").
_DESAMBIGUACAO: dict[str, tuple[str, str, str]] = {
    # nome base: (variavel discriminadora, sufixo acima, sufixo abaixo)
    "Turismo": ("agencias_por_100k_hab", "com rede", "sem banco"),
    "Sem rede bancaria": ("pib_per_capita", "renda alta", "renda baixa"),
    "Perfil intermediario": ("pix_pj_pct", "empresarial", "tradicional"),
}


def sugerir_nomes_perfis(perfis: pd.DataFrame) -> dict[int, str]:
    """
    Sugere um nome para cada cluster com base no SEU PERFIL (dados, nao
    rotulo manual): cada regra compara a media de uma variavel no cluster
    com a media nacional ponderada pelo tamanho dos clusters. A sugestao
    vai para validacao do grupo — e ponto de partida da narrativa, nao
    verdade final.

    Args:
        perfis: Saida de `perfis_clusters` (precisa das colunas
            `n_municipios` e `<variavel>_media` das variaveis de regra).

    Returns:
        Dicionario {cluster: nome sugerido}. Clusters sem regra que
        dispare recebem `NOME_PADRAO_PERFIL`.

    Raises:
        ValueError: Se faltar coluna obrigatoria em `perfis`.
    """
    obrigatorias = ["n_municipios"] + [
        f"{variavel}_media" for variavel, _, _, _ in _REGRAS_NOME
    ]
    faltantes = [c for c in obrigatorias if c not in perfis.columns]
    if faltantes:
        raise ValueError(f"perfis sem as colunas obrigatorias: {faltantes}")

    pesos = perfis["n_municipios"].to_numpy(dtype=float)

    def media_nacional(coluna: str) -> float:
        return float(np.average(perfis[coluna].to_numpy(), weights=pesos))

    nomes: dict[int, str] = {}
    for cluster, linha in perfis.iterrows():
        nome = NOME_PADRAO_PERFIL
        for variavel, rotulo, direcao, limiar in _REGRAS_NOME:
            referencia = media_nacional(f"{variavel}_media")
            if referencia <= 0:
                continue
            media = linha[f"{variavel}_media"]
            dispara = (
                media >= limiar * referencia
                if direcao == "acima"
                else media <= limiar * referencia
            )
            if dispara:
                nome = rotulo
                break
        nomes[int(cluster)] = nome

    # Desambiguacao: nomes repetidos ganham sufixo discriminador (dados).
    por_nome: dict[str, list[int]] = {}
    for cluster, nome in nomes.items():
        por_nome.setdefault(nome, []).append(cluster)
    for nome, grupo_clusters in por_nome.items():
        if len(grupo_clusters) < 2:
            continue
        regra = _DESAMBIGUACAO.get(nome)
        coluna = f"{regra[0]}_media" if regra else None
        if regra is None or coluna not in perfis.columns:
            # Sem discriminador conhecido: numero do grupo mantem unicidade.
            for c in grupo_clusters:
                nomes[c] = f"{nome} (grupo {c})"
            continue
        ordenado = sorted(
            grupo_clusters, key=lambda c: perfis.loc[c, coluna]
        )
        meio = len(ordenado) // 2
        for c in ordenado[:meio]:  # menores valores do discriminador
            nomes[c] = f"{nome} - {regra[2]}"
        for c in ordenado[meio:]:  # maiores valores
            nomes[c] = f"{nome} - {regra[1]}"

    # Garantia final: nomes unicos por construcao.
    vistos: set[str] = set()
    for c in sorted(nomes):
        if nomes[c] in vistos:
            nomes[c] = f"{nomes[c]} (grupo {c})"
        vistos.add(nomes[c])
    return nomes
