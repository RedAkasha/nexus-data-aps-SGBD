"""Dashboard estatistico (Etapa 06) - tudo calculado sobre os dados do banco."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import db
import ui

st.title("Painel de equidade · APS Recife")
st.caption("Dados fictícios do banco `nexusdata_etapa02`. Cada número abaixo vem de uma "
           "consulta SQL ao MySQL, mostrada no rodapé de cada bloco.")

# ------------------------------------------------------------------ filtros
cg = ui.cargas()
mapa = dict(zip(cg["id_carga"], cg["rotulo"]))
ids = cg["id_carga"].tolist()
dsdf = ui.distritos()

f1, f2, f3 = st.columns([2.2, 2, 1.3])
ini, fim = f1.select_slider("Período (cargas)", options=ids, value=(ids[0], ids[-1]),
                            format_func=lambda i: mapa[i].split(" · ")[1] + f" (C{i})")
sel_ds = f2.multiselect("Distritos Sanitários", dsdf["id_ds"].tolist(),
                        default=dsdf["id_ds"].tolist(),
                        format_func=dict(zip(dsdf["id_ds"], dsdf["nome"])).get)
acao = f3.radio("Equipes", ["todas", "com", "sem"], horizontal=False,
                format_func={"todas": "Todas", "com": "Com ação formativa",
                             "sem": "Sem ação formativa"}.get)
if not sel_ds:
    sel_ds = dsdf["id_ds"].tolist()
P = {"ini": ini, "fim": fim, "ds": tuple(sel_ds), "acao": acao}
st.caption(f"Carga de referência para os retratos: **{mapa[fim]}** (fim do período escolhido).")

FILTRO_V = """v.id_ds IN %(ds)s
  AND (%(acao)s = 'todas'
       OR EXISTS (SELECT 1 FROM ACAO_FORMATIVA af WHERE af.ine = v.ine) = (%(acao)s = 'com'))"""
FILTRO_SC = """u.id_ds IN %(ds)s
  AND (%(acao)s = 'todas'
       OR EXISTS (SELECT 1 FROM ACAO_FORMATIVA af WHERE af.ine = sc.ine) = (%(acao)s = 'com'))"""

# ------------------------------------------------------------------ séries
SQL_SERIE = f"""
SELECT v.id_carga, MAX(v.periodo_ref_fim) AS fim,
       SUM(v.ativos) AS ativos,
       SUM(v.populacao_negra) AS populacao_negra,
       SUM(v.publico_lgbt) AS publico_lgbt,
       SUM(v.lgbt_sem_informacao) AS lgbt_sem_informacao,
       SUM(v.pessoas_com_deficiencia) AS pessoas_com_deficiencia,
       ROUND(100 * SUM(v.raca_cor_preenchida) / SUM(v.ativos), 1) AS pct_raca,
       ROUND(100 * SUM(v.orientacao_preenchida) / SUM(v.ativos), 1) AS pct_orientacao,
       ROUND(100 * SUM(v.identidade_preenchida) / SUM(v.ativos), 1) AS pct_identidade,
       ROUND(100 * SUM(v.com_nome_social) / SUM(v.ativos), 1) AS pct_nome_social
FROM VW_PERFIL_EQUIDADE_EQUIPE v
WHERE v.id_carga BETWEEN %(ini)s AND %(fim)s
  AND {FILTRO_V}
GROUP BY v.id_carga
ORDER BY v.id_carga
"""
SQL_INC_SERIE = f"""
SELECT sc.id_carga, COUNT(*) AS inconsistencias
FROM INCONSISTENCIA i
JOIN SITUACAO_CADASTRAL sc ON sc.cns = i.cns AND sc.id_carga = i.id_carga
JOIN EQUIPE e ON e.ine = i.ine_responsavel
JOIN UNIDADE_SAUDE u ON u.cnes = e.cnes
WHERE i.id_carga BETWEEN %(ini)s AND %(fim)s
  AND {FILTRO_SC.replace('sc.ine', 'i.ine_responsavel')}
