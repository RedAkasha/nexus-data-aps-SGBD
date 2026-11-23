"""Funcoes, procedimentos e triggers da Etapa 05 executados pela interface."""
from __future__ import annotations

from datetime import date

import plotly.express as px
import streamlit as st

import db
import ui

st.title("Funções, procedimentos e triggers")
st.caption("Objetos da Etapa 05 executados direto no MySQL. As simulações rodam numa transação "
           "encerrada com ROLLBACK: mostram o efeito sem alterar o banco.")

aba_f, aba_p, aba_t = st.tabs(["Funções", "Procedimentos", "Triggers"])


def mostrar_sessao(resultado):
    for rotulo, tabelas in resultado:
        for df in tabelas:
            st.markdown(f"**{rotulo}**")
            st.dataframe(df, hide_index=True, width="stretch")


def comandos_sql(passos):
    with st.expander("SQL executado"):
        st.code("START TRANSACTION;\n" + "\n".join(
            " ".join(sql.split()) + ";" + (f"   -- {p}" if p else "") for _, sql, p in passos), language="sql")


# =================================================================== FUNÇÕES
with aba_f:
    st.subheader("F1 · fn_faixa_etaria(nascimento, data de referência)")
    st.caption("Centraliza as faixas etárias usadas pelas políticas; a data de referência é o fim do "
               "período da carga, para que o histórico não mude com o tempo.")
    c1, c2, c3 = st.columns([1, 1, 2])
    nasc = c1.date_input("Nascimento", date(1985, 6, 15), min_value=date(1900, 1, 1), key="f1n")
    ref = c2.date_input("Referência", date(2026, 6, 18), key="f1r")
    SQL_F1 = "SELECT fn_faixa_etaria(%(nasc)s, %(ref)s) AS faixa, TIMESTAMPDIFF(YEAR, %(nasc)s, %(ref)s) AS idade"
    r = db.consultar(SQL_F1, {"nasc": nasc, "ref": ref}).iloc[0]
    c3.metric("Resultado", r["faixa"], f"{r['idade']} anos completos", delta_color="off")
    st.code(f"SELECT fn_faixa_etaria('{nasc}', '{ref}');  -- '{r['faixa']}'", language="sql")

    carga = ui.seletor_carga("f1_carga", "Uso em consulta: distribuição por faixa na carga")
    SQL_F1_USO = """
        SELECT fn_faixa_etaria(p.dt_nascimento, c.periodo_ref_fim) AS faixa_etaria, COUNT(*) AS pessoas
        FROM SITUACAO_CADASTRAL sc
        JOIN PESSOA p ON p.cns = sc.cns
        JOIN CARGA c ON c.id_carga = sc.id_carga
        WHERE sc.id_carga = %(carga)s AND sc.situacao = 'ATIVO' AND p.cns_principal IS NULL
        GROUP BY faixa_etaria
        ORDER BY MIN(p.dt_nascimento) DESC"""
    df = db.consultar(SQL_F1_USO, {"carga": carga})
    fig = px.bar(df, x="faixa_etaria", y="pessoas", color_discrete_sequence=[ui.CORES[0]],
                 labels={"faixa_etaria": "", "pessoas": "Pessoas"})
    ui.grafico(fig, 280)
    ui.mostrar_sql(SQL_F1_USO, {"carga": carga})

    st.divider()
    st.subheader("F2 · fn_classifica_publico_lgbt(orientação, identidade)")
    st.caption("Fonte única da regra da seção 4: LGBTQIAPN+, Sem informação ou Não LGBTQIAPN+. "
               "Consulta os atributos `publico_lgbt` das tabelas de domínio.")
    SQL_F2 = """
        SELECT os.descricao AS orientacao, ig.descricao AS identidade,
               fn_classifica_publico_lgbt(os.id_orientacao_sexual, ig.id_identidade_genero) AS classificacao
        FROM ORIENTACAO_SEXUAL os CROSS JOIN IDENTIDADE_GENERO ig
        UNION ALL
        SELECT '(em branco)', ig.descricao, fn_classifica_publico_lgbt(NULL, ig.id_identidade_genero)
        FROM IDENTIDADE_GENERO ig
        UNION ALL
        SELECT os.descricao, '(em branco)', fn_classifica_publico_lgbt(os.id_orientacao_sexual, NULL)
        FROM ORIENTACAO_SEXUAL os
        UNION ALL
        SELECT '(em branco)', '(em branco)', fn_classifica_publico_lgbt(NULL, NULL)"""
    mat = db.consultar(SQL_F2)
    codigos = {"LGBTQIAPN+": 2, "Sem informacao": 1, "Nao LGBTQIAPN+": 0}
    piv = mat.pivot(index="orientacao", columns="identidade", values="classificacao")
    fig = px.imshow(piv.replace(codigos), aspect="auto",
                    color_continuous_scale=[[0, "#e6e5e1"], [0.5, "#eda100"], [1, ui.CORES[0]]],
                    labels={"x": "Identidade de gênero", "y": "Orientação sexual"})
    fig.update_traces(text=piv.values, texttemplate="%{text}", xgap=2, ygap=2)
    fig.update_layout(coloraxis_showscale=False, title="Todas as combinações dos domínios")
    ui.grafico(fig, 420)
    ui.mostrar_sql(SQL_F2)

