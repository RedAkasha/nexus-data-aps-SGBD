-- =====================================================================
-- NEXUSDATA - ETAPA 06 - CARGA DE DEMONSTRACAO (cargas 2 a 30)
-- Banco: nexusdata_etapa02 | SGBD: MySQL 8.0+
--
-- POR QUE ESTE SCRIPT EXISTE
-- A Etapa 02 cadastrou 30 cargas (jan/2024 a jun/2026), mas so a carga 1
-- tem situacoes cadastrais (60 pessoas). Com um unico retrato nao ha
-- tendencia temporal, nem distribuicao por equipe com tamanho suficiente
-- para medidas estatisticas. Este script preenche as cargas 2 a 30 com
-- dados FICTICIOS, gerados de forma deterministica (mesma execucao, mesmo
-- resultado), e faz isso pelos caminhos normais do banco:
--   * INSERT carga a carga, em ordem crescente, como faria a extracao
--     mensal do PEC: o trigger trg_resumo_carga_ai (Etapa 03) alimenta
--     RESUMO_CARGA linha a linha e a regra 8 (trigger G2, Etapa 05) e
--     respeitada, pois nenhum registro de carga anterior e alterado;
--   * a tabela INCONSISTENCIA e preenchida pelo procedimento com cursor
--     sp_auditar_inconsistencias_carga (Etapa 05), carga por carga;
--   * GABARITO_DEFEITO recebe os defeitos plantados de proposito, para
--     que a consulta C10 (full outer join) meca a auditoria.
--
-- O QUE A SIMULACAO REPRODUZ (para o dashboard ter o que mostrar)
--   * 540 pessoas novas (CNS 700000000000061 a 700000000000600), entrando
--     ~19 por carga; 10 delas sao duplicidades de outro cadastro;
--   * raca/cor com distribuicao proxima a do Recife (maioria parda);
--     parte dos cadastros chega com raca/cor "Sem informacao" e e
--     corrigida algumas cargas depois; algumas trocas preta <-> parda
--     geram divergencia entre cargas;
--   * orientacao sexual e identidade de genero comecam em branco e sao
--     preenchidas com atraso que depende da equipe; depois da acao
--     formativa da equipe (ACAO_FORMATIVA, 2025) o atraso cai;
--   * recusas ("nao deseja informar") e alguns registros invalidos
--     (recusou, mas o campo veio preenchido);
--   * deficiencia mais frequente nas idades mais altas;
--   * saidas por obito (idosos) e transferencia, e inativacoes eventuais.
--
-- Os 60 cadastros da Etapa 02 continuam nas cargas seguintes com os
-- mesmos dados da carga 1 (os que estavam com raca/cor "Sem informacao"
-- sao corrigidos entre as cargas 3 e 12). A carga 1 nao e alterada.
--
-- Objetos auxiliares (DEMO_PESSOA, fn_demo_u, sp_demo_gerar_cargas) sao
-- removidos no fim. Tempo de execucao: alguns segundos.
-- PRE-REQUISITO: Etapas 02 a 05 instaladas, nesta ordem.
-- =====================================================================

USE nexusdata_etapa02;
SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

DROP TABLE IF EXISTS DEMO_PESSOA;
DROP FUNCTION IF EXISTS fn_demo_u;
DROP PROCEDURE IF EXISTS sp_demo_gerar_cargas;

DELIMITER $$

-- Numero pseudoaleatorio deterministico entre 0 e 999 a partir de um texto.
CREATE FUNCTION fn_demo_u(p_txt VARCHAR(200))
RETURNS INT
DETERMINISTIC
NO SQL
BEGIN
    RETURN CRC32(p_txt) MOD 1000;
END$$

DELIMITER ;

