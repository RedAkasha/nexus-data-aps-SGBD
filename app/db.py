"""Acesso ao MySQL com SQL explicito (PyMySQL, sem ORM).

Toda instrucao que a aplicacao envia ao banco esta escrita por extenso nos
modulos de paginas e em sql_consultas.py; este modulo so abre a conexao,
executa e devolve o resultado. Os parametros vao separados do texto SQL
(%s / %(nome)s), o que evita injecao de SQL.

Configuracao (em ordem de prioridade):
  1. .streamlit/secrets.toml, secao [mysql] (host, port, user, password, database)
  2. variaveis de ambiente NEXUS_DB_HOST, NEXUS_DB_PORT, NEXUS_DB_USER,
     NEXUS_DB_PASSWORD, NEXUS_DB_NAME
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal

import pandas as pd
import pymysql
import streamlit as st

# Guarda as ultimas instrucoes executadas (mostradas na interface).
_HIST = "historico_sql"


def _config() -> dict:
    cfg = {
        "host": os.getenv("NEXUS_DB_HOST", "localhost"),
        "port": int(os.getenv("NEXUS_DB_PORT", "3306")),
        "user": os.getenv("NEXUS_DB_USER", "root"),
        "password": os.getenv("NEXUS_DB_PASSWORD", ""),
        "database": os.getenv("NEXUS_DB_NAME", "nexusdata_etapa02"),
    }
    try:
        sec = st.secrets.get("mysql", {})
        cfg.update({k: (int(v) if k == "port" else v) for k, v in sec.items() if k in cfg})
    except Exception:  # sem secrets.toml
        pass
    return cfg


@contextmanager
def conexao():
    """Abre uma conexao nova (o banco e local e as operacoes sao curtas)."""
    con = pymysql.connect(
        **_config(),
        charset="utf8mb4",
        autocommit=False,
        # A conexao usa a mesma collation do banco: evita o erro 1267 ao
        # comparar o retorno das funcoes com textos (ver Etapa 05).
        init_command="SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci",
    )
    try:
        yield con
    finally:
        con.close()


def _registrar(sql: str, params=None) -> None:
    hist = st.session_state.setdefault(_HIST, [])
    hist.append((datetime.now().strftime("%H:%M:%S"), " ".join(sql.split()), params))
    del hist[:-30]


def _para_df(cur) -> pd.DataFrame:
    if cur.description is None:
        return pd.DataFrame()
    nomes = [d[0] for d in cur.description]
    df = pd.DataFrame(cur.fetchall(), columns=nomes)
    for c in df.columns:
        amostra = df[c].dropna()
        if not amostra.empty and isinstance(amostra.iloc[0], Decimal):
            df[c] = df[c].astype(float)
    return df


@st.cache_data(ttl=300, show_spinner=False)
def _consultar_cache(sql: str, params_items: tuple | None) -> pd.DataFrame:
    params = dict(params_items) if params_items is not None else None
    with conexao() as con, con.cursor() as cur:
        cur.execute(sql, params)
        return _para_df(cur)


def _congelar(params):
    if params is None:
        return None
    if isinstance(params, dict):
        return tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in params.items()))
    raise TypeError("use parametros nomeados (dict) nas consultas com cache")


def consultar(sql: str, params: dict | None = None, cache: bool = True) -> pd.DataFrame:
    """Executa um SELECT e devolve um DataFrame."""
    _registrar(sql, params)
    if cache:
        return _consultar_cache(sql, _congelar(params)).copy()
    with conexao() as con, con.cursor() as cur:
        cur.execute(sql, params)
        return _para_df(cur)


def valor(sql: str, params: dict | None = None):
    df = consultar(sql, params)
    return None if df.empty else df.iat[0, 0]


def executar(comandos: list[tuple[str, object]]) -> list[int]:
    """Executa INSERT/UPDATE/DELETE numa unica transacao (COMMIT ou ROLLBACK).

    Devolve o numero de linhas afetadas por comando. Em caso de erro, desfaz
    tudo e propaga a excecao do MySQL (constraint, trigger com SIGNAL etc.).
    """
    afetadas = []
    with conexao() as con:
        try:
            with con.cursor() as cur:
                for sql, params in comandos:
                    _registrar(sql, params)
                    afetadas.append(cur.execute(sql, params))
            con.commit()
        except Exception:
            con.rollback()
            raise
    st.cache_data.clear()
    return afetadas


def sessao(passos, confirmar: bool):
    """Roda uma sequencia de instrucoes numa transacao e devolve TODOS os
    conjuntos de resultado (inclusive os de CALL). Se confirmar=False, faz
    ROLLBACK no final: serve para simular procedimentos e triggers sem
    alterar o banco.

    passos: lista de (rotulo, sql, params). Retorna lista de (rotulo, [DataFrames]).
    """
    saida = []
    with conexao() as con:
        try:
            with con.cursor() as cur:
                cur.execute("START TRANSACTION")
                for rotulo, sql, params in passos:
                    _registrar(sql, params)
                    cur.execute(sql, params)
                    tabelas = []
                    while True:
                        df = _para_df(cur)
                        if not df.empty or cur.description is not None:
                            tabelas.append(df)
                        if not cur.nextset():
                            break
                    saida.append((rotulo, tabelas))
            if confirmar:
                con.commit()
                st.cache_data.clear()
            else:
                con.rollback()
        except Exception:
            con.rollback()
            raise
    return saida


def mensagem_erro(erro: Exception) -> str:
    """Traduz o erro do MySQL para uma mensagem curta."""
    if isinstance(erro, pymysql.MySQLError) and len(erro.args) >= 2:
        codigo, texto = erro.args[0], erro.args[1]
        dicas = {
            1062: "valor duplicado em campo unico ou chave primaria",
            1451: "o registro e referenciado por outra tabela (ON DELETE RESTRICT)",
            1452: "a chave estrangeira aponta para um registro que nao existe",
            3819: "valor recusado por uma restricao CHECK",
            1644: "operacao bloqueada por regra de negocio (trigger/procedimento)",
            1048: "campo obrigatorio (NOT NULL) sem valor",
            1406: "texto maior que o tamanho da coluna",
        }
        dica = dicas.get(codigo)
        return f"MySQL {codigo}: {texto}" + (f"  \n_{dica}_" if dica else "")
    return str(erro)


def historico() -> list:
    return list(reversed(st.session_state.get(_HIST, [])))


def formatar_data(d) -> str:
    if isinstance(d, (date, datetime)):
        return d.strftime("%d/%m/%Y")
    return "" if d is None else str(d)
