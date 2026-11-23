# Etapa 05 – Funções, procedimentos e triggers

| Entregável | Arquivo |
|---|---|
| 1 – SQL das funções | [`01_funcoes.sql`](01_funcoes.sql) |
| 2 – SQL dos procedimentos | [`02_procedimentos.sql`](02_procedimentos.sql) |
| 3 – SQL dos triggers | [`03_triggers.sql`](03_triggers.sql) |

Ordem de execução: funções → procedimentos → triggers (o P1 e o P3 usam a F2). Cada arquivo traz a justificativa semântica completa em comentário e termina com testes; os que alteram dados terminam em `ROLLBACK`.

## Funções

| Função | Estrutura condicional | Justificativa |
|---|---|---|
| **F1** `fn_faixa_etaria(nascimento, referência)` | `IF` de validação + cadeia `IF/ELSEIF` | Idade e faixa não são armazenadas (seção 3). A função centraliza os cortes usados nas análises; a data de referência é o fim do período da carga, para o histórico não mudar com o tempo. |
| **F2** `fn_classifica_publico_lgbt(orientação, identidade)` | `IF / ELSEIF / ELSE` | Fonte única da regra da seção 4, com as três saídas (LGBTQIAPN+, Sem informação, Não LGBTQIAPN+). Lê `publico_lgbt` dos domínios em vez de fixar códigos. |

## Procedimentos

| Procedimento | Requisito | Justificativa |
|---|---|---|
| **P1** `sp_marcar_cadastro_duplicado(duplicado, principal)` | **atualização de dados** | Regra 5 (duplicidade conta uma vez). Valida os CNS, impede cadeias A→B→C, redireciona quem apontava para o duplicado e recalcula `RESUMO_CARGA` numa transação. `NULL` desfaz a marcação. |
| **P2** `sp_auditar_inconsistencias_carga(carga)` + auxiliar `sp_registrar_inconsistencia` | **CURSOR** que realmente precisa de cursor | Percorre cada situação da carga e gera zero, uma ou várias inconsistências por registro, em outra tabela, a partir de buscas feitas registro a registro (cadastro principal, carga anterior) e de um `CALL` por ocorrência – nada disso cabe num `UPDATE` ou `INSERT ... SELECT`. É reexecutável. |
| **P3** `sp_recalcular_resumo_carga(carga)` *(complemento da Etapa 06)* | – | Refaz o resumo de uma carga a partir de `SITUACAO_CADASTRAL`; chamado pelos triggers G3. |

## Triggers

| Trigger | Requisito | Justificativa |
|---|---|---|
| **G1** `trg_pessoa_au_log` (AFTER UPDATE em PESSOA) | **atualiza a tabela de log** `LOG_ALTERACAO_PESSOA` | PESSOA tem dados pessoais e o vínculo de duplicidade, que muda os indicadores. Uma linha por campo alterado, com valor anterior, novo, usuário e hora; CPF mascarado (LGPD). Vale para tela, procedimento ou UPDATE manual. |
| **G2** `trg_situacao_cadastral_bu` / `_bd` (BEFORE UPDATE/DELETE) | segundo trigger | Regra 8: registros de cargas anteriores não podem ser alterados nem excluídos, e nenhum registro pode mudar de carga. A carga corrente segue editável para correções. |
| G2 – complementos *(Etapa 06)*: `trg_situacao_cadastral_bi`, `trg_situacao_deficiencia_bi` / `_bd` | – | Com o CRUD final, a regra 8 ainda podia ser contornada inserindo um registro numa carga fechada ou mexendo nas deficiências de uma carga anterior. Estes triggers fecham essas portas. |
| G3 *(Etapa 06)*: `trg_situacao_cadastral_au_resumo`, `trg_situacao_cadastral_ad_resumo`, `trg_pessoa_au_resumo` | – | O resumo da Etapa 03 só conhecia o INSERT. Agora alterações e exclusões na carga corrente, e mudanças de `cns_principal`, recalculam o resumo (via P3), e a `VW_EVOLUCAO_CARGAS` continua igual às consultas. |

Os complementos são acréscimos: os objetos entregues na Etapa 05 (F1, F2, P1, P2, G1, G2) não mudaram.

## Na interface (Etapa 06)
A página **Funções, procedimentos e triggers** executa a F1 com datas escolhidas, mostra a matriz completa da F2, roda o P1 e o P2 (simulação com `ROLLBACK` ou gravação), o P3, filtra o log do G1 e dispara cada caso da regra 8 para mostrar a recusa do G2. O painel usa a F1 na pirâmide etária e na tabela de frequências.
