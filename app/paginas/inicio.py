"""Pagina inicial: o projeto, o modelo e o estado do banco."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

import db

RAIZ = Path(__file__).resolve().parents[2]

st.title("Nexus Data · Monitoramento de Equidade na APS do Recife")
st.markdown(
    "Aplicação final da disciplina **Modelagem e Projeto de Banco de Dados** (CESAR School). "
    "O banco MySQL guarda as extrações (cargas) do PEC/e-SUS APS e permite à Secretaria de Saúde "
    "acompanhar as três políticas de equidade: **População Negra**, **População LGBTQIAPN+** e "
    "**Pessoa com Deficiência**, por distrito, unidade e equipe."
)
st.info("Todos os dados são **fictícios**. Nenhuma linha corresponde a uma pessoa real.", icon="ℹ️")

SQL_CONT = """
SELECT 'Distritos' AS tabela, COUNT(*) AS registros FROM DISTRITO_SANITARIO
UNION ALL SELECT 'Unidades de saúde', COUNT(*) FROM UNIDADE_SAUDE
UNION ALL SELECT 'Equipes', COUNT(*) FROM EQUIPE
UNION ALL SELECT 'Pessoas', COUNT(*) FROM PESSOA
UNION ALL SELECT 'Cargas com registros', COUNT(DISTINCT id_carga) FROM SITUACAO_CADASTRAL
UNION ALL SELECT 'Situações cadastrais', COUNT(*) FROM SITUACAO_CADASTRAL
UNION ALL SELECT 'Deficiências registradas', COUNT(*) FROM SITUACAO_DEFICIENCIA
UNION ALL SELECT 'Inconsistências', COUNT(*) FROM INCONSISTENCIA
UNION ALL SELECT 'Linhas de log', COUNT(*) FROM LOG_ALTERACAO_PESSOA
"""
try:
    cont = db.consultar(SQL_CONT, cache=False)
except Exception as e:  # noqa: BLE001
    st.error("Não foi possível conectar ao MySQL. Confira `.streamlit/secrets.toml` ou as variáveis "
             "NEXUS_DB_* e rode `python scripts/instalar_banco.py`.\n\n" + db.mensagem_erro(e))
    st.stop()

cols = st.columns(len(cont))
for col, r in zip(cols, cont.itertuples()):
    col.metric(r.tabela, f"{int(r.registros):,}".replace(",", "."))

st.subheader("O que tem em cada página")
st.markdown("""
| Página | Requisitos atendidos |
|---|---|
| **Painel** | Etapa 06 – indicadores resumidos e 12 gráficos dinâmicos (linha, barras, pizza, radar, histograma, pirâmide, boxplot, dispersão com correlação, mapa de calor), estatística descritiva calculada no MySQL, filtros de período, distrito e equipes |
| **Consultas e visões** | Etapas 03 e 04 – C1 a C12 e as visões, com parâmetros (carga, distrito, usuário), tabela, gráfico, SQL e download |
| **Cadastros** | Etapas 03 e 06 – inserir, alterar, excluir e listar em 5 tabelas (PESSOA, SITUACAO_CADASTRAL, EQUIPE, ACAO_FORMATIVA, USUARIO) |
| **Funções, procedimentos e triggers** | Etapas 05 e 06 – executar as funções, os procedimentos (inclusive o de cursor) e ver o efeito dos triggers |
""")

c1, c2 = st.columns(2)
img_c = RAIZ / "etapa01-modelagem" / "modelo_conceitual.png"
img_l = RAIZ / "etapa01-modelagem" / "modelo_logico.png"
if img_c.exists():
    c1.image(str(img_c), caption="Modelo conceitual (brModelo)")
if img_l.exists():
    c2.image(str(img_l), caption="Modelo lógico")
