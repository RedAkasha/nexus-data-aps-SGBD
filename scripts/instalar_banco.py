"""Instala o banco do Nexus Data executando, em ordem, os scripts de todas as etapas.

Uso (na raiz do repositorio):
    python scripts/instalar_banco.py                 # instala tudo (Etapas 02 a 06)
    python scripts/instalar_banco.py --sem-demo      # sem a carga de demonstracao da Etapa 06
    python scripts/instalar_banco.py --quieto        # nao imprime os resultados dos SELECT de teste

Conexao: variaveis de ambiente NEXUS_DB_HOST, NEXUS_DB_PORT, NEXUS_DB_USER, NEXUS_DB_PASSWORD
(padrao: localhost, 3306, root, senha vazia). O banco nexusdata_etapa02 e APAGADO e recriado.

Os arquivos .sql usam DELIMITER (sintaxe do cliente mysql / Workbench). Este instalador
le os arquivos, interpreta DELIMITER e envia cada instrucao ao servidor pelo PyMySQL.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

import pymysql

RAIZ = Path(__file__).resolve().parents[1]
BANCO = "nexusdata_etapa02"

SCRIPTS = [
    "etapa02-criacao-insercao/01_criacao_tabelas.sql",
    "etapa02-criacao-insercao/02_insercao_dados.sql",
    "etapa03-consultas-interface/01_consultas.sql",
    "etapa03-consultas-interface/02_evolucao_cargas.sql",
    "etapa04-indices-consultas-visoes/01_indices.sql",
    "etapa04-indices-consultas-visoes/02_consultas.sql",
    "etapa04-indices-consultas-visoes/03_visoes.sql",
    "etapa05-funcoes-procedimentos-triggers/01_funcoes.sql",
    "etapa05-funcoes-procedimentos-triggers/02_procedimentos.sql",
    "etapa05-funcoes-procedimentos-triggers/03_triggers.sql",
]
DEMO = "etapa06-aplicacao-final/01_carga_demonstracao.sql"


def dividir_instrucoes(texto: str) -> list[str]:
    """Divide um script em instrucoes, respeitando DELIMITER, aspas e comentarios."""
    instrucoes: list[str] = []
    delim = ";"
    atual: list[str] = []
    i, n = 0, len(texto)
    inicio_linha = True
    while i < n:
        if inicio_linha:
            m = re.match(r"[ \t]*DELIMITER[ \t]+(\S+)[ \t]*(\r?\n|$)", texto[i:], re.IGNORECASE)
            if m:
                resto = "".join(atual).strip()
                if resto:
                    instrucoes.append(resto)
                atual = []
                delim = m.group(1)
                i += m.end()
                continue
        c = texto[i]
        if c in ("'", '"', "`"):
            j = i + 1
            while j < n:
                if texto[j] == "\\" and c != "`":
                    j += 2
                    continue
                if texto[j] == c:
                    if j + 1 < n and texto[j + 1] == c:
                        j += 2
                        continue
                    break
                j += 1
            atual.append(texto[i:j + 1])
            i = j + 1
            inicio_linha = False
            continue
        if texto.startswith("--", i) and (i + 2 >= n or texto[i + 2] in " \t\r\n"):
            j = texto.find("\n", i)
            j = n if j == -1 else j
            i = j
            continue
        if c == "#":
            j = texto.find("\n", i)
            i = n if j == -1 else j
            continue
        if texto.startswith("/*", i):
            j = texto.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        if texto.startswith(delim, i):
            resto = "".join(atual).strip()
            if resto:
                instrucoes.append(resto)
            atual = []
            i += len(delim)
            inicio_linha = False
            continue
        atual.append(c)
        inicio_linha = c == "\n"
        i += 1
    resto = "".join(atual).strip()
    if resto:
        instrucoes.append(resto)
    return instrucoes


def imprimir_resultado(cur, limite: int = 12) -> None:
    if cur.description is None:
        return
    nomes = [d[0] for d in cur.description]
    linhas = cur.fetchall()
    print("      | " + " | ".join(nomes))
    for linha in linhas[:limite]:
        print("      | " + " | ".join("NULL" if v is None else str(v) for v in linha))
    if len(linhas) > limite:
        print(f"      | ... ({len(linhas)} linhas)")


def executar_arquivo(con, caminho: Path, quieto: bool) -> None:
    texto = caminho.read_text(encoding="utf-8")
    instrucoes = dividir_instrucoes(texto)
    t0 = time.time()
    print(f"\n==> {caminho.relative_to(RAIZ)}  ({len(instrucoes)} instrucoes)")
    with con.cursor() as cur:
        for sql in instrucoes:
            try:
                cur.execute(sql)
            except pymysql.MySQLError as erro:
                print(f"\nERRO em {caminho.name}:\n{sql[:400]}\n-> {erro}")
                raise
            while True:
                if not quieto and cur.description is not None:
                    primeira = " ".join(sql.split())[:90]
                    print(f"   -- {primeira}")
                    imprimir_resultado(cur)
                if not cur.nextset():
                    break
    con.commit()
    print(f"    ok ({time.time() - t0:.1f}s)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sem-demo", action="store_true", help="nao executa a carga de demonstracao")
    ap.add_argument("--quieto", action="store_true", help="nao imprime resultados de SELECT")
    a = ap.parse_args()

    con = pymysql.connect(
        host=os.getenv("NEXUS_DB_HOST", "localhost"),
        port=int(os.getenv("NEXUS_DB_PORT", "3306")),
        user=os.getenv("NEXUS_DB_USER", "root"),
        password=os.getenv("NEXUS_DB_PASSWORD", ""),
        charset="utf8mb4",
        autocommit=True,
        client_flag=pymysql.constants.CLIENT.MULTI_STATEMENTS,
        init_command="SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci",
    )
    with con.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {BANCO}")
    arquivos = SCRIPTS + ([] if a.sem_demo else [DEMO])
    for rel in arquivos:
        executar_arquivo(con, RAIZ / rel, a.quieto)
    print(f"\nBanco {BANCO} instalado com {len(arquivos)} scripts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
