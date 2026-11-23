# Etapa 04 – Consultas avançadas, visões e índices

| Entregável | Arquivo |
|---|---|
| 1 – SQL dos índices | [`01_indices.sql`](01_indices.sql) |
| 2 – SQL das consultas | [`02_consultas.sql`](02_consultas.sql) |
| 3 – SQL das visões | [`03_visoes.sql`](03_visoes.sql) |

## 1. Índices

| Índice | Colunas | Por que é necessário | Usado por |
|---|---|---|---|
| `idx_sc_carga_situacao` | `SITUACAO_CADASTRAL (id_carga, situacao, ine)` | Toda consulta populacional filtra "carga X, situação ATIVO" e junta com EQUIPE pelo INE. A PK `(cns, id_carga)` começa pelo CNS e não serve para isso. Com o índice, o filtro vira `ref` com "Using index" e o `MAX(id_carga)` da carga corrente é resolvido no índice. | C1–C7, C9, C11, C12, `VW_PERFIL_EQUIDADE_EQUIPE`, triggers G2, painel |
| `idx_inc_carga_equipe` | `INCONSISTENCIA (id_carga, ine_responsavel, id_tipo_inconsistencia)` | Inconsistências são sempre lidas "da carga X, por equipe e tipo". Antes: varredura completa (`type = ALL`, "Using temporary"); depois: `ref` só no índice. | C4, C5, C8, C9, `VW_LISTA_NOMINAL_INCONSISTENCIAS`, painel |
| `uk_inc_ocorrencia` (único) | `INCONSISTENCIA (cns, id_carga, campo, id_tipo_inconsistencia)` | Identifica uma ocorrência (seção 5 do minimundo) e impede gravá-la duas vezes. Atende a busca do `sp_registrar_inconsistencia`, chamada uma vez por ocorrência pela auditoria com cursor, e o pareamento da C10. | P2 (Etapa 05), C10 |

O arquivo mostra o `EXPLAIN` **antes e depois** de cada índice.

## 2. Consultas (numeração continua a da Etapa 03)

| # | Tipo exigido | Pergunta respondida |
|---|---|---|
| C9 | **Anti join** (`LEFT JOIN ACAO_FORMATIVA ... WHERE af.id_acao IS NULL`) | Quais equipes nunca receberam ação formativa, com volume de cadastros e inconsistências – por onde começar a capacitação. |
| C10 | **Full outer join** (o MySQL não tem: `LEFT JOIN` `UNION ALL` `RIGHT JOIN ... WHERE esquerda IS NULL`) | Auditoria automática × gabarito de defeitos: acertos, defeitos não detectados e registros sem gabarito, com precisão e sensibilidade. |
| C11 | **Subconsultas** (tabela derivada + subconsulta escalar no `SELECT` e no `WHERE`) | Equipes com completude de orientação sexual abaixo da média municipal. |
| C12 | **Subconsultas correlacionadas** (`NOT EXISTS`) | Entradas e saídas de cadastros ativos entre a carga anterior e a corrente, por distrito. |

## 3. Visões

### `VW_PERFIL_EQUIDADE_EQUIPE` (8 tabelas, 7 joins)
Uma linha por **carga × equipe** com os totais dos três públicos e a completude dos marcadores.
**Justificativa:** a seção 6 do minimundo pede a distribuição dos públicos por distrito, unidade e equipe e a completude dos marcadores. Essas perguntas repetem sempre as mesmas regras (só ATIVO, sem duplicidade, preta/parda, LGBTQIAPN+ por orientação *ou* identidade, "sem informação" à parte, código 9 não conta como preenchido); a visão fixa essas regras num lugar só. Ela devolve **apenas agregados** (sem CNS, nome ou CPF), o que atende a LGPD (regra 6) e permite liberá-la às coordenações (regra 9). É a fonte do painel da Etapa 06.

### `VW_LISTA_NOMINAL_INCONSISTENCIAS` (8 tabelas, 7 joins)
Uma linha por inconsistência, com a pessoa, o campo, o tipo, a equipe, a unidade, o distrito e se a equipe já tinha sido capacitada.
**Justificativa:** quem corrige o cadastro é a equipe (regra 7), e ela precisa de uma lista nominal. A regra 6 manda usar o **nome social** quando existir nessas listagens – a visão faz isso em `nome_exibicao` e nunca expõe o CPF. Filtrando por `ine` (o `USUARIO.ine` do perfil "Equipe APS"), cada equipe vê só o seu território (regra 9); a interface demonstra isso na opção "Ver como".
