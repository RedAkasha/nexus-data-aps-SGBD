-- =====================================================================
-- NEXUSDATA - ENTREGAVEL 3 - SQL DOS TRIGGERS
-- Banco: nexusdata_etapa02 | SGBD: MySQL 8.0+
--
-- CONTEUDO:
--   Tabela de log LOG_ALTERACAO_PESSOA
--   G1) trg_pessoa_au_log          (AFTER UPDATE em PESSOA; grava o LOG)
--   G2) trg_situacao_cadastral_bu  (BEFORE UPDATE em SITUACAO_CADASTRAL;
--                                   protege cargas anteriores)
--       trg_situacao_cadastral_bd  (BEFORE DELETE; complemento do G2)
--       complemento da Etapa 06 (mesma regra 8, outras portas de entrada):
--       trg_situacao_cadastral_bi  (BEFORE INSERT em SITUACAO_CADASTRAL)
--       trg_situacao_deficiencia_bi / _bd (SITUACAO_DEFICIENCIA)
--   G3) complemento da Etapa 06 - consistencia de RESUMO_CARGA:
--       trg_situacao_cadastral_au_resumo (AFTER UPDATE em SITUACAO_CADASTRAL)
--       trg_situacao_cadastral_ad_resumo (AFTER DELETE em SITUACAO_CADASTRAL)
--       trg_pessoa_au_resumo             (AFTER UPDATE em PESSOA)
--
-- Estes triggers sao diferentes do trg_resumo_carga_ai da Etapa 03
-- (AFTER INSERT em SITUACAO_CADASTRAL), que continua valendo.
--
-- PRE-REQUISITO: scripts da Etapa 02 (criacao e insercao) ja executados.
-- ORDEM DESTA ENTREGA: 1) Funcoes  2) Procedimentos  3) Triggers
--
-- COMO EXECUTAR: o arquivo usa DELIMITER. No MySQL Workbench ou no cliente
-- mysql, execute o arquivo inteiro. No DBeaver, use "Executar script"
-- (Alt+X), e nao "Executar instrucao" (Ctrl+Enter).
-- =====================================================================

USE nexusdata_etapa02;

-- ---------------------------------------------------------------------
-- TABELA DE LOG
-- Uma linha por campo alterado em PESSOA: quem alterou, quando, o valor
-- anterior e o novo. Nao ha chave estrangeira para PESSOA de proposito:
-- o log e um registro historico e nao deve ser reescrito por cascatas.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS LOG_ALTERACAO_PESSOA (
    id_log BIGINT AUTO_INCREMENT PRIMARY KEY,
    cns CHAR(15) NOT NULL,
    campo VARCHAR(30) NOT NULL,
    valor_anterior VARCHAR(120) NULL,
    valor_novo VARCHAR(120) NULL,
    usuario_bd VARCHAR(100) NOT NULL,
    dt_hora_alteracao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_log_pessoa_cns (cns, dt_hora_alteracao)
) ENGINE=InnoDB;

DROP TRIGGER IF EXISTS trg_pessoa_au_log;
DROP TRIGGER IF EXISTS trg_situacao_cadastral_bu;
DROP TRIGGER IF EXISTS trg_situacao_cadastral_bd;
DROP TRIGGER IF EXISTS trg_situacao_cadastral_bi;
DROP TRIGGER IF EXISTS trg_situacao_deficiencia_bi;
DROP TRIGGER IF EXISTS trg_situacao_deficiencia_bd;
DROP TRIGGER IF EXISTS trg_situacao_cadastral_au_resumo;
DROP TRIGGER IF EXISTS trg_situacao_cadastral_ad_resumo;
DROP TRIGGER IF EXISTS trg_pessoa_au_resumo;

DELIMITER $$

