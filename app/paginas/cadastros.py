"""CRUD (inserir, listar, alterar, excluir) de 5 tabelas, com SQL explicito.

Tabelas: PESSOA, SITUACAO_CADASTRAL (+ SITUACAO_DEFICIENCIA), EQUIPE,
ACAO_FORMATIVA e USUARIO. Os erros do MySQL (CHECK, UNIQUE, FK, triggers
com SIGNAL) aparecem na tela com a explicacao da regra violada.
"""
from __future__ import annotations

from datetime import date

import streamlit as st

import db
import ui

st.title("Cadastros (CRUD)")
st.caption("Cada operação mostra o SQL enviado ao MySQL. As restrições do banco e os triggers "
           "continuam valendo: o que o banco recusa aparece como erro aqui.")

# Mensagem da operacao anterior (a pagina e recarregada depois de gravar).
if "flash" in st.session_state:
    tipo, texto, comandos = st.session_state.pop("flash")
    (st.success if tipo == "ok" else st.error)(texto)
    if comandos:
        with st.expander("SQL executado", expanded=False):
            for sql, params in comandos:
                st.code(" ".join(sql.split()), language="sql")
                st.caption(f"Parâmetros: {params}")


def gravar(comandos, msg_ok):
    """Executa os comandos numa transacao e recarrega a pagina com o resultado."""
    try:
        afetadas = db.executar(comandos)
        st.session_state["flash"] = ("ok", f"{msg_ok} ({sum(afetadas)} linha(s) afetada(s)).", comandos)
    except Exception as e:  # noqa: BLE001
        st.session_state["flash"] = ("erro", db.mensagem_erro(e), comandos)
    st.rerun()


def opcoes(sql, chave, rotulo):
    df = db.consultar(sql)
    return df[chave].tolist(), dict(zip(df[chave], df[rotulo]))


SEXOS = {"F": "Feminino", "M": "Masculino", "I": "Indeterminado"}
SITUACOES = ["ATIVO", "INATIVO", "TRANSFERIDO", "OBITO"]
TIPOS_EQUIPE = ["ESF", "EAP", "RIBEIRINHA", "OUTRA"]

abas = st.tabs(["PESSOA", "SITUACAO_CADASTRAL", "EQUIPE", "ACAO_FORMATIVA", "USUARIO"])

