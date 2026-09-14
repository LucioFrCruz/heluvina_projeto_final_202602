"""
Gera as figuras da apresentacao final (deck reveal.js) em docs/assets/img/.

Le os parquets locais em data/processed/ — 100% offline, sem BigQuery — da
camada analytics (IPB V3), da modelagem da Etapa 3 (arquetipos) e da trusted
municipal enriquecida (renda, Pix, banda larga, agencias), e produz quatro
figuras PNG com fundo branco, dpi 160 e titulos que ja carregam a leitura
do grafico (o professor exige que toda figura responda "o que aprendemos
com isso?").

Figuras geradas:
    1. fig_eda_dispersao.png     — dispersao PIB pc (log) x IPB V3 por estrato
    2. fig_top15_ipb.png         — barras horizontais do Top 15 em IPB V3
    3. fig_ipb_por_estrato.png   — boxplot do IPB V3 por estrato populacional
    4. fig_arquetipos.png        — painel: n por arquetipo + heatmap das
                                   medias padronizadas das features por cluster

Inputs (data/processed/):
    - analytics_ipb_v3_presenca_completa.parquet (ipb V3, rank, estrato,
      correspondentes, CEMPRE)
    - modelagem_resultados.parquet (cluster_kmeans, arquetipo)
    - trusted_municipios_eda.parquet (pib_per_capita, pix, banda larga,
      agencias, escolaridade)

Outputs:
    - docs/assets/img/fig_eda_dispersao.png
    - docs/assets/img/fig_top15_ipb.png
    - docs/assets/img/fig_ipb_por_estrato.png
    - docs/assets/img/fig_arquetipos.png
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_DATA_DIR = Path("data/processed")
SAIDA_DIR = Path("docs/assets/img")
DPI = 160

QUANTIDADE_ESPERADA = 5_570

# Paleta dos arquetipos — a mesma do mapa (docs/mapa.html, CORES_ARQUETIPOS),
# para o deck e o site contarem a mesma historia de cores.
CORES_ARQUETIPOS = {
    "Turismo - com rede": "#b07aa1",
    "Sem rede bancaria - renda baixa": "#e15759",
    "Perfil intermediario - empresarial": "#4e79a7",
    "Perfil intermediario - tradicional": "#f28e2b",
    "Turismo - sem banco": "#76b7b2",
    "Sem rede bancaria - renda alta": "#59a14f",
}

# Cores dos estratos (subconjunto da mesma familia, amigavel a daltônicos).
CORES_ESTRATO = {
    "pequena": "#4e79a7",
    "media": "#f28e2b",
    "grande": "#59a14f",
}
ROTULO_ESTRATO = {
    "pequena": "Pequena (<50 mil)",
    "media": "Média (50–500 mil)",
    "grande": "Grande (>500 mil)",
}
ORDEM_ESTRATO = ["pequena", "media", "grande"]

# Features do heatmap de perfil (chave -> rótulo pt-BR). Sao as variaveis que
# contam a historia de cada arquétipo, alinhadas a docs/Arquetipos_Municipais.md.
FEATURES_HEATMAP = {
    "populacao_total": "População total",
    "pib_per_capita": "PIB per capita",
    "rendimento_domiciliar_per_capita": "Renda dom. per capita",
    "pix_per_capita_12m": "Pix per capita",
    "pix_pj_pct": "Pix PJ (%)",
    "banda_larga_fixa_por_100_hab": "Banda larga /100 hab",
    "escolaridade_ensino_medio_pct": "Ensino médio (%)",
    "empregos_formais_por_1000_hab": "Empregos formais /1000",
    "unidades_alojamento_alimentacao_por_1000_hab": "Alojamento aliment. /1000",
    "agencias_por_100k_hab": "Agências /100 mil",
    "correspondentes_por_100k_hab": "Correspondentes /100 mil",
}

# Nomes de exibição dos arquétipos (acentos corrigidos; o parquet usa ASCII).
ROTULO_ARQUETIPO = {
    "Turismo - com rede": "Turismo - com rede",
    "Sem rede bancaria - renda baixa": "Sem rede bancária - renda baixa",
    "Perfil intermediario - empresarial": "Perfil intermediário - empresarial",
    "Perfil intermediario - tradicional": "Perfil intermediário - tradicional",
    "Turismo - sem banco": "Turismo - sem banco",
    "Sem rede bancaria - renda alta": "Sem rede bancária - renda alta",
}


def carregar_base() -> pd.DataFrame:
    """Consolida V3 + arquetipos + features da trusted em uma base por município."""
    logger.info("Lendo parquets de data/processed/...")
    v3 = pd.read_parquet(PROCESSED_DATA_DIR / "analytics_ipb_v3_presenca_completa.parquet")
    resultados = pd.read_parquet(PROCESSED_DATA_DIR / "modelagem_resultados.parquet")
    eda = pd.read_parquet(PROCESSED_DATA_DIR / "trusted_municipios_eda.parquet")

    for nome, df in [("v3", v3), ("resultados", resultados), ("trusted", eda)]:
        df["id_municipio"] = df["id_municipio"].astype(str).str.zfill(7)
        logger.info("  %s: %d linhas, %d colunas", nome, *df.shape)

    base = v3.merge(
        resultados[["id_municipio", "cluster_kmeans", "arquetipo"]],
        on="id_municipio",
        how="left",
        validate="one_to_one",
    ).merge(
        eda[
            [
                "id_municipio",
                "populacao_total",
                "pib_per_capita",
                "rendimento_domiciliar_per_capita",
                "pix_per_capita_12m",
                "pix_pj_pct",
                "banda_larga_fixa_por_100_hab",
                "escolaridade_ensino_medio_pct",
                "agencias_por_100k_hab",
            ]
        ],
        on="id_municipio",
        how="left",
        validate="one_to_one",
    )
    if len(base) != QUANTIDADE_ESPERADA:
        raise ValueError(f"esperado {QUANTIDADE_ESPERADA} linhas, encontrado {len(base)}")
    if base["arquetipo"].isna().any():
        raise ValueError("arquetipo nulo após o merge com modelagem_resultados")
    return base


def fig_eda_dispersao(base: pd.DataFrame) -> Path:
    """Dispersão PIB per capita (log) × IPB V3, colorida por estrato."""
    fig, ax = plt.subplots(figsize=(10, 6.2))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    for estrato in ORDEM_ESTRATO:
        fatia = base[base["estrato_populacional"] == estrato]
        ax.scatter(
            fatia["pib_per_capita"],
            fatia["ipb"],
            s=14,
            alpha=0.55,
            linewidths=0,
            color=CORES_ESTRATO[estrato],
            label=ROTULO_ESTRATO[estrato],
        )

    ax.set_xscale("log")
    ax.set_xlabel("PIB per capita (R$, escala log)", fontsize=11)
    ax.set_ylabel("IPB V3 (0–100)", fontsize=11)
    ax.set_title(
        "Quanto maior o PIB per capita, maior tende a ser o IPB:\n"
        "renda e digital dominam, a concorrência ajusta o recorte",
        fontsize=13,
        loc="left",
        fontweight="bold",
    )
    ax.legend(frameon=False, fontsize=10, loc="lower right")
    ax.grid(axis="y", color="#e2e7ec", linewidth=0.8)
    ax.set_axisbelow(True)
    sns.despine(ax=ax)

    caminho = SAIDA_DIR / "fig_eda_dispersao.png"
    fig.tight_layout()
    fig.savefig(caminho, dpi=DPI, facecolor="white")
    plt.close(fig)
    logger.info("  salvo %s", caminho)
    return caminho


def fig_top15_ipb(base: pd.DataFrame) -> Path:
    """Barras horizontais do Top 15 em IPB V3, com nome e UF."""
    top15 = base.nsmallest(15, "rank").copy()
    top15["rotulo"] = top15["nome_municipio"] + " (" + top15["sigla_uf"] + ")"
    top15 = top15.sort_values("rank", ascending=True)

    fig, ax = plt.subplots(figsize=(10, 6.2))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    cores = [CORES_ESTRATO[e] for e in top15["estrato_populacional"]]
    barras = ax.barh(
        top15["rotulo"],
        top15["ipb"],
        color=cores,
        height=0.68,
    )
    ax.invert_yaxis()
    for barra, valor in zip(barras, top15["ipb"]):
        ax.text(
            barra.get_width() + 0.6,
            barra.get_y() + barra.get_height() / 2,
            f"{valor:.1f}".replace(".", ","),
            va="center",
            fontsize=10,
            color="#24303b",
        )

    ax.set_xlim(0, 80)
    ax.set_xlabel("IPB V3 (0–100)", fontsize=11)
    ax.set_title(
        "Top 15 do IPB V3: litoral turístico, renda alta de entorno\n"
        "metropolitano e capitais planejadas",
        fontsize=13,
        loc="left",
        fontweight="bold",
    )
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=CORES_ESTRATO[e]) for e in ORDEM_ESTRATO
    ]
    ax.legend(
        handles,
        [ROTULO_ESTRATO[e] for e in ORDEM_ESTRATO],
        frameon=False,
        fontsize=10,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.13),
        ncol=3,
    )
    ax.grid(axis="x", color="#e2e7ec", linewidth=0.8)
    ax.set_axisbelow(True)
    sns.despine(ax=ax)

    caminho = SAIDA_DIR / "fig_top15_ipb.png"
    fig.tight_layout()
    fig.savefig(caminho, dpi=DPI, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    logger.info("  salvo %s", caminho)
    return caminho


def fig_ipb_por_estrato(base: pd.DataFrame) -> Path:
    """Boxplot do IPB V3 por estrato populacional."""
    ordem_rotulos = [ROTULO_ESTRATO[e] for e in ORDEM_ESTRATO]
    base = base.copy()
    base["estrato_rotulo"] = base["estrato_populacional"].map(ROTULO_ESTRATO)

    fig, ax = plt.subplots(figsize=(8.6, 6.2))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    sns.boxplot(
        data=base,
        x="estrato_rotulo",
        y="ipb",
        order=ordem_rotulos,
        palette=[CORES_ESTRATO[e] for e in ORDEM_ESTRATO],
        width=0.55,
        showcaps=True,
        boxprops={"facecolor": "white", "edgecolor": "#24303b", "linewidth": 1.4},
        medianprops={"color": "#16637a", "linewidth": 2},
        whiskerprops={"color": "#24303b"},
        flierprops={"marker": "o", "markerfacecolor": "#9aa5ae", "markeredgecolor": "none", "markersize": 3, "alpha": 0.5},
        ax=ax,
    )

    n_pequena = int((base["estrato_populacional"] == "pequena").sum())
    ax.set_xlabel("Estrato populacional", fontsize=11)
    ax.set_ylabel("IPB V3 (0–100)", fontsize=11)
    ax.set_title(
        f"Cidades grandes lideram o IPB; as {n_pequena:,} cidades pequenas\n"
        "disputam o ranking dentro do próprio estrato".replace(",", "."),
        fontsize=13,
        loc="left",
        fontweight="bold",
    )
    ax.grid(axis="y", color="#e2e7ec", linewidth=0.8)
    ax.set_axisbelow(True)
    sns.despine(ax=ax)

    caminho = SAIDA_DIR / "fig_ipb_por_estrato.png"
    fig.tight_layout()
    fig.savefig(caminho, dpi=DPI, facecolor="white")
    plt.close(fig)
    logger.info("  salvo %s", caminho)
    return caminho


def fig_arquetipos(base: pd.DataFrame) -> Path:
    """
    Painel com a quantidade de municípios por arquétipo e o heatmap das
    médias padronizadas (z-score) das principais features por cluster.
    """
    ordem_clusters = sorted(base["cluster_kmeans"].unique())
    # Um arquétipo por cluster (a regra de nome é 1:1 com o cluster).
    por_cluster = (
        base.groupby("cluster_kmeans")["arquetipo"]
        .agg(arquetipo="first", n="count")
        .reindex(ordem_clusters)
    )
    rotulos_clusters = [
        f"{ROTULO_ARQUETIPO[a]}\n(n={n:,})".replace(",", ".")
        for a, n in zip(por_cluster["arquetipo"], por_cluster["n"])
    ]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.5, 6.8), gridspec_kw={"width_ratios": [1, 1.35]})
    fig.patch.set_facecolor("white")

    # (a) Quantidade de municípios por arquétipo.
    nomes = [ROTULO_ARQUETIPO[a] for a in por_cluster["arquetipo"]]
    cores = [CORES_ARQUETIPOS[a] for a in por_cluster["arquetipo"]]
    barras = ax1.barh(nomes, por_cluster["n"], color=cores, height=0.66)
    ax1.invert_yaxis()
    for barra, valor in zip(barras, por_cluster["n"]):
        ax1.text(
            barra.get_width() + 12,
            barra.get_y() + barra.get_height() / 2,
            f"{valor:,}".replace(",", "."),
            va="center",
            fontsize=10,
            color="#24303b",
        )
    ax1.set_xlim(0, 1450)
    ax1.set_xlabel("Municípios", fontsize=11)
    ax1.set_title(
        "O interior pobre sem rede é o maior arquétipo;\n"
        "o turismo rico sem banco é o menor e o achado",
        fontsize=12.5,
        loc="left",
        fontweight="bold",
    )
    ax1.grid(axis="x", color="#e2e7ec", linewidth=0.8)
    ax1.set_axisbelow(True)
    sns.despine(ax=ax1)

    # (b) Heatmap das médias padronizadas das features por cluster.
    faltantes = [f for f in FEATURES_HEATMAP if f not in base.columns]
    if faltantes:
        raise ValueError(f"features ausentes na base: {faltantes}")
    features = list(FEATURES_HEATMAP)
    zscores = (base[features] - base[features].mean()) / base[features].std()
    zscores["cluster_kmeans"] = base["cluster_kmeans"]
    perfil = zscores.groupby("cluster_kmeans")[features].mean().reindex(ordem_clusters)

    sns.heatmap(
        perfil.T,
        annot=True,
        fmt=".1f",
        cmap="RdBu_r",
        center=0,
        vmin=-2.2,
        vmax=2.2,
        linewidths=0.6,
        linecolor="white",
        cbar_kws={"label": "Média padronizada (z-score)", "shrink": 0.85},
        xticklabels=rotulos_clusters,
        yticklabels=[FEATURES_HEATMAP[f] for f in features],
        ax=ax2,
    )
    ax2.set_xlabel("")
    ax2.set_ylabel("")
    ax2.set_title(
        "Cada arquétipo tem assinatura própria:\n"
        "turismo-rico × interior pobre × polo empresarial",
        fontsize=12.5,
        loc="left",
        fontweight="bold",
    )
    ax2.tick_params(axis="x", labelsize=9)
    ax2.tick_params(axis="y", labelsize=10)

    fig.tight_layout()
    caminho = SAIDA_DIR / "fig_arquetipos.png"
    fig.savefig(caminho, dpi=DPI, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    logger.info("  salvo %s", caminho)
    return caminho


def main() -> None:
    SAIDA_DIR.mkdir(parents=True, exist_ok=True)
    base = carregar_base()

    caminhos = [
        fig_eda_dispersao(base),
        fig_top15_ipb(base),
        fig_ipb_por_estrato(base),
        fig_arquetipos(base),
    ]
    for caminho in caminhos:
        tamanho = caminho.stat().st_size
        logger.info("Figura gerada: %s (%d bytes)", caminho, tamanho)
    logger.info("Concluído: %d figuras da apresentação geradas em %s.", len(caminhos), SAIDA_DIR)


if __name__ == "__main__":
    main()