-- ---------------------------------------------------------------------
-- G1) trg_pessoa_au_log - TRIGGER QUE ATUALIZA A TABELA DE LOGS
--
-- JUSTIFICATIVA SEMANTICA:
-- PESSOA guarda dados pessoais (nome civil, CPF, nascimento, sexo) e o
-- vinculo de duplicidade (cns_principal), que decide se a pessoa entra ou
-- nao nos indicadores das tres politicas (regra de negocio 5). Uma
-- alteracao ali muda os totais de todas as cargas da pessoa. A gestao
-- precisa saber quem alterou, quando e qual era o valor anterior, tanto
-- para explicar uma variacao nos indicadores quanto para prestar contas
-- do tratamento de dados pessoais (LGPD, regra de negocio 6).
--
-- O registro e feito por trigger, e nao pela aplicacao, para que nenhuma
-- alteracao escape: vale para o procedimento
-- sp_marcar_cadastro_duplicado, para o dashboard e para um UPDATE manual.
--
-- So os campos que realmente mudaram geram linha no log (comparacao <=>,
-- que trata NULL). O CPF e gravado mascarado: o log nao deve virar uma
-- segunda copia do dado pessoal.
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_pessoa_au_log
AFTER UPDATE ON PESSOA
FOR EACH ROW
BEGIN
    IF NOT (OLD.cns <=> NEW.cns) THEN
        INSERT INTO LOG_ALTERACAO_PESSOA
            (cns, campo, valor_anterior, valor_novo, usuario_bd)
        VALUES
            (NEW.cns, 'cns', OLD.cns, NEW.cns, USER());
    END IF;

    IF NOT (OLD.cns_principal <=> NEW.cns_principal) THEN
        INSERT INTO LOG_ALTERACAO_PESSOA
            (cns, campo, valor_anterior, valor_novo, usuario_bd)
        VALUES
            (NEW.cns, 'cns_principal', OLD.cns_principal, NEW.cns_principal,
             USER());
    END IF;

    IF NOT (OLD.nome_civil <=> NEW.nome_civil) THEN
        INSERT INTO LOG_ALTERACAO_PESSOA
            (cns, campo, valor_anterior, valor_novo, usuario_bd)
        VALUES
            (NEW.cns, 'nome_civil', OLD.nome_civil, NEW.nome_civil, USER());
    END IF;

    IF NOT (OLD.dt_nascimento <=> NEW.dt_nascimento) THEN
        INSERT INTO LOG_ALTERACAO_PESSOA
            (cns, campo, valor_anterior, valor_novo, usuario_bd)
        VALUES
            (NEW.cns, 'dt_nascimento',
             DATE_FORMAT(OLD.dt_nascimento, '%Y-%m-%d'),
             DATE_FORMAT(NEW.dt_nascimento, '%Y-%m-%d'), USER());
    END IF;

    IF NOT (OLD.sexo <=> NEW.sexo) THEN
        INSERT INTO LOG_ALTERACAO_PESSOA
            (cns, campo, valor_anterior, valor_novo, usuario_bd)
        VALUES
            (NEW.cns, 'sexo', OLD.sexo, NEW.sexo, USER());
    END IF;

    IF NOT (OLD.cpf <=> NEW.cpf) THEN
        INSERT INTO LOG_ALTERACAO_PESSOA
            (cns, campo, valor_anterior, valor_novo, usuario_bd)
        VALUES
            (NEW.cns, 'cpf',
             CONCAT('***.***.***-', RIGHT(OLD.cpf, 2)),
             CONCAT('***.***.***-', RIGHT(NEW.cpf, 2)), USER());
    END IF;
END$$

-- ---------------------------------------------------------------------
-- G2) trg_situacao_cadastral_bu - PROTECAO DAS CARGAS ANTERIORES
--
-- JUSTIFICATIVA SEMANTICA:
-- Regra de negocio 8: "Registros de periodos anteriores nao podem ser
-- alterados." Cada carga e o retrato de um periodo; a evolucao entre
-- cargas (VW_EVOLUCAO_CARGAS) e os indicadores ja apurados so fazem
-- sentido se esse retrato ficar congelado. Sem o trigger, a regra
-- dependeria da disciplina de cada usuario e de cada tela.
--
-- O trigger e BEFORE UPDATE porque precisa impedir a alteracao, e nao
-- apenas registra-la. Ele bloqueia:
--   * qualquer UPDATE em registro de carga anterior a carga corrente
--     (a corrente e a de maior id_carga em SITUACAO_CADASTRAL, mesma
--     convencao das consultas da Etapa 03);
--   * a troca do id_carga de um registro, que seria um jeito de mover
--     dados para dentro (ou para fora) de um periodo ja fechado.
-- Registros da carga corrente continuam editaveis, para permitir
-- correcoes enquanto a carga esta sendo conferida.
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_situacao_cadastral_bu
BEFORE UPDATE ON SITUACAO_CADASTRAL
FOR EACH ROW
BEGIN
    DECLARE v_carga_corrente INT;

    SELECT MAX(id_carga) INTO v_carga_corrente
    FROM SITUACAO_CADASTRAL;

    IF OLD.id_carga < v_carga_corrente THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Regra 8: registro de carga anterior nao pode ser alterado.';
    END IF;

    IF NEW.id_carga <> OLD.id_carga THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Regra 8: um registro nao pode ser movido para outra carga.';
    END IF;
END$$

