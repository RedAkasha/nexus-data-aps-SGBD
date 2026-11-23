-- =====================================================================
-- NEXUSDATA - ETAPA 03 - ENTREGAVEL 1: SQL DAS CONSULTAS (C1 A C8)
-- Banco: nexusdata_etapa02 | SGBD: MySQL 8.0+
--
-- IMPORTANTE:
-- 1) Execute primeiro os scripts da Etapa 02 (criacao e insercao).
-- 2) Este arquivo NAO apaga nem recria tabelas da Etapa 02.
-- 3) Os dados historicos de SITUACAO_CADASTRAL devem ser preservados.
-- 4) Cargas novas devem ser inseridas em CARGA antes dos registros da carga.
--
-- Regras aplicadas:
-- * Somente situacao ATIVO entra nas consultas populacionais.
-- * Duplicidades sao excluidas por PESSOA.cns_principal IS NULL.
-- * A carga corrente e a de maior id_carga presente em SITUACAO_CADASTRAL.
-- * Na classificacao LGBTQIAPN+, orientacao ou identidade marcada como
--   publico_lgbt = 1 coloca a pessoa no publico.
-- * Ausencia/nao declaracao nos dois marcadores fica em "Sem informacao".
-- =====================================================================

USE nexusdata_etapa02;

-- ---------------------------------------------------------------------
-- AJUSTES DE DADOS E VALIDACOES
-- ---------------------------------------------------------------------
-- A consulta abaixo permite conferir se existem cargas cadastradas.
-- Nao criamos cargas ficticias: cada carga precisa representar uma extracao
-- real/simulada definida pela equipe, com periodo de referencia correto.
SELECT id_carga, dt_hora_extracao, periodo_ref_inicio, periodo_ref_fim, fonte
FROM CARGA
ORDER BY id_carga;

-- Verifica se ha registros de situacao cadastral sem carga correspondente
-- (as FKs ja impedem isso, mas a consulta serve como conferencia).
SELECT sc.id_carga, COUNT(*) AS registros
FROM SITUACAO_CADASTRAL sc
GROUP BY sc.id_carga
ORDER BY sc.id_carga;

-- ---------------------------------------------------------------------
-- CONSULTA C1 - Populacao negra ativa por Distrito Sanitario
-- Finalidade: total de pessoas ativas, quantidade preta/parda e percentual.
-- ---------------------------------------------------------------------
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
WHERE sc.id_carga = (
    SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL
)
  AND sc.situacao = 'ATIVO'
  AND p.cns_principal IS NULL
GROUP BY ds.id_ds, ds.nome
ORDER BY percentual_negra DESC, ds.id_ds;

-- ---------------------------------------------------------------------
-- CONSULTA C2 - Publico LGBTQIAPN+ x Sem informacao x Demais (CORRIGIDA)
-- Correcao: evita classificar como "Nao LGBTQIAPN+" quem deixou sem
-- informacao qualquer um dos marcadores. LEFT JOIN preserva campos nulos.
-- A janela calcula o percentual sobre o total de pessoas classificadas.
-- ---------------------------------------------------------------------
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
    LEFT JOIN ORIENTACAO_SEXUAL ori
      ON ori.id_orientacao_sexual = sc.id_orientacao_sexual
    LEFT JOIN IDENTIDADE_GENERO ide
      ON ide.id_identidade_genero = sc.id_identidade_genero
    WHERE sc.id_carga = (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL)
      AND sc.situacao = 'ATIVO'
      AND p.cns_principal IS NULL
),
totais AS (
    SELECT categoria, COUNT(*) AS pessoas
    FROM classificacao
    GROUP BY categoria
)
SELECT categoria, pessoas,
       ROUND(100 * pessoas / NULLIF(SUM(pessoas) OVER (), 0), 1) AS percentual
FROM totais
ORDER BY pessoas DESC;