-- ---------------------------------------------------------------------
-- 1) Pessoas novas (PESSOA)
-- ---------------------------------------------------------------------
INSERT INTO PESSOA (cns, cpf, nome_civil, dt_nascimento, sexo, cns_principal)
WITH RECURSIVE seq (n) AS (
    SELECT 61
    UNION ALL
    SELECT n + 1 FROM seq WHERE n < 600
),
base AS (
    SELECT n,
           CASE WHEN fn_demo_u(CONCAT(n, '|a0')) < 700
                THEN fn_demo_u(CONCAT(n, '|a1')) MOD 80
                ELSE LEAST(fn_demo_u(CONCAT(n, '|a1')) MOD 90,
                           fn_demo_u(CONCAT(n, '|a2')) MOD 90)
           END AS idade
    FROM seq
)
SELECT CONCAT('7', LPAD(n, 14, '0')),
       IF(fn_demo_u(CONCAT(n, '|cpf')) < 100, NULL, CONCAT('1', LPAD(n, 10, '0'))),
       CONCAT('Pessoa Fictícia ', LPAD(n, 3, '0')),
       DATE_SUB('2024-01-01',
                INTERVAL idade * 365 + fn_demo_u(CONCAT(n, '|d')) MOD 365 DAY),
       CASE WHEN fn_demo_u(CONCAT(n, '|s')) < 520 THEN 'F'
            WHEN fn_demo_u(CONCAT(n, '|s')) < 995 THEN 'M'
            ELSE 'I' END,
       IF(n MOD 50 = 0, CONCAT('7', LPAD(n - 1, 14, '0')), NULL)
FROM base
ORDER BY n;

-- ---------------------------------------------------------------------
-- 2) Tabela auxiliar com o "comportamento" de cada pessoa na simulacao
-- ---------------------------------------------------------------------
CREATE TABLE DEMO_PESSOA (
    cns               CHAR(15) PRIMARY KEY,
    n                 INT NOT NULL,
    ine               CHAR(10) NOT NULL,
    idade             INT NOT NULL,
    carga_entrada     INT NOT NULL,
    carga_saida       INT NULL,
    tipo_saida        VARCHAR(30) NULL,
    inativo_fixo      BOOLEAN NOT NULL DEFAULT FALSE,
    carga_acao        INT NULL,             -- carga da 1a acao formativa da equipe
    qualidade_equipe  INT NOT NULL DEFAULT 0,
    raca_real         TINYINT UNSIGNED NOT NULL,
    raca_revela       INT NOT NULL DEFAULT 1,
    carga_divergencia INT NULL,
    raca_divergente   TINYINT UNSIGNED NULL,
    os_real           TINYINT UNSIGNED NULL,
    ig_real           TINYINT UNSIGNED NULL,
    recusa_os         BOOLEAN NOT NULL DEFAULT FALSE,
    invalido_os       BOOLEAN NOT NULL DEFAULT FALSE,
    recusa_ig         BOOLEAN NOT NULL DEFAULT FALSE,
    invalido_ig       BOOLEAN NOT NULL DEFAULT FALSE,
    os_revela         INT NOT NULL DEFAULT 1,
    ig_revela         INT NOT NULL DEFAULT 1,
    nome_social       VARCHAR(120) NULL,
    def1              TINYINT UNSIGNED NULL,
    def2              TINYINT UNSIGNED NULL
) ENGINE=InnoDB;

-- 2a) Os 60 cadastros da Etapa 02 mantem os dados da carga 1.
INSERT INTO DEMO_PESSOA
    (cns, n, ine, idade, carga_entrada, inativo_fixo, raca_real, raca_revela,
     os_real, ig_real, recusa_os, invalido_os, recusa_ig, invalido_ig,
     os_revela, ig_revela, nome_social, def1)
SELECT sc.cns,
       CAST(RIGHT(sc.cns, 3) AS UNSIGNED),
       sc.ine,
       TIMESTAMPDIFF(YEAR, p.dt_nascimento, '2024-01-30'),
       1,
       sc.situacao = 'INATIVO',
       CASE WHEN sc.id_raca_cor <> 9 THEN sc.id_raca_cor
            WHEN fn_demo_u(CONCAT(sc.cns, '|r')) < 550 THEN 3
            WHEN fn_demo_u(CONCAT(sc.cns, '|r')) < 880 THEN 1
            ELSE 2 END,
       IF(sc.id_raca_cor = 9, 3 + fn_demo_u(CONCAT(sc.cns, '|rr')) MOD 10, 1),
       sc.id_orientacao_sexual,
       sc.id_identidade_genero,
       sc.deseja_informar_os = 0,
       sc.deseja_informar_os = 0 AND sc.id_orientacao_sexual IS NOT NULL
           AND sc.id_orientacao_sexual <> 9,
       sc.deseja_informar_ig = 0,
       sc.deseja_informar_ig = 0 AND sc.id_identidade_genero IS NOT NULL
           AND sc.id_identidade_genero <> 9,
       1, 1,
       sc.nome_social,
       (SELECT MIN(sd.id_tipo_deficiencia) FROM SITUACAO_DEFICIENCIA sd
        WHERE sd.cns = sc.cns AND sd.id_carga = 1)