-- ---------------------------------------------------------------------
-- Complemento do G2: trg_situacao_cadastral_bd
-- Apagar um registro tambem e uma forma de alterar um periodo anterior.
-- Sem este trigger, a regra 8 poderia ser contornada com DELETE.
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_situacao_cadastral_bd
BEFORE DELETE ON SITUACAO_CADASTRAL
FOR EACH ROW
BEGIN
    DECLARE v_carga_corrente INT;

    SELECT MAX(id_carga) INTO v_carga_corrente
    FROM SITUACAO_CADASTRAL;

    IF OLD.id_carga < v_carga_corrente THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Regra 8: registro de carga anterior nao pode ser excluido.';
    END IF;
END$$

-- ---------------------------------------------------------------------
-- Complementos do G2 (Etapa 06): a interface final permite inserir e
-- editar situacoes cadastrais e deficiencias. Sem os triggers abaixo, a
-- regra 8 poderia ser contornada por duas portas:
--   * INSERT de um registro novo dentro de uma carga ja fechada;
--   * INSERT/DELETE em SITUACAO_DEFICIENCIA de uma carga anterior (a
--     deficiencia e parte do retrato da pessoa naquele periodo).
-- A carga corrente segue a mesma convencao: maior id_carga com registros.
-- Inserir numa carga NOVA (maior que a corrente) continua permitido: e
-- assim que cada extracao mensal chega.
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_situacao_cadastral_bi
BEFORE INSERT ON SITUACAO_CADASTRAL
FOR EACH ROW
BEGIN
    DECLARE v_carga_corrente INT;

    SELECT MAX(id_carga) INTO v_carga_corrente
    FROM SITUACAO_CADASTRAL;

    IF NEW.id_carga < v_carga_corrente THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Regra 8: nao e possivel incluir registros em carga anterior.';
    END IF;
END$$

CREATE TRIGGER trg_situacao_deficiencia_bi
BEFORE INSERT ON SITUACAO_DEFICIENCIA
FOR EACH ROW
BEGIN
    IF NEW.id_carga < (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Regra 8: deficiencia de carga anterior nao pode ser alterada.';
    END IF;
END$$

CREATE TRIGGER trg_situacao_deficiencia_bd
BEFORE DELETE ON SITUACAO_DEFICIENCIA
FOR EACH ROW
BEGIN
    IF OLD.id_carga < (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Regra 8: deficiencia de carga anterior nao pode ser alterada.';
    END IF;
END$$

-- ---------------------------------------------------------------------
-- G3) Complemento da Etapa 06 - RESUMO_CARGA sempre coerente
--
-- JUSTIFICATIVA SEMANTICA:
-- O trg_resumo_carga_ai (Etapa 03) so conhece o INSERT. Na versao final a
-- interface permite alterar e excluir registros da carga corrente (o G2
-- continua bloqueando as anteriores) e alterar PESSOA.cns_principal pelo
-- CRUD. Cada uma dessas operacoes muda os totais da carga (regra 5:
-- duplicidade conta uma vez; so ATIVO entra). Os tres triggers abaixo
-- chamam sp_recalcular_resumo_carga para que VW_EVOLUCAO_CARGAS e o
-- dashboard continuem iguais as consultas C1/C2, qualquer que seja o
-- caminho da alteracao (tela, procedimento ou UPDATE manual).
-- Os triggers de SITUACAO_CADASTRAL sao AFTER: rodam depois do G2, ou
-- seja, so quando a alteracao foi aceita.
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_situacao_cadastral_au_resumo
AFTER UPDATE ON SITUACAO_CADASTRAL
FOR EACH ROW
BEGIN
    CALL sp_recalcular_resumo_carga(NEW.id_carga);
END$$

CREATE TRIGGER trg_situacao_cadastral_ad_resumo
AFTER DELETE ON SITUACAO_CADASTRAL
FOR EACH ROW
BEGIN
    CALL sp_recalcular_resumo_carga(OLD.id_carga);
END$$

-- Mudar o vinculo de duplicidade altera a contagem de todas as cargas em
-- que a pessoa aparece. Nas demais alteracoes de PESSOA (nome, sexo...)
-- o resumo nao muda e o recalculo nao e feito.
CREATE TRIGGER trg_pessoa_au_resumo
AFTER UPDATE ON PESSOA
FOR EACH ROW
BEGIN
    IF NOT (OLD.cns_principal <=> NEW.cns_principal) THEN
        CALL sp_recalcular_resumo_carga(NULL);
    END IF;
END$$

DELIMITER ;

-- =====================================================================
-- TESTES / EVIDENCIAS
-- Os dois testes terminam com ROLLBACK: o banco fica como estava.
-- =====================================================================

-- ---------------------------------------------------------------------
-- T1) G1 - log de alteracoes em PESSOA.
-- Um UPDATE muda nome e sexo (2 linhas de log); o segundo UPDATE nao
-- muda nada de fato (0 linhas); o terceiro marca uma duplicidade.
-- ---------------------------------------------------------------------
START TRANSACTION;

