-- =====================================================================
-- NEXUSDATA - ETAPA 04 - ENTREGAVEL 3: SQL DAS VISOES
-- Banco: nexusdata_etapa02 | SGBD: MySQL 8.0+
--
-- CONTEUDO:
--   V1) VW_PERFIL_EQUIDADE_EQUIPE         (8 tabelas, 7 joins)
--   V2) VW_LISTA_NOMINAL_INCONSISTENCIAS  (8 tabelas, 7 joins)
--
-- A Etapa 03 ja tinha VW_EVOLUCAO_CARGAS (resumo por carga, sem joins).
-- As duas visoes abaixo sao novas.
-- =====================================================================

USE nexusdata_etapa02;

-- ---------------------------------------------------------------------
-- V1) VW_PERFIL_EQUIDADE_EQUIPE
--     Uma linha por carga x equipe, com os totais dos tres publicos das
--     politicas e a completude dos marcadores de equidade.
--
-- JUSTIFICATIVA SEMANTICA:
-- A secao 6 do minimundo pede "quantas pessoas de cada publico estao
-- cadastradas e como se distribuem por distrito, unidade e equipe" e "a
-- completude dos marcadores de equidade". Cada uma dessas perguntas, em
-- SQL, repete as mesmas regras: so ATIVO, sem duplicidade (regra 5),
-- populacao negra = preta ou parda, LGBTQIAPN+ pela orientacao OU pela
-- identidade, "sem informacao" a parte (secao 4), codigo 9 nao conta como
-- preenchido. A visao fixa essas regras num unico lugar.
--
-- Ela tambem atende a LGPD (regra 6): so devolve contagens agregadas por
-- equipe, sem CNS, nome ou CPF. Por isso pode ser liberada aos perfis de
-- coordenacao e gestao, que veem todo o municipio (regra 9), e e a fonte
-- do dashboard da Etapa 06. Somando as linhas obtem-se unidade, distrito
-- e municipio, porque cada equipe pertence a uma unica unidade e cada
-- unidade a um unico distrito (regra 1).
--
-- JOINs: SITUACAO_CADASTRAL, PESSOA, CARGA, EQUIPE, UNIDADE_SAUDE,
--        DISTRITO_SANITARIO, RACA_COR, ORIENTACAO_SEXUAL (LEFT),
--        IDENTIDADE_GENERO (LEFT), deficiencias (LEFT, agregadas).
-- O filtro por id_carga feito sobre a visao e empurrado para dentro dela
-- pelo otimizador e usa o indice idx_sc_carga_situacao (Etapa 04).
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW VW_PERFIL_EQUIDADE_EQUIPE AS
SELECT sc.id_carga,
       c.periodo_ref_inicio,
       c.periodo_ref_fim,
       ds.id_ds,
       ds.nome                                            AS distrito,
       u.cnes,
       u.nome                                             AS unidade,
       e.ine,
       e.nome                                             AS equipe,
       COUNT(*)                                           AS ativos,
       SUM(rc.pop_negra = 1)                              AS populacao_negra,
       SUM(COALESCE(os.publico_lgbt, 0) = 1
           OR COALESCE(ig.publico_lgbt, 0) = 1)           AS publico_lgbt,
       SUM(NOT (COALESCE(os.publico_lgbt, 0) = 1
                OR COALESCE(ig.publico_lgbt, 0) = 1)
           AND (sc.id_orientacao_sexual IS NULL OR sc.id_orientacao_sexual = 9
                OR sc.id_identidade_genero IS NULL OR sc.id_identidade_genero = 9))
                                                          AS lgbt_sem_informacao,
       SUM(def.cns IS NOT NULL)                           AS pessoas_com_deficiencia,
       SUM(sc.id_raca_cor <> 9)                           AS raca_cor_preenchida,
       SUM(sc.id_orientacao_sexual IS NOT NULL
           AND sc.id_orientacao_sexual <> 9)              AS orientacao_preenchida,
       SUM(sc.id_identidade_genero IS NOT NULL
           AND sc.id_identidade_genero <> 9)              AS identidade_preenchida,
       SUM(NULLIF(TRIM(sc.nome_social), '') IS NOT NULL)  AS com_nome_social,
       ROUND(100 * AVG(rc.pop_negra = 1), 1)              AS pct_populacao_negra,
       ROUND(100 * AVG(sc.id_orientacao_sexual IS NOT NULL
                       AND sc.id_orientacao_sexual <> 9), 1) AS pct_orientacao,
       ROUND(100 * AVG(sc.id_identidade_genero IS NOT NULL
                       AND sc.id_identidade_genero <> 9), 1) AS pct_identidade
FROM SITUACAO_CADASTRAL sc
JOIN PESSOA p              ON p.cns = sc.cns
JOIN CARGA c               ON c.id_carga = sc.id_carga
JOIN EQUIPE e              ON e.ine = sc.ine
JOIN UNIDADE_SAUDE u       ON u.cnes = e.cnes
JOIN DISTRITO_SANITARIO ds ON ds.id_ds = u.id_ds
JOIN RACA_COR rc           ON rc.id_raca_cor = sc.id_raca_cor
LEFT JOIN ORIENTACAO_SEXUAL os ON os.id_orientacao_sexual = sc.id_orientacao_sexual
LEFT JOIN IDENTIDADE_GENERO ig ON ig.id_identidade_genero = sc.id_identidade_genero
LEFT JOIN (
    SELECT DISTINCT cns, id_carga FROM SITUACAO_DEFICIENCIA
) def ON def.cns = sc.cns AND def.id_carga = sc.id_carga
WHERE sc.situacao = 'ATIVO'
  AND p.cns_principal IS NULL
