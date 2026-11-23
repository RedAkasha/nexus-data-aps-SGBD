"""SQL das consultas (Etapas 03 e 04) e das visoes, na forma usada pela interface.

O texto e o mesmo dos arquivos .sql das etapas, com duas diferencas:
  * a carga corrente (SELECT MAX(id_carga) ...) virou o parametro %(carga)s,
    para que o usuario escolha qualquer carga;
  * onde faz sentido, ha o filtro opcional de distrito %(ds)s (0 = todos).
"""

FILTRO_DS = "(%(ds)s = 0 OR ds.id_ds = %(ds)s)"

C1 = f"""
SELECT ds.id_ds, ds.nome AS distrito,
       COUNT(*) AS total_ativos,
       SUM(rc.pop_negra = 1) AS populacao_negra,
       ROUND(100 * SUM(rc.pop_negra = 1) / NULLIF(COUNT(*), 0), 1) AS percentual_negra
FROM SITUACAO_CADASTRAL sc
JOIN PESSOA p ON p.cns = sc.cns
JOIN RACA_COR rc ON rc.id_raca_cor = sc.id_raca_cor
JOIN EQUIPE e ON e.ine = sc.ine
JOIN UNIDADE_SAUDE u ON u.cnes = e.cnes
JOIN DISTRITO_SANITARIO ds ON ds.id_ds = u.id_ds
WHERE sc.id_carga = %(carga)s
  AND sc.situacao = 'ATIVO'
  AND p.cns_principal IS NULL
  AND {FILTRO_DS}
GROUP BY ds.id_ds, ds.nome
ORDER BY percentual_negra DESC, ds.id_ds
"""

C2 = f"""
WITH classificacao AS (
    SELECT sc.cns,
           CASE
             WHEN COALESCE(ori.publico_lgbt, 0) = 1
               OR COALESCE(ide.publico_lgbt, 0) = 1
               THEN 'LGBTQIAPN+'
             WHEN (sc.id_orientacao_sexual IS NULL OR sc.id_orientacao_sexual = 9)
               OR (sc.id_identidade_genero IS NULL OR sc.id_identidade_genero = 9)
               THEN 'Sem informacao'
             ELSE 'Nao LGBTQIAPN+'
           END AS categoria
    FROM SITUACAO_CADASTRAL sc
    JOIN PESSOA p ON p.cns = sc.cns
    JOIN EQUIPE e ON e.ine = sc.ine
    JOIN UNIDADE_SAUDE u ON u.cnes = e.cnes
    JOIN DISTRITO_SANITARIO ds ON ds.id_ds = u.id_ds
    LEFT JOIN ORIENTACAO_SEXUAL ori
      ON ori.id_orientacao_sexual = sc.id_orientacao_sexual
    LEFT JOIN IDENTIDADE_GENERO ide
      ON ide.id_identidade_genero = sc.id_identidade_genero
    WHERE sc.id_carga = %(carga)s
      AND sc.situacao = 'ATIVO'
      AND p.cns_principal IS NULL
      AND {FILTRO_DS}
),
totais AS (
    SELECT categoria, COUNT(*) AS pessoas
    FROM classificacao
    GROUP BY categoria
)
SELECT categoria, pessoas,
       ROUND(100 * pessoas / NULLIF(SUM(pessoas) OVER (), 0), 1) AS percentual
FROM totais
ORDER BY pessoas DESC
"""

C3 = f"""
SELECT ds.nome AS distrito,
       COUNT(*) AS total_ativos,
       ROUND(100 * AVG(sc.id_orientacao_sexual IS NOT NULL
                        AND sc.id_orientacao_sexual <> 9), 1) AS pct_orientacao,
       ROUND(100 * AVG(sc.id_identidade_genero IS NOT NULL
                        AND sc.id_identidade_genero <> 9), 1) AS pct_identidade,
       ROUND(100 * AVG(NULLIF(TRIM(sc.nome_social), '') IS NOT NULL), 1) AS pct_nome_social
FROM SITUACAO_CADASTRAL sc
JOIN PESSOA p ON p.cns = sc.cns
JOIN EQUIPE e ON e.ine = sc.ine
JOIN UNIDADE_SAUDE u ON u.cnes = e.cnes
JOIN DISTRITO_SANITARIO ds ON ds.id_ds = u.id_ds
WHERE sc.id_carga = %(carga)s
  AND sc.situacao = 'ATIVO'
  AND p.cns_principal IS NULL
  AND {FILTRO_DS}
GROUP BY ds.id_ds, ds.nome
ORDER BY ds.id_ds
"""

