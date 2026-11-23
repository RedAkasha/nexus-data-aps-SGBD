-- =====================================================================
-- NEXUSDATA - ENTREGAVEL 1 - SQL DAS FUNCOES
-- Banco: nexusdata_etapa02 | SGBD: MySQL 8.0+
--
-- CONTEUDO:
--   F1) fn_faixa_etaria             (usa estrutura condicional IF/ELSEIF)
--   F2) fn_classifica_publico_lgbt  (usa estrutura condicional IF/ELSEIF)
--
-- PRE-REQUISITO: scripts da Etapa 02 (criacao e insercao) ja executados.
-- ORDEM DESTA ENTREGA: 1) Funcoes  2) Procedimentos  3) Triggers
--
-- COMO EXECUTAR: o arquivo usa DELIMITER. No MySQL Workbench ou no cliente
-- mysql, execute o arquivo inteiro. No DBeaver, use "Executar script"
-- (Alt+X), e nao "Executar instrucao" (Ctrl+Enter).
-- =====================================================================

USE nexusdata_etapa02;

DROP FUNCTION IF EXISTS fn_faixa_etaria;
DROP FUNCTION IF EXISTS fn_classifica_publico_lgbt;

DELIMITER $$

-- ---------------------------------------------------------------------
-- F1) fn_faixa_etaria(data de nascimento, data de referencia)
--
-- JUSTIFICATIVA SEMANTICA:
-- O minimundo determina que idade e faixa etaria sao calculadas a partir
-- da data de nascimento e NAO sao armazenadas. As analises
-- sociodemograficas das tres politicas usam a faixa etaria, e a consulta
-- C7 repete o mesmo TIMESTAMPDIFF em cinco ramos de CASE. A funcao
-- centraliza a definicao das faixas: se a gestao mudar os cortes, muda-se
-- um unico ponto e todas as consultas e o dashboard passam a concordar.
--
-- A data de referencia e parametro (e nao CURDATE()) porque cada carga
-- retrata um periodo: a faixa etaria de uma carga antiga deve ser a que a
-- pessoa tinha no fim daquele periodo (CARGA.periodo_ref_fim), para que
-- o historico nao mude quando a consulta for refeita anos depois.
--
-- ESTRUTURA CONDICIONAL: IF de validacao + cadeia IF/ELSEIF das faixas.
-- ---------------------------------------------------------------------
CREATE FUNCTION fn_faixa_etaria(
    p_dt_nascimento DATE,
    p_dt_referencia DATE
)
RETURNS VARCHAR(15)
DETERMINISTIC
NO SQL
BEGIN
    DECLARE v_idade INT;

    -- Sem data, ou com nascimento posterior a referencia, nao ha idade.
    IF p_dt_nascimento IS NULL
       OR p_dt_referencia IS NULL
       OR p_dt_nascimento > p_dt_referencia THEN
        RETURN 'Nao calculavel';
    END IF;

    -- Anos completos na data de referencia.
    SET v_idade = TIMESTAMPDIFF(YEAR, p_dt_nascimento, p_dt_referencia);

    -- Mesmas faixas usadas na consulta C7.
    IF v_idade < 10 THEN
        RETURN '0 a 9';
    ELSEIF v_idade < 20 THEN
        RETURN '10 a 19';
    ELSEIF v_idade < 40 THEN
        RETURN '20 a 39';
    ELSEIF v_idade < 60 THEN
        RETURN '40 a 59';
    ELSE
        RETURN '60 ou mais';
    END IF;
END$$