GROUP BY sc.id_carga, c.periodo_ref_inicio, c.periodo_ref_fim,
         ds.id_ds, ds.nome, u.cnes, u.nome, e.ine, e.nome;

-- ---------------------------------------------------------------------
-- V2) VW_LISTA_NOMINAL_INCONSISTENCIAS
--     Uma linha por inconsistencia, com a pessoa identificada pelo nome
--     de exibicao, o territorio da equipe responsavel e o contexto da carga.
--
-- JUSTIFICATIVA SEMANTICA:
-- Toda inconsistencia esta vinculada a uma carga e a equipe responsavel
-- (regra 7), e quem corrige o cadastro e a equipe. Ela precisa de uma
-- lista nominal: quem e a pessoa, qual campo, qual tipo de problema. A
-- regra 6 diz que essas listagens sao restritas as equipes e usam o NOME
-- SOCIAL quando ele existe; a visao aplica isso em nome_exibicao e nunca
-- expoe o CPF. Filtrando por ine (USUARIO.ine do perfil "Equipe APS"),
-- cada equipe ve so o seu territorio (regra 9).
-- A visao tambem informa se a equipe ja tinha recebido acao formativa ate
-- o fim do periodo da carga, o que permite cruzar qualidade do registro e
-- capacitacao (consulta C5 e grafico do dashboard).
--
-- JOINs: INCONSISTENCIA, TIPO_INCONSISTENCIA, CARGA, PESSOA,
--        SITUACAO_CADASTRAL (LEFT), EQUIPE, UNIDADE_SAUDE,
--        DISTRITO_SANITARIO.
-- Indices usados: idx_inc_carga_equipe (filtro por carga/equipe) e
-- PK de SITUACAO_CADASTRAL (cns, id_carga).
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW VW_LISTA_NOMINAL_INCONSISTENCIAS AS
SELECT i.id_inconsistencia,
       i.id_carga,
       c.periodo_ref_inicio,
       c.periodo_ref_fim,
       ds.id_ds,
       ds.nome                                                  AS distrito,
       u.cnes,
       u.nome                                                   AS unidade,
       e.ine,
       e.nome                                                   AS equipe,
       i.cns,
       COALESCE(NULLIF(TRIM(sc.nome_social), ''), p.nome_civil) AS nome_exibicao,
       (NULLIF(TRIM(sc.nome_social), '') IS NOT NULL)           AS usa_nome_social,
       i.campo,
       ti.id_tipo_inconsistencia,
       ti.descricao                                             AS tipo_inconsistencia,
       sc.situacao                                              AS situacao_na_carga,
       sc.dt_atualizacao_pec,
       EXISTS (SELECT 1
               FROM ACAO_FORMATIVA af
               WHERE af.ine = e.ine
                 AND af.dt_acao <= c.periodo_ref_fim)           AS equipe_capacitada
FROM INCONSISTENCIA i
JOIN TIPO_INCONSISTENCIA ti ON ti.id_tipo_inconsistencia = i.id_tipo_inconsistencia
JOIN CARGA c                ON c.id_carga = i.id_carga
JOIN PESSOA p               ON p.cns = i.cns
LEFT JOIN SITUACAO_CADASTRAL sc
       ON sc.cns = i.cns AND sc.id_carga = i.id_carga
JOIN EQUIPE e               ON e.ine = i.ine_responsavel
JOIN UNIDADE_SAUDE u        ON u.cnes = e.cnes
JOIN DISTRITO_SANITARIO ds  ON ds.id_ds = u.id_ds;

-- =====================================================================
-- TESTES / EVIDENCIAS (somente leitura)
-- =====================================================================

-- V1: perfil por distrito na carga corrente (somando as equipes).
SELECT id_ds, distrito,
       SUM(ativos)                  AS ativos,
       SUM(populacao_negra)         AS populacao_negra,
       SUM(publico_lgbt)            AS publico_lgbt,
       SUM(pessoas_com_deficiencia) AS pessoas_com_deficiencia,
       ROUND(100 * SUM(orientacao_preenchida) / SUM(ativos), 1) AS pct_orientacao
FROM VW_PERFIL_EQUIDADE_EQUIPE
WHERE id_carga = (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL)
GROUP BY id_ds, distrito
ORDER BY id_ds;

-- V1 bate com a C1 da Etapa 03: o total municipal de ativos e de
-- populacao negra deve ser o mesmo.
SELECT SUM(ativos) AS ativos, SUM(populacao_negra) AS populacao_negra
FROM VW_PERFIL_EQUIDADE_EQUIPE
WHERE id_carga = (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL);

-- V2: lista da equipe 2000000002 (o que o perfil "Equipe APS" veria).
SELECT id_carga, nome_exibicao, usa_nome_social, campo,
       tipo_inconsistencia, situacao_na_carga, equipe_capacitada
FROM VW_LISTA_NOMINAL_INCONSISTENCIAS
WHERE ine = '2000000002'
ORDER BY id_carga DESC, nome_exibicao;