FROM SITUACAO_CADASTRAL sc
JOIN PESSOA p ON p.cns = sc.cns
WHERE sc.id_carga = 1;

-- 2b) As 540 pessoas novas: atributos sorteados de forma deterministica.
INSERT INTO DEMO_PESSOA
    (cns, n, ine, idade, carga_entrada, raca_real, os_real, ig_real)
SELECT p.cns, x.n,
       CONCAT('20000000', LPAD(1 + fn_demo_u(CONCAT(x.n, '|eq')) MOD 40, 2, '0')),
       TIMESTAMPDIFF(YEAR, p.dt_nascimento, '2024-01-30'),
       2 + (x.n - 61) MOD 29,
       CASE WHEN fn_demo_u(CONCAT(x.n, '|rc')) < 330 THEN 1   -- branca
            WHEN fn_demo_u(CONCAT(x.n, '|rc')) < 440 THEN 2   -- preta
            WHEN fn_demo_u(CONCAT(x.n, '|rc')) < 975 THEN 3   -- parda
            WHEN fn_demo_u(CONCAT(x.n, '|rc')) < 987 THEN 4   -- amarela
            WHEN fn_demo_u(CONCAT(x.n, '|rc')) < 993 THEN 5   -- indigena
            ELSE 3 END,
       CASE WHEN fn_demo_u(CONCAT(x.n, '|os')) < 940 THEN 1   -- heterossexual
            WHEN fn_demo_u(CONCAT(x.n, '|os')) < 965 THEN 2
            WHEN fn_demo_u(CONCAT(x.n, '|os')) < 990 THEN 3
            WHEN fn_demo_u(CONCAT(x.n, '|os')) < 995 THEN 4
            ELSE 5 END,
       CASE WHEN fn_demo_u(CONCAT(x.n, '|ig')) < 985 THEN 1   -- cisgenero
            WHEN fn_demo_u(CONCAT(x.n, '|ig')) < 991 THEN 2
            WHEN fn_demo_u(CONCAT(x.n, '|ig')) < 993 THEN 3
            WHEN fn_demo_u(CONCAT(x.n, '|ig')) < 998 THEN 4
            ELSE 5 END
FROM (SELECT cns, CAST(RIGHT(cns, 3) AS UNSIGNED) AS n
      FROM PESSOA WHERE cns > '700000000000060') x
JOIN PESSOA p ON p.cns = x.cns;

-- 2c) Equipe: carga da primeira acao formativa e "qualidade" (0 a 29;
--     quanto maior, mais demorado o preenchimento dos campos voluntarios).
UPDATE DEMO_PESSOA d
SET d.qualidade_equipe = fn_demo_u(CONCAT(d.ine, '|q')) MOD 30,
    d.carga_acao = (SELECT MIN(c.id_carga)
                    FROM ACAO_FORMATIVA af
                    JOIN CARGA c ON af.dt_acao BETWEEN c.periodo_ref_inicio
                                                   AND c.periodo_ref_fim
                    WHERE af.ine = d.ine);

