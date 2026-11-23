-- =====================================================================
-- NEXUSDATA - ETAPA 04 - ENTREGAVEL 1: SQL DOS INDICES
-- Banco: nexusdata_etapa02 | SGBD: MySQL 8.0+
--
-- CONTEUDO:
--   I1) idx_sc_carga_situacao  em SITUACAO_CADASTRAL (id_carga, situacao, ine)
--   I2) idx_inc_carga_equipe   em INCONSISTENCIA (id_carga, ine_responsavel,
--                                                 id_tipo_inconsistencia)
--   I3) uk_inc_ocorrencia      em INCONSISTENCIA (cns, id_carga, campo,
--                                                 id_tipo_inconsistencia)  UNIQUE
--
-- PRE-REQUISITO: Etapas 02 e 03 ja executadas.
-- Execute uma unica vez (o MySQL nao tem CREATE INDEX IF NOT EXISTS); o
-- script 01 da Etapa 02 recria as tabelas e permite reinstalar do zero.
--
-- POR QUE ESTES CAMPOS
-- Quase todas as consultas do projeto (C1 a C8, as consultas e as visoes
-- desta etapa e o dashboard) comecam do mesmo jeito: "registros da carga X
-- com situacao ATIVO", seguidos de um JOIN com EQUIPE pelo INE. A chave
-- primaria de SITUACAO_CADASTRAL e (cns, id_carga): ela comeca pelo CNS e
-- nao serve para filtrar por carga. O mesmo vale para INCONSISTENCIA, que
-- e sempre lida "da carga X, por equipe e por tipo".
-- Os EXPLAIN abaixo mostram o plano antes e depois de cada indice.
-- =====================================================================

USE nexusdata_etapa02;

-- ---------------------------------------------------------------------
-- I1) idx_sc_carga_situacao
--
-- Usado por: C1-C7 (Etapa 03), C9, C11 e C12 (Etapa 04),
--            VW_PERFIL_EQUIDADE_EQUIPE, trigger G2 (MAX(id_carga)),
--            dashboard (filtro de carga).
-- * id_carga em primeiro: igualdade da carga e o filtro mais seletivo
--   (cada carga e um retrato completo do cadastro);
-- * situacao em segundo: so ATIVO entra nas contagens (regra 5);
-- * ine em terceiro: o JOIN com EQUIPE/UNIDADE/DISTRITO le o INE direto
--   do indice, e o GROUP BY por equipe fica ordenado.
-- O MAX(id_carga) da "carga corrente" passa a ser resolvido pelo indice
-- ("Select tables optimized away"), sem varrer a tabela.
-- O MySQL remove automaticamente o indice que ele mesmo havia criado para
-- a FK fk_sc_carga, porque este novo indice comeca por id_carga.
-- ---------------------------------------------------------------------

-- ANTES: o filtro por carga usa apenas o indice da FK (so id_carga).
EXPLAIN
SELECT sc.ine, COUNT(*)
FROM SITUACAO_CADASTRAL sc
WHERE sc.id_carga = (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL)
  AND sc.situacao = 'ATIVO'
GROUP BY sc.ine;

CREATE INDEX idx_sc_carga_situacao
    ON SITUACAO_CADASTRAL (id_carga, situacao, ine);

-- DEPOIS: key = idx_sc_carga_situacao, com "Using index" (indice de cobertura).
EXPLAIN
SELECT sc.ine, COUNT(*)
FROM SITUACAO_CADASTRAL sc
WHERE sc.id_carga = (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL)
  AND sc.situacao = 'ATIVO'
GROUP BY sc.ine;

-- ---------------------------------------------------------------------
-- I2) idx_inc_carga_equipe
--
-- Usado por: C4, C5, C8 (Etapa 03), C9 (anti join) e
--            VW_LISTA_NOMINAL_INCONSISTENCIAS, painel de qualidade.
-- Sem ele, contar as inconsistencias de uma carga por equipe e por tipo
-- exige ler a tabela inteira. Com ele, a contagem e feita so no indice.
-- ---------------------------------------------------------------------

-- ANTES: type = ref pelo indice da FK de carga, com leitura das linhas.
EXPLAIN
SELECT ine_responsavel, id_tipo_inconsistencia, COUNT(*)
FROM INCONSISTENCIA
WHERE id_carga = 1
GROUP BY ine_responsavel, id_tipo_inconsistencia;

CREATE INDEX idx_inc_carga_equipe
    ON INCONSISTENCIA (id_carga, ine_responsavel, id_tipo_inconsistencia);

-- DEPOIS: key = idx_inc_carga_equipe, "Using index".
EXPLAIN
SELECT ine_responsavel, id_tipo_inconsistencia, COUNT(*)
FROM INCONSISTENCIA
WHERE id_carga = 1
GROUP BY ine_responsavel, id_tipo_inconsistencia;

-- ---------------------------------------------------------------------
-- I3) uk_inc_ocorrencia (UNIQUE)
--
-- Uma inconsistencia e identificada pela pessoa, a carga, o campo e o
-- tipo (secao 5 do minimundo). O indice unico:
-- * impede que a mesma ocorrencia seja gravada duas vezes;
-- * atende a busca do procedimento sp_registrar_inconsistencia (Etapa 05),
--   chamada uma vez por ocorrencia pela auditoria com cursor;
-- * atende o pareamento INCONSISTENCIA x GABARITO_DEFEITO da consulta C10
--   (full outer join), que compara exatamente estas quatro colunas.
-- ---------------------------------------------------------------------
CREATE UNIQUE INDEX uk_inc_ocorrencia
    ON INCONSISTENCIA (cns, id_carga, campo, id_tipo_inconsistencia);

-- DEPOIS: key = uk_inc_ocorrencia, type = const (uma unica linha).
EXPLAIN
SELECT 1
FROM INCONSISTENCIA
WHERE cns = '700000000000001' AND id_carga = 1
  AND campo = 'raca_cor' AND id_tipo_inconsistencia = 1;

-- Conferencia: indices criados nesta etapa.
SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE,
       GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) AS colunas
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
  AND INDEX_NAME IN ('idx_sc_carga_situacao', 'idx_inc_carga_equipe', 'uk_inc_ocorrencia')
GROUP BY TABLE_NAME, INDEX_NAME, NON_UNIQUE;