# =============================================================== PROCEDIMENTOS
with aba_p:
    st.subheader("P1 · sp_marcar_cadastro_duplicado(cns duplicado, cns principal)")
    st.caption("Regra 5: duplicidade conta uma vez. Valida os CNS, evita cadeias A→B→C, redireciona "
               "quem apontava para o duplicado e recalcula RESUMO_CARGA — tudo numa transação. "
               "Principal vazio desfaz a marcação.")
    c1, c2, c3 = st.columns([2, 2, 1.2])
    dup = c1.text_input("CNS duplicado", "700000000000050", max_chars=15)
    princ = c2.text_input("CNS principal (vazio = desfazer)", "700000000000049", max_chars=15)
    modo = c3.radio("Modo", ["Simular", "Gravar"], key="p1_modo",
                    help="Simular: executa e desfaz (ROLLBACK). Gravar: confirma.")
    if st.button("Executar P1", type="primary"):
        passos = [
            ("Resumo das cargas da pessoa — antes",
             """SELECT id_carga, total_registros, total_ativos, total_negros_ativos, total_lgbt_ativos
                FROM RESUMO_CARGA WHERE id_carga IN
                (SELECT id_carga FROM SITUACAO_CADASTRAL WHERE cns = %s) ORDER BY id_carga DESC LIMIT 5""",
             (dup,)),
            ("Resultado do procedimento", "CALL sp_marcar_cadastro_duplicado(%s, %s)", (dup, princ or None)),
            ("PESSOA depois", "SELECT cns, nome_civil, cns_principal FROM PESSOA WHERE cns IN (%s, %s)",
             (dup, princ or dup)),
            ("Resumo das cargas da pessoa — depois",
             """SELECT id_carga, total_registros, total_ativos, total_negros_ativos, total_lgbt_ativos
                FROM RESUMO_CARGA WHERE id_carga IN
                (SELECT id_carga FROM SITUACAO_CADASTRAL WHERE cns = %s) ORDER BY id_carga DESC LIMIT 5""",
             (dup,)),
            ("Linhas gravadas no log pelo trigger G1",
             """SELECT campo, valor_anterior, valor_novo, usuario_bd, dt_hora_alteracao
                FROM LOG_ALTERACAO_PESSOA WHERE cns = %s ORDER BY id_log DESC LIMIT 3""", (dup,)),
        ]
        try:
            # O P1 abre e confirma a propria transacao (START TRANSACTION ... COMMIT),
            # entao nao da para desfaze-lo com um ROLLBACK externo. No modo Simular,
            # a interface chama o P1 de novo com o principal anterior, o que devolve
            # o cadastro e o resumo ao estado de antes (o log registra as duas idas).
            res = db.sessao(passos, confirmar=True)
            if modo == "Simular":
                ant = res[1][1][0]["principal_anterior"].iloc[0]
                db.sessao([("desfaz", "CALL sp_marcar_cadastro_duplicado(%s, %s)", (dup, ant))],
                          confirmar=True)
                st.info("Simulação: o P1 confirma a própria transação, por isso a interface executou "
                        "em seguida a chamada inversa e o cadastro voltou ao estado anterior.")
            mostrar_sessao(res)
            comandos_sql(passos)
        except Exception as e:  # noqa: BLE001
            st.error(db.mensagem_erro(e))
    with st.expander("Chamadas que o procedimento recusa (teste as validações)"):
        st.markdown("- `('700000000000050', '700000000000050')` → duplicado de si mesmo\n"
                    "- `('700000000000050', '700000000000051')` → principal já é duplicado\n"
                    "- `('700000000000999', '700000000000001')` → CNS inexistente\n"
                    "- `('700000000000001', '')` → nada a desfazer")

    st.divider()
    st.subheader("P2 · sp_auditar_inconsistencias_carga(carga)  — com CURSOR")
    st.caption("Percorre cada situação da carga e registra, via `sp_registrar_inconsistencia`, "
               "raça/cor vazia (tipo 1), valor inválido (tipo 2) e divergência entre registros (tipo 3). "
               "É reexecutável: o que já existe aparece em `ja_registradas`.")
    c1, c2 = st.columns([2, 1])
    with c1:
        carga_a = ui.seletor_carga("p2_carga", "Carga a auditar")
    modo2 = c2.radio("Modo", ["Simular (ROLLBACK)", "Gravar (COMMIT)"], key="p2_modo")
    if st.button("Executar auditoria", type="primary"):
        passos = [
            ("Inconsistências da carga antes", "SELECT COUNT(*) AS inconsistencias FROM INCONSISTENCIA "
                                               "WHERE id_carga = %s", (carga_a,)),
            ("Resumo da auditoria", "CALL sp_auditar_inconsistencias_carga(%s)", (carga_a,)),
            ("Inconsistências por campo e tipo depois",
             """SELECT i.campo, ti.descricao AS tipo, COUNT(*) AS quantidade
                FROM INCONSISTENCIA i JOIN TIPO_INCONSISTENCIA ti
                  ON ti.id_tipo_inconsistencia = i.id_tipo_inconsistencia
                WHERE i.id_carga = %s GROUP BY i.campo, ti.id_tipo_inconsistencia, ti.descricao
                ORDER BY quantidade DESC""", (carga_a,)),
        ]
        try:
            res = db.sessao(passos, confirmar=modo2.startswith("Gravar"))
            st.success("Gravado." if modo2.startswith("Gravar") else "Simulação concluída: ROLLBACK feito.")
            mostrar_sessao(res)
            comandos_sql(passos)
        except Exception as e:  # noqa: BLE001
            st.error(db.mensagem_erro(e))

    st.divider()
    st.subheader("P3 · sp_recalcular_resumo_carga(carga)")
    st.caption("Refaz RESUMO_CARGA a partir de SITUACAO_CADASTRAL (NULL = todas). Chamado pelos triggers "
               "do grupo G3; aqui pode ser executado à mão para conferência.")
    if st.button("Recalcular todas as cargas"):
        try:
            db.sessao([("P3", "CALL sp_recalcular_resumo_carga(NULL)", None)], confirmar=True)
            st.success("Resumo recalculado.")
        except Exception as e:  # noqa: BLE001
            st.error(db.mensagem_erro(e))
    st.dataframe(db.consultar("SELECT * FROM RESUMO_CARGA ORDER BY id_carga DESC", cache=False),
                 hide_index=True, width="stretch", height=220)