-- 2d) Comportamento das pessoas novas.
UPDATE DEMO_PESSOA d
SET -- recusas e registros invalidos (recusou, mas o campo veio preenchido)
    d.recusa_os   = fn_demo_u(CONCAT(d.n, '|ro')) < 70,
    d.recusa_ig   = fn_demo_u(CONCAT(d.n, '|ro')) < 70
                    OR fn_demo_u(CONCAT(d.n, '|rg')) < 15,
    -- atraso no preenchimento de OS/IG, maior nas equipes de qualidade baixa
    d.os_revela   = d.carga_entrada
                    + fn_demo_u(CONCAT(d.n, '|osr')) MOD (8 + d.qualidade_equipe),
    -- raca/cor "Sem informacao" na entrada (6% a 15%, conforme a equipe)
    d.raca_revela = CASE
        WHEN fn_demo_u(CONCAT(d.n, '|rn')) < 15 THEN 99          -- nunca corrigida
        WHEN fn_demo_u(CONCAT(d.n, '|rv')) < 60 + 3 * (d.qualidade_equipe MOD 10)
            THEN d.carga_entrada + 1 + fn_demo_u(CONCAT(d.n, '|rr')) MOD 8
        ELSE d.carga_entrada END,
    -- saidas: obito (65+) ou transferencia
    d.carga_saida = IF(fn_demo_u(CONCAT(d.n, '|sa')) < 130,
                       d.carga_entrada + 1 + fn_demo_u(CONCAT(d.n, '|sb')) MOD 29, NULL),
    d.tipo_saida  = IF(d.idade >= 65, 'OBITO', 'TRANSFERIDO'),
    -- nome social: mais comum entre pessoas trans, travestis e nao binarias
    d.nome_social = IF((d.ig_real IN (2, 3, 4, 5) AND fn_demo_u(CONCAT(d.n, '|ns')) < 650)
                       OR fn_demo_u(CONCAT(d.n, '|nt')) < 4,
                       CONCAT('Nome social ', LPAD(d.n, 3, '0')), NULL),
    -- deficiencia: 4,5% ate 39 anos, 9% de 40 a 59, 25% com 60 ou mais
    d.def1 = IF(fn_demo_u(CONCAT(d.n, '|df')) <
                CASE WHEN d.idade >= 60 THEN 250 WHEN d.idade >= 40 THEN 90 ELSE 45 END,
                CASE WHEN fn_demo_u(CONCAT(d.n, '|dt')) < 150 THEN 1   -- auditiva
                     WHEN fn_demo_u(CONCAT(d.n, '|dt')) < 550 THEN 2   -- visual
                     WHEN fn_demo_u(CONCAT(d.n, '|dt')) < 850 THEN 3   -- fisica
                     WHEN fn_demo_u(CONCAT(d.n, '|dt')) < 950 THEN 4   -- intelectual
                     ELSE 5 END,
                NULL)
WHERE d.n > 60;

UPDATE DEMO_PESSOA d
SET d.invalido_os = d.recusa_os AND fn_demo_u(CONCAT(d.n, '|io')) < 150,
    d.invalido_ig = d.recusa_ig AND fn_demo_u(CONCAT(d.n, '|ii')) < 150,
    -- depois da acao formativa da equipe, o atraso cai
    d.os_revela = IF(d.carga_acao IS NOT NULL AND d.carga_acao < d.os_revela,
                     LEAST(d.os_revela,
                           GREATEST(d.carga_entrada, d.carga_acao + 1)
                           + fn_demo_u(CONCAT(d.n, '|oa')) MOD 4),
                     d.os_revela),
    d.raca_revela = IF(d.carga_acao IS NOT NULL AND d.carga_acao < d.raca_revela
                       AND d.raca_revela < 99,
                       GREATEST(d.carga_entrada, d.carga_acao + 1),
                       d.raca_revela),
    d.carga_saida = IF(d.carga_saida > 30, NULL, d.carga_saida),
    d.def2 = IF(d.def1 IS NOT NULL AND fn_demo_u(CONCAT(d.n, '|d2')) < 150,
                (d.def1 MOD 5) + 1, NULL)
WHERE d.n > 60;

UPDATE DEMO_PESSOA d
SET d.ig_revela = d.os_revela + fn_demo_u(CONCAT(d.n, '|igd')) MOD 2,
    -- troca preta <-> parda (ou outra) numa carga: divergencia entre registros
    d.carga_divergencia = IF(fn_demo_u(CONCAT(d.n, '|dv')) < 30
                             AND d.raca_revela < 99
                             AND d.raca_revela + 2 + fn_demo_u(CONCAT(d.n, '|dw')) MOD 5
                                 <= COALESCE(d.carga_saida - 1, 30),
                             d.raca_revela + 2 + fn_demo_u(CONCAT(d.n, '|dw')) MOD 5, NULL),
    d.raca_divergente = CASE d.raca_real WHEN 2 THEN 3 WHEN 3 THEN 2
                                         WHEN 1 THEN 3 ELSE 1 END
WHERE d.n > 60;

-- ---------------------------------------------------------------------
-- 3) Geracao das cargas 2 a 30, em ordem
-- ---------------------------------------------------------------------
DELIMITER $$

