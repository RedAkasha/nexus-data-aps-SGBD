"""Consultas das Etapas 03 e 04 e visoes, com parametros, tabela e grafico."""
from __future__ import annotations

import plotly.express as px
import streamlit as st

import db
import sql_consultas as S
import ui

st.title("Consultas e visões")
st.caption("As consultas C1–C8 são da Etapa 03; C9–C12 e as visões novas, da Etapa 04. "
           "A carga e o distrito viram parâmetros do SQL (`%(carga)s`, `%(ds)s`).")

aba_c, aba_v = st.tabs(["Consultas C1 a C12", "Visões"])


def desenhar(df, spec):
    tipo, x, y, cor = spec
    if df.empty:
        return
    titulo = None
    if tipo == "barra":
        fig = px.bar(df, x=x, y=y, color_discrete_sequence=[ui.CORES[0]])
    elif tipo == "barra_h":
        fig = px.bar(df, x=x, y=y, color=cor, orientation="h")
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
    elif tipo == "pizza":
        fig = px.pie(df, names=x, values=y, hole=0.55)
        fig.update_traces(marker_line_color="white", marker_line_width=2)
    elif tipo == "barras_agrupadas":
        longo = df.melt(id_vars=x, value_vars=y, var_name="medida", value_name="valor")
        fig = px.bar(longo, x=x, y="valor", color="medida", barmode="group")
    elif tipo == "barra_empilhada":
        fig = px.bar(df, x=x, y=y, color=cor)
        fig.update_traces(marker_line_color="white", marker_line_width=2)
    elif tipo == "barra_empilhada_cols":
        rot = df[x] + " · " + df["tipo_inconsistencia"]
        longo = df.assign(item=rot).melt(id_vars="item", value_vars=y, var_name="resultado", value_name="qtd")
        fig = px.bar(longo, x="qtd", y="item", color="resultado", orientation="h",
                     color_discrete_map={"acertos": ui.CORES[2], "nao_detectados": ui.CORES[1],
                                         "sem_gabarito": ui.MUDO})
        fig.update_traces(marker_line_color="white", marker_line_width=2)
    else:
        return
    fig.update_layout(title=titulo, xaxis_title="", yaxis_title="")
    ui.grafico(fig, 380)


