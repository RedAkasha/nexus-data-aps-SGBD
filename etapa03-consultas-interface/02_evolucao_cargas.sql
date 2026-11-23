-- =====================================================================
-- NEXUSDATA - ETAPA 03 - ENTREGAVEL 2: EVOLUCAO ENTRE CARGAS
-- Banco: nexusdata_etapa02 | SGBD: MySQL 8.0+
--
-- CONTEUDO:
--   Tabela RESUMO_CARGA (contagens agregadas por carga, sem CNS)
--   Carga inicial (backfill) do resumo
--   Trigger trg_resumo_carga_ai (AFTER INSERT em SITUACAO_CADASTRAL)
--   View VW_EVOLUCAO_CARGAS (variacao entre cargas com LAG)
--
-- PRE-REQUISITO: Etapa 02 (criacao e insercao) e 01_consultas.sql.
--
-- COMO EXECUTAR: o arquivo usa DELIMITER. No MySQL Workbench ou no cliente
-- mysql, execute o arquivo inteiro. No DBeaver, use "Executar script"
-- (Alt+X), e nao "Executar instrucao" (Ctrl+Enter).
-- =====================================================================

USE nexusdata_etapa02;

-- =====================================================================
-- EVOLUCAO ENTRE CARGAS: TABELA DE RESUMO + TRIGGER + VIEW
-- =====================================================================
-- O resumo guarda contagens agregadas por carga (nao guarda CNS).
-- O trigger e disparado a cada INSERT em SITUACAO_CADASTRAL e atualiza
-- os totais da carga. Assim, a carga pode ser carregada linha a linha.
-- IMPORTANTE: o resumo acompanha registros inseridos apos a criacao do
-- trigger. Para cargas antigas, o INSERT ... SELECT abaixo faz a carga
-- inicial (backfill) sem alterar os dados originais.

