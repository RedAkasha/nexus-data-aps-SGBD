-- =====================================================================
-- NEXUSDATA - ENTREGAVEL 2 - SQL DOS PROCEDIMENTOS
-- Banco: nexusdata_etapa02 | SGBD: MySQL 8.0+
--
-- CONTEUDO:
--   P1) sp_marcar_cadastro_duplicado      (ATUALIZACAO de dados)
--   P2) sp_auditar_inconsistencias_carga  (usa CURSOR)
--       sp_registrar_inconsistencia       (auxiliar chamado pelo P2)
--   P3) sp_recalcular_resumo_carga        (complemento da Etapa 06: mantem
--                                          RESUMO_CARGA correto depois de
--                                          UPDATE/DELETE; chamado por triggers)
--
-- PRE-REQUISITOS:
--   * Etapa 02 (criacao e insercao) e Etapa 03 (tabela RESUMO_CARGA).
--   * NexusData_Funcoes.sql (o P1 usa fn_classifica_publico_lgbt).
-- ORDEM DESTA ENTREGA: 1) Funcoes  2) Procedimentos  3) Triggers
--
-- COMO EXECUTAR: o arquivo usa DELIMITER. No MySQL Workbench ou no cliente
-- mysql, execute o arquivo inteiro. No DBeaver, use "Executar script"
-- (Alt+X), e nao "Executar instrucao" (Ctrl+Enter).
-- =====================================================================

USE nexusdata_etapa02;

DROP PROCEDURE IF EXISTS sp_marcar_cadastro_duplicado;
DROP PROCEDURE IF EXISTS sp_auditar_inconsistencias_carga;
DROP PROCEDURE IF EXISTS sp_registrar_inconsistencia;
DROP PROCEDURE IF EXISTS sp_recalcular_resumo_carga;

DELIMITER $$

