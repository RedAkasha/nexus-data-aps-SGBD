"""Nexus Data - aplicacao final (Etapa 06).

Executar na raiz do repositorio:
    streamlit run app/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

import db  # noqa: E402

st.set_page_config(page_title="Nexus Data · APS Recife", page_icon="🧬", layout="wide")

paginas = st.navigation([
    st.Page("paginas/inicio.py", title="Início", icon="🏠", default=True),
    st.Page("paginas/painel.py", title="Painel", icon="📊"),
    st.Page("paginas/consultas.py", title="Consultas e visões", icon="🔎"),
    st.Page("paginas/cadastros.py", title="Cadastros (CRUD)", icon="✏️"),
    st.Page("paginas/rotinas.py", title="Funções, procedimentos e triggers", icon="⚙️"),
])

with st.sidebar:
    st.caption("Banco: `nexusdata_etapa02` · MySQL 8")
    if st.button("Atualizar dados", help="Limpa o cache das consultas"):
        st.cache_data.clear()
        st.rerun()
    with st.expander("Últimos comandos SQL"):
        for hora, sql, params in db.historico()[:12]:
            st.caption(f"{hora} · {params if params else ''}")
            st.code(sql[:600], language="sql")

paginas.run()