C4 = f"""
WITH totais AS (
    SELECT ds.id_ds, ds.nome AS distrito,
           ti.id_tipo_inconsistencia, ti.descricao AS tipo_inconsistencia,
           COUNT(*) AS quantidade
    FROM INCONSISTENCIA i
    JOIN TIPO_INCONSISTENCIA ti
      ON ti.id_tipo_inconsistencia = i.id_tipo_inconsistencia
    JOIN EQUIPE e ON e.ine = i.ine_responsavel
    JOIN UNIDADE_SAUDE u ON u.cnes = e.cnes
    JOIN DISTRITO_SANITARIO ds ON ds.id_ds = u.id_ds
    WHERE i.id_carga = %(carga)s
      AND {FILTRO_DS}
    GROUP BY ds.id_ds, ds.nome, ti.id_tipo_inconsistencia, ti.descricao
)
SELECT distrito, tipo_inconsistencia, quantidade,
       ROUND(100 * quantidade / NULLIF(SUM(quantidade) OVER (PARTITION BY id_ds), 0), 1)
         AS pct_no_distrito
FROM totais
ORDER BY id_ds, quantidade DESC
"""

C5 = """
WITH acoes AS (
    SELECT ine, COUNT(*) AS qtd_acoes
    FROM ACAO_FORMATIVA
    GROUP BY ine
),
inconsistencias AS (
    SELECT ine_responsavel AS ine, COUNT(*) AS qtd_inconsistencias
    FROM INCONSISTENCIA
    WHERE id_carga = %(carga)s
    GROUP BY ine_responsavel
)
SELECT CASE WHEN a.ine IS NULL THEN 'Sem acao formativa'
            ELSE 'Com acao formativa' END AS grupo,
       COUNT(*) AS qtd_equipes,
       SUM(COALESCE(i.qtd_inconsistencias, 0)) AS total_inconsistencias,
       ROUND(AVG(COALESCE(i.qtd_inconsistencias, 0)), 2) AS media_por_equipe
FROM EQUIPE e
LEFT JOIN acoes a ON a.ine = e.ine
LEFT JOIN inconsistencias i ON i.ine = e.ine
GROUP BY grupo
ORDER BY grupo
"""

C6 = f"""
SELECT ds.id_ds, ds.nome AS distrito, td.descricao AS tipo_deficiencia,
       COUNT(DISTINCT sc.cns) AS pessoas
FROM SITUACAO_CADASTRAL sc
JOIN PESSOA p ON p.cns = sc.cns
JOIN SITUACAO_DEFICIENCIA sd
  ON sd.cns = sc.cns AND sd.id_carga = sc.id_carga
JOIN TIPO_DEFICIENCIA td ON td.id_tipo_deficiencia = sd.id_tipo_deficiencia
JOIN EQUIPE e ON e.ine = sc.ine
JOIN UNIDADE_SAUDE u ON u.cnes = e.cnes
JOIN DISTRITO_SANITARIO ds ON ds.id_ds = u.id_ds
WHERE sc.id_carga = %(carga)s
  AND sc.situacao = 'ATIVO'
  AND p.cns_principal IS NULL
  AND {FILTRO_DS}
GROUP BY ds.id_ds, ds.nome, td.id_tipo_deficiencia, td.descricao
ORDER BY ds.id_ds, pessoas DESC
"""