-- ---------------------------------------------------------------------
-- P1) sp_marcar_cadastro_duplicado(cns duplicado, cns principal)
--     PROCEDIMENTO DE ATUALIZACAO DE DADOS
--
-- JUSTIFICATIVA SEMANTICA:
-- Regra de negocio 5: "duplicidades contam uma vez". Quando a gestao
-- descobre que dois CNS sao da mesma pessoa, um deles passa a apontar
-- para o outro em PESSOA.cns_principal e deixa de entrar nas contagens.
-- Essa curadoria e feita no Nexus Data e nao edita o registro original
-- do PEC/e-SUS APS (que esta fora do escopo).
--
-- Um UPDATE avulso nao basta, porque a operacao tem regras proprias:
--   1) valida os dois CNS (existem, sao diferentes, o principal nao e
--      ele mesmo um duplicado), para nao criar cadeias A -> B -> C;
--   2) se o cadastro que virou duplicado ja era principal de outros,
--      redireciona esses outros para o novo principal;
--   3) recalcula RESUMO_CARGA nas cargas em que a pessoa aparece, pois o
--      trigger trg_resumo_carga_ai so contabiliza no momento do INSERT e
--      a view VW_EVOLUCAO_CARGAS ficaria com totais errados;
--   4) faz tudo em uma transacao: ou as tres atualizacoes valem, ou
--      nenhuma.
-- Passar NULL como principal desfaz a marcacao (falso positivo): o
-- cadastro volta a ser principal e os resumos sao recalculados.
--
-- Observacao: o resumo e um agregado derivado (nao guarda CNS). Recalcula-
-- lo nao altera os registros historicos de SITUACAO_CADASTRAL.
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_marcar_cadastro_duplicado(
    IN p_cns_duplicado CHAR(15),
    IN p_cns_principal CHAR(15)    -- NULL = desfazer a marcacao
)
BEGIN
    DECLARE v_existe INT DEFAULT 0;
    DECLARE v_principal_atual CHAR(15);
    DECLARE v_existe_principal INT DEFAULT 0;
    DECLARE v_principal_do_principal CHAR(15);
    DECLARE v_redirecionados INT DEFAULT 0;
    DECLARE v_cargas_recalculadas INT DEFAULT 0;

    -- ----------------------- validacoes ------------------------------
    SELECT COUNT(*), MAX(cns_principal)
    INTO v_existe, v_principal_atual
    FROM PESSOA
    WHERE cns = p_cns_duplicado;

    IF v_existe = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'CNS informado como duplicado nao existe em PESSOA.';
    END IF;

    IF p_cns_principal IS NULL THEN
        IF v_principal_atual IS NULL THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'O cadastro ja e principal: nao ha marcacao para desfazer.';
        END IF;
    ELSE
        IF p_cns_principal = p_cns_duplicado THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Um cadastro nao pode ser duplicado de si mesmo.';
        END IF;

        SELECT COUNT(*), MAX(cns_principal)
        INTO v_existe_principal, v_principal_do_principal
        FROM PESSOA
        WHERE cns = p_cns_principal;

        IF v_existe_principal = 0 THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'CNS informado como principal nao existe em PESSOA.';
        END IF;

        IF v_principal_do_principal IS NOT NULL THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'O CNS indicado como principal ja e um duplicado; informe o principal dele.';
        END IF;

        IF v_principal_atual <=> p_cns_principal THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'O cadastro ja esta marcado como duplicado desse principal.';
        END IF;
    END IF;

    -- ----------------------- atualizacao -----------------------------
    BEGIN
        -- Qualquer erro desfaz as atualizacoes e devolve o erro original.
        DECLARE EXIT HANDLER FOR SQLEXCEPTION
        BEGIN
            ROLLBACK;
            RESIGNAL;
        END;

        START TRANSACTION;

        -- (a) Quem apontava para o cadastro que virou duplicado passa a
        --     apontar para o novo principal (evita cadeias).
        IF p_cns_principal IS NOT NULL THEN
            UPDATE PESSOA
            SET cns_principal = p_cns_principal
            WHERE cns_principal = p_cns_duplicado;

            SET v_redirecionados = ROW_COUNT();
        END IF;

        -- (b) Marca (ou desmarca, se NULL) o cadastro.
        UPDATE PESSOA
        SET cns_principal = p_cns_principal
        WHERE cns = p_cns_duplicado;

        -- (c) Recalcula o resumo das cargas em que o cadastro aparece.
        --     LEFT JOIN: se a carga ficar sem nenhum principal, zera.
        UPDATE RESUMO_CARGA r
        LEFT JOIN (
            SELECT sc.id_carga,
                   COUNT(*) AS total_registros,
                   SUM(sc.situacao = 'ATIVO') AS total_ativos,
                   SUM(sc.situacao = 'ATIVO' AND rc.pop_negra = 1)
                       AS total_negros_ativos,
                   -- COLLATE explicito: evita o erro 1267 quando a conexao
                   -- usa collation diferente da do banco.
                   SUM(sc.situacao = 'ATIVO'
                       AND fn_classifica_publico_lgbt(
                               sc.id_orientacao_sexual,
                               sc.id_identidade_genero)
                           COLLATE utf8mb4_unicode_ci = 'LGBTQIAPN+')
                       AS total_lgbt_ativos
            FROM SITUACAO_CADASTRAL sc
            JOIN PESSOA p ON p.cns = sc.cns
            JOIN RACA_COR rc ON rc.id_raca_cor = sc.id_raca_cor
            WHERE p.cns_principal IS NULL
            GROUP BY sc.id_carga
        ) t ON t.id_carga = r.id_carga
        SET r.total_registros     = COALESCE(t.total_registros, 0),
            r.total_ativos        = COALESCE(t.total_ativos, 0),
            r.total_negros_ativos = COALESCE(t.total_negros_ativos, 0),
            r.total_lgbt_ativos   = COALESCE(t.total_lgbt_ativos, 0)
        WHERE r.id_carga IN (
            SELECT id_carga FROM SITUACAO_CADASTRAL WHERE cns = p_cns_duplicado
        );

        -- Cargas do cadastro que tiveram o resumo recalculado.
        SELECT COUNT(*) INTO v_cargas_recalculadas
        FROM RESUMO_CARGA
        WHERE id_carga IN (
            SELECT id_carga FROM SITUACAO_CADASTRAL WHERE cns = p_cns_duplicado
        );

        COMMIT;
    END;

    SELECT p_cns_duplicado AS cns,
           v_principal_atual AS principal_anterior,
           p_cns_principal AS principal_novo,
           v_redirecionados AS duplicados_redirecionados,
           v_cargas_recalculadas AS cargas_recalculadas;