-- ---------------------------------------------------------------------
-- F2) fn_classifica_publico_lgbt(orientacao sexual, identidade de genero)
--
-- JUSTIFICATIVA SEMANTICA:
-- A regra do publico LGBTQIAPN+ (secao 4 do minimundo) tem tres saidas:
--   * 'LGBTQIAPN+'     : identidade diferente de cisgenero OU orientacao
--                        diferente de heterossexual;
--   * 'Sem informacao' : quem nao informou e contabilizado a parte;
--   * 'Nao LGBTQIAPN+' : os dois campos informados e nenhum no publico.
-- Hoje essa regra esta escrita em tres lugares (consulta C2, backfill de
-- RESUMO_CARGA e trigger trg_resumo_carga_ai). Se uma copia for alterada
-- e as outras nao, o dashboard e o resumo passam a divergir. A funcao
-- vira a fonte unica da regra e ja e usada pelo procedimento
-- sp_marcar_cadastro_duplicado (entregavel 2).
--
-- A funcao consulta o atributo publico_lgbt das tabelas de dominio, em
-- vez de fixar codigos: se o PEC/e-SUS APS ganhar uma nova categoria,
-- basta cadastra-la no dominio. O codigo 9 ("Nao deseja informar") segue
-- a mesma convencao das consultas C2 e C3.
--
-- ESTRUTURA CONDICIONAL: IF / ELSEIF / ELSE com as tres saidas.
--
-- ATENCAO AO COMPARAR O RETORNO COM UM TEXTO: o banco usa a collation
-- utf8mb4_unicode_ci, mas a conexao do MySQL 8 costuma usar
-- utf8mb4_0900_ai_ci. Nesse caso, "fn_...(...) = 'LGBTQIAPN+'" gera o
-- erro 1267 (Illegal mix of collations). Escreva a comparacao assim:
--   fn_classifica_publico_lgbt(os, ig) COLLATE utf8mb4_unicode_ci = 'LGBTQIAPN+'
-- Em SELECT e GROUP BY (teste T4) nao e preciso nada.
-- ---------------------------------------------------------------------
CREATE FUNCTION fn_classifica_publico_lgbt(
    p_id_orientacao_sexual TINYINT UNSIGNED,
    p_id_identidade_genero TINYINT UNSIGNED
)
RETURNS VARCHAR(20)
READS SQL DATA
BEGIN
    DECLARE v_os_lgbt BOOLEAN DEFAULT FALSE;
    DECLARE v_ig_lgbt BOOLEAN DEFAULT FALSE;

    -- Codigo nulo ou inexistente no dominio conta como "nao e do publico".
    SET v_os_lgbt = COALESCE(
        (SELECT publico_lgbt
         FROM ORIENTACAO_SEXUAL
         WHERE id_orientacao_sexual = p_id_orientacao_sexual), FALSE);

    SET v_ig_lgbt = COALESCE(
        (SELECT publico_lgbt
         FROM IDENTIDADE_GENERO
         WHERE id_identidade_genero = p_id_identidade_genero), FALSE);

    IF v_os_lgbt OR v_ig_lgbt THEN
        -- Basta um dos marcadores para a pessoa pertencer ao publico.
        RETURN 'LGBTQIAPN+';
    ELSEIF p_id_orientacao_sexual IS NULL OR p_id_orientacao_sexual = 9
        OR p_id_identidade_genero IS NULL OR p_id_identidade_genero = 9 THEN
        -- Falta resposta em algum marcador: nao se pode afirmar que a
        -- pessoa esta fora do publico.
        RETURN 'Sem informacao';
    ELSE
        RETURN 'Nao LGBTQIAPN+';
    END IF;
END$$

DELIMITER ;

-- =====================================================================
-- TESTES / EVIDENCIAS (somente leitura; nao alteram dados)
-- =====================================================================

-- T1) Limites das faixas etarias, na data-base 2024-01-30 (fim da carga 1).
SELECT fn_faixa_etaria('2014-01-31', '2024-01-30') AS nove_anos,        -- 0 a 9
       fn_faixa_etaria('2014-01-30', '2024-01-30') AS dez_anos,         -- 10 a 19
       fn_faixa_etaria('1984-01-30', '2024-01-30') AS quarenta_anos,    -- 40 a 59
       fn_faixa_etaria('1964-01-30', '2024-01-30') AS sessenta_anos,    -- 60 ou mais
       fn_faixa_etaria('2025-01-01', '2024-01-30') AS nasc_futuro,      -- Nao calculavel
       fn_faixa_etaria(NULL, '2024-01-30')         AS sem_nascimento;   -- Nao calculavel

-- T2) As tres saidas da classificacao (codigos do dominio da Etapa 02).
SELECT fn_classifica_publico_lgbt(1, 1)       AS hetero_cis,          -- Nao LGBTQIAPN+
       fn_classifica_publico_lgbt(2, 1)       AS homo_cis,            -- LGBTQIAPN+
       fn_classifica_publico_lgbt(1, 2)       AS hetero_trans,        -- LGBTQIAPN+
       fn_classifica_publico_lgbt(9, 2)       AS nao_informa_trans,   -- LGBTQIAPN+
       fn_classifica_publico_lgbt(1, 9)       AS hetero_nao_informa,  -- Sem informacao
       fn_classifica_publico_lgbt(NULL, NULL) AS em_branco;           -- Sem informacao

-- T3) Consulta C7 reescrita com fn_faixa_etaria.
--     Deve devolver as mesmas linhas da C7 original.
SELECT ds.id_ds, ds.nome AS distrito,
       fn_faixa_etaria(p.dt_nascimento, c.periodo_ref_fim) AS faixa_etaria,
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
ORDER BY ds.id_ds, MAX(p.dt_nascimento) DESC;

-- T4) Consulta C2 reescrita com fn_classifica_publico_lgbt.
--     Deve devolver os mesmos totais da C2 original.
SELECT categoria, pessoas,
       ROUND(100 * pessoas / NULLIF(SUM(pessoas) OVER (), 0), 1) AS percentual
FROM (
    SELECT fn_classifica_publico_lgbt(sc.id_orientacao_sexual,
                                      sc.id_identidade_genero) AS categoria,
           COUNT(*) AS pessoas
    FROM SITUACAO_CADASTRAL sc
    JOIN PESSOA p ON p.cns = sc.cns
    WHERE sc.id_carga = (SELECT MAX(id_carga) FROM SITUACAO_CADASTRAL)
      AND sc.situacao = 'ATIVO'
      AND p.cns_principal IS NULL
    GROUP BY categoria
) totais
ORDER BY pessoas DESC;