GROUP BY sc.id_carga
"""
serie = db.consultar(SQL_SERIE, P)
if serie.empty:
    st.warning("Nenhum cadastro ativo para os filtros escolhidos.")
    st.stop()
serie = serie.merge(db.consultar(SQL_INC_SERIE, P), on="id_carga", how="left").fillna({"inconsistencias": 0})
serie["fim"] = pd.to_datetime(serie["fim"])
for c in ["populacao_negra", "publico_lgbt", "pessoas_com_deficiencia"]:
    serie[f"pct_{c}"] = 100 * serie[c] / serie["ativos"]
serie["inc_100"] = 100 * serie["inconsistencias"] / serie["ativos"]

atual = serie.iloc[-1]
anterior = serie.iloc[-2] if len(serie) > 1 else None
primeiro = serie.iloc[0]

SQL_IDADE_RESUMO = f"""
SELECT ROUND(AVG(TIMESTAMPDIFF(YEAR, p.dt_nascimento, c.periodo_ref_fim)), 1) AS media
FROM SITUACAO_CADASTRAL sc
JOIN PESSOA p ON p.cns = sc.cns
JOIN CARGA c ON c.id_carga = sc.id_carga
JOIN EQUIPE e ON e.ine = sc.ine
JOIN UNIDADE_SAUDE u ON u.cnes = e.cnes
WHERE sc.id_carga = %(fim)s AND sc.situacao = 'ATIVO' AND p.cns_principal IS NULL
  AND {FILTRO_SC}
