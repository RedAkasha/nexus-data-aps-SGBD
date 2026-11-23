"""Componentes visuais compartilhados: paleta, tema dos graficos e filtros."""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

import db

# Paleta categorica validada (ordem fixa; a cor acompanha a entidade, nunca o ranking).
CORES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
COR_DS = {f"Distrito {i}": CORES[i - 1] for i in range(1, 9)}
INK, INK2, MUDO, GRADE, SUPERFICIE = "#0b0b0b", "#52514e", "#898781", "#e6e5e1", "#fcfcfb"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

pio.templates["nexus"] = go.layout.Template(
    layout=dict(
        font=dict(family="Inter, system-ui, sans-serif", size=13, color=INK2),
        title=dict(font=dict(size=15, color=INK), x=0, xanchor="left"),
        colorway=CORES,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor=GRADE, linecolor=GRADE, zerolinecolor=GRADE, ticks=""),
        yaxis=dict(gridcolor=GRADE, linecolor=GRADE, zerolinecolor=GRADE, ticks=""),
        legend=dict(orientation="h", yanchor="top", y=-0.16, xanchor="left", x=0,
                    title_text="", font=dict(color=INK2)),
        hoverlabel=dict(bgcolor="white", font=dict(color=INK)),
        margin=dict(l=8, r=8, t=48, b=8),
        bargap=0.25,
    )
)
pio.templates.default = "plotly_white+nexus"


def rgba(hexcor: str, alfa: float) -> str:
    h = hexcor.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alfa})"


def ajustar(fig, altura: int = 360):
    """Acabamento comum: marcas finas, cantos e altura."""
    fig.update_layout(height=altura, legend_title_text="",
                      legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="left", x=0))
    fig.update_traces(selector=dict(type="bar"), marker_line_width=0)
    fig.update_traces(selector=dict(type="scatter", mode="lines"), line_width=2)
    fig.update_traces(selector=dict(type="scatter", mode="lines+markers"), line_width=2, marker_size=8)
    return fig


def grafico(fig, altura: int = 360):
    st.plotly_chart(ajustar(fig, altura), width="stretch", theme=None, config={"displaylogo": False})


@st.cache_data(ttl=300, show_spinner=False)
def _cargas():
    return db.consultar(
        """
        SELECT c.id_carga, c.periodo_ref_inicio, c.periodo_ref_fim
        FROM CARGA c
        WHERE c.id_carga IN (SELECT DISTINCT id_carga FROM SITUACAO_CADASTRAL)
        ORDER BY c.id_carga
        """,
        cache=False,
    )


MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def rotulo_carga(row) -> str:
    fim = row["periodo_ref_fim"]
    return f"Carga {row['id_carga']} · {MESES[fim.month - 1]}/{fim.year}"


def cargas():
    """DataFrame das cargas que tem registros, com rotulo legivel."""
    df = _cargas()
    df["rotulo"] = df.apply(rotulo_carga, axis=1)
    return df


def seletor_carga(chave: str, rotulo: str = "Carga", ajuda: str | None = None) -> int:
    df = cargas()
    ids = df["id_carga"].tolist()
    mapa = dict(zip(df["id_carga"], df["rotulo"]))
    return st.selectbox(rotulo, ids, index=len(ids) - 1, format_func=mapa.get, key=chave, help=ajuda)


@st.cache_data(ttl=300, show_spinner=False)
def distritos():
    return db.consultar("SELECT id_ds, nome FROM DISTRITO_SANITARIO ORDER BY id_ds", cache=False)


def seletor_distrito(chave: str) -> int:
    df = distritos()
    opcoes = [0] + df["id_ds"].tolist()
    nomes = {0: "Todos os distritos", **dict(zip(df["id_ds"], df["nome"]))}
    return st.selectbox("Distrito Sanitario", opcoes, format_func=nomes.get, key=chave)


def mostrar_sql(sql: str, params=None, titulo: str = "SQL executado"):
    with st.expander(titulo):
        st.code(sql.strip(), language="sql")
        if params:
            st.caption(f"Parametros: {params}")


def kpi(col, rotulo: str, valor: str, delta: str | None = None, ajuda: str | None = None,
        delta_color: str = "normal"):
    col.metric(rotulo, valor, delta=delta, help=ajuda, delta_color=delta_color)


def pct(x, casas: int = 1) -> str:
    return "–" if x is None else f"{x:.{casas}f}%".replace(".", ",")


def num(x, casas: int = 0) -> str:
    if x is None:
        return "–"
    s = f"{x:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")
