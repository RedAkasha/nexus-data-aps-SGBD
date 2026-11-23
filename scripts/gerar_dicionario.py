"""Gera o dicionario de dados (Markdown) a partir do banco instalado.

Tipos, nulidade, chaves, padroes, CHECK e FK vem do information_schema;
as descricoes das colunas estao neste arquivo. Uso:
    python scripts/gerar_dicionario.py > etapa01-modelagem/dicionario_dados.md
"""
from __future__ import annotations

import os
import re
from collections import defaultdict

import pymysql

BANCO = os.getenv("NEXUS_DB_NAME", "nexusdata_etapa02")

TABELAS = {
    "DISTRITO_SANITARIO": "Os 8 Distritos Sanitários do Recife (regra 1).",
    "UNIDADE_SAUDE": "Unidades de Saúde da Família; cada uma pertence a um único distrito.",
    "EQUIPE": "Equipes de Saúde da Família; cada uma pertence a uma única unidade.",
    "ACAO_FORMATIVA": "Capacitações realizadas com as equipes.",
    "PESSOA": "Pessoa cadastrada, identificada pelo CNS; guarda o vínculo de duplicidade.",
    "CARGA": "Cada extração periódica do PEC/e-SUS APS e seu período de referência.",
    "RACA_COR": "Domínio de raça/cor do PEC; marca quem é população negra.",
    "ORIENTACAO_SEXUAL": "Domínio de orientação sexual; marca o público LGBTQIAPN+.",
    "IDENTIDADE_GENERO": "Domínio de identidade de gênero; marca o público LGBTQIAPN+.",
    "TIPO_DEFICIENCIA": "Domínio dos tipos de deficiência.",
    "SITUACAO_CADASTRAL": "Retrato da pessoa em cada carga: equipe, marcadores de equidade e situação.",
    "SITUACAO_DEFICIENCIA": "Deficiências registradas para a pessoa em cada carga (0..N).",
    "PARAMETRO": "Parâmetros de cálculo vigentes em cada carga.",
    "TIPO_INCONSISTENCIA": "Domínio dos tipos de inconsistência de registro.",
    "INCONSISTENCIA": "Inconsistências encontradas em cada carga, ligadas à equipe responsável (regra 7).",
    "GABARITO_DEFEITO": "Defeitos plantados de propósito nos dados de teste, para avaliar a auditoria.",
    "PERFIL": "Perfis de acesso e sua abrangência (regra 9).",
    "USUARIO": "Usuários do sistema, com perfil e, para equipes, o território.",
    "POLITICA": "As três políticas de equidade da Secretaria.",
    "INDICADOR": "Indicadores de cada política, com descrição e forma de cálculo.",
    "APURACAO_INDICADOR": "Valor de um indicador numa carga e num nível territorial.",
    "RESUMO_CARGA": "(Etapa 03) Totais agregados por carga, mantidos por trigger; base da VW_EVOLUCAO_CARGAS.",
    "LOG_ALTERACAO_PESSOA": "(Etapa 05) Log de alterações em PESSOA, gravado pelo trigger G1.",
}