"""
idade_media = db.valor(SQL_IDADE_RESUMO, P)


def delta(atual_v, ant_v, sufixo="", casas=0):
    if ant_v is None:
        return None
    d = atual_v - ant_v
    return f"{d:+.{casas}f}".replace(".", ",") + sufixo


# ------------------------------------------------------------------ indicadores
k = st.columns(4)
d_ativos = delta(atual["ativos"], anterior["ativos"] if anterior is not None else None)
ui.kpi(k[0], "Cadastros ativos", ui.num(atual["ativos"]),
       f"{d_ativos} vs carga anterior" if d_ativos else None,
       "Pessoas com situação ATIVO, sem duplicidades (regra 5).")
ui.kpi(k[1], "População negra", ui.pct(atual["pct_populacao_negra"]),
       f"{ui.num(atual['populacao_negra'])} pessoas", "Raça/cor preta ou parda.", "off")
ui.kpi(k[2], "LGBTQIAPN+", ui.pct(atual["pct_publico_lgbt"]),
       f"{ui.num(atual['lgbt_sem_informacao'])} sem informação",
       "Orientação ≠ heterossexual ou identidade ≠ cisgênero; quem não informou fica à parte.", "off")
ui.kpi(k[3], "Pessoas com deficiência", ui.pct(atual["pct_pessoas_com_deficiencia"]),
       f"{ui.num(atual['pessoas_com_deficiencia'])} pessoas", None, "off")
k = st.columns(4)
ui.kpi(k[0], "Completude · orientação sexual", ui.pct(atual["pct_orientacao"]),
       delta(atual["pct_orientacao"], primeiro["pct_orientacao"], " p.p.", 1) + " no período",
       "Campo preenchido com categoria válida (código 9 não conta).")
ui.kpi(k[1], "Completude · identidade de gênero", ui.pct(atual["pct_identidade"]),
       delta(atual["pct_identidade"], primeiro["pct_identidade"], " p.p.", 1) + " no período")
ui.kpi(k[2], "Inconsistências por 100 cadastros", ui.num(atual["inc_100"], 1),
       delta(atual["inc_100"], primeiro["inc_100"], "", 1) + " no período",
       "Inconsistências registradas na carga por 100 cadastros ativos.", "inverse")
ui.kpi(k[3], "Idade média", f"{ui.num(idade_media, 1)} anos", None,
       "Idade no fim do período da carga (não armazenada).")

aba1, aba2, aba3, aba4 = st.tabs(["Visão geral", "Perfil sociodemográfico",
                                  "Qualidade do registro", "Estatística descritiva"])

# datas das ações formativas (faixa sombreada nos gráficos temporais)
acoes = db.consultar("SELECT MIN(dt_acao) AS ini, MAX(dt_acao) AS fim FROM ACAO_FORMATIVA")


def faixa_acoes(fig):
    if not acoes.empty and acoes.iat[0, 0] is not None:
        fig.add_vrect(x0=acoes.iat[0, 0], x1=acoes.iat[0, 1], fillcolor="#eda100", opacity=0.12,
                      line_width=0, annotation_text="ações formativas",
                      annotation_position="top left", annotation_font_color=ui.INK2)
    return fig


# ================================================================== aba 1
with aba1:
    c1, c2 = st.columns(2)
    with c1:
        longo = serie.melt(id_vars=["fim"], value_vars=["ativos", "populacao_negra",
                           "publico_lgbt", "pessoas_com_deficiencia"],
                           var_name="serie", value_name="pessoas")
        nomes = {"ativos": "Cadastros ativos", "populacao_negra": "População negra",
                 "publico_lgbt": "LGBTQIAPN+", "pessoas_com_deficiencia": "Pessoas com deficiência"}
        longo["serie"] = longo["serie"].map(nomes)
        fig = px.line(longo, x="fim", y="pessoas", color="serie", markers=False,
                      title="Evolução dos cadastros ativos e dos públicos",
                      labels={"fim": "Fim do período da carga", "pessoas": "Pessoas"})
        fig.update_traces(hovertemplate="%{x|%b/%Y}: %{y}")
        ui.grafico(fig)
        if len(serie) >= 3:
            x = np.arange(len(serie))
            a, b = np.polyfit(x, serie["ativos"], 1)
            r2 = np.corrcoef(x, serie["ativos"])[0, 1] ** 2
            st.caption(f"Tendência linear dos ativos: **{ui.num(a, 1)} cadastros por carga** "
                       f"(R² = {ui.num(r2, 2)}).")
    with c2:
        longo = serie.melt(id_vars=["fim"], value_vars=["pct_raca", "pct_orientacao", "pct_identidade"],
                           var_name="campo", value_name="pct")
        longo["campo"] = longo["campo"].map({"pct_raca": "Raça/cor", "pct_orientacao": "Orientação sexual",
                                             "pct_identidade": "Identidade de gênero"})
        fig = px.line(longo, x="fim", y="pct", color="campo",
                      title="Completude dos marcadores de equidade (%)",
                      labels={"fim": "Fim do período da carga", "pct": "% preenchido"})
        fig.update_yaxes(range=[0, 102])
        ui.grafico(faixa_acoes(fig))
        st.caption("A faixa amarela marca o período das ações formativas (ACAO_FORMATIVA).")

    c3, c4 = st.columns(2)
    SQL_DS = f"""
    SELECT v.distrito,
           ROUND(100 * SUM(v.populacao_negra) / SUM(v.ativos), 1) AS pct_negra,
           ROUND(100 * SUM(v.publico_lgbt) / SUM(v.ativos), 1) AS pct_lgbt,
           ROUND(100 * SUM(v.pessoas_com_deficiencia) / SUM(v.ativos), 1) AS pct_pcd,
           ROUND(100 * SUM(v.raca_cor_preenchida) / SUM(v.ativos), 1) AS pct_raca,
           ROUND(100 * SUM(v.orientacao_preenchida) / SUM(v.ativos), 1) AS pct_orientacao,
           ROUND(100 * SUM(v.identidade_preenchida) / SUM(v.ativos), 1) AS pct_identidade,
           SUM(v.ativos) AS ativos
    FROM VW_PERFIL_EQUIDADE_EQUIPE v
    WHERE v.id_carga = %(fim)s AND {FILTRO_V}
    GROUP BY v.id_ds, v.distrito
    ORDER BY v.id_ds
    """
    por_ds = db.consultar(SQL_DS, P)
    with c3:
        longo = por_ds.melt(id_vars="distrito", value_vars=["pct_negra", "pct_lgbt", "pct_pcd"],
                            var_name="publico", value_name="pct")
        longo["publico"] = longo["publico"].map({"pct_negra": "População negra", "pct_lgbt": "LGBTQIAPN+",
                                                 "pct_pcd": "Pessoas com deficiência"})
        fig = px.bar(longo, x="distrito", y="pct", color="publico", barmode="group",
                     title="Públicos das políticas por distrito (% dos ativos)",
                     labels={"distrito": "", "pct": "% dos ativos"})
        ui.grafico(fig)
    with c4:
        eixos = {"pct_negra": "% pop. negra", "pct_lgbt": "% LGBTQIAPN+", "pct_pcd": "% PcD",
                 "pct_raca": "Compl. raça/cor", "pct_orientacao": "Compl. orientação",
                 "pct_identidade": "Compl. identidade"}
        escolha = st.selectbox("Distrito no radar", por_ds["distrito"].tolist(), key="radar")
        tot = por_ds[list(eixos)].multiply(por_ds["ativos"], axis=0).sum() / por_ds["ativos"].sum()
        linha = por_ds.set_index("distrito").loc[escolha]
        fig = go.Figure()
        cats = list(eixos.values())
        fig.add_trace(go.Scatterpolar(r=[tot[c] for c in eixos] + [tot["pct_negra"]], theta=cats + cats[:1],
                                      name="Seleção completa", line_color=ui.MUDO, fill="toself",
                                      fillcolor="rgba(137,135,129,0.10)"))
        fig.add_trace(go.Scatterpolar(r=[linha[c] for c in eixos] + [linha["pct_negra"]], theta=cats + cats[:1],
                                      name=escolha, line_color=ui.COR_DS.get(escolha, ui.CORES[0]),
                                      fill="toself", fillcolor=ui.rgba(ui.COR_DS.get(escolha, ui.CORES[0]), 0.15)))
        fig.update_layout(title="Perfil do distrito x conjunto selecionado",
                          polar=dict(radialaxis=dict(range=[0, 100], gridcolor=ui.GRADE),
                                     angularaxis=dict(gridcolor=ui.GRADE)))
        ui.grafico(fig, 330)
    ui.mostrar_sql(SQL_SERIE + "\n-- por distrito:\n" + SQL_DS, P, "SQL dos gráficos desta aba")

# ================================================================== aba 2
with aba2:
    c1, c2 = st.columns(2)
    SQL_RACA = f"""
    SELECT rc.descricao AS raca_cor, COUNT(*) AS pessoas
    FROM SITUACAO_CADASTRAL sc
    JOIN PESSOA p ON p.cns = sc.cns
    JOIN RACA_COR rc ON rc.id_raca_cor = sc.id_raca_cor
    JOIN EQUIPE e ON e.ine = sc.ine
    JOIN UNIDADE_SAUDE u ON u.cnes = e.cnes
    WHERE sc.id_carga = %(fim)s AND sc.situacao = 'ATIVO' AND p.cns_principal IS NULL
      AND {FILTRO_SC}
    GROUP BY rc.id_raca_cor, rc.descricao
    ORDER BY rc.id_raca_cor
    """
    raca = db.consultar(SQL_RACA, P)
    with c1:
        ordem = ["Branca", "Preta", "Parda", "Amarela", "Indígena", "Sem informação"]
        fig = px.pie(raca, names="raca_cor", values="pessoas", hole=0.55,
                     title="Distribuição por raça/cor", category_orders={"raca_cor": ordem},
                     color="raca_cor", color_discrete_map=dict(zip(ordem, ui.CORES[:5] + [ui.MUDO])))
        fig.update_traces(textinfo="percent", sort=False, marker_line_color="white", marker_line_width=2)
        ui.grafico(fig)
    SQL_PIRAMIDE = f"""
    SELECT fn_faixa_etaria(p.dt_nascimento, c.periodo_ref_fim) AS faixa_etaria,
           p.sexo, COUNT(*) AS pessoas
    FROM SITUACAO_CADASTRAL sc
    JOIN PESSOA p ON p.cns = sc.cns
    JOIN CARGA c ON c.id_carga = sc.id_carga
    JOIN EQUIPE e ON e.ine = sc.ine
    JOIN UNIDADE_SAUDE u ON u.cnes = e.cnes
    WHERE sc.id_carga = %(fim)s AND sc.situacao = 'ATIVO' AND p.cns_principal IS NULL
      AND {FILTRO_SC}
    GROUP BY faixa_etaria, p.sexo
    """
    pir = db.consultar(SQL_PIRAMIDE, P)
    with c2:
        faixas = ["0 a 9", "10 a 19", "20 a 39", "40 a 59", "60 ou mais"]
        fig = go.Figure()
        for sexo, nome, cor, sinal in [("F", "Feminino", ui.CORES[0], 1), ("M", "Masculino", ui.CORES[1], -1)]:
            d = pir[pir["sexo"] == sexo].set_index("faixa_etaria").reindex(faixas).fillna(0)
            fig.add_bar(y=faixas, x=sinal * d["pessoas"], orientation="h", name=nome, marker_color=cor,
                        customdata=d["pessoas"], hovertemplate="%{y}: %{customdata} pessoas")
        maxv = pir["pessoas"].max() if not pir.empty else 1
        passo = max(5, int(np.ceil(maxv / 3 / 5) * 5))
        marcas = list(range(-3 * passo, 3 * passo + 1, passo))
        fig.update_layout(barmode="relative", title="Pirâmide etária (faixas da função fn_faixa_etaria)",
                          xaxis=dict(tickvals=marcas, ticktext=[ui.num(abs(m)) for m in marcas],
                                     range=[-3.2 * passo, 3.2 * passo],
                                     title="Pessoas"), yaxis_title="")
        ui.grafico(fig)
        n_i = int(pir.loc[pir["sexo"] == "I", "pessoas"].sum())
        if n_i:
            st.caption(f"{n_i} pessoa(s) com sexo 'I' (indeterminado) ficam fora da pirâmide.")

    c3, c4 = st.columns(2)
    SQL_IDADES = f"""
    SELECT TIMESTAMPDIFF(YEAR, p.dt_nascimento, c.periodo_ref_fim) AS idade
    FROM SITUACAO_CADASTRAL sc
    JOIN PESSOA p ON p.cns = sc.cns
    JOIN CARGA c ON c.id_carga = sc.id_carga
    JOIN EQUIPE e ON e.ine = sc.ine
    JOIN UNIDADE_SAUDE u ON u.cnes = e.cnes
    WHERE sc.id_carga = %(fim)s AND sc.situacao = 'ATIVO' AND p.cns_principal IS NULL
      AND {FILTRO_SC}
    """
    SQL_STATS_IDADE = f"""
    WITH valores AS ({SQL_IDADES.replace('AS idade', 'AS x')}),
    ordenados AS (
        SELECT x, ROW_NUMBER() OVER (ORDER BY x) AS rn, COUNT(*) OVER () AS n FROM valores
    )
    SELECT COUNT(*) AS n,
           ROUND(AVG(x), 2) AS media,
           (SELECT AVG(x) FROM ordenados
            WHERE rn IN (FLOOR((n + 1) / 2), CEIL((n + 1) / 2))) AS mediana,
           (SELECT x FROM valores GROUP BY x ORDER BY COUNT(*) DESC, x LIMIT 1) AS moda,
           ROUND(VAR_SAMP(x), 2) AS variancia,
           ROUND(STDDEV_SAMP(x), 2) AS desvio_padrao,
           MIN(x) AS minimo, MAX(x) AS maximo
    FROM valores
    """
    idades = db.consultar(SQL_IDADES, P)
    est = db.consultar(SQL_STATS_IDADE, P).iloc[0]
    with c3:
        fig = go.Figure()
        fig.add_histogram(x=idades["idade"], xbins=dict(start=0, size=5), name="Pessoas",
                          marker_color=ui.CORES[0], marker_line_color="white", marker_line_width=1,
                          hovertemplate="%{x} anos: %{y} pessoas<extra></extra>")
        topo = int((idades["idade"] // 5).value_counts().max()) if not idades.empty else 1
        for v, nome, cor, traco in [(est["media"], "média", ui.INK, "solid"),
                                    (est["mediana"], "mediana", ui.CORES[1], "dash"),
                                    (est["moda"], "moda", ui.CORES[6], "dot")]:
            fig.add_scatter(x=[float(v), float(v)], y=[0, topo * 1.05], mode="lines",
                            name=f"{nome}: {ui.num(float(v), 1)}", line=dict(color=cor, width=2, dash=traco))
        fig.update_layout(title="Distribuição das idades (classes de 5 anos)", xaxis_title="Idade (anos)",
                          yaxis_title="Pessoas", bargap=0.04)
        ui.grafico(fig)
        st.caption(f"Medidas calculadas no MySQL: n = {int(est['n'])}, média {ui.num(est['media'], 1)}, "
                   f"mediana {ui.num(float(est['mediana']), 1)}, moda {int(est['moda'])}, variância "
                   f"{ui.num(est['variancia'], 1)}, desvio-padrão {ui.num(est['desvio_padrao'], 1)} anos.")
    SQL_DEF = f"""
    SELECT ds.nome AS distrito, td.descricao AS tipo_deficiencia,
           COUNT(DISTINCT sc.cns) AS pessoas
    FROM SITUACAO_CADASTRAL sc
    JOIN PESSOA p ON p.cns = sc.cns
    JOIN SITUACAO_DEFICIENCIA sd ON sd.cns = sc.cns AND sd.id_carga = sc.id_carga
    JOIN TIPO_DEFICIENCIA td ON td.id_tipo_deficiencia = sd.id_tipo_deficiencia
    JOIN EQUIPE e ON e.ine = sc.ine
    JOIN UNIDADE_SAUDE u ON u.cnes = e.cnes
    JOIN DISTRITO_SANITARIO ds ON ds.id_ds = u.id_ds
    WHERE sc.id_carga = %(fim)s AND sc.situacao = 'ATIVO' AND p.cns_principal IS NULL
      AND {FILTRO_SC}
    GROUP BY ds.id_ds, ds.nome, td.id_tipo_deficiencia, td.descricao
    ORDER BY ds.id_ds, td.id_tipo_deficiencia
    """
    defi = db.consultar(SQL_DEF, P)
    with c4:
        fig = px.bar(defi, x="distrito", y="pessoas", color="tipo_deficiencia",
                     title="Pessoas com deficiência por tipo e distrito",
                     labels={"distrito": "", "pessoas": "Pessoas", "tipo_deficiencia": "Tipo"},
                     category_orders={"tipo_deficiencia": ["Auditiva", "Visual", "Física", "Intelectual", "Outra"]})
        fig.update_traces(marker_line_color="white", marker_line_width=2)
        ui.grafico(fig)
    ui.mostrar_sql("\n\n".join([SQL_RACA, SQL_PIRAMIDE, SQL_STATS_IDADE, SQL_DEF]), P, "SQL dos gráficos desta aba")

# ================================================================== aba 3
SQL_EQUIPES = f"""
SELECT v.id_ds, v.distrito, v.ine, v.equipe, v.ativos, v.pct_orientacao, v.pct_identidade,
       COALESCE(inc.qtd, 0) AS inconsistencias,
       ROUND(100 * COALESCE(inc.qtd, 0) / v.ativos, 1) AS inc_100,
       CASE WHEN EXISTS (SELECT 1 FROM ACAO_FORMATIVA af WHERE af.ine = v.ine)
            THEN 'Com ação formativa' ELSE 'Sem ação formativa' END AS capacitacao