UPDATE PESSOA
SET nome_civil = 'Pessoa Ficticia 050 (nome corrigido)', sexo = 'F'
WHERE cns = '700000000000050';

UPDATE PESSOA
SET sexo = 'F'                       -- mesmo valor: nao gera log
WHERE cns = '700000000000050';

UPDATE PESSOA
SET cns_principal = '700000000000049'
WHERE cns = '700000000000050';

SELECT id_log, cns, campo, valor_anterior, valor_novo,
       usuario_bd, dt_hora_alteracao
FROM LOG_ALTERACAO_PESSOA
ORDER BY id_log;                     -- esperado: 3 linhas novas

ROLLBACK;

-- Com o entregavel 2 instalado, o log tambem e alimentado pelo
-- procedimento (estas linhas ficam gravadas, pois o procedimento confirma
-- a propria transacao):
-- CALL sp_marcar_cadastro_duplicado('700000000000050', '700000000000049');
-- CALL sp_marcar_cadastro_duplicado('700000000000050', NULL);
-- SELECT * FROM LOG_ALTERACAO_PESSOA ORDER BY id_log;

-- ---------------------------------------------------------------------
-- T2) G2 - protecao das cargas anteriores.
-- Hoje so a carga 1 tem registros, entao ela e a carga corrente.
-- ---------------------------------------------------------------------
START TRANSACTION;

-- (a) Carga 1 ainda e a corrente: a alteracao e ACEITA.
UPDATE SITUACAO_CADASTRAL
SET dt_atualizacao_pec = '2024-01-29'
WHERE cns = '700000000000001' AND id_carga = 1;

-- (b) Chega o primeiro registro da carga 2: a carga 1 passa a ser
--     "periodo anterior".
INSERT INTO SITUACAO_CADASTRAL
    (cns, id_carga, ine, nome_social, id_raca_cor,
     deseja_informar_os, id_orientacao_sexual,
     deseja_informar_ig, id_identidade_genero,
     situacao, dt_atualizacao_pec)
VALUES
    ('700000000000001', 2, '2000000001', NULL, 1, 1, 1, 1, 1,
     'ATIVO', '2024-02-10');

-- (c) A carga 2 (corrente) continua editavel: ACEITA.
UPDATE SITUACAO_CADASTRAL
SET situacao = 'TRANSFERIDO'
WHERE cns = '700000000000001' AND id_carga = 2;

SELECT cns, id_carga, situacao, dt_atualizacao_pec
FROM SITUACAO_CADASTRAL
WHERE cns = '700000000000001'
ORDER BY id_carga;

-- (d) As instrucoes abaixo devem FALHAR (erro 1644, SQLSTATE 45000).
--     Execute uma por vez, antes do ROLLBACK (o erro interrompe o script).
-- UPDATE SITUACAO_CADASTRAL SET situacao = 'OBITO'
--   WHERE cns = '700000000000001' AND id_carga = 1;   -- carga anterior
-- UPDATE SITUACAO_CADASTRAL SET id_carga = 3
--   WHERE cns = '700000000000001' AND id_carga = 2;   -- mover de carga
-- DELETE FROM SITUACAO_CADASTRAL
--   WHERE cns = '700000000000060' AND id_carga = 1;   -- excluir carga anterior
-- INSERT INTO SITUACAO_CADASTRAL (cns, id_carga, ine, id_raca_cor, situacao,
--   dt_atualizacao_pec) VALUES ('700000000000002', 1, '2000000002', 2,
--   'ATIVO', '2024-01-10');                           -- incluir em carga anterior
--   (o BEFORE INSERT roda antes da checagem de chave: o erro e o da regra 8)
-- DELETE FROM SITUACAO_DEFICIENCIA
--   WHERE cns = '700000000000001' AND id_carga = 1;   -- deficiencia de carga anterior

ROLLBACK;

-- ---------------------------------------------------------------------
-- T3) G3 - o resumo acompanha UPDATE e DELETE na carga corrente.
-- ---------------------------------------------------------------------
START TRANSACTION;

SELECT id_carga, total_registros, total_ativos FROM RESUMO_CARGA
WHERE id_carga = 1;                                  -- antes: 50 / 45

UPDATE SITUACAO_CADASTRAL SET situacao = 'INATIVO'
WHERE cns = '700000000000001' AND id_carga = 1;      -- um ativo a menos

DELETE FROM SITUACAO_DEFICIENCIA
WHERE cns = '700000000000002' AND id_carga = 1;
DELETE FROM SITUACAO_CADASTRAL
WHERE cns = '700000000000002' AND id_carga = 1;      -- um registro a menos

SELECT id_carga, total_registros, total_ativos FROM RESUMO_CARGA
WHERE id_carga = 1;                                  -- depois: 49 / 43

ROLLBACK;