END$$

-- ---------------------------------------------------------------------
-- Auxiliar do P2: sp_registrar_inconsistencia
--
-- Grava UMA inconsistencia, vinculada a carga e a equipe responsavel
-- (regra de negocio 7), desde que ela ainda nao exista. Isso torna a
-- auditoria reexecutavel: rodar duas vezes nao duplica registros.
-- p_inserida devolve 1 (gravou) ou 0 (ja existia).
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_registrar_inconsistencia(
    IN  p_ine CHAR(10),
    IN  p_cns CHAR(15),
    IN  p_id_carga INT,
    IN  p_campo VARCHAR(80),
    IN  p_id_tipo_inconsistencia TINYINT UNSIGNED,
    OUT p_inserida TINYINT
)
BEGIN
    IF EXISTS (SELECT 1
               FROM INCONSISTENCIA
               WHERE cns = p_cns
                 AND id_carga = p_id_carga
                 AND campo = p_campo
                 AND id_tipo_inconsistencia = p_id_tipo_inconsistencia) THEN
        SET p_inserida = 0;
    ELSE
        INSERT INTO INCONSISTENCIA
            (ine_responsavel, cns, id_carga, campo, id_tipo_inconsistencia)
        VALUES
            (p_ine, p_cns, p_id_carga, p_campo, p_id_tipo_inconsistencia);
        SET p_inserida = 1;
    END IF;
END$$