FROM VW_PERFIL_EQUIDADE_EQUIPE v
LEFT JOIN (SELECT ine_responsavel, COUNT(*) AS qtd FROM INCONSISTENCIA
           WHERE id_carga = %(fim)s GROUP BY ine_responsavel) inc
       ON inc.ine_responsavel = v.ine
WHERE v.id_carga = %(fim)s AND {FILTRO_V}
"""
with aba3:
    equipes = db.consultar(SQL_EQUIPES, P)
    c1, c2 = st.columns(2)
    with c1:
        fig = px.box(equipes, x="distrito", y="pct_orientacao", points="all", color="distrito",
                     color_discrete_map=ui.COR_DS, hover_data=["equipe", "ativos"],
                     title="Completude de orientação sexual por equipe",
                     labels={"distrito": "", "pct_orientacao": "% preenchido na equipe"})
        fig.update_layout(showlegend=False)
        fig.update_traces(marker_size=8)
        ui.grafico(fig)
        st.caption("Cada ponto é uma equipe; a caixa mostra mediana e quartis da distribuição entre equipes.")
    with c2:
        SQL_CORR = f"""
        WITH eq AS ({SQL_EQUIPES})
        SELECT COUNT(*) AS n,
               ROUND((AVG(pct_orientacao * inc_100) - AVG(pct_orientacao) * AVG(inc_100))
                     / NULLIF(STDDEV_POP(pct_orientacao) * STDDEV_POP(inc_100), 0), 3) AS pearson
        FROM eq
        """
        corr = db.consultar(SQL_CORR, P).iloc[0]
        fig = px.scatter(equipes, x="pct_orientacao", y="inc_100", color="capacitacao",
                         hover_data=["equipe", "distrito", "ativos"],
                         color_discrete_map={"Com ação formativa": ui.CORES[0], "Sem ação formativa": ui.CORES[1]},
                         title="Completude x inconsistências por equipe",
                         labels={"pct_orientacao": "% orientação sexual preenchida",
                                 "inc_100": "Inconsistências por 100 cadastros", "capacitacao": ""})
        if len(equipes) >= 3 and equipes["pct_orientacao"].std() > 0:
            a, b = np.polyfit(equipes["pct_orientacao"], equipes["inc_100"], 1)
            xs = np.linspace(equipes["pct_orientacao"].min(), equipes["pct_orientacao"].max(), 2)
            fig.add_scatter(x=xs, y=a * xs + b, mode="lines", name="reta de regressão",
                            line=dict(color=ui.MUDO, dash="dash", width=2))
        fig.update_traces(selector=dict(mode="markers"), marker=dict(size=10, line=dict(color="white", width=2)))
        ui.grafico(fig)
        r = corr["pearson"]
        st.caption(f"Correlação de Pearson calculada no MySQL: **r = {ui.num(r, 2)}** "
                   f"(n = {int(corr['n'])} equipes)." if r is not None else "Correlação indisponível.")

    c3, c4 = st.columns(2)
    SQL_GRUPO = f"""
    SELECT v.id_carga, MAX(v.periodo_ref_fim) AS fim,
           CASE WHEN EXISTS (SELECT 1 FROM ACAO_FORMATIVA af WHERE af.ine = v.ine)
                THEN 'Com ação formativa' ELSE 'Sem ação formativa' END AS capacitacao,
           ROUND(100 * SUM(v.orientacao_preenchida) / SUM(v.ativos), 1) AS pct_orientacao
    FROM VW_PERFIL_EQUIDADE_EQUIPE v
    WHERE v.id_carga BETWEEN %(ini)s AND %(fim)s AND v.id_ds IN %(ds)s
    GROUP BY v.id_carga, capacitacao
    ORDER BY v.id_carga
    """
    grupo = db.consultar(SQL_GRUPO, P)
    with c3:
        fig = px.line(grupo, x="fim", y="pct_orientacao", color="capacitacao",
                      color_discrete_map={"Com ação formativa": ui.CORES[0], "Sem ação formativa": ui.CORES[1]},
                      title="Efeito da ação formativa na completude (orientação sexual)",
                      labels={"fim": "Fim do período da carga", "pct_orientacao": "% preenchido",
                              "capacitacao": ""})
        fig.update_yaxes(range=[0, 102])
        ui.grafico(faixa_acoes(fig))
        st.caption("Ignora o filtro de equipes, para comparar os dois grupos.")
    SQL_HEAT = f"""
    SELECT ds.nome AS distrito, ti.descricao AS tipo_inconsistencia, COUNT(*) AS quantidade
    FROM INCONSISTENCIA i
    JOIN TIPO_INCONSISTENCIA ti ON ti.id_tipo_inconsistencia = i.id_tipo_inconsistencia
    JOIN EQUIPE e ON e.ine = i.ine_responsavel
    JOIN UNIDADE_SAUDE u ON u.cnes = e.cnes
    JOIN DISTRITO_SANITARIO ds ON ds.id_ds = u.id_ds
    WHERE i.id_carga BETWEEN %(ini)s AND %(fim)s
      AND {FILTRO_SC.replace('sc.ine', 'i.ine_responsavel')}
    GROUP BY ds.id_ds, ds.nome, ti.id_tipo_inconsistencia, ti.descricao
    """
    heat = db.consultar(SQL_HEAT, P)
    with c4:
        if heat.empty:
            st.info("Sem inconsistências no período.")
        else:
            mat = heat.pivot(index="tipo_inconsistencia", columns="distrito", values="quantidade").fillna(0)
            fig = px.imshow(mat, text_auto=True, aspect="auto", color_continuous_scale=ui.SEQ,
                            title="Inconsistências no período: tipo x distrito",
                            labels={"x": "", "y": "", "color": "Qtd."})
            fig.update_traces(xgap=2, ygap=2)
            ui.grafico(fig)
    ui.mostrar_sql("\n\n".join([SQL_EQUIPES, SQL_CORR, SQL_GRUPO, SQL_HEAT]), P, "SQL dos gráficos desta aba")

# ================================================================== aba 4
with aba4:
    st.markdown("Medidas de posição e dispersão calculadas **no MySQL** (funções de agregação e de janela) "
                "para a carga de referência e os filtros escolhidos.")
    variaveis = {
        "Idade das pessoas ativas (anos)": SQL_IDADES.replace("AS idade", "AS x"),
        "Cadastros ativos por equipe": f"SELECT v.ativos AS x FROM VW_PERFIL_EQUIDADE_EQUIPE v WHERE v.id_carga = %(fim)s AND {FILTRO_V}",
        "Completude de orientação sexual por equipe (%)": f"SELECT v.pct_orientacao AS x FROM VW_PERFIL_EQUIDADE_EQUIPE v WHERE v.id_carga = %(fim)s AND {FILTRO_V}",
        "Completude de identidade de gênero por equipe (%)": f"SELECT v.pct_identidade AS x FROM VW_PERFIL_EQUIDADE_EQUIPE v WHERE v.id_carga = %(fim)s AND {FILTRO_V}",
        "Inconsistências por 100 cadastros, por equipe": f"SELECT eq.inc_100 AS x FROM ({SQL_EQUIPES}) eq",
    }
    MODELO = """
    WITH valores AS ({fonte}),
    ordenados AS (
        SELECT x, ROW_NUMBER() OVER (ORDER BY x) AS rn, COUNT(*) OVER () AS n FROM valores
    )
    SELECT COUNT(*) AS n,
           ROUND(AVG(x), 2) AS media,
           (SELECT ROUND(AVG(x), 2) FROM ordenados
            WHERE rn IN (FLOOR((n + 1) / 2), CEIL((n + 1) / 2))) AS mediana,
           (SELECT x FROM valores GROUP BY x ORDER BY COUNT(*) DESC, x LIMIT 1) AS moda,
           ROUND(VAR_SAMP(x), 2) AS variancia,
           ROUND(STDDEV_SAMP(x), 2) AS desvio_padrao,
           ROUND(100 * STDDEV_SAMP(x) / NULLIF(AVG(x), 0), 1) AS cv_pct,
           MIN(x) AS minimo,
           (SELECT x FROM ordenados WHERE rn = GREATEST(1, ROUND(0.25 * n)) LIMIT 1) AS q1,
           (SELECT x FROM ordenados WHERE rn = GREATEST(1, ROUND(0.75 * n)) LIMIT 1) AS q3,
           MAX(x) AS maximo
    FROM valores
    """
    linhas = []
    for nome, fonte in variaveis.items():
        r = db.consultar(MODELO.format(fonte=fonte), P)
        r.insert(0, "variável", nome)
        linhas.append(r)
    tabela = pd.concat(linhas, ignore_index=True)
    st.dataframe(tabela, hide_index=True, width="stretch",
                 column_config={"cv_pct": st.column_config.NumberColumn("CV (%)"),
                                "desvio_padrao": st.column_config.NumberColumn("desvio-padrão")})
    st.caption("Mediana pela média dos dois valores centrais; quartis pelo método do posto mais próximo; "
               "moda = valor mais frequente (menor valor em caso de empate); variância e desvio amostrais.")

    c1, c2 = st.columns(2)
    SQL_FREQ = f"""
    SELECT fn_faixa_etaria(p.dt_nascimento, c.periodo_ref_fim) AS faixa_etaria,
           COUNT(*) AS freq_absoluta,
           ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS freq_relativa_pct,
           ROUND(100 * SUM(COUNT(*)) OVER (ORDER BY MIN(p.dt_nascimento) DESC)
                 / SUM(COUNT(*)) OVER (), 1) AS freq_acumulada_pct
    FROM SITUACAO_CADASTRAL sc
    JOIN PESSOA p ON p.cns = sc.cns
    JOIN CARGA c ON c.id_carga = sc.id_carga
    JOIN EQUIPE e ON e.ine = sc.ine
    JOIN UNIDADE_SAUDE u ON u.cnes = e.cnes
    WHERE sc.id_carga = %(fim)s AND sc.situacao = 'ATIVO' AND p.cns_principal IS NULL
      AND {FILTRO_SC}
    GROUP BY faixa_etaria
    ORDER BY MIN(p.dt_nascimento) DESC
    """
    freq = db.consultar(SQL_FREQ, P)
    with c1:
        st.markdown("**Distribuição de frequências por faixa etária**")
        st.dataframe(freq, hide_index=True, width="stretch")
    with c2:
        fig = go.Figure()
        fig.add_bar(x=freq["faixa_etaria"], y=freq["freq_relativa_pct"], name="Frequência relativa",
                    marker_color=ui.CORES[0])
        fig.add_scatter(x=freq["faixa_etaria"], y=freq["freq_acumulada_pct"], name="Frequência acumulada",
                        mode="lines+markers", line_color=ui.CORES[1])
        fig.update_layout(title="Frequência relativa e acumulada (%)", yaxis_title="% das pessoas",
                          yaxis_range=[0, 105])
        ui.grafico(fig, 320)
    ui.mostrar_sql(MODELO.format(fonte="<variável>") + "\n\n" + SQL_FREQ, P, "SQL das estatísticas")