C7 = f"""
SELECT ds.id_ds, ds.nome AS distrito,
       CASE
         WHEN TIMESTAMPDIFF(YEAR, p.dt_nascimento, c.periodo_ref_fim) < 10 THEN '0 a 9'
         WHEN TIMESTAMPDIFF(YEAR, p.dt_nascimento, c.periodo_ref_fim) BETWEEN 10 AND 19 THEN '10 a 19'
         WHEN TIMESTAMPDIFF(YEAR, p.dt_nascimento, c.periodo_ref_fim) BETWEEN 20 AND 39 THEN '20 a 39'
         WHEN TIMESTAMPDIFF(YEAR, p.dt_nascimento, c.periodo_ref_fim) BETWEEN 40 AND 59 THEN '40 a 59'
         ELSE '60 ou mais'
       END AS faixa_etaria,
       COUNT(*) AS pessoas
FROM SITUACAO_CADASTRAL sc
JOIN PESSOA p ON p.cns = sc.cns
JOIN CARGA c ON c.id_carga = sc.id_carga
JOIN EQUIPE e ON e.ine = sc.ine
JOIN UNIDADE_SAUDE u ON u.cnes = e.cnes
JOIN DISTRITO_SANITARIO ds ON ds.id_ds = u.id_ds
WHERE sc.id_carga = %(carga)s
  AND sc.situacao = 'ATIVO'
  AND p.cns_principal IS NULL
  AND {FILTRO_DS}
GROUP BY ds.id_ds, ds.nome, faixa_etaria
ORDER BY ds.id_ds,
         MIN(TIMESTAMPDIFF(YEAR, p.dt_nascimento, c.periodo_ref_fim))
"""

C8 = """
WITH por_campo AS (
    SELECT i.campo, ti.descricao AS tipo_inconsistencia,
           COUNT(*) AS quantidade
    FROM INCONSISTENCIA i
    JOIN TIPO_INCONSISTENCIA ti
      ON ti.id_tipo_inconsistencia = i.id_tipo_inconsistencia
    WHERE i.id_carga = %(carga)s
    GROUP BY i.campo, ti.id_tipo_inconsistencia, ti.descricao
)
SELECT campo, tipo_inconsistencia, quantidade,
       ROUND(100 * quantidade / NULLIF(SUM(quantidade) OVER (), 0), 1)
         AS pct_total_inconsistencias
FROM por_campo
ORDER BY quantidade DESC, campo
"""

C9 = f"""
SELECT ds.id_ds,
       ds.nome                         AS distrito,
       u.nome                          AS unidade,
       e.ine,
       e.nome                          AS equipe,
       COALESCE(pop.ativos, 0)         AS cadastros_ativos,
       COALESCE(inc.qtd, 0)            AS inconsistencias_carga,
       ROUND(100 * COALESCE(inc.qtd, 0) / NULLIF(pop.ativos, 0), 1)
                                       AS inconsistencias_por_100
FROM EQUIPE e
JOIN UNIDADE_SAUDE u        ON u.cnes = e.cnes
JOIN DISTRITO_SANITARIO ds  ON ds.id_ds = u.id_ds
LEFT JOIN ACAO_FORMATIVA af ON af.ine = e.ine
LEFT JOIN (
    SELECT sc.ine, COUNT(*) AS ativos
    FROM SITUACAO_CADASTRAL sc
    JOIN PESSOA p ON p.cns = sc.cns
    WHERE sc.id_carga = %(carga)s
      AND sc.situacao = 'ATIVO'
      AND p.cns_principal IS NULL
    GROUP BY sc.ine
) pop ON pop.ine = e.ine
LEFT JOIN (
    SELECT i.ine_responsavel AS ine, COUNT(*) AS qtd
    FROM INCONSISTENCIA i
    WHERE i.id_carga = %(carga)s
    GROUP BY i.ine_responsavel
) inc ON inc.ine = e.ine
WHERE af.id_acao IS NULL
  AND {FILTRO_DS}
ORDER BY inconsistencias_carga DESC, cadastros_ativos DESC, e.ine
"""