-- ---------------------------------------------------------------------
-- P2) sp_auditar_inconsistencias_carga(id da carga)
--     PROCEDIMENTO COM CURSOR
--
-- JUSTIFICATIVA SEMANTICA:
-- Secao 5 do minimundo: "A cada carga identificam-se as inconsistencias
-- (campo obrigatorio vazio, valor invalido ou divergencia entre
-- registros), guardando-se a pessoa, o campo, o tipo e a carga", sempre
-- associadas a equipe responsavel. Ate aqui a tabela INCONSISTENCIA so
-- recebia dados digitados; este procedimento e quem de fato a alimenta.
--
-- Regras verificadas em cada situacao cadastral da carga:
--   R1 (tipo 1 - campo obrigatorio vazio): raca/cor "Sem informacao".
--   R2 (tipo 2 - valor invalido): a pessoa marcou que NAO deseja informar
--      (deseja_informar_os / deseja_informar_ig = 0), mas o campo veio
--      com uma categoria preenchida.
--   R3 (tipo 3 - divergencia entre registros): a raca/cor do registro
--      difere (a) da raca/cor do cadastro principal na mesma carga, se o
--      registro e de um duplicado, ou (b) da raca/cor da propria pessoa
--      na carga anterior mais recente em que ela aparece.
--
-- POR QUE PRECISA DE CURSOR (e nao pode ser um UPDATE):
--   * nenhuma coluna da tabela percorrida e alterada: o resultado sao
--     linhas NOVAS em outra tabela (INCONSISTENCIA);
--   * cada registro pode gerar zero, uma ou varias inconsistencias, de
--     campos e tipos diferentes. Um UPDATE produz no maximo um efeito por
--     linha lida;
--   * a decisao depende de buscas feitas registro a registro (o cadastro
--     principal na mesma carga, a carga anterior da mesma pessoa);
--   * cada inconsistencia e gravada por uma chamada a outro procedimento
--     (CALL sp_registrar_inconsistencia), que decide se grava ou se ja
--     existia. CALL nao pode ser usado dentro de UPDATE/INSERT...SELECT;
--   * contadores sao acumulados durante a leitura para o resumo final.
--
-- O procedimento nao abre transacao propria: quem chama decide entre
-- COMMIT e ROLLBACK (ver teste no fim do arquivo).
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_auditar_inconsistencias_carga(
    IN p_id_carga INT    -- NULL = carga corrente
)
BEGIN
    -- Codigos de dominio usados nas regras.
    DECLARE c_sem_informacao   TINYINT UNSIGNED DEFAULT 9;  -- "Sem informacao" / "Nao deseja informar"
    DECLARE c_tipo_vazio       TINYINT UNSIGNED DEFAULT 1;  -- Campo obrigatorio vazio
    DECLARE c_tipo_invalido    TINYINT UNSIGNED DEFAULT 2;  -- Valor invalido
    DECLARE c_tipo_divergencia TINYINT UNSIGNED DEFAULT 3;  -- Divergencia entre registros

    -- Carga auditada.
    DECLARE v_id_carga INT;

    -- Linha corrente do cursor.
    DECLARE v_cns CHAR(15);
    DECLARE v_ine CHAR(10);
    DECLARE v_raca TINYINT UNSIGNED;
    DECLARE v_deseja_os BOOLEAN;
    DECLARE v_os TINYINT UNSIGNED;
    DECLARE v_deseja_ig BOOLEAN;
    DECLARE v_ig TINYINT UNSIGNED;
    DECLARE v_cns_principal CHAR(15);

    -- Apoio as regras.
    DECLARE v_raca_principal TINYINT UNSIGNED;
    DECLARE v_raca_anterior TINYINT UNSIGNED;
    DECLARE v_inserida TINYINT DEFAULT 0;

    -- Contadores do resumo final.
    DECLARE v_lidos INT DEFAULT 0;
    DECLARE v_novas_vazio INT DEFAULT 0;
    DECLARE v_novas_invalido INT DEFAULT 0;
    DECLARE v_novas_divergencia INT DEFAULT 0;
    DECLARE v_ja_registradas INT DEFAULT 0;

    DECLARE v_fim BOOLEAN DEFAULT FALSE;

    -- Todos os registros da carga entram na auditoria (ativos ou nao,
    -- principais ou duplicados): a qualidade do registro e avaliada no
    -- cadastro como ele veio do PEC.
    DECLARE cur_situacao CURSOR FOR
        SELECT sc.cns, sc.ine, sc.id_raca_cor,
               sc.deseja_informar_os, sc.id_orientacao_sexual,
               sc.deseja_informar_ig, sc.id_identidade_genero,
               p.cns_principal
        FROM SITUACAO_CADASTRAL sc
        JOIN PESSOA p ON p.cns = sc.cns
        WHERE sc.id_carga = v_id_carga
        ORDER BY sc.ine, sc.cns;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_fim = TRUE;

    -- Carga a auditar: a informada ou, se NULL, a corrente.
    SET v_id_carga = COALESCE(
        p_id_carga,
        (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL));

    IF NOT EXISTS (SELECT 1 FROM SITUACAO_CADASTRAL
                   WHERE id_carga = v_id_carga) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Nao ha situacoes cadastrais para a carga informada.';
    END IF;

    OPEN cur_situacao;

    leitura: LOOP
        FETCH cur_situacao
        INTO v_cns, v_ine, v_raca, v_deseja_os, v_os, v_deseja_ig, v_ig,
             v_cns_principal;

        IF v_fim THEN
            LEAVE leitura;
        END IF;

        SET v_lidos = v_lidos + 1;

        IF v_raca = c_sem_informacao THEN
            -- R1: raca/cor e obrigatoria e veio sem informacao.
            CALL sp_registrar_inconsistencia(
                v_ine, v_cns, v_id_carga, 'raca_cor', c_tipo_vazio, v_inserida);
            SET v_novas_vazio = v_novas_vazio + v_inserida;
            SET v_ja_registradas = v_ja_registradas + (1 - v_inserida);
        ELSE
            -- R3: so ha divergencia quando os dois lados estao informados.
            -- As buscas usam SET com subconsulta: se nao houver linha, o
            -- resultado e NULL e o handler NOT FOUND do cursor nao dispara.
            SET v_raca_principal = NULL;
            IF v_cns_principal IS NOT NULL THEN
                SET v_raca_principal = (
                    SELECT a.id_raca_cor
                    FROM SITUACAO_CADASTRAL a
                    WHERE a.cns = v_cns_principal
                      AND a.id_carga = v_id_carga);
            END IF;

            SET v_raca_anterior = (
                SELECT a.id_raca_cor
                FROM SITUACAO_CADASTRAL a
                WHERE a.cns = v_cns
                  AND a.id_carga < v_id_carga
                ORDER BY a.id_carga DESC
                LIMIT 1);

            IF (v_raca_principal IS NOT NULL
                AND v_raca_principal <> c_sem_informacao
                AND v_raca_principal <> v_raca)
               OR
               (v_raca_anterior IS NOT NULL
                AND v_raca_anterior <> c_sem_informacao
                AND v_raca_anterior <> v_raca) THEN
                CALL sp_registrar_inconsistencia(
                    v_ine, v_cns, v_id_carga, 'raca_cor', c_tipo_divergencia,
                    v_inserida);
                SET v_novas_divergencia = v_novas_divergencia + v_inserida;
                SET v_ja_registradas = v_ja_registradas + (1 - v_inserida);
            END IF;
        END IF;

        -- R2: nao deseja informar a orientacao, mas ha categoria preenchida.
        IF v_deseja_os = 0
           AND v_os IS NOT NULL AND v_os <> c_sem_informacao THEN
            CALL sp_registrar_inconsistencia(
                v_ine, v_cns, v_id_carga, 'orientacao_sexual', c_tipo_invalido,
                v_inserida);
            SET v_novas_invalido = v_novas_invalido + v_inserida;
            SET v_ja_registradas = v_ja_registradas + (1 - v_inserida);
        END IF;

        -- R2: nao deseja informar a identidade, mas ha categoria preenchida.
        IF v_deseja_ig = 0
           AND v_ig IS NOT NULL AND v_ig <> c_sem_informacao THEN
            CALL sp_registrar_inconsistencia(
                v_ine, v_cns, v_id_carga, 'identidade_genero', c_tipo_invalido,
                v_inserida);
            SET v_novas_invalido = v_novas_invalido + v_inserida;
            SET v_ja_registradas = v_ja_registradas + (1 - v_inserida);
        END IF;
    END LOOP leitura;

    CLOSE cur_situacao;

    -- Resumo da auditoria.
    SELECT v_id_carga AS id_carga,
           v_lidos AS registros_lidos,
           v_novas_vazio AS novas_campo_obrigatorio_vazio,
           v_novas_invalido AS novas_valor_invalido,
           v_novas_divergencia AS novas_divergencia_registros,
           v_novas_vazio + v_novas_invalido + v_novas_divergencia
               AS total_novas,
           v_ja_registradas AS ja_registradas;