# ====================================================================== PESSOA
with abas[0]:
    st.markdown("Dados pessoais. **Alterações geram linhas em `LOG_ALTERACAO_PESSOA`** (trigger G1); "
                "mudar `cns_principal` recalcula o resumo das cargas (trigger G3).")
    busca = st.text_input("Buscar por nome ou CNS", key="p_busca")
    SQL_LISTA = """
        SELECT cns, CONCAT('***.***.***-', RIGHT(cpf, 2)) AS cpf_mascarado, nome_civil,
               dt_nascimento, sexo, cns_principal
        FROM PESSOA
        WHERE %(busca)s = '' OR nome_civil LIKE %(like)s OR cns LIKE %(like)s
        ORDER BY cns DESC
        LIMIT 200"""
    pl = {"busca": busca, "like": f"%{busca}%"}
    st.dataframe(db.consultar(SQL_LISTA, pl), hide_index=True, width="stretch", height=260)
    ui.mostrar_sql(SQL_LISTA, pl, "SQL da listagem")

    principais, rot_p = opcoes("SELECT cns, CONCAT(cns, ' – ', nome_civil) AS r FROM PESSOA "
                               "WHERE cns_principal IS NULL ORDER BY cns", "cns", "r")
    op = st.radio("Operação", ["Inserir", "Alterar", "Excluir"], horizontal=True, key="p_op")

    if op == "Inserir":
        with st.form("p_ins", clear_on_submit=False):
            c1, c2, c3 = st.columns(3)
            cns = c1.text_input("CNS (15 dígitos)", max_chars=15)
            cpf = c2.text_input("CPF (opcional, 11 dígitos)", max_chars=11)
            sexo = c3.selectbox("Sexo", list(SEXOS), format_func=SEXOS.get)
            nome = st.text_input("Nome civil", max_chars=120)
            c4, c5 = st.columns(2)
            nasc = c4.date_input("Data de nascimento", value=date(1990, 1, 1),
                                 min_value=date(1900, 1, 1), max_value=date.today())
            princ = c5.selectbox("É duplicidade de (cns_principal)", [None] + principais,
                                 format_func=lambda x: "— não (cadastro principal)" if x is None else rot_p[x])
            if st.form_submit_button("Inserir pessoa", type="primary"):
                gravar([("""INSERT INTO PESSOA (cns, cpf, nome_civil, dt_nascimento, sexo, cns_principal)
                            VALUES (%s, %s, %s, %s, %s, %s)""",
                         (cns.strip(), cpf.strip() or None, nome.strip(), nasc, sexo, princ))],
                       "Pessoa inserida")
    else:
        cns_sel = st.text_input("CNS da pessoa", key="p_cns", placeholder="ex.: 700000000000050")
        reg = db.consultar("SELECT * FROM PESSOA WHERE cns = %(cns)s", {"cns": cns_sel}, cache=False) \
            if cns_sel else None
        if cns_sel and reg is not None and reg.empty:
            st.warning("CNS não encontrado.")
        elif reg is not None and not reg.empty:
            r = reg.iloc[0]
            if op == "Alterar":
                with st.form("p_upd"):
                    c1, c2 = st.columns(2)
                    nome = c1.text_input("Nome civil", r["nome_civil"])
                    cpf = c2.text_input("CPF", r["cpf"] or "", max_chars=11)
                    c3, c4, c5 = st.columns(3)
                    nasc = c3.date_input("Nascimento", r["dt_nascimento"], min_value=date(1900, 1, 1))
                    sexo = c4.selectbox("Sexo", list(SEXOS), index=list(SEXOS).index(r["sexo"]),
                                        format_func=SEXOS.get)
                    lista = [None] + [x for x in principais if x != r["cns"]]
                    atual = r["cns_principal"] if r["cns_principal"] in lista else None
                    princ = c5.selectbox("cns_principal", lista, index=lista.index(atual),
                                         format_func=lambda x: "— nenhum" if x is None else rot_p[x])
                    if st.form_submit_button("Salvar alterações", type="primary"):
                        gravar([("""UPDATE PESSOA
                                    SET nome_civil = %s, cpf = %s, dt_nascimento = %s,
                                        sexo = %s, cns_principal = %s
                                    WHERE cns = %s""",
                                 (nome.strip(), cpf.strip() or None, nasc, sexo, princ, r["cns"]))],
                               "Pessoa alterada")
                log = db.consultar("""SELECT campo, valor_anterior, valor_novo, usuario_bd, dt_hora_alteracao
                                      FROM LOG_ALTERACAO_PESSOA WHERE cns = %(cns)s
                                      ORDER BY id_log DESC LIMIT 20""", {"cns": r["cns"]}, cache=False)
                st.markdown("**Histórico desta pessoa no log (trigger G1)**")
                st.dataframe(log, hide_index=True, width="stretch")
            else:
                st.write(f"Excluir **{r['nome_civil']}** ({r['cns']})?")
                st.caption("Se a pessoa tiver situações cadastrais, inconsistências ou gabarito, o banco "
                           "recusa (ON DELETE RESTRICT). Duplicidades que apontam para ela passam a NULL "
                           "(ON DELETE SET NULL em cns_principal).")
                if st.button("Confirmar exclusão", type="primary", key="p_del"):
                    gravar([("DELETE FROM PESSOA WHERE cns = %s", (r["cns"],))], "Pessoa excluída")