C10 = """
WITH gab AS (
    SELECT g.cns, g.id_carga, g.campo, g.id_tipo_inconsistencia
    FROM GABARITO_DEFEITO g WHERE g.id_carga = %(carga)s
),
det AS (
    SELECT i.cns, i.id_carga, i.campo, i.id_tipo_inconsistencia
    FROM INCONSISTENCIA i WHERE i.id_carga = %(carga)s
),
pareamento AS (
    SELECT g.campo AS campo_gab, g.id_tipo_inconsistencia AS tipo_gab,
           d.campo AS campo_det, d.id_tipo_inconsistencia AS tipo_det
    FROM gab g
    LEFT JOIN det d
      ON d.cns = g.cns AND d.id_carga = g.id_carga
     AND d.campo = g.campo AND d.id_tipo_inconsistencia = g.id_tipo_inconsistencia
    UNION ALL
    SELECT g.campo, g.id_tipo_inconsistencia,
           d.campo, d.id_tipo_inconsistencia
    FROM gab g
    RIGHT JOIN det d
      ON d.cns = g.cns AND d.id_carga = g.id_carga
     AND d.campo = g.campo AND d.id_tipo_inconsistencia = g.id_tipo_inconsistencia
    WHERE g.cns IS NULL
)
SELECT COALESCE(p.campo_gab, p.campo_det)               AS campo,
       ti.descricao                                     AS tipo_inconsistencia,
       SUM(p.campo_gab IS NOT NULL AND p.campo_det IS NOT NULL) AS acertos,
       SUM(p.campo_det IS NULL)                         AS nao_detectados,
       SUM(p.campo_gab IS NULL)                         AS sem_gabarito,
       ROUND(100 * SUM(p.campo_gab IS NOT NULL AND p.campo_det IS NOT NULL)
             / NULLIF(SUM(p.campo_det IS NOT NULL), 0), 1) AS precisao_pct,
       ROUND(100 * SUM(p.campo_gab IS NOT NULL AND p.campo_det IS NOT NULL)
             / NULLIF(SUM(p.campo_gab IS NOT NULL), 0), 1) AS sensibilidade_pct
FROM pareamento p
JOIN TIPO_INCONSISTENCIA ti
  ON ti.id_tipo_inconsistencia = COALESCE(p.tipo_gab, p.tipo_det)
GROUP BY campo, ti.id_tipo_inconsistencia, ti.descricao
ORDER BY campo, ti.id_tipo_inconsistencia
"""

C11 = f"""
SELECT ds.nome                          AS distrito,
       e.ine,
       e.nome                           AS equipe,
       t.ativos,
       t.pct_orientacao,
       t.pct_identidade,
       (SELECT ROUND(100 * AVG(sc2.id_orientacao_sexual IS NOT NULL
                               AND sc2.id_orientacao_sexual <> 9), 1)
        FROM SITUACAO_CADASTRAL sc2
        JOIN PESSOA p2 ON p2.cns = sc2.cns
        WHERE sc2.id_carga = %(carga)s
          AND sc2.situacao = 'ATIVO'
          AND p2.cns_principal IS NULL)  AS media_municipal_orientacao
FROM (
    SELECT sc.ine,
           COUNT(*) AS ativos,
           ROUND(100 * AVG(sc.id_orientacao_sexual IS NOT NULL
                           AND sc.id_orientacao_sexual <> 9), 1) AS pct_orientacao,
           ROUND(100 * AVG(sc.id_identidade_genero IS NOT NULL
                           AND sc.id_identidade_genero <> 9), 1) AS pct_identidade
    FROM SITUACAO_CADASTRAL sc
    JOIN PESSOA p ON p.cns = sc.cns
    WHERE sc.id_carga = %(carga)s
      AND sc.situacao = 'ATIVO'
      AND p.cns_principal IS NULL
    GROUP BY sc.ine
) t
JOIN EQUIPE e              ON e.ine = t.ine
JOIN UNIDADE_SAUDE u       ON u.cnes = e.cnes
JOIN DISTRITO_SANITARIO ds ON ds.id_ds = u.id_ds
WHERE t.pct_orientacao < (
        SELECT 100 * AVG(sc3.id_orientacao_sexual IS NOT NULL
                         AND sc3.id_orientacao_sexual <> 9)
        FROM SITUACAO_CADASTRAL sc3
        JOIN PESSOA p3 ON p3.cns = sc3.cns
        WHERE sc3.id_carga = %(carga)s
          AND sc3.situacao = 'ATIVO'
          AND p3.cns_principal IS NULL)
  AND {FILTRO_DS}
ORDER BY t.pct_orientacao, t.ativos DESC
"""

