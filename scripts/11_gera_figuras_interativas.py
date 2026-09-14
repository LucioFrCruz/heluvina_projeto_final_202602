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
    7. fig_classificacao_roc.json              — curva ROC re-treinada do classificador
                                                 de presenca bancaria (teste)
    8. fig_resultados_ipb_arquetipos.json      — distribuicao do IPB V3 por arquetipo
    9. fig_top15_ipb.json                      — Top 15 do IPB V3 (substitui o PNG)

Figuras geradas para o apendice (docs/apendice.html), fora da fala:
    - fig_rede_por_estrato.json                — agencias vs correspondentes por
                                                 estrato (a rede paralela, secao A8)
    - fig_espelho_escolaridade_extremos.json   — top 10 e bottom 10 de escolaridade

Inputs (data/processed/):
    - trusted_municipios_eda.parquet (escolaridade, pix, agencias)
    - analytics_ipb_v3_presenca_completa.parquet (ipb V3, correspondentes, CEMPRE)
    - modelagem_resultados.parquet (arquetipo, cluster)
    - modelagem.parquet (features e alvo da classificacao e do PCA)

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
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import auc, roc_curve
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from src.analytics.modelagem import FEATURES_MODELO, FEATURES_SEM_PRESENCA

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
    "font": {"size": 13, "color": "#24303b"},
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
        height=470,
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
        height=560,
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
        height=470,
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
        height=560,
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
        height=470,
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
        height=560,
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
        height=560,
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
        height=470,
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
        title="Cada arquétipo ocupa um território próprio no mapa de perfil das cidades",
        xaxis_title="Componente principal 1",
        yaxis_title="Componente principal 2",
        height=470,
        margin={"l": 60, "r": 30, "t": 75, "b": 55},
    )
    return gravar(fig, "fig_pca_arquetipos.json")


def fig_classificacao_roc() -> Path:
    """
    Curva ROC do classificador de presenca bancaria, re-treinado aqui.

    O parquet de resultados guarda a probabilidade do modelo final (treinado em
    100% dos dados, in-sample), que separa quase perfeitamente e nao serve pra
    curva. Aqui a gente reproduz o experimento do notebook: mesmo split
    estratificado 80/20 (seed 42), mesmas 13 features e mesmo RF tunado
    (400 arvores, profundidade 20), e mede a ROC no teste.
    """
    logger.info("Re-treinando RF para a curva ROC (pode levar ~1 min)...")
    mod = pd.read_parquet(PROCESSED_DATA_DIR / "modelagem.parquet")
    X = mod[FEATURES_SEM_PRESENCA]
    y = mod["flag_tem_agencia"]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    rf = RandomForestClassifier(n_estimators=400, max_depth=20, random_state=42, n_jobs=-1)
    rf.fit(Xtr, ytr)
    prob = rf.predict_proba(Xte)[:, 1]
    fpr, tpr, _ = roc_curve(yte, prob)
    valor_auc = auc(fpr, tpr)
    logger.info("ROC no teste (n=%d): AUC=%.4f", len(yte), valor_auc)

    fig = go.Figure()
    fig.add_scatter(
        x=fpr, y=tpr,
        mode="lines",
        line_color="#16637a",
        line_width=2.5,
        hovertemplate="FPR %{x:.2f} · TPR %{y:.2f}<extra></extra>".replace(".", ","),
        name=f"ROC (AUC {valor_auc:.3f})".replace(".", ","),
    )
    fig.add_scatter(
        x=[0, 1], y=[0, 1],
        mode="lines",
        line_color="#9aa5ae",
        line_dash="dash",
        hoverinfo="skip",
        name="Aleatório (AUC 0,50)",
    )
    fig.add_annotation(
        x=0.55, y=0.25,
        text=f"AUC = {valor_auc:.3f}".replace(".", ","),
        showarrow=False,
        font=dict(size=16, color="#16637a"),
    )
    fig.update_layout(
        **LAYOUT_BASE,
        title="O modelo separa bem quem tem agência. A pergunta que ele responde é a do proxy",
        xaxis_title="Taxa de falso positivo",
        yaxis_title="Taxa de verdadeiro positivo",
        height=470,
        margin={"l": 70, "r": 25, "t": 80, "b": 62},
        legend=dict(orientation="h", x=0.3, y=0.06),
    )
    return gravar(fig, "fig_classificacao_roc.json")


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
        height=470,
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
        fig_classificacao_roc(),
        fig_ipb_por_arquetipo(base),
    ]
    validar_jsons(caminhos)
    logger.info("Concluído: %d figuras interativas geradas em %s.", len(caminhos), SAIDA_DIR)


if __name__ == "__main__":
    main()
