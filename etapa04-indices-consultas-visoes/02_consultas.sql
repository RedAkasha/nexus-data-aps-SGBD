-- =====================================================================
-- NEXUSDATA - ETAPA 04 - ENTREGAVEL 2: SQL DAS CONSULTAS (C9 A C12)
-- Banco: nexusdata_etapa02 | SGBD: MySQL 8.0+
--
-- CONTEUDO (numeracao continua a da Etapa 03, que vai de C1 a C8):
--   C9)  ANTI JOIN (LEFT JOIN ... IS NULL): equipes sem acao formativa
--   C10) FULL OUTER JOIN: auditoria x gabarito de defeitos
--   C11) SUBCONSULTA (tabela derivada + escalar): equipes abaixo da media
--   C12) SUBCONSULTA CORRELACIONADA (NOT EXISTS): entradas e saidas
--
-- Convencoes do projeto (as mesmas da Etapa 03):
--   * carga corrente = maior id_carga presente em SITUACAO_CADASTRAL;
--   * so situacao ATIVO entra nas contagens populacionais;
--   * duplicidades ficam fora (PESSOA.cns_principal IS NULL).
-- =====================================================================

USE nexusdata_etapa02;

-- ---------------------------------------------------------------------
-- C9) ANTI JOIN - Equipes que nunca receberam acao formativa
--
-- Pergunta da gestao: "quais equipes ainda nao passaram por capacitacao e
-- por onde comecar?". O anti join (LEFT JOIN ACAO_FORMATIVA + IS NULL)
-- devolve so as equipes SEM nenhuma acao. Para priorizar, cada equipe vem
-- com o volume de cadastros ativos e de inconsistencias na carga corrente.
-- As contagens sao agregadas antes do JOIN, para nao multiplicar linhas.
-- Indices usados: idx_sc_carga_situacao e idx_inc_carga_equipe.
-- ---------------------------------------------------------------------
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
    WHERE sc.id_carga = (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL)
      AND sc.situacao = 'ATIVO'
      AND p.cns_principal IS NULL
    GROUP BY sc.ine
) pop ON pop.ine = e.ine
LEFT JOIN (
    SELECT i.ine_responsavel AS ine, COUNT(*) AS qtd
    FROM INCONSISTENCIA i
    WHERE i.id_carga = (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL)
    GROUP BY i.ine_responsavel
) inc ON inc.ine = e.ine
WHERE af.id_acao IS NULL                       -- anti join: nao existe acao
ORDER BY inconsistencias_carga DESC, cadastros_ativos DESC, e.ine;

-- ---------------------------------------------------------------------
-- C10) FULL OUTER JOIN - Auditoria automatica x gabarito de defeitos
--
-- GABARITO_DEFEITO guarda os defeitos plantados de proposito nos dados de
-- teste; INCONSISTENCIA guarda o que a auditoria (sp_auditar_inconsistencias_carga,
-- Etapa 05) e as equipes registraram. O FULL OUTER JOIN entre as duas,
-- pareando pessoa + carga + campo + tipo, separa tres grupos:
--   * acerto ............ esta nas duas (verdadeiro positivo);
--   * nao detectado ..... so no gabarito (falso negativo);
--   * sem gabarito ...... so em INCONSISTENCIA (falso positivo ou defeito
--                         que nao estava previsto no gabarito).
-- Com isso a gestao mede a precisao e a sensibilidade da auditoria.
--
-- O MySQL nao tem FULL OUTER JOIN. A forma equivalente e:
--   LEFT JOIN  (todas as linhas do gabarito, com ou sem par)
--   UNION ALL
--   RIGHT JOIN ... WHERE lado esquerdo IS NULL (so as detectadas sem par).
-- O UNION ALL com o filtro IS NULL nao duplica os pares encontrados.
-- Indice usado no pareamento: uk_inc_ocorrencia.
-- ---------------------------------------------------------------------
WITH ref AS (
    SELECT MAX(id_carga) AS id_carga FROM SITUACAO_CADASTRAL
),
gab AS (
    SELECT g.cns, g.id_carga, g.campo, g.id_tipo_inconsistencia
    FROM GABARITO_DEFEITO g JOIN ref ON ref.id_carga = g.id_carga
),
det AS (
    SELECT i.cns, i.id_carga, i.campo, i.id_tipo_inconsistencia
    FROM INCONSISTENCIA i JOIN ref ON ref.id_carga = i.id_carga
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
ORDER BY campo, ti.id_tipo_inconsistencia;

-- ---------------------------------------------------------------------
-- C11) SUBCONSULTAS - Equipes com completude de orientacao sexual abaixo
--      da media municipal na carga corrente
--
-- Orientacao sexual e identidade de genero sao voluntarias, mas a
-- completude delas e um indicador de qualidade (secao 5 do minimundo).
-- A tabela derivada calcula a completude de cada equipe; a subconsulta
-- escalar calcula a media do municipio, usada tanto na coluna de
-- comparacao quanto no filtro WHERE. Resultado: lista de equipes a apoiar.
-- Indice usado: idx_sc_carga_situacao (nas duas subconsultas).
-- ---------------------------------------------------------------------
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
        WHERE sc2.id_carga = (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL)
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
    WHERE sc.id_carga = (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL)
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
        WHERE sc3.id_carga = (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL)
          AND sc3.situacao = 'ATIVO'
          AND p3.cns_principal IS NULL)
ORDER BY t.pct_orientacao, t.ativos DESC;

-- ---------------------------------------------------------------------
-- C12) SUBCONSULTAS CORRELACIONADAS - Entradas e saidas entre a carga
--      anterior e a carga corrente, por distrito
--
-- Cada carga e um retrato do periodo (secao 5). Comparar dois retratos
-- seguidos mostra a dinamica do cadastro em cada territorio:
--   * entrada: ATIVO na carga corrente e NAO ATIVO na anterior
--              (cadastro novo, reativado ou que chegou de outro territorio);
--   * saida:   ATIVO na carga anterior e NAO ATIVO na corrente
--              (obito, transferencia, inativacao ou ausencia na extracao).
-- As duas regras sao subconsultas correlacionadas NOT EXISTS: para cada
-- registro, procura-se a mesma pessoa no outro retrato. O distrito da
-- saida e o da equipe da carga anterior; o da entrada, o da corrente.
-- Indices usados: PK (cns, id_carga) nas subconsultas correlacionadas e
-- idx_sc_carga_situacao na leitura externa.
-- ---------------------------------------------------------------------
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
    SELECT MAX(id_carga) AS corrente,
           (SELECT MAX(x.id_carga) FROM SITUACAO_CADASTRAL x
            WHERE x.id_carga < (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL)) AS anterior
    FROM SITUACAO_CADASTRAL
) ref
JOIN PESSOA p              ON p.cns = sc.cns
JOIN EQUIPE e              ON e.ine = sc.ine
JOIN UNIDADE_SAUDE u       ON u.cnes = e.cnes
JOIN DISTRITO_SANITARIO ds ON ds.id_ds = u.id_ds
WHERE sc.id_carga IN (ref.corrente, ref.anterior)
  AND p.cns_principal IS NULL
GROUP BY ds.id_ds, ds.nome
ORDER BY ds.id_ds;