-- ---------------------------------------------------------------------
-- CONSULTA C3 - Completude dos campos opcionais por distrito
-- "Nao deseja informar" (codigo 9) nao conta como campo preenchido.
-- ---------------------------------------------------------------------
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
WHERE sc.id_carga = (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL)
  AND sc.situacao = 'ATIVO'
  AND p.cns_principal IS NULL
GROUP BY ds.id_ds, ds.nome
ORDER BY ds.id_ds;

-- ---------------------------------------------------------------------
-- CONSULTA C4 - Inconsistencias por distrito e tipo
-- O denominador da janela e o total de inconsistencias daquele distrito.
-- ---------------------------------------------------------------------
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
    WHERE i.id_carga = (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL)
    GROUP BY ds.id_ds, ds.nome, ti.id_tipo_inconsistencia, ti.descricao
)
SELECT distrito, tipo_inconsistencia, quantidade,
       ROUND(100 * quantidade / NULLIF(SUM(quantidade) OVER (PARTITION BY id_ds), 0), 1)
         AS pct_no_distrito
FROM totais
ORDER BY id_ds, quantidade DESC;

-- ---------------------------------------------------------------------
-- CONSULTA C5 - Equipes com/sem acao formativa x media de inconsistencias
-- As CTEs agregam antes dos JOINs para nao multiplicar linhas.
-- Equipes sem inconsistencias entram na media com zero.
-- ---------------------------------------------------------------------
WITH acoes AS (
    SELECT ine, COUNT(*) AS qtd_acoes
    FROM ACAO_FORMATIVA
    GROUP BY ine
),
inconsistencias AS (
    SELECT ine_responsavel AS ine, COUNT(*) AS qtd_inconsistencias
    FROM INCONSISTENCIA
    WHERE id_carga = (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL)
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
ORDER BY grupo;

-- ---------------------------------------------------------------------
-- CONSULTA C6 - Pessoas com deficiencia por distrito e tipo
-- COUNT(DISTINCT) evita contar a mesma pessoa mais de uma vez no grupo.
-- ---------------------------------------------------------------------
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
WHERE sc.id_carga = (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL)
  AND sc.situacao = 'ATIVO'
  AND p.cns_principal IS NULL
GROUP BY ds.id_ds, ds.nome, td.id_tipo_deficiencia, td.descricao
ORDER BY ds.id_ds, pessoas DESC;

-- ---------------------------------------------------------------------
-- CONSULTA C7 - Perfil etario da populacao ativa por distrito
-- A idade nao e armazenada: e calculada na data de fim do periodo da carga
-- (c.periodo_ref_fim), para que o retrato de uma carga antiga nao mude
-- quando a consulta for refeita anos depois.
-- ---------------------------------------------------------------------
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
WHERE sc.id_carga = (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL)
  AND sc.situacao = 'ATIVO'
  AND p.cns_principal IS NULL
GROUP BY ds.id_ds, ds.nome, faixa_etaria
ORDER BY ds.id_ds,
         MIN(TIMESTAMPDIFF(YEAR, p.dt_nascimento, c.periodo_ref_fim));

-- ---------------------------------------------------------------------
-- CONSULTA C8 - Indicadores de inconsistencias por campo
-- Mostra os campos mais problematicos da carga corrente e a participacao
-- percentual de cada campo no total de inconsistencias.
-- ---------------------------------------------------------------------
WITH por_campo AS (
    SELECT i.campo, ti.descricao AS tipo_inconsistencia,
           COUNT(*) AS quantidade
    FROM INCONSISTENCIA i
    JOIN TIPO_INCONSISTENCIA ti
      ON ti.id_tipo_inconsistencia = i.id_tipo_inconsistencia
    WHERE i.id_carga = (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL)
    GROUP BY i.campo, ti.id_tipo_inconsistencia, ti.descricao
)
SELECT campo, tipo_inconsistencia, quantidade,
       ROUND(100 * quantidade / NULLIF(SUM(quantidade) OVER (), 0), 1)
         AS pct_total_inconsistencias
FROM por_campo
ORDER BY quantidade DESC, campo;