CREATE PROCEDURE sp_demo_gerar_cargas(IN p_de INT, IN p_ate INT)
BEGIN
    DECLARE v_carga INT DEFAULT p_de;

    WHILE v_carga <= p_ate DO
        -- Situacao cadastral de quem esta no territorio nesta carga.
        -- Cada INSERT dispara trg_resumo_carga_ai (RESUMO_CARGA).
        INSERT INTO SITUACAO_CADASTRAL
            (cns, id_carga, ine, nome_social, id_raca_cor,
             deseja_informar_os, id_orientacao_sexual,
             deseja_informar_ig, id_identidade_genero,
             situacao, dt_atualizacao_pec)
        SELECT d.cns, c.id_carga, d.ine, d.nome_social,
               CASE WHEN c.id_carga < d.raca_revela THEN 9
                    WHEN c.id_carga = d.carga_divergencia THEN d.raca_divergente
                    ELSE d.raca_real END,
               NOT d.recusa_os,
               CASE WHEN d.recusa_os AND d.invalido_os THEN d.os_real
                    WHEN d.recusa_os THEN 9
                    WHEN c.id_carga >= d.os_revela THEN d.os_real
                    ELSE NULL END,
               NOT d.recusa_ig,
               CASE WHEN d.recusa_ig AND d.invalido_ig THEN d.ig_real
                    WHEN d.recusa_ig THEN 9
                    WHEN c.id_carga >= d.ig_revela THEN d.ig_real
                    ELSE NULL END,
               CASE WHEN c.id_carga = d.carga_saida THEN d.tipo_saida
                    WHEN d.inativo_fixo THEN 'INATIVO'
                    WHEN fn_demo_u(CONCAT(d.cns, '|', c.id_carga, '|in')) < 25 THEN 'INATIVO'
                    ELSE 'ATIVO' END,
               DATE_ADD(c.periodo_ref_inicio,
                        INTERVAL fn_demo_u(CONCAT(d.cns, '|', c.id_carga, '|dt'))
                                 MOD (DATEDIFF(c.periodo_ref_fim, c.periodo_ref_inicio) + 1) DAY)
        FROM DEMO_PESSOA d
        JOIN CARGA c ON c.id_carga = v_carga
        WHERE d.carga_entrada <= v_carga
          AND (d.carga_saida IS NULL OR v_carga <= d.carga_saida)
        ORDER BY d.cns;

        -- Deficiencias registradas.
        INSERT INTO SITUACAO_DEFICIENCIA (cns, id_carga, id_tipo_deficiencia)
        SELECT d.cns, v_carga, d.def1
        FROM DEMO_PESSOA d
        JOIN SITUACAO_CADASTRAL sc ON sc.cns = d.cns AND sc.id_carga = v_carga
        WHERE d.def1 IS NOT NULL
        UNION
        SELECT d.cns, v_carga, d.def2
        FROM DEMO_PESSOA d
        JOIN SITUACAO_CADASTRAL sc ON sc.cns = d.cns AND sc.id_carga = v_carga
        WHERE d.def2 IS NOT NULL;

        -- Gabarito dos defeitos plantados nesta carga.
        INSERT INTO GABARITO_DEFEITO (cns, id_carga, campo, id_tipo_inconsistencia)
        SELECT d.cns, v_carga, 'raca_cor', 1
        FROM DEMO_PESSOA d
        JOIN SITUACAO_CADASTRAL sc ON sc.cns = d.cns AND sc.id_carga = v_carga
        WHERE v_carga < d.raca_revela
        UNION ALL
        SELECT d.cns, v_carga, 'raca_cor', 3
        FROM DEMO_PESSOA d
        JOIN SITUACAO_CADASTRAL sc ON sc.cns = d.cns AND sc.id_carga = v_carga
        WHERE v_carga = d.carga_divergencia
        UNION ALL
        SELECT d.cns, v_carga, 'orientacao_sexual', 2
        FROM DEMO_PESSOA d
        JOIN SITUACAO_CADASTRAL sc ON sc.cns = d.cns AND sc.id_carga = v_carga
        WHERE d.recusa_os AND d.invalido_os
        UNION ALL
        SELECT d.cns, v_carga, 'identidade_genero', 2
        FROM DEMO_PESSOA d
        JOIN SITUACAO_CADASTRAL sc ON sc.cns = d.cns AND sc.id_carga = v_carga
        WHERE d.recusa_ig AND d.invalido_ig;

        SET v_carga = v_carga + 1;
    END WHILE;