END$$

-- ---------------------------------------------------------------------
-- P3) sp_recalcular_resumo_carga(id da carga)   [complemento da Etapa 06]
--
-- JUSTIFICATIVA SEMANTICA:
-- RESUMO_CARGA (Etapa 03) e alimentado pelo trigger trg_resumo_carga_ai,
-- que so soma no INSERT. Na Etapa 06 a interface passou a permitir
-- alterar e excluir registros da carga corrente (a regra 8 continua
-- protegendo as anteriores) e alterar o vinculo de duplicidade em PESSOA.
-- Sem recalculo, a VW_EVOLUCAO_CARGAS e o dashboard ficariam com totais
-- diferentes das consultas C1/C2. Este procedimento refaz o resumo de uma
-- carga (ou de todas, com NULL) a partir de SITUACAO_CADASTRAL, usando a
-- mesma regra das consultas e a funcao fn_classifica_publico_lgbt como
-- fonte unica da classificacao LGBTQIAPN+.
-- E chamado pelos triggers trg_situacao_cadastral_au_resumo,
-- trg_situacao_cadastral_ad_resumo e trg_pessoa_au_resumo (03_triggers.sql).
-- Nao altera SITUACAO_CADASTRAL: o resumo e um agregado derivado.
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_recalcular_resumo_carga(
    IN p_id_carga INT    -- NULL = todas as cargas que tem registros
)
BEGIN
    -- Cargas que ja tem linha no resumo ou registros na carga.
    INSERT INTO RESUMO_CARGA
        (id_carga, total_registros, total_ativos,
         total_negros_ativos, total_lgbt_ativos)
    SELECT c.id_carga,
           COALESCE(t.total_registros, 0),
           COALESCE(t.total_ativos, 0),
           COALESCE(t.total_negros_ativos, 0),
           COALESCE(t.total_lgbt_ativos, 0)
    FROM CARGA c
    LEFT JOIN (
        SELECT sc.id_carga,
               COUNT(*) AS total_registros,
               SUM(sc.situacao = 'ATIVO') AS total_ativos,
               SUM(sc.situacao = 'ATIVO' AND rc.pop_negra = 1)
                   AS total_negros_ativos,
               SUM(sc.situacao = 'ATIVO'
                   AND fn_classifica_publico_lgbt(
                           sc.id_orientacao_sexual,
                           sc.id_identidade_genero)
                       COLLATE utf8mb4_unicode_ci = 'LGBTQIAPN+')
                   AS total_lgbt_ativos
        FROM SITUACAO_CADASTRAL sc
        JOIN PESSOA p ON p.cns = sc.cns
        JOIN RACA_COR rc ON rc.id_raca_cor = sc.id_raca_cor
        WHERE p.cns_principal IS NULL
          AND (p_id_carga IS NULL OR sc.id_carga = p_id_carga)
        GROUP BY sc.id_carga
    ) t ON t.id_carga = c.id_carga
    WHERE (p_id_carga IS NULL OR c.id_carga = p_id_carga)
      AND (t.id_carga IS NOT NULL
           OR EXISTS (SELECT 1 FROM RESUMO_CARGA r WHERE r.id_carga = c.id_carga))
    ON DUPLICATE KEY UPDATE
        total_registros     = VALUES(total_registros),
        total_ativos        = VALUES(total_ativos),
        total_negros_ativos = VALUES(total_negros_ativos),
        total_lgbt_ativos   = VALUES(total_lgbt_ativos);
