# Etapa 02 – Criação das tabelas e inserção de dados

| Entregável | Arquivo |
|---|---|
| 1 – SQL de criação das tabelas | [`01_criacao_tabelas.sql`](01_criacao_tabelas.sql) |
| 2 – SQL de inserção de dados | [`02_insercao_dados.sql`](02_insercao_dados.sql) |

SGBD: **MySQL 8.0** · banco `nexusdata_etapa02` · `utf8mb4_unicode_ci`.

## Restrições usadas

| Recurso | Onde |
|---|---|
| `PRIMARY KEY` simples e composta | todas; compostas em `SITUACAO_CADASTRAL (cns, id_carga)` e `SITUACAO_DEFICIENCIA (cns, id_carga, id_tipo_deficiencia)` |
| `FOREIGN KEY ... ON UPDATE CASCADE` | todas as chaves estrangeiras (ex.: trocar o INE de uma equipe propaga para situações, inconsistências, ações e usuários) |
| `ON DELETE SET NULL` | `PESSOA.cns_principal`, `USUARIO.ine`, `SITUACAO_CADASTRAL.id_orientacao_sexual / id_identidade_genero`, `APURACAO_INDICADOR.id_ds / cnes / ine` |
| `ON DELETE CASCADE` | `PARAMETRO → CARGA` (o parâmetro só existe com a sua carga) |
| `ON DELETE RESTRICT` | demais FKs: não se apaga equipe, pessoa ou carga com histórico |
| `CHECK` | distrito entre 1 e 8, latitude/longitude, sexo `F/M/I`, CNS com 15 dígitos (`REGEXP`), período da carga, situação cadastral, tipo de equipe, abrangência do perfil, nível territorial, valor do indicador ≥ 0, idade mínima |
| `DEFAULT` | `tipo_equipe 'ESF'`, `situacao 'ATIVO'`, `fonte 'PEC/e-SUS APS'`, `idade_min_elegivel 11`, `deseja_informar_* TRUE`, `dt_hora_extracao CURRENT_TIMESTAMP` |
| `UNIQUE` | `PESSOA.cpf`, `USUARIO.login`, nome do distrito, descrições dos domínios, nomes de política e indicador |
| `AUTO_INCREMENT` (sequências) | `ACAO_FORMATIVA`, `CARGA`, `INCONSISTENCIA`, `GABARITO_DEFEITO`, `USUARIO`, `APURACAO_INDICADOR` (omitidas nos `INSERT`) |

## Quantidade de tuplas

| Tabela | Tuplas | | Tabela | Tuplas |
|---|---:|---|---|---:|
| UNIDADE_SAUDE | 30 | | PESSOA | 60 |
| EQUIPE | 40 | | SITUACAO_CADASTRAL | 60 |
| ACAO_FORMATIVA | 30 | | SITUACAO_DEFICIENCIA | 35 |
| CARGA | 30 | | INCONSISTENCIA | 35 |
| PARAMETRO | 30 | | GABARITO_DEFEITO | 30 |
| USUARIO | 30 | | INDICADOR | 30 |
| APURACAO_INDICADOR | 60 | | | |

**Exceções justificadas** (comentadas no próprio script): `DISTRITO_SANITARIO` tem 8 linhas porque o Recife tem exatamente 8 distritos; `RACA_COR`, `ORIENTACAO_SEXUAL`, `IDENTIDADE_GENERO`, `TIPO_DEFICIENCIA`, `TIPO_INCONSISTENCIA`, `PERFIL` e `POLITICA` são domínios fechados (categorias do PEC/e-SUS APS e do minimundo) – inventar 30 categorias aceitaria classificações inválidas e violaria a regra 4.

Na Etapa 06, o script [`../etapa06-aplicacao-final/01_carga_demonstracao.sql`](../etapa06-aplicacao-final/01_carga_demonstracao.sql) amplia a base para 600 pessoas em 30 cargas, sem alterar estes dados.

## Ajuste feito na entrega final

O script de criação agora remove também os objetos criados nas etapas seguintes (`RESUMO_CARGA`, `LOG_ALTERACAO_PESSOA` e as visões) antes de recriar as tabelas, para que a reinstalação parta do zero. O restante do SQL é o entregue na Etapa 02.