CREATE TABLE IF NOT EXISTS RESUMO_CARGA (
    id_carga INT PRIMARY KEY,
    total_registros INT UNSIGNED NOT NULL DEFAULT 0,
    total_ativos INT UNSIGNED NOT NULL DEFAULT 0,
    total_negros_ativos INT UNSIGNED NOT NULL DEFAULT 0,
    total_lgbt_ativos INT UNSIGNED NOT NULL DEFAULT 0,
    dt_processamento DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_resumo_carga FOREIGN KEY (id_carga)
      REFERENCES CARGA(id_carga) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- Inicializacao dos resumos para as cargas que ja existem.
-- A operacao e repetivel: ON DUPLICATE KEY UPDATE atualiza o resumo.
INSERT INTO RESUMO_CARGA
    (id_carga, total_registros, total_ativos, total_negros_ativos, total_lgbt_ativos)
SELECT sc.id_carga,
       COUNT(*) AS total_registros,
       SUM(sc.situacao = 'ATIVO') AS total_ativos,
       SUM(sc.situacao = 'ATIVO' AND rc.pop_negra = 1) AS total_negros_ativos,
       SUM(sc.situacao = 'ATIVO' AND
           (COALESCE(ori.publico_lgbt, 0) = 1 OR COALESCE(ide.publico_lgbt, 0) = 1))
           AS total_lgbt_ativos
FROM SITUACAO_CADASTRAL sc
JOIN RACA_COR rc ON rc.id_raca_cor = sc.id_raca_cor
LEFT JOIN ORIENTACAO_SEXUAL ori
  ON ori.id_orientacao_sexual = sc.id_orientacao_sexual
LEFT JOIN IDENTIDADE_GENERO ide
  ON ide.id_identidade_genero = sc.id_identidade_genero
JOIN PESSOA p ON p.cns = sc.cns
WHERE p.cns_principal IS NULL
GROUP BY sc.id_carga
ON DUPLICATE KEY UPDATE
    total_registros = VALUES(total_registros),
    total_ativos = VALUES(total_ativos),
    total_negros_ativos = VALUES(total_negros_ativos),
    total_lgbt_ativos = VALUES(total_lgbt_ativos);

-- Trigger incremental: ao inserir uma situacao, soma 1 ao resumo.
-- A classificacao e calculada com base nas tabelas de dominio.
DROP TRIGGER IF EXISTS trg_resumo_carga_ai;
DELIMITER $$
CREATE TRIGGER trg_resumo_carga_ai
AFTER INSERT ON SITUACAO_CADASTRAL
FOR EACH ROW
BEGIN
    DECLARE v_pop_negra BOOLEAN DEFAULT FALSE;
    DECLARE v_publico_lgbt BOOLEAN DEFAULT FALSE;
    DECLARE v_principal CHAR(15);

    SELECT cns_principal INTO v_principal
    FROM PESSOA WHERE cns = NEW.cns;

    SELECT pop_negra INTO v_pop_negra
    FROM RACA_COR WHERE id_raca_cor = NEW.id_raca_cor;

    SELECT
      (COALESCE((SELECT publico_lgbt FROM ORIENTACAO_SEXUAL
                 WHERE id_orientacao_sexual = NEW.id_orientacao_sexual), 0) = 1)
      OR
      (COALESCE((SELECT publico_lgbt FROM IDENTIDADE_GENERO
                 WHERE id_identidade_genero = NEW.id_identidade_genero), 0) = 1)
    INTO v_publico_lgbt;

    IF v_principal IS NULL THEN
      INSERT INTO RESUMO_CARGA
        (id_carga, total_registros, total_ativos, total_negros_ativos, total_lgbt_ativos)
      VALUES
        (NEW.id_carga, 1,
         IF(NEW.situacao = 'ATIVO', 1, 0),
         IF(NEW.situacao = 'ATIVO' AND v_pop_negra = 1, 1, 0),
         IF(NEW.situacao = 'ATIVO' AND v_publico_lgbt = 1, 1, 0))
      ON DUPLICATE KEY UPDATE
        total_registros = total_registros + 1,
        total_ativos = total_ativos + IF(NEW.situacao = 'ATIVO', 1, 0),
        total_negros_ativos = total_negros_ativos +
          IF(NEW.situacao = 'ATIVO' AND v_pop_negra = 1, 1, 0),
        total_lgbt_ativos = total_lgbt_ativos +
          IF(NEW.situacao = 'ATIVO' AND v_publico_lgbt = 1, 1, 0);
    END IF;
END$$
DELIMITER ;

-- View: compara cada carga com a carga imediatamente anterior.
-- LAG recupera o valor anterior; variacao mostra diferenca absoluta.
-- CORRECAO (Etapa 06): as colunas de RESUMO_CARGA sao UNSIGNED. Sem o
-- CAST para SIGNED, qualquer queda entre cargas (variacao negativa) gerava
-- o erro 1690 "BIGINT UNSIGNED value is out of range" e a view parava de
-- funcionar justamente quando havia uma reducao a mostrar.
CREATE OR REPLACE VIEW VW_EVOLUCAO_CARGAS AS
SELECT id_carga, total_registros, total_ativos,
       total_negros_ativos, total_lgbt_ativos,
       LAG(total_ativos) OVER w AS ativos_carga_anterior,
       CAST(total_ativos AS SIGNED)
         - CAST(LAG(total_ativos) OVER w AS SIGNED) AS variacao_ativos,
       LAG(total_negros_ativos) OVER w AS negros_carga_anterior,
       CAST(total_negros_ativos AS SIGNED)
         - CAST(LAG(total_negros_ativos) OVER w AS SIGNED) AS variacao_negros,
       LAG(total_lgbt_ativos) OVER w AS lgbt_carga_anterior,
       CAST(total_lgbt_ativos AS SIGNED)
         - CAST(LAG(total_lgbt_ativos) OVER w AS SIGNED) AS variacao_lgbt,
       dt_processamento
FROM RESUMO_CARGA
WINDOW w AS (ORDER BY id_carga);

-- Resultado da evolucao entre as cargas:
SELECT * FROM VW_EVOLUCAO_CARGAS ORDER BY id_carga;

-- Conferencia do trigger e do resumo por carga:
SELECT * FROM RESUMO_CARGA ORDER BY id_carga;

-- ---------------------------------------------------------------------
-- TESTE DO TRIGGER (termina com ROLLBACK: o banco fica como estava)
-- Um registro novo na carga 2 cria a linha da carga 2 em RESUMO_CARGA.
-- ---------------------------------------------------------------------
START TRANSACTION;

INSERT INTO SITUACAO_CADASTRAL
    (cns, id_carga, ine, nome_social, id_raca_cor,
     deseja_informar_os, id_orientacao_sexual,
     deseja_informar_ig, id_identidade_genero,
     situacao, dt_atualizacao_pec)
VALUES
    ('700000000000002', 2, '2000000002', NULL, 2, 1, 1, 1, 1,
     'ATIVO', '2024-02-15');

-- carga 2: 1 ativo, 1 negro; variacao_ativos = 1 - 45 = -44 (negativa)
SELECT * FROM VW_EVOLUCAO_CARGAS ORDER BY id_carga;

ROLLBACK;
