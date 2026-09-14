"""
Gera as figuras interativas (plotly) da apresentacao final em docs/assets/data/.

Le os parquets locais em data/processed/ — 100% offline, sem BigQuery — e grava
um JSON por figura (plotly.io.to_json), consumido pelo deck reveal.js via
fetch + Plotly.newPlot com renderizacao preguicosa (o deck so renderiza o
grafico quando o slide fica visivel, porque plotly em slide display:none
mede 0x0).

Figuras geradas:
    1. fig_espelho_escolaridade_hist.json      — distribuicao da escolaridade
                                                 por municipio, com media nacional
    2. fig_espelho_escolaridade_extremos.json  — top 10 e bottom 10 de escolaridade
    3. fig_espelho_pix_top15.json              — top 15 de Pix per capita, tooltip rico
    4. fig_espelho_pix_agencias.json           — dispersao Pix x agencias, cor =
                                                 correspondentes (rede paralela)
    5. fig_arquetipos_barras.json              — quantidade de municipios por arquetipo
    6. fig_arquetipos_radar.json               — radar das medias padronizadas por
                                                 arquetipo, com dropdown de selecao
    7. fig_classificacao_roc.json              — curva ROC re-treinada do classificador
                                                 de presenca bancaria (teste)
    8. fig_resultados_ipb_arquetipos.json      — distribuicao do IPB V3 por arquetipo

Inputs (data/processed/):
    - trusted_municipios_eda.parquet (escolaridade, pix, agencias)
    - analytics_ipb_v3_presenca_completa.parquet (ipb V3, correspondentes, CEMPRE)
    - modelagem_resultados.parquet (arquetipo, cluster)
    - modelagem.parquet (features e alvo da classificacao)

Outputs:
    - docs/assets/data/*.json (um por figura)

Nota metodologica: a media de escolaridade usada na linha do histograma e a
media simples entre municipios (cada municipio pesa igual, coerente com o
histograma e com o desenho do IPB). A media ponderada pela populacao sobe
para ~52%, porque as grandes cidades sao mais escolarizadas; a diferenca e
ela mesma um achado de equidade urbano/rural, citada nas notas do slide.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import auc, roc_curve
from sklearn.model_selection import train_test_split

from src.analytics.modelagem import FEATURES_SEM_PRESENCA

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
ROTULO_ESTRATO = {
    "pequena": "Pequena (<50 mil)",
    "media": "Média (50–500 mil)",
    "grande": "Grande (>500 mil)",
}

# Features do radar de arquetipos (chave -> rotulo curto pt-BR).
FEATURES_RADAR = {
    "pib_per_capita": "PIB pc",
    "rendimento_domiciliar_per_capita": "Renda dom.",
    "pix_per_capita_12m": "Pix pc",
    "banda_larga_fixa_por_100_hab": "Banda larga",
    "escolaridade_ensino_medio_pct": "Escolaridade",
    "empregos_formais_por_1000_hab": "Empregos formais",
    "unidades_alojamento_alimentacao_por_1000_hab": "Alojamento",
    "agencias_por_100k_hab": "Agências",
    "correspondentes_por_100k_hab": "Correspondentes",
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
        height=460,
    )
    return gravar(fig, "fig_espelho_escolaridade_hist.json")


def fig_escolaridade_extremos(base: pd.DataFrame) -> Path:
    """Barras combinadas das 10 cidades mais altas e 10 mais baixas em escolaridade."""
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


def fig_pix_agencias(base: pd.DataFrame) -> Path:
    """Dispersão Pix x agências com cor por correspondentes (rede paralela)."""
    fig = go.Figure()
    fig.add_scatter(
        x=base["agencias_por_100k_hab"] + 0.05,
        y=base["pix_per_capita_12m"],
        mode="markers",
        marker=dict(
            size=7,
            color=base["correspondentes_por_100k_hab"],
            colorscale="YlGnBu",
            showscale=True,
            colorbar=dict(title="Corresp.<br>/100 mil"),
            opacity=0.65,
        ),
        text=base["nome_municipio"] + " (" + base["sigla_uf"] + ")",
        customdata=base[["agencias_por_100k_hab", "correspondentes_por_100k_hab"]],
        hovertemplate=(
            "%{text}<br>Pix per capita: R$ %{y:,.0f}"
            "<br>Agências /100 mil: %{customdata[0]:.1f} · Correspondentes /100 mil: %{customdata[1]:.0f}"
            "<extra></extra>"
        ).replace(",", "X").replace(".", ",").replace("X", "."),
    )
    fig.update_layout(
        **LAYOUT_BASE,
        title="Pix alto não pede licença pra agência: onde uma é rara, a outra rede cresce",
        xaxis_title="Agências por 100 mil hab (escala log)",
        yaxis_title="Pix per capita, 12m (escala log)",
        height=480,
    )
    fig.update_xaxes(type="log")
    fig.update_yaxes(type="log")
    return gravar(fig, "fig_espelho_pix_agencias.json")


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
        title="O interior pobre sem rede é o maior arquétipo; o turismo rico sem banco é o achado",
        xaxis_title="",
        yaxis_title="Nº de municípios",
        showlegend=False,
        height=440,
    )
    return gravar(fig, "fig_arquetipos_barras.json")


def fig_arquetipos_radar(base: pd.DataFrame) -> Path:
    """Radar das medias padronizadas por arquetipo, com dropdown de selecao."""
    faltantes = [f for f in FEATURES_RADAR if f not in base.columns]
    if faltantes:
        raise ValueError(f"features ausentes na base: {faltantes}")
    features = list(FEATURES_RADAR)
    z = (base[features] - base[features].mean()) / base[features].std()
    z["cluster_kmeans"] = base["cluster_kmeans"]
    perfil = z.groupby("cluster_kmeans")[features].mean()
    ordem = sorted(perfil.index)
    arquetipos = base.groupby("cluster_kmeans")["arquetipo"].first().reindex(ordem)

    theta = [FEATURES_RADAR[f] for f in features] + [FEATURES_RADAR[features[0]]]
    fig = go.Figure()
    botoes = []
    for i, cl in enumerate(ordem):
        valores = perfil.loc[cl].tolist()
        valores_fechados = valores + [valores[0]]
        visiveis = [j == i for j in range(len(ordem))]
        fig.add_scatterpolar(
            r=valores_fechados,
            theta=theta,
            fill="toself",
            fillcolor=hex_para_rgba(CORES_ARQUETIPOS[arquetipos[cl]], 0.18),
            line_color=CORES_ARQUETIPOS[arquetipos[cl]],
            name=ROTULO_ARQUETIPO[arquetipos[cl]],
            visible=(i == 0),
            hovertemplate="%{theta}: %{r:.1f} desvios<extra></extra>".replace(".", ","),
        )
        botoes.append(
            {
                "label": ROTULO_ARQUETIPO[arquetipos[cl]],
                "method": "update",
                "args": [{"visible": visiveis}, {"title": f"Assinatura: {ROTULO_ARQUETIPO[arquetipos[cl]]}"}],
            }
        )
    fig.update_layout(
        **LAYOUT_BASE,
        title=f"Assinatura: {ROTULO_ARQUETIPO[arquetipos[ordem[0]]]}",
        updatemenus=[{"buttons": botoes, "direction": "down", "x": 1.0, "y": 1.12, "showactive": True}],
        polar=dict(radialaxis=dict(visible=True, range=[-2.2, 2.2])),
        height=480,
        margin={"l": 60, "r": 80, "t": 80, "b": 55},
    )
    return gravar(fig, "fig_arquetipos_radar.json")


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
        height=460,
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
        margin={"l": 60, "r": 30, "t": 70, "b": 110},
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
        fig_escolaridade_extremos(base),
        fig_pix_top15(base),
        fig_pix_agencias(base),
        fig_arquetipos_barras(base),
        fig_arquetipos_radar(base),
        fig_classificacao_roc(),
        fig_ipb_por_arquetipo(base),
    ]
    validar_jsons(caminhos)
    logger.info("Concluído: %d figuras interativas geradas em %s.", len(caminhos), SAIDA_DIR)


if __name__ == "__main__":
    main()