# ==================================================================== TRIGGERS
with aba_t:
    st.subheader("G1 · trg_pessoa_au_log — tabela de log")
    st.caption("Toda alteração em PESSOA grava uma linha por campo alterado (CPF mascarado), "
               "venha da tela, de um procedimento ou de um UPDATE manual.")
    c1, c2 = st.columns(2)
    filtro_cns = c1.text_input("Filtrar por CNS", key="g1_cns")
    campo = c2.selectbox("Campo", ["(todos)", "nome_civil", "cpf", "dt_nascimento", "sexo",
                                   "cns_principal", "cns"], key="g1_campo")
    SQL_LOG = """
        SELECT id_log, cns, campo, valor_anterior, valor_novo, usuario_bd, dt_hora_alteracao
        FROM LOG_ALTERACAO_PESSOA
        WHERE (%(cns)s = '' OR cns = %(cns)s) AND (%(campo)s = '(todos)' OR campo = %(campo)s)
        ORDER BY id_log DESC LIMIT 200"""
    pl = {"cns": filtro_cns.strip(), "campo": campo}
    log = db.consultar(SQL_LOG, pl, cache=False)
    st.dataframe(log, hide_index=True, width="stretch", height=220)
    ui.mostrar_sql(SQL_LOG, pl)
    with st.form("g1_demo"):
        st.markdown("**Teste rápido:** altere o nome de uma pessoa e veja a linha de log nascer.")
        c1, c2, c3 = st.columns([1.2, 2, 1])
        cns_t = c1.text_input("CNS", "700000000000010")
        novo = c2.text_input("Novo nome civil", "Pessoa Fictícia 010 (corrigido)")
        simular = c3.checkbox("Só simular", True)
        if st.form_submit_button("Executar UPDATE"):
            passos = [("UPDATE", "UPDATE PESSOA SET nome_civil = %s WHERE cns = %s", (novo, cns_t)),
                      ("Log gerado pelo trigger",
                       "SELECT campo, valor_anterior, valor_novo, usuario_bd, dt_hora_alteracao "
                       "FROM LOG_ALTERACAO_PESSOA WHERE cns = %s ORDER BY id_log DESC LIMIT 1", (cns_t,))]
            try:
                mostrar_sessao(db.sessao(passos, confirmar=not simular))
                comandos_sql(passos)
            except Exception as e:  # noqa: BLE001
                st.error(db.mensagem_erro(e))

    st.divider()
    st.subheader("G2 · proteção das cargas anteriores (regra 8)")
    st.caption("`trg_situacao_cadastral_bu/bd/bi` e `trg_situacao_deficiencia_bi/bd` recusam qualquer "
               "alteração em carga anterior à corrente. Cada teste roda e é desfeito.")
    corrente = int(db.valor("SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL"))
    cns_g2 = db.valor("SELECT MIN(cns) FROM SITUACAO_CADASTRAL WHERE id_carga = %(c)s",
                      {"c": corrente}) or "700000000000001"
    testes = {
        f"UPDATE na carga 1 (anterior)":
            ("UPDATE SITUACAO_CADASTRAL SET situacao = 'OBITO' WHERE cns = %s AND id_carga = 1",
             ("700000000000001",)),
        "DELETE na carga 1 (anterior)":
            ("DELETE FROM SITUACAO_CADASTRAL WHERE cns = %s AND id_carga = 1", ("700000000000060",)),
        "INSERT na carga 1 (anterior)":
            ("""INSERT INTO SITUACAO_CADASTRAL (cns, id_carga, ine, id_raca_cor, situacao, dt_atualizacao_pec)
                VALUES (%s, 1, '2000000001', 3, 'ATIVO', '2024-01-15')""", ("700000000000600",)),
        "Mover registro de carga (id_carga)":
            ("UPDATE SITUACAO_CADASTRAL SET id_carga = 1 WHERE cns = %s AND id_carga = %s",
             (cns_g2, corrente)),
        f"UPDATE na carga {corrente} (corrente) — permitido":
            ("UPDATE SITUACAO_CADASTRAL SET dt_atualizacao_pec = dt_atualizacao_pec WHERE cns = %s AND id_carga = %s",
             (cns_g2, corrente)),
    }
    escolha = st.selectbox("Teste", list(testes))
    if st.button("Executar teste (com ROLLBACK)"):
        sql, params = testes[escolha]
        try:
            db.sessao([("teste", sql, params)], confirmar=False)
            st.success("Aceito pelo banco (e desfeito com ROLLBACK).")
        except Exception as e:  # noqa: BLE001
            st.error(db.mensagem_erro(e))
        st.code(" ".join(sql.split()) + f";   -- {params}", language="sql")

    st.divider()
    st.subheader("trg_resumo_carga_ai (Etapa 03) e G3 — RESUMO_CARGA sempre em dia")
    st.caption("Insere uma pessoa nova e sua situação numa carga NOVA (31), mostra o resumo criado pelo "
               "trigger AFTER INSERT, altera a situação (G3 recalcula) e desfaz tudo.")
    if st.button("Simular nova extração"):
        passos = [
            ("Carga nova", """INSERT INTO CARGA (id_carga, dt_hora_extracao, periodo_ref_inicio, periodo_ref_fim)
                              VALUES (31, '2026-07-18 02:00:00', '2026-06-19', '2026-07-18')""", None),
            ("Pessoa nova", """INSERT INTO PESSOA (cns, cpf, nome_civil, dt_nascimento, sexo)
                               VALUES ('799999999999999', NULL, 'Pessoa de Teste', '1990-03-10', 'F')""", None),
            ("Situação na carga 31", """INSERT INTO SITUACAO_CADASTRAL
                (cns, id_carga, ine, id_raca_cor, deseja_informar_os, id_orientacao_sexual,
                 deseja_informar_ig, id_identidade_genero, situacao, dt_atualizacao_pec)
                VALUES ('799999999999999', 31, '2000000001', 2, 1, 3, 1, 1, 'ATIVO', '2026-07-01')""", None),
            ("Resumo criado pelo trigger AFTER INSERT",
             "SELECT * FROM RESUMO_CARGA WHERE id_carga = 31", None),
            ("Situação muda para INATIVO", """UPDATE SITUACAO_CADASTRAL SET situacao = 'INATIVO'
                                              WHERE cns = '799999999999999' AND id_carga = 31""", None),
            ("Resumo recalculado pelo G3", "SELECT * FROM RESUMO_CARGA WHERE id_carga = 31", None),
        ]
        try:
            mostrar_sessao(db.sessao(passos, confirmar=False))
            st.success("Tudo desfeito com ROLLBACK.")
            comandos_sql(passos)
        except Exception as e:  # noqa: BLE001
            st.error(db.mensagem_erro(e))