C12 = f"""
SELECT ds.id_ds,
       ds.nome AS distrito,
       SUM(sc.id_carga = ref.corrente AND sc.situacao = 'ATIVO'
           AND NOT EXISTS (SELECT 1
                           FROM SITUACAO_CADASTRAL a
                           WHERE a.cns = sc.cns
                             AND a.id_carga = ref.anterior
                             AND a.situacao = 'ATIVO'))      AS entradas,
       SUM(sc.id_carga = ref.anterior AND sc.situacao = 'ATIVO'
           AND NOT EXISTS (SELECT 1
                           FROM SITUACAO_CADASTRAL n
                           WHERE n.cns = sc.cns
                             AND n.id_carga = ref.corrente
                             AND n.situacao = 'ATIVO'))      AS saidas,
       SUM(sc.id_carga = ref.corrente AND sc.situacao = 'ATIVO') AS ativos_corrente,
       COALESCE(SUM(sc.id_carga = ref.anterior AND sc.situacao = 'ATIVO'), 0)
                                                             AS ativos_anterior
FROM SITUACAO_CADASTRAL sc
CROSS JOIN (
    SELECT %(carga)s AS corrente,
           (SELECT MAX(x.id_carga) FROM SITUACAO_CADASTRAL x
            WHERE x.id_carga < %(carga)s) AS anterior
) ref
JOIN PESSOA p              ON p.cns = sc.cns
JOIN EQUIPE e              ON e.ine = sc.ine
JOIN UNIDADE_SAUDE u       ON u.cnes = e.cnes
JOIN DISTRITO_SANITARIO ds ON ds.id_ds = u.id_ds
WHERE sc.id_carga IN (ref.corrente, ref.anterior)
  AND p.cns_principal IS NULL
  AND {FILTRO_DS}
GROUP BY ds.id_ds, ds.nome
ORDER BY ds.id_ds
"""

V_EVOLUCAO = """
SELECT * FROM VW_EVOLUCAO_CARGAS
WHERE id_carga BETWEEN %(carga_ini)s AND %(carga)s
ORDER BY id_carga
"""

V_PERFIL = """
SELECT distrito, unidade, ine, equipe, ativos, populacao_negra, publico_lgbt,
       lgbt_sem_informacao, pessoas_com_deficiencia, pct_populacao_negra,
       pct_orientacao, pct_identidade, com_nome_social
FROM VW_PERFIL_EQUIDADE_EQUIPE
WHERE id_carga = %(carga)s
  AND (%(ds)s = 0 OR id_ds = %(ds)s)
ORDER BY id_ds, ine
"""

V_LISTA = """
SELECT id_carga, distrito, equipe, nome_exibicao, usa_nome_social, campo,
       tipo_inconsistencia, situacao_na_carga, equipe_capacitada
FROM VW_LISTA_NOMINAL_INCONSISTENCIAS
WHERE id_carga = %(carga)s
  AND (%(ds)s = 0 OR id_ds = %(ds)s)
  AND (%(ine)s = '' OR ine = %(ine)s)
ORDER BY distrito, equipe, nome_exibicao
"""