END$$

DELIMITER ;

-- =====================================================================
-- TESTES / EVIDENCIAS
-- =====================================================================

-- ---------------------------------------------------------------------
-- T1) P1 - marcar e desfazer uma duplicidade.
-- O teste desfaz a propria alteracao: o banco termina como comecou.
-- Pessoa 050 (principal, INATIVA na carga 1) vira duplicado da 049.
-- Esperado: total_registros da carga 1 cai em 1 e depois volta.
-- ---------------------------------------------------------------------
SELECT id_carga, total_registros, total_ativos,
       total_negros_ativos, total_lgbt_ativos
FROM RESUMO_CARGA WHERE id_carga = 1;                      -- antes

CALL sp_marcar_cadastro_duplicado('700000000000050', '700000000000049');

SELECT cns, nome_civil, cns_principal
FROM PESSOA WHERE cns IN ('700000000000049', '700000000000050');

SELECT id_carga, total_registros, total_ativos,
       total_negros_ativos, total_lgbt_ativos
FROM RESUMO_CARGA WHERE id_carga = 1;                      -- depois de marcar

CALL sp_marcar_cadastro_duplicado('700000000000050', NULL);  -- desfaz

SELECT id_carga, total_registros, total_ativos,
       total_negros_ativos, total_lgbt_ativos