# ========================================================== SITUACAO_CADASTRAL
with abas[1]:
    st.markdown("Situação de cada pessoa em cada carga. **Regra 8:** só a carga corrente aceita "
                "alteração; os triggers G2 bloqueiam cargas anteriores. Inserir, alterar e excluir "
                "mantêm `RESUMO_CARGA` em dia (triggers de resumo).")
    corrente = int(db.valor("SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL") or 1)
    todas_cargas, rot_c = opcoes(
        "SELECT id_carga, CONCAT('Carga ', id_carga, ' · ', DATE_FORMAT(periodo_ref_fim, '%m/%Y')) AS r "
        "FROM CARGA ORDER BY id_carga", "id_carga", "r")
    equipes, rot_e = opcoes("SELECT ine, CONCAT(ine, ' – ', nome) AS r FROM EQUIPE ORDER BY ine", "ine", "r")
    racas, rot_r = opcoes("SELECT id_raca_cor, descricao FROM RACA_COR ORDER BY id_raca_cor",
                          "id_raca_cor", "descricao")
    oss, rot_os = opcoes("SELECT id_orientacao_sexual, descricao FROM ORIENTACAO_SEXUAL "
                         "ORDER BY id_orientacao_sexual", "id_orientacao_sexual", "descricao")
    igs, rot_ig = opcoes("SELECT id_identidade_genero, descricao FROM IDENTIDADE_GENERO "
                         "ORDER BY id_identidade_genero", "id_identidade_genero", "descricao")
    defs, rot_d = opcoes("SELECT id_tipo_deficiencia, descricao FROM TIPO_DEFICIENCIA "
                         "ORDER BY id_tipo_deficiencia", "id_tipo_deficiencia", "descricao")

    c1, c2 = st.columns(2)
    carga = c1.selectbox("Carga", todas_cargas, index=todas_cargas.index(corrente),
                         format_func=lambda c: rot_c[c] + ("  (corrente)" if c == corrente else ""),
                         key="sc_carga")
    eq_f = c2.selectbox("Equipe", [""] + equipes, format_func=lambda x: "Todas" if x == "" else rot_e[x],
                        key="sc_eq")
    SQL_SC = """
        SELECT sc.cns, COALESCE(sc.nome_social, p.nome_civil) AS nome_exibicao, sc.ine,
               rc.descricao AS raca_cor, sc.deseja_informar_os, os.descricao AS orientacao,
               sc.deseja_informar_ig, ig.descricao AS identidade, sc.situacao, sc.dt_atualizacao_pec,
               (SELECT GROUP_CONCAT(td.descricao ORDER BY td.id_tipo_deficiencia SEPARATOR ', ')
                FROM SITUACAO_DEFICIENCIA sd
                JOIN TIPO_DEFICIENCIA td ON td.id_tipo_deficiencia = sd.id_tipo_deficiencia
                WHERE sd.cns = sc.cns AND sd.id_carga = sc.id_carga) AS deficiencias
        FROM SITUACAO_CADASTRAL sc
        JOIN PESSOA p ON p.cns = sc.cns
        JOIN RACA_COR rc ON rc.id_raca_cor = sc.id_raca_cor
        LEFT JOIN ORIENTACAO_SEXUAL os ON os.id_orientacao_sexual = sc.id_orientacao_sexual
        LEFT JOIN IDENTIDADE_GENERO ig ON ig.id_identidade_genero = sc.id_identidade_genero
        WHERE sc.id_carga = %(carga)s AND (%(ine)s = '' OR sc.ine = %(ine)s)
        ORDER BY sc.cns DESC
        LIMIT 300"""
    psc = {"carga": carga, "ine": eq_f}
    st.dataframe(db.consultar(SQL_SC, psc), hide_index=True, width="stretch", height=260)
    ui.mostrar_sql(SQL_SC, psc, "SQL da listagem")
    if carga != corrente:
        st.warning(f"A carga {carga} é anterior à corrente ({corrente}). Tente alterar ou excluir: "
                   "o trigger vai recusar, como manda a regra 8.")

    def form_situacao(prefixo, r=None, defs_atuais=()):
        """Campos comuns de inserir/alterar. Devolve dict com os valores."""
        def g(k, d=None):
            if r is None:
                return d
            v = r[k]
            if v is None or (isinstance(v, float) and v != v):   # NaN vindo do pandas
                return None
            return int(v) if isinstance(v, float) else v
        c1, c2 = st.columns(2)
        ine = c1.selectbox("Equipe responsável", equipes, format_func=rot_e.get, key=prefixo + "ine",
                           index=equipes.index(g("ine", equipes[0])))
        nome_social = c2.text_input("Nome social (opcional)", g("nome_social", "") or "", key=prefixo + "ns")
        c3, c4, c5 = st.columns(3)
        raca = c3.selectbox("Raça/cor (obrigatória)", racas, format_func=rot_r.get, key=prefixo + "rc",
                            index=racas.index(g("id_raca_cor", racas[0])))
        situacao = c4.selectbox("Situação", SITUACOES, key=prefixo + "sit",
                                index=SITUACOES.index(g("situacao", "ATIVO")))
        dt = c5.date_input("Atualização no PEC", g("dt_atualizacao_pec", date.today()), key=prefixo + "dt")
        c6, c7, c8, c9 = st.columns(4)
        des_os = c6.checkbox("Deseja informar orientação", bool(g("deseja_informar_os", True)), key=prefixo + "dos")
        os_l = [None] + oss
        os_v = c7.selectbox("Orientação sexual", os_l, format_func=lambda x: "— em branco" if x is None else rot_os[x],
                            index=os_l.index(g("id_orientacao_sexual", None)), key=prefixo + "os")
        des_ig = c8.checkbox("Deseja informar identidade", bool(g("deseja_informar_ig", True)), key=prefixo + "dig")
        ig_l = [None] + igs
        ig_v = c9.selectbox("Identidade de gênero", ig_l, format_func=lambda x: "— em branco" if x is None else rot_ig[x],
                            index=ig_l.index(g("id_identidade_genero", None)), key=prefixo + "ig")
        dfs = st.multiselect("Deficiências", defs, default=list(defs_atuais), format_func=rot_d.get, key=prefixo + "df")
        return dict(ine=ine, nome_social=nome_social.strip() or None, raca=raca, situacao=situacao, dt=dt,
                    des_os=des_os, os=os_v, des_ig=des_ig, ig=ig_v, defs=dfs)

    op = st.radio("Operação", ["Inserir", "Alterar", "Excluir"], horizontal=True, key="sc_op")
    if op == "Inserir":
        st.caption(f"Inserir na carga {carga}. Se ela for anterior à corrente, o trigger "
                   "`trg_situacao_cadastral_bi` recusa.")
        livres, rot_l = opcoes(
            "SELECT p.cns, CONCAT(p.cns, ' – ', p.nome_civil) AS r FROM PESSOA p "
            f"WHERE NOT EXISTS (SELECT 1 FROM SITUACAO_CADASTRAL s WHERE s.cns = p.cns AND s.id_carga = {int(carga)}) "
            "ORDER BY p.cns DESC", "cns", "r")
        if not livres:
            st.info("Todas as pessoas já têm registro nesta carga. Cadastre uma pessoa nova na aba PESSOA.")
        else:
            with st.form("sc_ins"):
                cns = st.selectbox("Pessoa (sem registro nesta carga)", livres, format_func=rot_l.get)
                v = form_situacao("sci_")
                if st.form_submit_button("Inserir situação", type="primary"):
                    cmds = [("""INSERT INTO SITUACAO_CADASTRAL
                                (cns, id_carga, ine, nome_social, id_raca_cor, deseja_informar_os,
                                 id_orientacao_sexual, deseja_informar_ig, id_identidade_genero,
                                 situacao, dt_atualizacao_pec)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                             (cns, carga, v["ine"], v["nome_social"], v["raca"], v["des_os"], v["os"],
                              v["des_ig"], v["ig"], v["situacao"], v["dt"]))]
                    cmds += [("""INSERT INTO SITUACAO_DEFICIENCIA (cns, id_carga, id_tipo_deficiencia)
                                 VALUES (%s, %s, %s)""", (cns, carga, d)) for d in v["defs"]]
                    gravar(cmds, "Situação inserida")
    else:
        cns_sel = st.text_input("CNS do registro", key="sc_cns", placeholder="ex.: 700000000000001")
        reg = db.consultar("SELECT * FROM SITUACAO_CADASTRAL WHERE cns = %(cns)s AND id_carga = %(c)s",
                           {"cns": cns_sel, "c": carga}, cache=False) if cns_sel else None
        if cns_sel and reg is not None and reg.empty:
            st.warning(f"Não há registro desse CNS na carga {carga}.")
        elif reg is not None and not reg.empty:
            r = reg.iloc[0].to_dict()
            atuais = db.consultar("SELECT id_tipo_deficiencia FROM SITUACAO_DEFICIENCIA "
                                  "WHERE cns = %(cns)s AND id_carga = %(c)s",
                                  {"cns": cns_sel, "c": carga}, cache=False)["id_tipo_deficiencia"].tolist()
            if op == "Alterar":
                with st.form("sc_upd"):
                    v = form_situacao("scu_", r, atuais)
                    if st.form_submit_button("Salvar alterações", type="primary"):
                        # O UPDATE vem primeiro: se a carga for anterior, o G2 recusa e nada e gravado.
                        cmds = [("""UPDATE SITUACAO_CADASTRAL
                                    SET ine = %s, nome_social = %s, id_raca_cor = %s,
                                        deseja_informar_os = %s, id_orientacao_sexual = %s,
                                        deseja_informar_ig = %s, id_identidade_genero = %s,
                                        situacao = %s, dt_atualizacao_pec = %s
                                    WHERE cns = %s AND id_carga = %s""",
                                 (v["ine"], v["nome_social"], v["raca"], v["des_os"], v["os"], v["des_ig"],
                                  v["ig"], v["situacao"], v["dt"], cns_sel, carga))]
                        if set(v["defs"]) != set(atuais):
                            cmds.append(("DELETE FROM SITUACAO_DEFICIENCIA WHERE cns = %s AND id_carga = %s",
                                         (cns_sel, carga)))
                            cmds += [("""INSERT INTO SITUACAO_DEFICIENCIA (cns, id_carga, id_tipo_deficiencia)
                                         VALUES (%s, %s, %s)""", (cns_sel, carga, d)) for d in v["defs"]]
                        gravar(cmds, "Situação alterada")
            else:
                st.write(f"Excluir o registro de **{cns_sel}** na carga **{carga}** "
                         f"(e suas {len(atuais)} deficiência(s))?")
                if st.button("Confirmar exclusão", type="primary", key="sc_del"):
                    gravar([("DELETE FROM SITUACAO_DEFICIENCIA WHERE cns = %s AND id_carga = %s", (cns_sel, carga)),
                            ("DELETE FROM SITUACAO_CADASTRAL WHERE cns = %s AND id_carga = %s", (cns_sel, carga))],
                           "Situação excluída")

# ====================================================================== EQUIPE
with abas[2]:
    st.markdown("Equipes de Saúde da Família. Trocar o **INE** propaga a mudança para situações, "
                "inconsistências, ações e usuários (**ON UPDATE CASCADE**). Excluir uma equipe com "
                "registros é recusado (RESTRICT); usuários vinculados ficam sem equipe (**ON DELETE SET NULL**).")
    SQL_EQ = """
        SELECT e.ine, e.nome, e.tipo_equipe, e.cnes, u.nome AS unidade, ds.nome AS distrito,
               (SELECT COUNT(*) FROM USUARIO us WHERE us.ine = e.ine) AS usuarios,
               (SELECT COUNT(*) FROM ACAO_FORMATIVA af WHERE af.ine = e.ine) AS acoes
        FROM EQUIPE e
        JOIN UNIDADE_SAUDE u ON u.cnes = e.cnes
        JOIN DISTRITO_SANITARIO ds ON ds.id_ds = u.id_ds
        ORDER BY e.ine"""
    st.dataframe(db.consultar(SQL_EQ), hide_index=True, width="stretch", height=260)
    ui.mostrar_sql(SQL_EQ, None, "SQL da listagem")
    unidades, rot_u = opcoes("SELECT cnes, CONCAT(cnes, ' – ', nome, ' (', bairro, ')') AS r "
                             "FROM UNIDADE_SAUDE ORDER BY cnes", "cnes", "r")
    equipes, rot_e = opcoes("SELECT ine, CONCAT(ine, ' – ', nome) AS r FROM EQUIPE ORDER BY ine", "ine", "r")
    op = st.radio("Operação", ["Inserir", "Alterar", "Excluir"], horizontal=True, key="e_op")
    if op == "Inserir":
        with st.form("e_ins"):
            c1, c2, c3 = st.columns(3)
            ine = c1.text_input("INE (10 dígitos)", max_chars=10)
            nome = c2.text_input("Nome", max_chars=80)
            tipo = c3.selectbox("Tipo (CHECK)", TIPOS_EQUIPE)
            cnes = st.selectbox("Unidade de saúde", unidades, format_func=rot_u.get)
            if st.form_submit_button("Inserir equipe", type="primary"):
                gravar([("INSERT INTO EQUIPE (ine, nome, tipo_equipe, cnes) VALUES (%s, %s, %s, %s)",
                         (ine.strip(), nome.strip(), tipo, cnes))], "Equipe inserida")
    else:
        sel = st.selectbox("Equipe", equipes, format_func=rot_e.get, key="e_sel")
        r = db.consultar("SELECT * FROM EQUIPE WHERE ine = %(i)s", {"i": sel}, cache=False).iloc[0]
        if op == "Alterar":
            with st.form("e_upd"):
                c1, c2, c3 = st.columns(3)
                novo_ine = c1.text_input("INE", r["ine"], max_chars=10)
                nome = c2.text_input("Nome", r["nome"])
                tipo = c3.selectbox("Tipo", TIPOS_EQUIPE, index=TIPOS_EQUIPE.index(r["tipo_equipe"]))
                cnes = st.selectbox("Unidade", unidades, index=unidades.index(r["cnes"]), format_func=rot_u.get)
                if st.form_submit_button("Salvar alterações", type="primary"):
                    gravar([("""UPDATE EQUIPE SET ine = %s, nome = %s, tipo_equipe = %s, cnes = %s
                                WHERE ine = %s""", (novo_ine.strip(), nome.strip(), tipo, cnes, r["ine"]))],
                           "Equipe alterada")
        else:
            st.write(f"Excluir **{r['nome']}** ({r['ine']})?")
            if st.button("Confirmar exclusão", type="primary", key="e_del"):
                gravar([("DELETE FROM EQUIPE WHERE ine = %s", (r["ine"],))], "Equipe excluída")

# ============================================================== ACAO_FORMATIVA
with abas[3]:
    st.markdown("Capacitações das equipes. O id é gerado por **AUTO_INCREMENT**. "
                "As datas alimentam a comparação com/sem ação formativa do painel e a consulta C9.")
    SQL_AF = """
        SELECT af.id_acao, af.ine, e.nome AS equipe, af.dt_acao, af.tipo_acao
        FROM ACAO_FORMATIVA af JOIN EQUIPE e ON e.ine = af.ine
        ORDER BY af.dt_acao DESC, af.id_acao DESC"""
    st.dataframe(db.consultar(SQL_AF), hide_index=True, width="stretch", height=260)
    ui.mostrar_sql(SQL_AF, None, "SQL da listagem")
    equipes, rot_e = opcoes("SELECT ine, CONCAT(ine, ' – ', nome) AS r FROM EQUIPE ORDER BY ine", "ine", "r")
    tipos_ac = ["Capacitação em equidade", "Oficina de cadastro", "Treinamento de qualidade de dados"]
    op = st.radio("Operação", ["Inserir", "Alterar", "Excluir"], horizontal=True, key="a_op")
    if op == "Inserir":
        with st.form("a_ins"):
            c1, c2, c3 = st.columns(3)
            ine = c1.selectbox("Equipe", equipes, format_func=rot_e.get)
            dt = c2.date_input("Data", date.today())
            tipo = c3.selectbox("Tipo de ação", tipos_ac, accept_new_options=True)
            if st.form_submit_button("Inserir ação", type="primary"):
                gravar([("INSERT INTO ACAO_FORMATIVA (ine, dt_acao, tipo_acao) VALUES (%s, %s, %s)",
                         (ine, dt, tipo))], "Ação formativa inserida")
    else:
        ids, rot_a = opcoes("SELECT id_acao, CONCAT('#', id_acao, ' · ', ine, ' · ', "
                            "DATE_FORMAT(dt_acao, '%d/%m/%Y'), ' · ', tipo_acao) AS r "
                            "FROM ACAO_FORMATIVA ORDER BY id_acao DESC", "id_acao", "r")
        if ids:
            sel = st.selectbox("Ação", ids, format_func=rot_a.get, key="a_sel")
            r = db.consultar("SELECT * FROM ACAO_FORMATIVA WHERE id_acao = %(i)s", {"i": int(sel)}, cache=False).iloc[0]
            if op == "Alterar":
                with st.form("a_upd"):
                    c1, c2, c3 = st.columns(3)
                    ine = c1.selectbox("Equipe", equipes, index=equipes.index(r["ine"]), format_func=rot_e.get)
                    dt = c2.date_input("Data", r["dt_acao"])
                    tipo = c3.text_input("Tipo de ação", r["tipo_acao"], max_chars=80)
                    if st.form_submit_button("Salvar alterações", type="primary"):
                        gravar([("UPDATE ACAO_FORMATIVA SET ine = %s, dt_acao = %s, tipo_acao = %s WHERE id_acao = %s",
                                 (ine, dt, tipo.strip(), int(sel)))], "Ação alterada")
            else:
                if st.button("Confirmar exclusão", type="primary", key="a_del"):
                    gravar([("DELETE FROM ACAO_FORMATIVA WHERE id_acao = %s", (int(sel),))], "Ação excluída")

# ===================================================================== USUARIO
with abas[4]:
    st.markdown("Usuários e perfis de acesso (regra 9). `login` é **UNIQUE**; a equipe é opcional "
                "(perfis municipais não têm equipe).")
    SQL_US = """
        SELECT u.id_usuario, u.nome, u.login, p.nome AS perfil, p.abrangencia, u.ine, e.nome AS equipe
        FROM USUARIO u
        JOIN PERFIL p ON p.id_perfil = u.id_perfil
        LEFT JOIN EQUIPE e ON e.ine = u.ine
        ORDER BY u.id_usuario"""
    st.dataframe(db.consultar(SQL_US), hide_index=True, width="stretch", height=260)
    ui.mostrar_sql(SQL_US, None, "SQL da listagem")
    perfis, rot_pf = opcoes("SELECT id_perfil, CONCAT(nome, ' (', abrangencia, ')') AS r FROM PERFIL "
                            "ORDER BY id_perfil", "id_perfil", "r")
    equipes, rot_e = opcoes("SELECT ine, CONCAT(ine, ' – ', nome) AS r FROM EQUIPE ORDER BY ine", "ine", "r")
    eq_l = [None] + equipes
    op = st.radio("Operação", ["Inserir", "Alterar", "Excluir"], horizontal=True, key="u_op")
    if op == "Inserir":
        with st.form("u_ins"):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome", max_chars=120)
            login = c2.text_input("Login", max_chars=80)
            c3, c4 = st.columns(2)
            perfil = c3.selectbox("Perfil", perfis, format_func=rot_pf.get)
            ine = c4.selectbox("Equipe", eq_l, format_func=lambda x: "— nenhuma" if x is None else rot_e[x])
            if st.form_submit_button("Inserir usuário", type="primary"):
                gravar([("INSERT INTO USUARIO (nome, login, id_perfil, ine) VALUES (%s, %s, %s, %s)",
                         (nome.strip(), login.strip(), perfil, ine))], "Usuário inserido")
    else:
        ids, rot_us = opcoes("SELECT id_usuario, CONCAT('#', id_usuario, ' · ', nome, ' (', login, ')') AS r "
                             "FROM USUARIO ORDER BY id_usuario", "id_usuario", "r")
        sel = st.selectbox("Usuário", ids, format_func=rot_us.get, key="u_sel")
        r = db.consultar("SELECT * FROM USUARIO WHERE id_usuario = %(i)s", {"i": int(sel)}, cache=False).iloc[0]
        if op == "Alterar":
            with st.form("u_upd"):
                c1, c2 = st.columns(2)
                nome = c1.text_input("Nome", r["nome"])
                login = c2.text_input("Login", r["login"])
                c3, c4 = st.columns(2)
                perfil = c3.selectbox("Perfil", perfis, index=perfis.index(r["id_perfil"]), format_func=rot_pf.get)
                ine = c4.selectbox("Equipe", eq_l, index=eq_l.index(r["ine"] if r["ine"] in eq_l else None),
                                   format_func=lambda x: "— nenhuma" if x is None else rot_e[x])
                if st.form_submit_button("Salvar alterações", type="primary"):
                    gravar([("UPDATE USUARIO SET nome = %s, login = %s, id_perfil = %s, ine = %s WHERE id_usuario = %s",
                             (nome.strip(), login.strip(), perfil, ine, int(sel)))], "Usuário alterado")
        else:
            if st.button("Confirmar exclusão", type="primary", key="u_del"):
                gravar([("DELETE FROM USUARIO WHERE id_usuario = %s", (int(sel),))], "Usuário excluído")