# Catalogo usado pela pagina de consultas.
# grafico: (tipo, x, y, cor) - interpretado em paginas/consultas.py
CATALOGO = {
    "C1": dict(etapa="Etapa 03", titulo="Populacao negra ativa por distrito",
               tecnica="JOIN de 6 tabelas + agregacao", sql=C1, ds=True,
               desc="Total de pessoas ativas, quantidade preta/parda e percentual por Distrito Sanitario.",
               grafico=("barra", "distrito", "percentual_negra", None)),
    "C2": dict(etapa="Etapa 03", titulo="Publico LGBTQIAPN+ x sem informacao x demais",
               tecnica="CTE + LEFT JOIN + funcao de janela", sql=C2, ds=True,
               desc="Classificacao da secao 4 do minimundo; quem nao informou fica a parte.",
               grafico=("pizza", "categoria", "pessoas", None)),
    "C3": dict(etapa="Etapa 03", titulo="Completude dos campos voluntarios por distrito",
               tecnica="JOIN + AVG de expressao booleana", sql=C3, ds=True,
               desc="Percentual de orientacao sexual, identidade de genero e nome social preenchidos (codigo 9 nao conta).",
               grafico=("barras_agrupadas", "distrito",
                        ["pct_orientacao", "pct_identidade", "pct_nome_social"], None)),
    "C4": dict(etapa="Etapa 03", titulo="Inconsistencias por distrito e tipo",
               tecnica="CTE + janela PARTITION BY", sql=C4, ds=True,
               desc="Participacao de cada tipo de inconsistencia no total do distrito.",
               grafico=("barra_empilhada", "distrito", "quantidade", "tipo_inconsistencia")),
    "C5": dict(etapa="Etapa 03", titulo="Equipes com e sem acao formativa x inconsistencias",
               tecnica="CTEs agregadas + LEFT JOIN", sql=C5, ds=False,
               desc="Media de inconsistencias por equipe nos dois grupos.",
               grafico=("barra", "grupo", "media_por_equipe", None)),
    "C6": dict(etapa="Etapa 03", titulo="Pessoas com deficiencia por distrito e tipo",
               tecnica="JOIN de 7 tabelas + COUNT DISTINCT", sql=C6, ds=True,
               desc="Uma pessoa pode ter mais de uma deficiencia; COUNT(DISTINCT) evita dupla contagem no grupo.",
               grafico=("barra_empilhada", "distrito", "pessoas", "tipo_deficiencia")),
    "C7": dict(etapa="Etapa 03", titulo="Perfil etario da populacao ativa por distrito",
               tecnica="JOIN + CASE + TIMESTAMPDIFF", sql=C7, ds=True,
               desc="Idade calculada no fim do periodo da carga (nao e armazenada).",
               grafico=("barra_empilhada", "distrito", "pessoas", "faixa_etaria")),
    "C8": dict(etapa="Etapa 03", titulo="Inconsistencias por campo",
               tecnica="CTE + janela sobre o total", sql=C8, ds=False,
               desc="Campos mais problematicos da carga e participacao no total.",
               grafico=("barra_h", "quantidade", "campo", "tipo_inconsistencia")),
    "C9": dict(etapa="Etapa 04", titulo="Equipes que nunca receberam acao formativa",
               tecnica="ANTI JOIN (LEFT JOIN ... IS NULL)", sql=C9, ds=True,
               desc="Prioridade para capacitacao: equipes sem acao, com volume de cadastros e inconsistencias.",
               grafico=("barra", "equipe", "inconsistencias_por_100", None)),
    "C10": dict(etapa="Etapa 04", titulo="Auditoria automatica x gabarito de defeitos",
                tecnica="FULL OUTER JOIN (LEFT JOIN UNION ALL RIGHT JOIN)", sql=C10, ds=False,
                desc="Acertos, defeitos nao detectados e registros sem gabarito; precisao e sensibilidade da auditoria.",
                grafico=("barra_empilhada_cols", "campo",
                         ["acertos", "nao_detectados", "sem_gabarito"], None)),
    "C11": dict(etapa="Etapa 04", titulo="Equipes abaixo da media municipal de completude",
                tecnica="SUBCONSULTAS (tabela derivada + escalar)", sql=C11, ds=True,
                desc="Equipes cuja completude de orientacao sexual esta abaixo da media do municipio.",
                grafico=("barra", "equipe", "pct_orientacao", None)),
    "C12": dict(etapa="Etapa 04", titulo="Entradas e saidas entre cargas por distrito",
                tecnica="SUBCONSULTAS CORRELACIONADAS (NOT EXISTS)", sql=C12, ds=True,
                desc="Cadastros que entraram ou sairam da condicao de ativo entre a carga anterior e a escolhida.",
                grafico=("barras_agrupadas", "distrito", ["entradas", "saidas"], None)),
}

VISOES = {
    "VW_EVOLUCAO_CARGAS": dict(etapa="Etapa 03", sql=V_EVOLUCAO,
        desc="Resumo por carga mantido por trigger, com a variacao em relacao a carga anterior (LAG)."),
    "VW_PERFIL_EQUIDADE_EQUIPE": dict(etapa="Etapa 04", sql=V_PERFIL,
        desc="Publicos das politicas e completude por equipe, unidade e distrito (agregado, sem identificar pessoas)."),
    "VW_LISTA_NOMINAL_INCONSISTENCIAS": dict(etapa="Etapa 04", sql=V_LISTA,
        desc="Lista nominal para as equipes, com nome social quando existir (regra 6) e sem CPF."),
}