FROM RESUMO_CARGA WHERE id_carga = 1;                      -- igual ao "antes"

-- Validacoes do P1: cada chamada abaixo deve FALHAR com a mensagem
-- indicada. Execute uma por vez (o erro interrompe a execucao do script).
-- CALL sp_marcar_cadastro_duplicado('700000000000050', '700000000000050');  -- duplicado de si mesmo
-- CALL sp_marcar_cadastro_duplicado('700000000000050', '700000000000051');  -- principal ja e duplicado
-- CALL sp_marcar_cadastro_duplicado('700000000000999', '700000000000001');  -- CNS inexistente
-- CALL sp_marcar_cadastro_duplicado('700000000000051', '700000000000001');  -- ja marcado
-- CALL sp_marcar_cadastro_duplicado('700000000000001', NULL);               -- nada a desfazer

-- ---------------------------------------------------------------------
-- T2) P2 - auditoria da carga corrente, dentro de uma transacao.
-- Resultado esperado com os dados da Etapa 02 (carga 1, 60 registros):
--   10 novas "campo obrigatorio vazio" (raca/cor = Sem informacao)
--    9 novas "valor invalido" (+1 que ja estava registrada: pessoa 020)
--    7 novas "divergencia entre registros" (duplicado x principal)
-- O teste termina com ROLLBACK para nao alterar os resultados das
-- consultas C4, C5 e C8 ja entregues. Para efetivar a auditoria,
-- troque o ROLLBACK por COMMIT.
-- ---------------------------------------------------------------------
START TRANSACTION;

CALL sp_auditar_inconsistencias_carga(NULL);

-- Inconsistencias por campo e tipo depois da auditoria.
SELECT i.campo, ti.descricao AS tipo_inconsistencia, COUNT(*) AS quantidade
FROM INCONSISTENCIA i
JOIN TIPO_INCONSISTENCIA ti
  ON ti.id_tipo_inconsistencia = i.id_tipo_inconsistencia
WHERE i.id_carga = 1
GROUP BY i.campo, ti.id_tipo_inconsistencia, ti.descricao
ORDER BY i.campo, ti.id_tipo_inconsistencia;

-- Divergencias encontradas: duplicado x cadastro principal.
SELECT i.cns AS cns_duplicado, rd.descricao AS raca_cor_duplicado,
       p.cns_principal, rp.descricao AS raca_cor_principal,
       i.ine_responsavel
FROM INCONSISTENCIA i
JOIN PESSOA p ON p.cns = i.cns
JOIN SITUACAO_CADASTRAL sd ON sd.cns = i.cns AND sd.id_carga = i.id_carga
JOIN RACA_COR rd ON rd.id_raca_cor = sd.id_raca_cor
JOIN SITUACAO_CADASTRAL sp
  ON sp.cns = p.cns_principal AND sp.id_carga = i.id_carga
JOIN RACA_COR rp ON rp.id_raca_cor = sp.id_raca_cor
WHERE i.id_carga = 1
  AND i.campo = 'raca_cor'
  AND i.id_tipo_inconsistencia = 3
  AND p.cns_principal IS NOT NULL
ORDER BY i.cns;

-- Reexecucao: nada novo; tudo aparece como "ja_registradas".
CALL sp_auditar_inconsistencias_carga(NULL);

ROLLBACK;

-- ---------------------------------------------------------------------
-- T3) P3 - recalculo do resumo. Deve devolver os mesmos totais do
-- backfill da Etapa 03 (o recalculo e idempotente).
-- ---------------------------------------------------------------------
CALL sp_recalcular_resumo_carga(NULL);
SELECT id_carga, total_registros, total_ativos,
       total_negros_ativos, total_lgbt_ativos
FROM RESUMO_CARGA ORDER BY id_carga;