DESC = {
    "DISTRITO_SANITARIO.id_ds": "Número do distrito (1 a 8)",
    "DISTRITO_SANITARIO.nome": "Nome do distrito",
    "UNIDADE_SAUDE.cnes": "Código CNES da unidade",
    "UNIDADE_SAUDE.nome": "Nome da unidade",
    "UNIDADE_SAUDE.bairro": "Bairro onde fica a unidade",
    "UNIDADE_SAUDE.latitude": "Latitude (graus decimais)",
    "UNIDADE_SAUDE.longitude": "Longitude (graus decimais)",
    "UNIDADE_SAUDE.id_ds": "Distrito ao qual a unidade pertence",
    "EQUIPE.ine": "Identificador Nacional de Equipe (INE)",
    "EQUIPE.nome": "Nome da equipe",
    "EQUIPE.tipo_equipe": "Tipo da equipe (ESF, EAP, RIBEIRINHA, OUTRA)",
    "EQUIPE.cnes": "Unidade à qual a equipe pertence",
    "ACAO_FORMATIVA.id_acao": "Identificador da ação (sequência)",
    "ACAO_FORMATIVA.ine": "Equipe capacitada",
    "ACAO_FORMATIVA.dt_acao": "Data da ação",
    "ACAO_FORMATIVA.tipo_acao": "Tipo da ação (oficina, capacitação...)",
    "PESSOA.cns": "Cartão Nacional de Saúde (15 dígitos)",
    "PESSOA.cpf": "CPF (opcional)",
    "PESSOA.nome_civil": "Nome civil",
    "PESSOA.dt_nascimento": "Data de nascimento (idade e faixa etária são calculadas, não armazenadas)",
    "PESSOA.sexo": "Sexo: F, M ou I (indeterminado)",
    "PESSOA.cns_principal": "Se preenchido, o cadastro é duplicidade deste CNS e não entra nas contagens (regra 5)",
    "CARGA.id_carga": "Número da carga",
    "CARGA.dt_hora_extracao": "Data e hora da extração",
    "CARGA.periodo_ref_inicio": "Início do período de referência",
    "CARGA.periodo_ref_fim": "Fim do período de referência (data-base de idade)",
    "CARGA.fonte": "Sistema de origem",
    "RACA_COR.id_raca_cor": "Código da raça/cor no PEC (9 = sem informação)",
    "RACA_COR.descricao": "Descrição",
    "RACA_COR.pop_negra": "1 = preta ou parda (público da política da população negra)",
    "ORIENTACAO_SEXUAL.id_orientacao_sexual": "Código no PEC (9 = não deseja informar)",
    "ORIENTACAO_SEXUAL.descricao": "Descrição",
    "ORIENTACAO_SEXUAL.publico_lgbt": "1 = diferente de heterossexual",
    "IDENTIDADE_GENERO.id_identidade_genero": "Código no PEC (9 = não deseja informar)",
    "IDENTIDADE_GENERO.descricao": "Descrição",
    "IDENTIDADE_GENERO.publico_lgbt": "1 = diferente de cisgênero",
    "TIPO_DEFICIENCIA.id_tipo_deficiencia": "Código do tipo",
    "TIPO_DEFICIENCIA.descricao": "Auditiva, visual, física, intelectual ou outra",
    "SITUACAO_CADASTRAL.cns": "Pessoa",
    "SITUACAO_CADASTRAL.id_carga": "Carga (período) do retrato",
    "SITUACAO_CADASTRAL.ine": "Equipe responsável pela pessoa nesta carga (regra 2)",
    "SITUACAO_CADASTRAL.nome_social": "Nome social (opcional; usado em listagens nominais, regra 6)",
    "SITUACAO_CADASTRAL.id_raca_cor": "Raça/cor (obrigatória, regra 3)",
    "SITUACAO_CADASTRAL.deseja_informar_os": "A pessoa aceitou informar a orientação sexual",
    "SITUACAO_CADASTRAL.id_orientacao_sexual": "Orientação sexual (voluntária; pode ficar em branco)",
    "SITUACAO_CADASTRAL.deseja_informar_ig": "A pessoa aceitou informar a identidade de gênero",
    "SITUACAO_CADASTRAL.id_identidade_genero": "Identidade de gênero (voluntária; pode ficar em branco)",
    "SITUACAO_CADASTRAL.situacao": "ATIVO, INATIVO, TRANSFERIDO ou OBITO (só ATIVO entra nas contagens)",
    "SITUACAO_CADASTRAL.dt_atualizacao_pec": "Última atualização do cadastro no PEC",
    "SITUACAO_DEFICIENCIA.cns": "Pessoa",
    "SITUACAO_DEFICIENCIA.id_carga": "Carga",
    "SITUACAO_DEFICIENCIA.id_tipo_deficiencia": "Tipo de deficiência registrado",
    "PARAMETRO.id_carga": "Carga à qual o parâmetro se aplica",
    "PARAMETRO.idade_min_elegivel": "Idade mínima para perguntar orientação/identidade",
    "TIPO_INCONSISTENCIA.id_tipo_inconsistencia": "Código do tipo",
    "TIPO_INCONSISTENCIA.descricao": "Descrição do tipo",
    "INCONSISTENCIA.id_inconsistencia": "Identificador (sequência)",
    "INCONSISTENCIA.ine_responsavel": "Equipe responsável pelo cadastro",
    "INCONSISTENCIA.cns": "Pessoa",
    "INCONSISTENCIA.id_carga": "Carga em que foi encontrada",
    "INCONSISTENCIA.campo": "Campo com problema",
    "INCONSISTENCIA.id_tipo_inconsistencia": "Tipo da inconsistência",
    "GABARITO_DEFEITO.id_defeito": "Identificador (sequência)",
    "GABARITO_DEFEITO.cns": "Pessoa",
    "GABARITO_DEFEITO.id_carga": "Carga",
    "GABARITO_DEFEITO.campo": "Campo com o defeito plantado",
    "GABARITO_DEFEITO.id_tipo_inconsistencia": "Tipo esperado",
    "PERFIL.id_perfil": "Código do perfil",
    "PERFIL.nome": "Nome do perfil",
    "PERFIL.abrangencia": "O que o perfil enxerga: EQUIPE, UNIDADE, TERRITORIO ou MUNICIPIO",
    "USUARIO.id_usuario": "Identificador (sequência)",
    "USUARIO.nome": "Nome do usuário",
    "USUARIO.login": "Login (único)",
    "USUARIO.id_perfil": "Perfil de acesso",
    "USUARIO.ine": "Equipe do usuário (só para perfis de equipe)",
    "POLITICA.id_politica": "Código da política",
    "POLITICA.nome": "Nome da política",
    "INDICADOR.id_indicador": "Código do indicador",
    "INDICADOR.nome": "Nome do indicador",
    "INDICADOR.descricao": "O que o indicador mede",
    "INDICADOR.formula_calculo": "Forma de cálculo",
    "INDICADOR.id_politica": "Política à qual pertence",
    "APURACAO_INDICADOR.id_apuracao": "Identificador (sequência)",
    "APURACAO_INDICADOR.id_indicador": "Indicador apurado",
    "APURACAO_INDICADOR.id_carga": "Carga (período) da apuração",
    "APURACAO_INDICADOR.nivel_territorial": "MUNICIPIO, DISTRITO, UNIDADE ou EQUIPE",
    "APURACAO_INDICADOR.id_ds": "Distrito (quando o nível é DISTRITO)",
    "APURACAO_INDICADOR.cnes": "Unidade (quando o nível é UNIDADE)",
    "APURACAO_INDICADOR.ine": "Equipe (quando o nível é EQUIPE)",
    "APURACAO_INDICADOR.numerador": "Numerador",
    "APURACAO_INDICADOR.denominador": "Denominador",
    "APURACAO_INDICADOR.valor": "Valor apurado",
    "RESUMO_CARGA.id_carga": "Carga",
    "RESUMO_CARGA.total_registros": "Registros de cadastros principais",
    "RESUMO_CARGA.total_ativos": "Cadastros principais ativos",
    "RESUMO_CARGA.total_negros_ativos": "Ativos da população negra",
    "RESUMO_CARGA.total_lgbt_ativos": "Ativos do público LGBTQIAPN+",
    "RESUMO_CARGA.dt_processamento": "Última atualização do resumo",
    "LOG_ALTERACAO_PESSOA.id_log": "Identificador (sequência)",
    "LOG_ALTERACAO_PESSOA.cns": "Pessoa alterada (sem FK, para preservar o histórico)",
    "LOG_ALTERACAO_PESSOA.campo": "Campo alterado",
    "LOG_ALTERACAO_PESSOA.valor_anterior": "Valor antes (CPF mascarado)",
    "LOG_ALTERACAO_PESSOA.valor_novo": "Valor depois (CPF mascarado)",
    "LOG_ALTERACAO_PESSOA.usuario_bd": "Usuário do banco que fez a alteração",
    "LOG_ALTERACAO_PESSOA.dt_hora_alteracao": "Data e hora da alteração",
}