with aba_c:
    chaves = list(S.CATALOGO)
    escolha = st.selectbox(
        "Consulta", chaves,
        format_func=lambda k: f"{k} · {S.CATALOGO[k]['titulo']}  ({S.CATALOGO[k]['etapa']} – {S.CATALOGO[k]['tecnica']})")
    q = S.CATALOGO[escolha]
    st.markdown(f"**{escolha} – {q['titulo']}**  \n{q['desc']}  \nTécnica: `{q['tecnica']}`")
    c1, c2 = st.columns(2)
    with c1:
        carga = ui.seletor_carga("cons_carga")
    ds = 0
    if q["ds"]:
        with c2:
            ds = ui.seletor_distrito("cons_ds")
    params = {"carga": carga, "ds": ds}
    try:
        df = db.consultar(q["sql"], params)
    except Exception as e:  # noqa: BLE001
        st.error(db.mensagem_erro(e))
        st.stop()
    m1, m2 = st.columns([3, 2])
    with m1:
        desenhar(df, q["grafico"])
    with m2:
        st.metric("Linhas retornadas", len(df))
        if escolha == "C10" and not df.empty:
            tp, gab, det = df["acertos"].sum(), (df["acertos"] + df["nao_detectados"]).sum(), \
                (df["acertos"] + df["sem_gabarito"]).sum()
            st.metric("Precisão geral", ui.pct(100 * tp / det if det else None))
            st.metric("Sensibilidade geral", ui.pct(100 * tp / gab if gab else None))
        if escolha == "C12" and not df.empty:
            st.metric("Saldo (entradas − saídas)", int(df["entradas"].sum() - df["saidas"].sum()))
    st.dataframe(df, hide_index=True, width="stretch")
    st.download_button("Baixar CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name=f"{escolha.lower()}_carga{carga}.csv", mime="text/csv")
    ui.mostrar_sql(q["sql"], params)

with aba_v:
    nome = st.selectbox("Visão", list(S.VISOES))
    v = S.VISOES[nome]
    st.markdown(f"**{nome}** ({v['etapa']}) – {v['desc']}")

    if nome == "VW_EVOLUCAO_CARGAS":
        cg = ui.cargas()
        mapa = dict(zip(cg["id_carga"], cg["rotulo"]))
        ids = cg["id_carga"].tolist()
        ini, fim = st.select_slider("Intervalo de cargas", options=ids, value=(ids[0], ids[-1]),
                                    format_func=mapa.get)
        params = {"carga_ini": ini, "carga": fim}
        df = db.consultar(v["sql"], params)
        serie = st.radio("Série", ["ativos", "negros", "lgbt"], horizontal=True,
                         format_func={"ativos": "Ativos", "negros": "População negra", "lgbt": "LGBTQIAPN+"}.get)
        col = {"ativos": "variacao_ativos", "negros": "variacao_negros", "lgbt": "variacao_lgbt"}[serie]
        d = df.dropna(subset=[col]).copy()
        d["sinal"] = d[col].apply(lambda x: "aumento" if x >= 0 else "redução")
        fig = px.bar(d, x="id_carga", y=col, color="sinal",
                     color_discrete_map={"aumento": ui.CORES[0], "redução": ui.CORES[1]},
                     title="Variação em relação à carga anterior (LAG)",
                     labels={"id_carga": "Carga", col: "Variação"})
        ui.grafico(fig, 320)
    elif nome == "VW_PERFIL_EQUIDADE_EQUIPE":
        c1, c2 = st.columns(2)
        with c1:
            carga = ui.seletor_carga("v1_carga")
        with c2:
            ds = ui.seletor_distrito("v1_ds")
        params = {"carga": carga, "ds": ds}
        df = db.consultar(v["sql"], params)
        if not df.empty:
            fig = px.scatter(df, x="pct_orientacao", y="pct_populacao_negra", size="ativos",
                             color="distrito", color_discrete_map=ui.COR_DS, hover_name="equipe",
                             title="Equipes: completude de orientação × % população negra (tamanho = ativos)",
                             labels={"pct_orientacao": "% orientação preenchida",
                                     "pct_populacao_negra": "% população negra"})
            ui.grafico(fig, 380)
    else:
        st.info("Regra 9 do minimundo: o perfil do usuário define o que ele vê. "
                "Escolha um usuário: perfis de equipe só enxergam o próprio território.")
        usuarios = db.consultar("""
            SELECT u.id_usuario, u.nome, u.login, p.nome AS perfil, p.abrangencia, u.ine
            FROM USUARIO u JOIN PERFIL p ON p.id_perfil = u.id_perfil
            ORDER BY u.id_usuario""")
        rot = {r.id_usuario: f"{r.nome} ({r.perfil})" for r in usuarios.itertuples()}
        c1, c2, c3 = st.columns(3)
        with c1:
            uid = st.selectbox("Ver como", usuarios["id_usuario"].tolist(), format_func=rot.get)
        u = usuarios.set_index("id_usuario").loc[uid]
        with c2:
            carga = ui.seletor_carga("v2_carga")
        ine = ""
        ds = 0
        if u["abrangencia"] == "EQUIPE" and u["ine"]:
            ine = u["ine"]
            c3.text_input("Equipe (fixa pelo perfil)", ine, disabled=True)
        else:
            with c3:
                ds = ui.seletor_distrito("v2_ds")
        params = {"carga": carga, "ds": ds, "ine": ine}
        df = db.consultar(v["sql"], params)
        if not df.empty:
            cont = df.groupby("tipo_inconsistencia").size().reset_index(name="qtd")
            fig = px.bar(cont, x="qtd", y="tipo_inconsistencia", orientation="h",
                         color_discrete_sequence=[ui.CORES[0]], title="Inconsistências na lista, por tipo",
                         labels={"qtd": "Quantidade", "tipo_inconsistencia": ""})
            ui.grafico(fig, 260)
    st.dataframe(df, hide_index=True, width="stretch")
    ui.mostrar_sql(v["sql"], params)
