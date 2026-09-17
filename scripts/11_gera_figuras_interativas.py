"""
Gera as figuras interativas (plotly) da apresentacao final em docs/assets/data/.

Le os parquets locais em data/processed/ — 100% offline, sem BigQuery — e grava
um JSON por figura (plotly.io.to_json), consumido pelo deck reveal.js via
fetch + Plotly.newPlot com renderizacao preguicosa (o deck so renderiza o
grafico quando o slide fica visivel, porque plotly em slide display:none
mede 0x0).

Figuras usadas no deck:
    1. fig_espelho_escolaridade_hist.json      — distribuicao da escolaridade
                                                 por municipio, com media nacional
    2. fig_espelho_escolaridade_regiao.json    — box da escolaridade por regiao,
                                                 com pontos da media
    3. fig_espelho_pix_top15.json              — top 15 de Pix per capita, tooltip rico
    4. fig_pix_por_uf.json                     — mediana de Pix per capita por UF,
                                                 hover com maximo e municipio recordista
    5. fig_arquetipos_barras.json              — quantidade de municipios por arquetipo
    6. fig_pca_arquetipos.json                 — dispersao PCA (2D) dos clusters com
                                                 centroides
    7. fig_resultados_ipb_arquetipos.json      — distribuicao do IPB V3 por arquetipo
    8. fig_top15_ipb.json                      — Top 15 do IPB V3 (substitui o PNG)
    9. fig_comparacao_versoes.json             — por que a V3 e a oficial:
                                                 dumbbell V1->V3 de 7 cidades
                                                 + quanto do Top 100 de cada
                                                 versao ja tem agencia bancaria
   10. fig_escolha_k.json                      — por que K=6: silhouette e elbow
                                                 lado a lado (re-treina K-Means/GMM)

Figuras geradas para o apendice (docs/apendice.html), fora da fala:
    - fig_rede_por_estrato.json                — agencias vs correspondentes por
                                                 estrato (a rede paralela, secao A8)
    - fig_espelho_escolaridade_extremos.json   — top 10 e bottom 10 de escolaridade

Inputs (data/processed/):
    - trusted_municipios_eda.parquet (escolaridade, pix, agencias)
    - analytics_ipb_v1_classico.parquet / analytics_ipb_v2_recalibrado.parquet /
      analytics_ipb_v3_presenca_completa.parquet (ipb e rank das 3 versoes)
    - modelagem_resultados.parquet (arquetipo, cluster)
    - modelagem.parquet (features da Etapa 3; PCA e avaliacao de K)

Outputs:
    - docs/assets/data/*.json (um por figura)

Nota metodologica: a media de escolaridade usada na linha do histograma e a
media simples entre municipios (cada municipio pesa igual, coerente com o
histograma e com o desenho do IPB). A media ponderada pela populacao sobe
para ~52%, porque as grandes cidades sao mais escolarizadas; a diferenca e
ela mesma um achado de equidade urbano/rural, citado nas notas do slide.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from src.analytics.clustering import avaliar_k
from src.analytics.modelagem import FEATURES_MODELO, SEED

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_DATA_DIR = Path("data/processed")
SAIDA_DIR = Path("docs/assets/data")
QUANTIDADE_ESPERADA = 5_570

# Familia de cores usada no mapa e nas figuras estaticas (Tableau 10),
# amigavel a daltônicos e consistente entre site e deck.
CORES_ARQUETIPOS = {
    "Turismo - com rede": "#b07aa1",
    "Sem rede bancaria - renda baixa": "#e15759",
    "Perfil intermediario - empresarial": "#4e79a7",
    "Perfil intermediario - tradicional": "#f28e2b",
    "Turismo - sem banco": "#76b7b2",
    "Sem rede bancaria - renda alta": "#59a14f",
}
ROTULO_ARQUETIPO = {
    "Turismo - com rede": "Turismo - com rede",
    "Sem rede bancaria - renda baixa": "Sem rede bancária - renda baixa",
    "Perfil intermediario - empresarial": "Perfil intermediário - empresarial",
    "Perfil intermediario - tradicional": "Perfil intermediário - tradicional",
    "Turismo - sem banco": "Turismo - sem banco",
    "Sem rede bancaria - renda alta": "Sem rede bancária - renda alta",
}
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
CORES_REGIAO = {
    "Norte": "#59a14f",
    "Nordeste": "#e15759",
    "Centro-Oeste": "#f28e2b",
    "Sudeste": "#4e79a7",
    "Sul": "#76b7b2",
}

LAYOUT_BASE = {
    "paper_bgcolor": "white",
    "plot_bgcolor": "white",
    "font": {"size": 15, "color": "#24303b"},
    "title_font": {"size": 20},
}


def hex_para_rgba(hex_cor: str, alpha: float) -> str:
    """Converte '#rrggbb' em 'rgba(r,g,b,a)' (plotly nao aceita hex de 8 digitos aqui)."""
    hex_cor = hex_cor.lstrip("#")
    r, g, b = (int(hex_cor[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def carregar_base() -> pd.DataFrame:
    """Consolida trusted + V3 + arquetipos em uma base por municipio."""
    logger.info("Lendo parquets de data/processed/...")
    eda = pd.read_parquet(PROCESSED_DATA_DIR / "trusted_municipios_eda.parquet")
    v3 = pd.read_parquet(PROCESSED_DATA_DIR / "analytics_ipb_v3_presenca_completa.parquet")
    res = pd.read_parquet(PROCESSED_DATA_DIR / "modelagem_resultados.parquet")
    for nome, df in [("trusted", eda), ("v3", v3), ("resultados", res)]:
        df["id_municipio"] = df["id_municipio"].astype(str).str.zfill(7)
        logger.info("  %s: %d linhas, %d colunas", nome, *df.shape)
    base = eda.merge(
        v3[
            [
                "id_municipio",
                "ipb",
                "rank",
                "correspondentes_por_100k_hab",
                "empregos_formais_por_1000_hab",
                "unidades_alojamento_alimentacao_por_1000_hab",
            ]
        ],
        on="id_municipio",
        how="left",
        validate="one_to_one",
    ).merge(
        res[["id_municipio", "cluster_kmeans", "arquetipo"]],
        on="id_municipio",
        how="left",
        validate="one_to_one",
    )
    if len(base) != QUANTIDADE_ESPERADA:
        raise ValueError(f"esperado {QUANTIDADE_ESPERADA} linhas, encontrado {len(base)}")
    return base


def gravar(fig: go.Figure, nome: str) -> Path:
    """Grava a figura como JSON para Plotly.newPlot e retorna o caminho."""
    caminho = SAIDA_DIR / nome
    caminho.write_text(fig.to_json(), encoding="utf-8")
    logger.info("  salvo %s (%d bytes)", caminho, caminho.stat().st_size)
    return caminho


def fig_escolaridade_hist(base: pd.DataFrame) -> Path:
    """Histograma da escolaridade por municipio, com a media nacional em linha."""
    media = base["escolaridade_ensino_medio_pct"].mean()
    media_pond = (base["escolaridade_ensino_medio_pct"] * base["populacao_total"]).sum() / base["populacao_total"].sum()
    logger.info("escolaridade: media entre municipios %.2f | ponderada %.2f", media, media_pond)

    fig = go.Figure()
    fig.add_histogram(
        x=base["escolaridade_ensino_medio_pct"],
        nbinsx=60,
        marker_color="#4e79a7",
        opacity=0.85,
        hovertemplate="%{x:.1f}% · %{y} municípios<extra></extra>",
    )
    fig.add_vline(
        x=media,
        line_color="#16637a",
        line_width=2.5,
        annotation_text=f"Média nacional: {media:.1f}%".replace(".", ","),
        annotation_position="top",
        annotation_font_color="#16637a",
    )
    fig.update_layout(
        **LAYOUT_BASE,
        title="Na cidade média do país, só 4 em cada 10 adultos concluíram o ensino médio",
        xaxis_title="% da população 18+ com ensino médio completo (Censo 2022)",
        yaxis_title="Nº de municípios",
        showlegend=False,
        height=560,
        margin={"l": 60, "r": 30, "t": 75, "b": 55},
    )
    return gravar(fig, "fig_espelho_escolaridade_hist.json")


def fig_escolaridade_extremos(base: pd.DataFrame) -> Path:
    """Barras combinadas das 10 cidades mais altas e 10 mais baixas em escolaridade.

    Gerada para consulta no apêndice; fora do deck por falta de espaço.
    """
    top = base.nlargest(10, "escolaridade_ensino_medio_pct")
    bottom = base.nsmallest(10, "escolaridade_ensino_medio_pct")
    comb = pd.concat([bottom, top])  # bottom primeiro: barras mais baixas embaixo
    rotulos = [f"{r['nome_municipio']} ({r['sigla_uf']})" for _, r in comb.iterrows()]
    cores = ["#e15759"] * 10 + ["#16637a"] * 10

    fig = go.Figure()
    fig.add_bar(
        y=rotulos,
        x=comb["escolaridade_ensino_medio_pct"],
        orientation="h",
        marker_color=cores,
        customdata=comb[["nome_regiao", "estrato_populacional"]],
        hovertemplate=(
            "%{y}<br>Escolaridade: %{x:.1f}% · Região: %{customdata[0]}"
            " · Estrato: %{customdata[1]}<extra></extra>"
        ),
    )
    fig.update_layout(
        **LAYOUT_BASE,
        title=(
            "A fila tem duas pontas: de "
            f"{comb.iloc[-1]['escolaridade_ensino_medio_pct']:.0f}% em "
            f"{comb.iloc[-1]['nome_municipio']} a {comb.iloc[0]['escolaridade_ensino_medio_pct']:.1f}% em "
            f"{comb.iloc[0]['nome_municipio']}"
        ).replace(".", ","),
        xaxis_title="% da população 18+ com ensino médio completo",
        yaxis_title="",
        showlegend=False,
        height=620,
        margin={"l": 190, "r": 30, "t": 70, "b": 55},
    )
    return gravar(fig, "fig_espelho_escolaridade_extremos.json")


def fig_escolaridade_regiao(base: pd.DataFrame) -> Path:
    """Box da escolaridade por regiao, com pontos da media e titulo interpretado."""
    resumo = (
        base.groupby("nome_regiao")["escolaridade_ensino_medio_pct"]
        .agg(media="mean", mediana="median")
        .sort_values("media", ascending=False)
    )
    logger.info("escolaridade por regiao (media): %s", resumo["media"].round(2).to_dict())
    ordem = resumo.index.tolist()

    fig = go.Figure()
    for regiao in ordem:
        fatia = base[base["nome_regiao"] == regiao]["escolaridade_ensino_medio_pct"]
        fig.add_box(
            y=fatia,
            name=regiao,
            marker_color=CORES_REGIAO[regiao],
            boxmean=False,
            boxpoints=False,
            hovertemplate="%{y:.1f}%<extra></extra>".replace(".", ","),
        )
    fig.add_scatter(
        x=ordem,
        y=resumo["media"].round(2),
        mode="markers",
        marker=dict(symbol="diamond", size=11, color="#24303b"),
        name="Média",
        hovertemplate="Média %{x}: %{y:.1f}%<extra></extra>".replace(".", ","),
    )
    fig.update_layout(
        **LAYOUT_BASE,
        title=(
            f"O Nordeste fica embaixo: {resumo.loc['Nordeste', 'media']:.1f}% com ensino médio, "
            f"contra {resumo.loc['Sudeste', 'media']:.1f}% no Sudeste"
        ).replace(".", ","),
        yaxis_title="% da população 18+ com ensino médio completo",
        showlegend=False,
        height=560,
        margin={"l": 60, "r": 30, "t": 75, "b": 55},
    )
    return gravar(fig, "fig_espelho_escolaridade_regiao.json")


def fig_pix_top15(base: pd.DataFrame) -> Path:
    """Top 15 de Pix per capita com tooltip rico."""
    top = base.nlargest(15, "pix_per_capita_12m")
    rotulos = [f"{r['nome_municipio']} ({r['sigla_uf']})" for _, r in top.iterrows()]
    fig = go.Figure()
    fig.add_bar(
        y=rotulos,
        x=top["pix_per_capita_12m"],
        orientation="h",
        marker_color=[CORES_REGIAO[r] for r in top["nome_regiao"]],
        customdata=top[["sigla_uf", "pix_per_capita_12m", "agencias_por_100k_hab", "correspondentes_por_100k_hab", "nome_regiao"]],
        hovertemplate=(
            "%{y}<br>Pix per capita (12m): R$ %{customdata[1]:,.0f}"
            "<br>Agências /100 mil: %{customdata[2]:.1f} · Correspondentes /100 mil: %{customdata[3]:.0f}"
            "<br>Região: %{customdata[4]}<extra></extra>"
        ).replace(",", "X").replace(".", ",").replace("X", "."),
    )
    fig.update_layout(
        **LAYOUT_BASE,
        title="As 15 maiores taxas de Pix per capita do país são de cidades pequenas, agro e fronteira",
        xaxis_title="Pix per capita, últimos 12 meses (R$)",
        yaxis_title="",
        showlegend=False,
        height=620,
        margin={"l": 190, "r": 30, "t": 70, "b": 55},
    )
    fig.update_yaxes(categoryorder="total ascending")
    return gravar(fig, "fig_espelho_pix_top15.json")


def fig_rede_por_estrato(base: pd.DataFrame) -> Path:
    """Barras agrupadas: agencias vs correspondentes por 100 mil hab, por estrato."""
    resumo = (
        base.groupby("estrato_populacional")[["agencias_por_100k_hab", "correspondentes_por_100k_hab"]]
        .median()
        .reindex(["pequena", "media", "grande"])
    )
    logger.info("rede por estrato (mediana): %s", resumo.round(1).to_dict())
    estratos = [ROTULO_ESTRATO[e] for e in resumo.index]

    fig = go.Figure()
    fig.add_bar(
        x=estratos,
        y=resumo["agencias_por_100k_hab"],
        name="Agências /100 mil hab",
        marker_color="#16637a",
        hovertemplate="%{x}<br>Agências: %{y:.1f} /100 mil hab<extra></extra>".replace(".", ","),
    )
    fig.add_bar(
        x=estratos,
        y=resumo["correspondentes_por_100k_hab"],
        name="Correspondentes /100 mil hab",
        marker_color="#f28e2b",
        hovertemplate="%{x}<br>Correspondentes: %{y:.0f} /100 mil hab<extra></extra>",
    )
    fig.update_layout(
        **LAYOUT_BASE,
        title=(
            f"Na cidade pequena, a lotérica é o banco: {resumo.loc['pequena', 'agencias_por_100k_hab']:.0f} agência "
            f"na mediana e {resumo.loc['pequena', 'correspondentes_por_100k_hab']:.0f} correspondentes por 100 mil hab"
        ).replace(".", ","),
        yaxis_title="Pontos por 100 mil hab (mediana)",
        barmode="group",
        height=560,
        margin={"l": 60, "r": 30, "t": 75, "b": 55},
        legend=dict(orientation="h", y=1.12, x=0),
    )
    return gravar(fig, "fig_rede_por_estrato.json")


def fig_pix_por_uf(base: pd.DataFrame) -> Path:
    """Mediana de Pix per capita por UF, com tooltip rico (maximo e recordista)."""
    resumo = (
        base.groupby(["sigla_uf", "nome_regiao"])["pix_per_capita_12m"]
        .agg(mediana="median", maximo="max")
        .reset_index()
    )
    recordistas = base.loc[base.groupby("sigla_uf")["pix_per_capita_12m"].idxmax(),
                            ["sigla_uf", "nome_municipio"]]
    resumo = resumo.merge(recordistas, on="sigla_uf", validate="one_to_one")
    resumo = resumo.sort_values("mediana", ascending=True)  # barh: maior no topo

    fig = go.Figure()
    fig.add_bar(
        y=resumo["sigla_uf"],
        x=resumo["mediana"],
        orientation="h",
        marker_color=[CORES_REGIAO[r] for r in resumo["nome_regiao"]],
        customdata=resumo[["maximo", "nome_municipio", "nome_regiao"]],
        hovertemplate=(
            "%{y}<br>Mediana: R$ %{x:,.0f}"
            "<br>Máximo: R$ %{customdata[0]:,.0f} (%{customdata[1]})"
            "<br>Região: %{customdata[2]}<extra></extra>"
        ).replace(",", "X").replace(".", ",").replace("X", "."),
    )
    fig.update_layout(
        **LAYOUT_BASE,
        title="O agro do Centro-Oeste e a fronteira do Norte movem mais Pix per capita que as metrópoles",
        xaxis_title="Mediana de Pix per capita, 12 meses (R$)",
        yaxis_title="",
        showlegend=False,
        height=620,
        margin={"l": 55, "r": 30, "t": 70, "b": 55},
    )
    return gravar(fig, "fig_pix_por_uf.json")


def fig_top15_ipb(base: pd.DataFrame) -> Path:
    """Top 15 do IPB V3 em barras interativas (substitui o PNG da rodada 1)."""
    top = base.nsmallest(15, "rank").copy()
    top["rotulo"] = top["nome_municipio"] + " (" + top["sigla_uf"] + ")"
    fig = go.Figure()
    fig.add_bar(
        y=top["rotulo"],
        x=top["ipb"],
        orientation="h",
        marker_color=[CORES_ESTRATO[e] for e in top["estrato_populacional"]],
        customdata=top[["ipb", "arquetipo", "estrato_populacional"]],
        hovertemplate=(
            "%{y}<br>IPB V3: %{customdata[0]:.2f} · Arquétipo: %{customdata[1]}"
            " · Estrato: %{customdata[2]}<extra></extra>"
        ).replace(".", ","),
    )
    fig.update_layout(
        **LAYOUT_BASE,
        title="O Top 15 do IPB V3 mistura turismo, dormitórios ricos e capitais",
        xaxis_title="IPB V3 (0–100)",
        yaxis_title="",
        showlegend=False,
        height=620,
        margin={"l": 190, "r": 30, "t": 70, "b": 55},
    )
    fig.update_yaxes(categoryorder="total ascending")
    fig.update_xaxes(range=[0, 80])
    return gravar(fig, "fig_top15_ipb.json")


def fig_arquetipos_barras(base: pd.DataFrame) -> Path:
    """Barras da quantidade de municipios por arquetipo, com % no tooltip."""
    contagem = (
        base.groupby("cluster_kmeans")["arquetipo"]
        .agg(arquetipo="first", n="count")
        .sort_values("cluster_kmeans")
    )
    total = contagem["n"].sum()
    rotulos = [ROTULO_ARQUETIPO[a] for a in contagem["arquetipo"]]
    fig = go.Figure()
    fig.add_bar(
        x=rotulos,
        y=contagem["n"],
        marker_color=[CORES_ARQUETIPOS[a] for a in contagem["arquetipo"]],
        customdata=contagem[["n"]].assign(pct=contagem["n"] / total * 100),
        hovertemplate="%{x}<br>%{y:,} municípios (%{customdata[1]:.1f}% do país)<extra></extra>".replace(",", "X").replace(".", ",").replace("X", "."),
    )
    fig.update_layout(
        **LAYOUT_BASE,
        title="O interior pobre sem rede é o maior grupo; o turismo rico sem banco é o achado",
        xaxis_title="",
        yaxis_title="Nº de municípios",
        showlegend=False,
        height=560,
        margin={"l": 60, "r": 30, "t": 75, "b": 95},
    )
    fig.update_xaxes(tickangle=-20)
    return gravar(fig, "fig_arquetipos_barras.json")


def fig_pca_arquetipos() -> Path:
    """
    Dispersao 2D dos clusters via PCA sobre as 19 features padronizadas.

    As features de modelagem.parquet ja tem log1p aplicado; a padronizacao
    (StandardScaler) acontece aqui, antes do PCA, como nos notebooks.
    """
    logger.info("Calculando PCA dos arquetipos...")
    mod = pd.read_parquet(PROCESSED_DATA_DIR / "modelagem.parquet")
    res = pd.read_parquet(PROCESSED_DATA_DIR / "modelagem_resultados.parquet")
    mod["id_municipio"] = mod["id_municipio"].astype(str).str.zfill(7)
    res["id_municipio"] = res["id_municipio"].astype(str).str.zfill(7)

    X = StandardScaler().fit_transform(mod[FEATURES_MODELO])
    pca = PCA(n_components=2)
    comps = pca.fit_transform(X)
    logger.info("variancia explicada PC1+PC2: %.1f%%", pca.explained_variance_ratio_.sum() * 100)

    base = pd.DataFrame({
        "id_municipio": mod["id_municipio"],
        "nome_municipio": mod["nome_municipio"],
        "pc1": comps[:, 0],
        "pc2": comps[:, 1],
    }).merge(res[["id_municipio", "cluster_kmeans", "arquetipo"]], on="id_municipio", validate="one_to_one")

    fig = go.Figure()
    ordem = sorted(base["cluster_kmeans"].unique())
    arquetipos = base.groupby("cluster_kmeans")["arquetipo"].first().reindex(ordem)
    for cl in ordem:
        fatia = base[base["cluster_kmeans"] == cl]
        arq = arquetipos[cl]
        fig.add_scatter(
            x=fatia["pc1"],
            y=fatia["pc2"],
            mode="markers",
            marker=dict(size=5, color=CORES_ARQUETIPOS[arq], opacity=0.55),
            name=ROTULO_ARQUETIPO[arq],
            customdata=fatia[["nome_municipio", "arquetipo"]],
            hovertemplate="%{customdata[0]}<br>%{customdata[1]}<extra></extra>",
            showlegend=False,
        )
    centroides = base.groupby("cluster_kmeans")[["pc1", "pc2"]].mean().reindex(ordem)
    fig.add_scatter(
        x=centroides["pc1"],
        y=centroides["pc2"],
        mode="markers",
        marker=dict(symbol="x", size=15, color="#1f2937", line_width=3),
        name="Centroide",
        customdata=[ROTULO_ARQUETIPO[a] for a in arquetipos],
        hovertemplate="Centroide: %{customdata[0]}<extra></extra>",
    )
    fig.update_layout(
        **LAYOUT_BASE,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=600,
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
    )
    return gravar(fig, "fig_pca_arquetipos.json")


def fig_comparacao_versoes() -> Path:
    """
    Por que a V3 e a versao oficial: 2 paineis que contam a decisao.

    Painel A — dumbbell de 7 cidades conhecidas ligando o rank V1 ao rank
    V3 (escala log, rank 1 a esquerda): verde sobe, vermelho cai. Ranks
    confirmados nos parquets (Bombinhas 21 -> 1; Brasilia 134 -> 13;
    Sao Paulo 174 -> 15; Rio de Janeiro 611 -> 51; Pacaraima 3.545 -> 1.889;
    Jundiai 30 -> 110; Fernando de Noronha 13 -> 2.578).

    Painel B — o argumento: quanto do Top 100 de cada versao ja esta
    servido por agencia bancaria (% das 100 com agencia + mediana de
    agencias/100 mil hab, da trusted). A V1 premia quem ja tem banco;
    a V3 abre espaco para quem ainda falta.
    """
    logger.info("Comparando as 3 versoes do IPB (decisao V3)...")
    v1 = pd.read_parquet(PROCESSED_DATA_DIR / "analytics_ipb_v1_classico.parquet")
    v2 = pd.read_parquet(PROCESSED_DATA_DIR / "analytics_ipb_v2_recalibrado.parquet")
    v3 = pd.read_parquet(PROCESSED_DATA_DIR / "analytics_ipb_v3_presenca_completa.parquet")
    eda = pd.read_parquet(PROCESSED_DATA_DIR / "trusted_municipios_eda.parquet")
    for df in (v1, v2, v3, eda):
        df["id_municipio"] = df["id_municipio"].astype(str).str.zfill(7)

    m = (
        v1[["id_municipio", "nome_municipio", "sigla_uf", "rank"]]
        .rename(columns={"rank": "rank_v1"})
        .merge(
            v2[["id_municipio", "rank"]].rename(columns={"rank": "rank_v2"}),
            on="id_municipio", validate="one_to_one",
        )
        .merge(
            v3[["id_municipio", "rank"]].rename(columns={"rank": "rank_v3"}),
            on="id_municipio", validate="one_to_one",
        )
        .merge(
            eda[["id_municipio", "quantidade_agencias", "agencias_por_100k_hab"]],
            on="id_municipio", validate="one_to_one",
        )
    )
    if len(m) != QUANTIDADE_ESPERADA:
        raise ValueError(f"esperado {QUANTIDADE_ESPERADA} linhas, encontrado {len(m)}")

    fig = make_subplots(
        rows=2, cols=2,
        column_widths=[0.58, 0.42],
        row_heights=[0.55, 0.45],
        specs=[[{"rowspan": 2}, {}], [None, {}]],
        subplot_titles=(
            "Quem sobe e quem cai no ranking",
            "O Top 100 de cada versão: % com agência bancária",
            "Mediana de agências por 100 mil hab no Top 100",
        ),
    )

    # --- Painel A: dumbbell V1 -> V3 para 7 casos conhecidos ---------------
    casos = [
        ("Bombinhas", "SC", 21, 1),
        ("Brasília", "DF", 134, 13),
        ("São Paulo", "SP", 174, 15),
        ("Rio de Janeiro", "RJ", 611, 51),
        ("Pacaraima", "RR", 3545, 1889),
        ("Jundiaí", "SP", 30, 110),
        ("Fernando de Noronha", "PE", 13, 2578),
    ]
    casos_df = pd.DataFrame(casos, columns=["nome", "uf", "rank_v1", "rank_v3"])
    casos_df = casos_df.merge(
        m[["id_municipio", "nome_municipio", "sigla_uf", "rank_v2"]],
        left_on=["nome", "uf"], right_on=["nome_municipio", "sigla_uf"],
        validate="one_to_one",
    )
    # Ordem de baixo para cima: quem mais caiu no canto superior.
    casos_df = casos_df.sort_values("rank_v3", ascending=False).reset_index(drop=True)
    casos_df["y"] = casos_df.index
    casos_df["sobe"] = casos_df["rank_v3"] < casos_df["rank_v1"]
    logger.info("casos do dumbbell (rank V1 -> V3): %s",
                casos_df.set_index("nome")[["rank_v1", "rank_v3"]].astype(int).T.to_dict())

    for _, r in casos_df.iterrows():
        cor = "#2f9e6e" if r["sobe"] else "#d64550"
        fig.add_scatter(
            x=[r["rank_v1"], r["rank_v3"]], y=[r["y"], r["y"]],
            mode="lines",
            line=dict(color=cor, width=3),
            hoverinfo="skip",
            showlegend=False,
            row=1, col=1,
        )
    hover_rank = (
        "%{customdata[0]} (%{customdata[1]})<br>Rank V1: %{customdata[2]:.0f}"
        " · V2: %{customdata[3]:.0f} · V3: %{customdata[4]:.0f}<extra></extra>"
    )
    for sobe, cor, nome in [
        (True, "#2f9e6e", "Sobe na V3"),
        (False, "#d64550", "Cai na V3"),
    ]:
        fatia = casos_df[casos_df["sobe"] == sobe]
        fig.add_scatter(
            x=fatia["rank_v1"], y=fatia["y"],
            mode="markers",
            marker=dict(symbol="circle-open", size=13, line=dict(color=cor, width=2.5)),
            name=f"{nome} — V1",
            customdata=fatia[["nome", "uf", "rank_v1", "rank_v2", "rank_v3"]],
            hovertemplate=hover_rank,
            row=1, col=1,
        )
        fig.add_scatter(
            x=fatia["rank_v3"], y=fatia["y"],
            mode="markers",
            marker=dict(symbol="circle", size=13, color=cor),
            name=f"{nome} — V3",
            customdata=fatia[["nome", "uf", "rank_v1", "rank_v2", "rank_v3"]],
            hovertemplate=hover_rank,
            row=1, col=1,
        )
    fig.update_yaxes(
        tickvals=casos_df["y"],
        ticktext=[f"{r['nome']} ({r['uf']})" for _, r in casos_df.iterrows()],
        tickfont_size=16,
        row=1, col=1,
    )
    fig.update_xaxes(
        title_text="Rank (log) — 1º à direita",
        title_font_size=16,
        type="log",
        autorange="reversed",
        tickfont_size=16,
        row=1, col=1,
    )

    # --- Painel B: quanto do Top 100 de cada versao ja tem banco -----------
    versoes = [("V1", "rank_v1", "#4e79a7"), ("V2", "rank_v2", "#f28e2b"), ("V3", "rank_v3", "#16637a")]
    pct_com_agencia, mediana_ag = [], []
    for nome, rk, _ in versoes:
        top = m.nsmallest(100, rk)
        pct = (top["quantidade_agencias"] > 0).mean() * 100
        med = top["agencias_por_100k_hab"].median()
        pct_com_agencia.append(pct)
        mediana_ag.append(med)
        logger.info("Top 100 %s: %.0f%% com agencia | mediana %.1f ag/100k hab", nome, pct, med)

    nomes_versoes = [v[0] for v in versoes]
    cores_versoes = [v[2] for v in versoes]
    fig.add_bar(
        x=nomes_versoes,
        y=[round(p) for p in pct_com_agencia],
        marker_color=cores_versoes,
        text=[f"{p:.0f}%" for p in pct_com_agencia],
        textposition="outside",
        textfont_size=16,
        hovertemplate="Top 100 %{x}: %{y:.0f}% das cidades têm agência bancária<extra></extra>",
        showlegend=False,
        row=1, col=2,
    )
    fig.add_bar(
        x=nomes_versoes,
        y=[round(med, 1) for med in mediana_ag],
        marker_color=cores_versoes,
        text=[f"{med:.1f}".replace(".", ",") for med in mediana_ag],
        textposition="outside",
        textfont_size=16,
        hovertemplate="Top 100 %{x}: mediana de %{y:.1f} agências/100 mil hab<extra></extra>".replace(".", ","),
        showlegend=False,
        row=2, col=2,
    )
    fig.update_yaxes(range=[0, 108], tickfont_size=16, row=1, col=2)
    fig.update_yaxes(range=[0, 8.5], tickfont_size=16, row=2, col=2)
    fig.update_xaxes(tickfont_size=16, row=1, col=2)
    fig.update_xaxes(tickfont_size=16, row=2, col=2)

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text="A V3 troca “onde já tem banco” por “onde ainda falta banco”",
            font=dict(size=22),
        ),
        height=620,
        margin={"l": 200, "r": 30, "t": 95, "b": 60},
        # Legenda no canto inferior direito do painel A (regiao de rank 1,
        # onde so ha pontos das cidades do topo — longe das linhas de baixo).
        legend=dict(
            orientation="v",
            x=0.44, y=0.04, xanchor="left", yanchor="bottom",
            font_size=15,
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#c7cdd3", borderwidth=1,
        ),
    )
    fig.update_annotations(font_size=17)
    return gravar(fig, "fig_comparacao_versoes.json")


def fig_escolha_k() -> Path:
    """
    Por que K=6: silhouette (K-Means e GMM) e elbow (inercia WSS) lado a lado.

    Re-treina os modelos via `avaliar_k` (mesmo pipeline dos notebooks:
    log1p ja aplicado no parquet, padronizacao interna, seed 42, n_init=10).
    As anotacoes usam os valores reais computados — conferidos contra o
    Relatorio_Modelagem_Etapa3 (silhouette 0,252 em K=3 e 0,200 em K=6;
    BIC do GMM -20.591 em K=6).
    """
    logger.info("Avaliando K (KMeans/GMM, ks=3..8 — leva ~1 min)...")
    mod = pd.read_parquet(PROCESSED_DATA_DIR / "modelagem.parquet")
    aval = avaliar_k(mod, FEATURES_MODELO, ks=range(3, 9), seed=SEED)
    ks = aval["k"].tolist()
    sil_km = aval["silhouette_kmeans"]
    sil_gmm = aval["silhouette_gmm"]
    inercia_mil = aval["inercia_wss_kmeans"] / 1000

    def valor(k: int, coluna: str) -> float:
        return float(aval.loc[aval["k"] == k, coluna].iloc[0])

    sil3 = valor(3, "silhouette_kmeans")
    sil6 = valor(6, "silhouette_kmeans")
    bic6 = valor(6, "bic_gmm")
    queda_56 = valor(5, "inercia_wss_kmeans") / 1000 - valor(6, "inercia_wss_kmeans") / 1000
    queda_45 = valor(4, "inercia_wss_kmeans") / 1000 - valor(5, "inercia_wss_kmeans") / 1000
    logger.info(
        "silhouette K=3: %.3f | K=6: %.3f | BIC K=6: %.0f | queda inercia 4->5: %.1f mil | 5->6: %.1f mil",
        sil3, sil6, bic6, queda_45, queda_56,
    )

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=(
            "Silhouette por K (maior é melhor)",
            "Elbow: inércia (WSS) por K, em milhares",
        ),
    )
    fig.add_scatter(
        x=ks, y=sil_km.round(3),
        mode="lines+markers",
        line=dict(color="#16637a", width=2.5),
        marker=dict(size=9),
        name="K-Means",
        hovertemplate="K=%{x}<br>Silhouette: %{y:.3f}<extra></extra>",
        row=1, col=1,
    )
    fig.add_scatter(
        x=ks, y=sil_gmm.round(3),
        mode="lines+markers",
        line=dict(color="#f28e2b", width=2.5, dash="dot"),
        marker=dict(size=9),
        name="GMM",
        hovertemplate="K=%{x}<br>Silhouette: %{y:.3f}<extra></extra>",
        row=1, col=1,
    )
    fig.add_scatter(
        x=[6], y=[round(sil6, 3)],
        mode="markers",
        marker=dict(symbol="star", size=20, color="#16637a", line=dict(color="#24303b", width=1.5)),
        name="K escolhido (6)",
        hovertemplate="K=6 · Silhouette K-Means: %{y:.3f}<extra></extra>".replace(".", ","),
        row=1, col=1,
    )
    fig.add_annotation(
        x=3, y=sil3,
        text=f"K=3: {sil3:.3f} — mas vira divisão por porte".replace(".", ","),
        showarrow=True, arrowhead=2, arrowsize=1.2, arrowcolor="#24303b",
        ax=30, ay=-45,
        font=dict(size=13, color="#24303b"),
        bgcolor="rgba(255,255,255,0.85)",
        row=1, col=1,
    )
    fig.add_annotation(
        x=6, y=sil6,
        text=f"K=6: {sil6:.3f} — 6 arquétipos legíveis".replace(".", ","),
        showarrow=True, arrowhead=2, arrowsize=1.2, arrowcolor="#24303b",
        ax=-25, ay=55,
        font=dict(size=13, color="#24303b"),
        bgcolor="rgba(255,255,255,0.85)",
        row=1, col=1,
    )

    fig.add_scatter(
        x=ks, y=inercia_mil.round(1),
        mode="lines+markers",
        line=dict(color="#16637a", width=2.5),
        marker=dict(size=9),
        name="Inércia (WSS)",
        hovertemplate="K=%{x}<br>Inércia: %{y:,.1f} mil<extra></extra>".replace(",", "X").replace(".", ",").replace("X", "."),
        showlegend=False,
        row=1, col=2,
    )
    fig.add_annotation(
        x=5.5, y=inercia_mil.iloc[list(ks).index(6)] + 2.5,
        text=(
            f"Joelho entre K=5 e K=6: a queda desacelera de "
            f"{queda_45:.1f} mil (4→5) para {queda_56:.1f} mil (5→6)"
        ).replace(".", ","),
        showarrow=False,
        font=dict(size=13, color="#24303b"),
        bgcolor="rgba(255,255,255,0.85)",
        row=1, col=2,
    )
    fig.add_annotation(
        x=0.5, y=-0.18, xref="x2 domain", yref="y2 domain",
        text=(
            f"GMM concorda no equilíbrio: BIC = {bic6:,.0f} em K=6 e segue em queda na faixa,"
            " mas os grupos de K>6 deixam de ter leitura de negócio"
        ).replace(",", "X").replace(".", ",").replace("X", "."),
        showarrow=False,
        font=dict(size=13, color="#24303b"),
        row=1, col=2,
    )

    fig.update_xaxes(title_text="Número de clusters (K)", dtick=1, row=1, col=1)
    fig.update_yaxes(title_text="Silhouette", row=1, col=1)
    fig.update_xaxes(title_text="Número de clusters (K)", dtick=1, row=1, col=2)
    fig.update_yaxes(title_text="Inércia WSS (milhares)", row=1, col=2)

    fig.update_layout(
        **LAYOUT_BASE,
        title="Por que 6 arquétipos: silhouette e elbow convergem, e a narrativa de negócio fecha",
        height=600,
        margin={"l": 70, "r": 30, "t": 90, "b": 70},
        legend=dict(orientation="h", y=1.1, x=0),
    )
    fig.update_annotations(font_size=15)
    return gravar(fig, "fig_escolha_k.json")


def fig_ipb_por_arquetipo(base: pd.DataFrame) -> Path:
    """Box plot do IPB V3 por arquetipo, ordenado pela mediana."""
    ordem = (
        base.groupby("arquetipo")["ipb"]
        .median()
        .sort_values(ascending=False)
        .index
        .tolist()
    )
    fig = go.Figure()
    for arq in ordem:
        fatia = base[base["arquetipo"] == arq]["ipb"]
        fig.add_box(
            y=fatia,
            name=ROTULO_ARQUETIPO[arq],
            marker_color=CORES_ARQUETIPOS[arq],
            boxmean=True,
            boxpoints=False,
            hovertemplate="%{y:.1f}<extra></extra>".replace(".", ","),
        )
    fig.update_layout(
        **LAYOUT_BASE,
        title="Onde cada arquétipo mora no índice: turismo pontua alto, interior sem rede fica embaixo",
        yaxis_title="IPB V3 (0–100)",
        showlegend=False,
        height=560,
        margin={"l": 60, "r": 30, "t": 75, "b": 110},
    )
    fig.update_xaxes(tickangle=-18)
    return gravar(fig, "fig_resultados_ipb_arquetipos.json")


def validar_jsons(caminhos: list[Path]) -> None:
    """Confirma que cada JSON gerado é parseável, tem data/layout e não é vazio."""
    for caminho in caminhos:
        conteudo = json.loads(caminho.read_text(encoding="utf-8"))
        if not conteudo.get("data") or not conteudo.get("layout"):
            raise ValueError(f"{caminho}: JSON sem data/layout")
        logger.info("  validado %s: %d traces", caminho.name, len(conteudo["data"]))


def main() -> None:
    SAIDA_DIR.mkdir(parents=True, exist_ok=True)
    base = carregar_base()

    caminhos = [
        fig_escolaridade_hist(base),
        fig_escolaridade_regiao(base),
        fig_escolaridade_extremos(base),
        fig_pix_top15(base),
        fig_pix_por_uf(base),
        fig_rede_por_estrato(base),
        fig_top15_ipb(base),
        fig_arquetipos_barras(base),
        fig_pca_arquetipos(),
        fig_ipb_por_arquetipo(base),
        fig_comparacao_versoes(),
        fig_escolha_k(),
    ]
    validar_jsons(caminhos)
    logger.info("Concluído: %d figuras interativas geradas em %s.", len(caminhos), SAIDA_DIR)


if __name__ == "__main__":
    main()