def main() -> None:
    con = pymysql.connect(host=os.getenv("NEXUS_DB_HOST", "localhost"),
                          port=int(os.getenv("NEXUS_DB_PORT", "3306")),
                          user=os.getenv("NEXUS_DB_USER", "root"),
                          password=os.getenv("NEXUS_DB_PASSWORD", ""), database=BANCO)
    cur = con.cursor()
    cur.execute("""SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY,
                          COLUMN_DEFAULT, EXTRA
                   FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = %s
                   ORDER BY TABLE_NAME, ORDINAL_POSITION""", (BANCO,))
    colunas = defaultdict(list)
    for t, c, tipo, nulo, chave, padrao, extra in cur.fetchall():
        colunas[t].append((c, tipo, nulo, chave, padrao, extra))

    cur.execute("""SELECT k.TABLE_NAME, k.COLUMN_NAME, k.REFERENCED_TABLE_NAME, k.REFERENCED_COLUMN_NAME,
                          r.UPDATE_RULE, r.DELETE_RULE
                   FROM information_schema.KEY_COLUMN_USAGE k
                   JOIN information_schema.REFERENTIAL_CONSTRAINTS r
                     ON r.CONSTRAINT_SCHEMA = k.CONSTRAINT_SCHEMA AND r.CONSTRAINT_NAME = k.CONSTRAINT_NAME
                   WHERE k.TABLE_SCHEMA = %s""", (BANCO,))
    fks = defaultdict(list)
    for t, c, rt, rc, up, de in cur.fetchall():
        fks[(t, c)].append(f"FK → {rt}.{rc} (UPDATE {up}, DELETE {de})")

    cur.execute("""SELECT tc.TABLE_NAME, cc.CHECK_CLAUSE
                   FROM information_schema.TABLE_CONSTRAINTS tc
                   JOIN information_schema.CHECK_CONSTRAINTS cc
                     ON cc.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA AND cc.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
                   WHERE tc.TABLE_SCHEMA = %s AND tc.CONSTRAINT_TYPE = 'CHECK'""", (BANCO,))
    checks = defaultdict(list)
    for t, clausula in cur.fetchall():
        clausula = clausula.replace("`", "").replace("_utf8mb4", "").replace("\\'", "'")
        clausula = re.sub(r"\s+", " ", clausula)
        for c, *_ in colunas[t]:
            if re.search(rf"\b{c}\b", clausula):
                checks[(t, c)].append(f"CHECK {clausula}")
                break

    cur.execute("""SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.STATISTICS
                   WHERE TABLE_SCHEMA = %s AND NON_UNIQUE = 0 AND INDEX_NAME <> 'PRIMARY'
                     AND SEQ_IN_INDEX = 1
                     AND INDEX_NAME NOT IN (SELECT INDEX_NAME FROM information_schema.STATISTICS s2
                                            WHERE s2.TABLE_SCHEMA = %s AND s2.SEQ_IN_INDEX > 1)""",
                (BANCO, BANCO))
    unicos = {(t, c) for t, c in cur.fetchall()}

    print("# Dicionário de dados – Nexus Data\n")
    print(f"Gerado a partir do banco `{BANCO}` (MySQL 8) por `scripts/gerar_dicionario.py`. "
          "Legenda de chave: **PK** chave primária, **FK** chave estrangeira, **UK** único.\n")
    for t in TABELAS:
        if t not in colunas:
            continue
        print(f"## {t}\n\n{TABELAS[t]}\n")
        print("| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |")
        print("|---|---|---|---|---|---|---|")
        for c, tipo, nulo, chave, padrao, extra in colunas[t]:
            ch = []
            if chave == "PRI":
                ch.append("PK")
            if (t, c) in fks:
                ch.append("FK")
            if (t, c) in unicos:
                ch.append("UK")
            restr = fks.get((t, c), []) + checks.get((t, c), [])
            if "auto_increment" in (extra or ""):
                restr.insert(0, "AUTO_INCREMENT")
            pad = "" if padrao is None else str(padrao).replace("_utf8mb4", "").strip("'\\")
            if "on update" in (extra or "").lower():
                pad += " (ON UPDATE CURRENT_TIMESTAMP)"
            print(f"| {c} | {tipo} | {'sim' if nulo == 'YES' else 'não'} | {', '.join(ch)} | {pad} | "
                  f"{'<br>'.join(restr)} | {DESC.get(f'{t}.{c}', '')} |")
        print()


if __name__ == "__main__":
    main()