END$$

DELIMITER ;

CALL sp_demo_gerar_cargas(2, 30);

-- ---------------------------------------------------------------------
-- 4) Auditoria com cursor (Etapa 05) em todas as cargas, da mais antiga
--    para a mais recente. Cada chamada devolve o seu resumo.
-- ---------------------------------------------------------------------
CALL sp_auditar_inconsistencias_carga(1);
CALL sp_auditar_inconsistencias_carga(2);
CALL sp_auditar_inconsistencias_carga(3);
CALL sp_auditar_inconsistencias_carga(4);
CALL sp_auditar_inconsistencias_carga(5);
CALL sp_auditar_inconsistencias_carga(6);
CALL sp_auditar_inconsistencias_carga(7);
CALL sp_auditar_inconsistencias_carga(8);
CALL sp_auditar_inconsistencias_carga(9);
CALL sp_auditar_inconsistencias_carga(10);
CALL sp_auditar_inconsistencias_carga(11);
CALL sp_auditar_inconsistencias_carga(12);
CALL sp_auditar_inconsistencias_carga(13);
CALL sp_auditar_inconsistencias_carga(14);
CALL sp_auditar_inconsistencias_carga(15);
CALL sp_auditar_inconsistencias_carga(16);
CALL sp_auditar_inconsistencias_carga(17);
CALL sp_auditar_inconsistencias_carga(18);
CALL sp_auditar_inconsistencias_carga(19);
CALL sp_auditar_inconsistencias_carga(20);
CALL sp_auditar_inconsistencias_carga(21);
CALL sp_auditar_inconsistencias_carga(22);
CALL sp_auditar_inconsistencias_carga(23);
CALL sp_auditar_inconsistencias_carga(24);
CALL sp_auditar_inconsistencias_carga(25);
CALL sp_auditar_inconsistencias_carga(26);
CALL sp_auditar_inconsistencias_carga(27);
CALL sp_auditar_inconsistencias_carga(28);
CALL sp_auditar_inconsistencias_carga(29);
CALL sp_auditar_inconsistencias_carga(30);

-- ---------------------------------------------------------------------
-- 5) Curadoria feita pela gestao depois das cargas (Etapa 05 em uso):
--    duas duplicidades descobertas sao marcadas pelo procedimento P1 e um
--    nome e corrigido. As tres operacoes passam pelo trigger G1 (log) e
--    pelos triggers de resumo.
-- ---------------------------------------------------------------------
CALL sp_marcar_cadastro_duplicado('700000000000333', '700000000000332');
CALL sp_marcar_cadastro_duplicado('700000000000418', '700000000000417');
UPDATE PESSOA SET nome_civil = 'Pessoa Fictícia 077 (nome corrigido)'
WHERE cns = '700000000000077';

-- ---------------------------------------------------------------------
-- 6) Limpeza dos objetos auxiliares
-- ---------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_demo_gerar_cargas;
DROP FUNCTION IF EXISTS fn_demo_u;
DROP TABLE IF EXISTS DEMO_PESSOA;

-- ---------------------------------------------------------------------
-- 7) Conferencias
-- ---------------------------------------------------------------------
-- Registros por carga (deve crescer de 60 para cerca de 550).
SELECT id_carga, COUNT(*) AS registros, SUM(situacao = 'ATIVO') AS ativos
FROM SITUACAO_CADASTRAL
GROUP BY id_carga
ORDER BY id_carga;

-- O resumo mantido pelo trigger deve bater com o recalculo completo.
SELECT r.id_carga, r.total_ativos AS pelo_trigger, t.total_ativos AS recalculado
FROM RESUMO_CARGA r
JOIN (SELECT sc.id_carga, SUM(sc.situacao = 'ATIVO') AS total_ativos
      FROM SITUACAO_CADASTRAL sc JOIN PESSOA p ON p.cns = sc.cns
      WHERE p.cns_principal IS NULL
      GROUP BY sc.id_carga) t ON t.id_carga = r.id_carga
WHERE r.total_ativos <> t.total_ativos;          -- esperado: nenhuma linha

SELECT * FROM VW_EVOLUCAO_CARGAS ORDER BY id_carga;

SELECT * FROM LOG_ALTERACAO_PESSOA ORDER BY id_log;
