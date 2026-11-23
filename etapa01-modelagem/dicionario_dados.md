# Dicionário de dados – Nexus Data

Gerado a partir do banco `nexusdata_etapa02` (MySQL 8) por `scripts/gerar_dicionario.py`. Legenda de chave: **PK** chave primária, **FK** chave estrangeira, **UK** único.

## DISTRITO_SANITARIO

Os 8 Distritos Sanitários do Recife (regra 1).

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| id_ds | tinyint unsigned | não | PK |  | CHECK (id_ds between 1 and 8) | Número do distrito (1 a 8) |
| nome | varchar(20) | não | UK |  |  | Nome do distrito |

## UNIDADE_SAUDE

Unidades de Saúde da Família; cada uma pertence a um único distrito.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| cnes | char(7) | não | PK |  |  | Código CNES da unidade |
| nome | varchar(120) | não |  |  |  | Nome da unidade |
| bairro | varchar(80) | não |  |  |  | Bairro onde fica a unidade |
| latitude | decimal(9,6) | sim |  |  | CHECK ((latitude is null) or (latitude between -(90) and 90)) | Latitude (graus decimais) |
| longitude | decimal(9,6) | sim |  |  | CHECK ((longitude is null) or (longitude between -(180) and 180)) | Longitude (graus decimais) |
| id_ds | tinyint unsigned | não | FK |  | FK → DISTRITO_SANITARIO.id_ds (UPDATE CASCADE, DELETE RESTRICT) | Distrito ao qual a unidade pertence |

## EQUIPE

Equipes de Saúde da Família; cada uma pertence a uma única unidade.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| ine | char(10) | não | PK |  |  | Identificador Nacional de Equipe (INE) |
| nome | varchar(80) | não |  |  |  | Nome da equipe |
| tipo_equipe | varchar(20) | não |  | ESF | CHECK (tipo_equipe in ('ESF','EAP','RIBEIRINHA','OUTRA')) | Tipo da equipe (ESF, EAP, RIBEIRINHA, OUTRA) |
| cnes | char(7) | não | FK |  | FK → UNIDADE_SAUDE.cnes (UPDATE CASCADE, DELETE RESTRICT) | Unidade à qual a equipe pertence |

## ACAO_FORMATIVA

Capacitações realizadas com as equipes.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| id_acao | int | não | PK |  | AUTO_INCREMENT | Identificador da ação (sequência) |
| ine | char(10) | não | FK |  | FK → EQUIPE.ine (UPDATE CASCADE, DELETE RESTRICT) | Equipe capacitada |
| dt_acao | date | não |  |  |  | Data da ação |
| tipo_acao | varchar(80) | não |  |  |  | Tipo da ação (oficina, capacitação...) |

## PESSOA

Pessoa cadastrada, identificada pelo CNS; guarda o vínculo de duplicidade.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| cns | char(15) | não | PK |  | CHECK regexp_like(cns,'^[0-9]{15}$') | Cartão Nacional de Saúde (15 dígitos) |
| cpf | char(11) | sim | UK |  |  | CPF (opcional) |
| nome_civil | varchar(120) | não |  |  |  | Nome civil |
| dt_nascimento | date | não |  |  |  | Data de nascimento (idade e faixa etária são calculadas, não armazenadas) |
| sexo | char(1) | não |  |  | CHECK (sexo in ('F','M','I')) | Sexo: F, M ou I (indeterminado) |
| cns_principal | char(15) | sim | FK |  | FK → PESSOA.cns (UPDATE CASCADE, DELETE SET NULL) | Se preenchido, o cadastro é duplicidade deste CNS e não entra nas contagens (regra 5) |

## CARGA

Cada extração periódica do PEC/e-SUS APS e seu período de referência.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| id_carga | int | não | PK |  | AUTO_INCREMENT | Número da carga |
| dt_hora_extracao | datetime | não |  | CURRENT_TIMESTAMP |  | Data e hora da extração |
| periodo_ref_inicio | date | não |  |  | CHECK (periodo_ref_fim >= periodo_ref_inicio) | Início do período de referência |
| periodo_ref_fim | date | não |  |  |  | Fim do período de referência (data-base de idade) |
| fonte | varchar(40) | não |  | PEC/e-SUS APS |  | Sistema de origem |

## RACA_COR

Domínio de raça/cor do PEC; marca quem é população negra.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| id_raca_cor | tinyint unsigned | não | PK |  |  | Código da raça/cor no PEC (9 = sem informação) |
| descricao | varchar(80) | não | UK |  |  | Descrição |
| pop_negra | tinyint(1) | não |  | 0 |  | 1 = preta ou parda (público da política da população negra) |

## ORIENTACAO_SEXUAL

Domínio de orientação sexual; marca o público LGBTQIAPN+.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| id_orientacao_sexual | tinyint unsigned | não | PK |  |  | Código no PEC (9 = não deseja informar) |
| descricao | varchar(80) | não | UK |  |  | Descrição |
| publico_lgbt | tinyint(1) | não |  | 0 |  | 1 = diferente de heterossexual |

## IDENTIDADE_GENERO

Domínio de identidade de gênero; marca o público LGBTQIAPN+.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| id_identidade_genero | tinyint unsigned | não | PK |  |  | Código no PEC (9 = não deseja informar) |
| descricao | varchar(80) | não | UK |  |  | Descrição |
| publico_lgbt | tinyint(1) | não |  | 0 |  | 1 = diferente de cisgênero |

## TIPO_DEFICIENCIA

Domínio dos tipos de deficiência.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| id_tipo_deficiencia | tinyint unsigned | não | PK |  |  | Código do tipo |
| descricao | varchar(100) | não | UK |  |  | Auditiva, visual, física, intelectual ou outra |

## SITUACAO_CADASTRAL

Retrato da pessoa em cada carga: equipe, marcadores de equidade e situação.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| cns | char(15) | não | PK, FK |  | FK → PESSOA.cns (UPDATE CASCADE, DELETE RESTRICT) | Pessoa |
| id_carga | int | não | PK, FK |  | FK → CARGA.id_carga (UPDATE CASCADE, DELETE RESTRICT) | Carga (período) do retrato |
| ine | char(10) | não | FK |  | FK → EQUIPE.ine (UPDATE CASCADE, DELETE RESTRICT) | Equipe responsável pela pessoa nesta carga (regra 2) |
| nome_social | varchar(120) | sim |  |  |  | Nome social (opcional; usado em listagens nominais, regra 6) |
| id_raca_cor | tinyint unsigned | não | FK |  | FK → RACA_COR.id_raca_cor (UPDATE CASCADE, DELETE RESTRICT) | Raça/cor (obrigatória, regra 3) |
| deseja_informar_os | tinyint(1) | não |  | 1 |  | A pessoa aceitou informar a orientação sexual |
| id_orientacao_sexual | tinyint unsigned | sim | FK |  | FK → ORIENTACAO_SEXUAL.id_orientacao_sexual (UPDATE CASCADE, DELETE SET NULL) | Orientação sexual (voluntária; pode ficar em branco) |
| deseja_informar_ig | tinyint(1) | não |  | 1 |  | A pessoa aceitou informar a identidade de gênero |
| id_identidade_genero | tinyint unsigned | sim | FK |  | FK → IDENTIDADE_GENERO.id_identidade_genero (UPDATE CASCADE, DELETE SET NULL) | Identidade de gênero (voluntária; pode ficar em branco) |
| situacao | varchar(30) | não |  | ATIVO | CHECK (situacao in ('ATIVO','INATIVO','TRANSFERIDO','OBITO')) | ATIVO, INATIVO, TRANSFERIDO ou OBITO (só ATIVO entra nas contagens) |
| dt_atualizacao_pec | date | não |  |  |  | Última atualização do cadastro no PEC |

## SITUACAO_DEFICIENCIA

Deficiências registradas para a pessoa em cada carga (0..N).

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| cns | char(15) | não | PK, FK |  | FK → SITUACAO_CADASTRAL.cns (UPDATE CASCADE, DELETE RESTRICT) | Pessoa |
| id_carga | int | não | PK, FK |  | FK → SITUACAO_CADASTRAL.id_carga (UPDATE CASCADE, DELETE RESTRICT) | Carga |
| id_tipo_deficiencia | tinyint unsigned | não | PK, FK |  | FK → TIPO_DEFICIENCIA.id_tipo_deficiencia (UPDATE CASCADE, DELETE RESTRICT) | Tipo de deficiência registrado |

## PARAMETRO

Parâmetros de cálculo vigentes em cada carga.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| id_carga | int | não | PK, FK |  | FK → CARGA.id_carga (UPDATE CASCADE, DELETE CASCADE) | Carga à qual o parâmetro se aplica |
| idade_min_elegivel | tinyint unsigned | não |  | 11 | CHECK (idade_min_elegivel between 0 and 120) | Idade mínima para perguntar orientação/identidade |

## TIPO_INCONSISTENCIA

Domínio dos tipos de inconsistência de registro.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| id_tipo_inconsistencia | tinyint unsigned | não | PK |  |  | Código do tipo |
| descricao | varchar(120) | não | UK |  |  | Descrição do tipo |

## INCONSISTENCIA

Inconsistências encontradas em cada carga, ligadas à equipe responsável (regra 7).

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| id_inconsistencia | bigint | não | PK |  | AUTO_INCREMENT | Identificador (sequência) |
| ine_responsavel | char(10) | não | FK |  | FK → EQUIPE.ine (UPDATE CASCADE, DELETE RESTRICT) | Equipe responsável pelo cadastro |
| cns | char(15) | não | FK |  | FK → PESSOA.cns (UPDATE CASCADE, DELETE RESTRICT) | Pessoa |
| id_carga | int | não | FK |  | FK → CARGA.id_carga (UPDATE CASCADE, DELETE RESTRICT) | Carga em que foi encontrada |
| campo | varchar(80) | não |  |  |  | Campo com problema |
| id_tipo_inconsistencia | tinyint unsigned | não | FK |  | FK → TIPO_INCONSISTENCIA.id_tipo_inconsistencia (UPDATE CASCADE, DELETE RESTRICT) | Tipo da inconsistência |

## GABARITO_DEFEITO

Defeitos plantados de propósito nos dados de teste, para avaliar a auditoria.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| id_defeito | bigint | não | PK |  | AUTO_INCREMENT | Identificador (sequência) |
| cns | char(15) | não | FK |  | FK → PESSOA.cns (UPDATE CASCADE, DELETE RESTRICT) | Pessoa |
| id_carga | int | não | FK |  | FK → CARGA.id_carga (UPDATE CASCADE, DELETE RESTRICT) | Carga |
| campo | varchar(80) | não |  |  |  | Campo com o defeito plantado |
| id_tipo_inconsistencia | tinyint unsigned | não | FK |  | FK → TIPO_INCONSISTENCIA.id_tipo_inconsistencia (UPDATE CASCADE, DELETE RESTRICT) | Tipo esperado |

## PERFIL

Perfis de acesso e sua abrangência (regra 9).

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| id_perfil | tinyint unsigned | não | PK |  |  | Código do perfil |
| nome | varchar(40) | não | UK |  |  | Nome do perfil |
| abrangencia | varchar(40) | não |  | TERRITORIO | CHECK (abrangencia in ('TERRITORIO','MUNICIPIO','UNIDADE','EQUIPE')) | O que o perfil enxerga: EQUIPE, UNIDADE, TERRITORIO ou MUNICIPIO |

## USUARIO

Usuários do sistema, com perfil e, para equipes, o território.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| id_usuario | int | não | PK |  | AUTO_INCREMENT | Identificador (sequência) |
| nome | varchar(120) | não |  |  |  | Nome do usuário |
| login | varchar(80) | não | UK |  |  | Login (único) |
| id_perfil | tinyint unsigned | não | FK |  | FK → PERFIL.id_perfil (UPDATE CASCADE, DELETE RESTRICT) | Perfil de acesso |
| ine | char(10) | sim | FK |  | FK → EQUIPE.ine (UPDATE CASCADE, DELETE SET NULL) | Equipe do usuário (só para perfis de equipe) |

## POLITICA

As três políticas de equidade da Secretaria.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| id_politica | tinyint unsigned | não | PK |  |  | Código da política |
| nome | varchar(120) | não | UK |  |  | Nome da política |

## INDICADOR

Indicadores de cada política, com descrição e forma de cálculo.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| id_indicador | smallint unsigned | não | PK |  |  | Código do indicador |
| nome | varchar(120) | não | UK |  |  | Nome do indicador |
| descricao | text | não |  |  |  | O que o indicador mede |
| formula_calculo | text | não |  |  |  | Forma de cálculo |
| id_politica | tinyint unsigned | não | FK |  | FK → POLITICA.id_politica (UPDATE CASCADE, DELETE RESTRICT) | Política à qual pertence |

## APURACAO_INDICADOR

Valor de um indicador numa carga e num nível territorial.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| id_apuracao | bigint | não | PK |  | AUTO_INCREMENT | Identificador (sequência) |
| id_indicador | smallint unsigned | não | FK |  | FK → INDICADOR.id_indicador (UPDATE CASCADE, DELETE RESTRICT) | Indicador apurado |
| id_carga | int | não | FK |  | FK → CARGA.id_carga (UPDATE CASCADE, DELETE RESTRICT) | Carga (período) da apuração |
| nivel_territorial | varchar(30) | não |  |  | CHECK (nivel_territorial in ('MUNICIPIO','DISTRITO','UNIDADE','EQUIPE')) | MUNICIPIO, DISTRITO, UNIDADE ou EQUIPE |
| id_ds | tinyint unsigned | sim | FK |  | FK → DISTRITO_SANITARIO.id_ds (UPDATE CASCADE, DELETE SET NULL) | Distrito (quando o nível é DISTRITO) |
| cnes | char(7) | sim | FK |  | FK → UNIDADE_SAUDE.cnes (UPDATE CASCADE, DELETE SET NULL) | Unidade (quando o nível é UNIDADE) |
| ine | char(10) | sim | FK |  | FK → EQUIPE.ine (UPDATE CASCADE, DELETE SET NULL) | Equipe (quando o nível é EQUIPE) |
| numerador | int unsigned | não |  | 0 |  | Numerador |
| denominador | int unsigned | não |  | 0 |  | Denominador |
| valor | decimal(10,4) | sim |  |  | CHECK ((valor is null) or (valor >= 0)) | Valor apurado |

## RESUMO_CARGA

(Etapa 03) Totais agregados por carga, mantidos por trigger; base da VW_EVOLUCAO_CARGAS.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| id_carga | int | não | PK, FK |  | FK → CARGA.id_carga (UPDATE CASCADE, DELETE RESTRICT) | Carga |
| total_registros | int unsigned | não |  | 0 |  | Registros de cadastros principais |
| total_ativos | int unsigned | não |  | 0 |  | Cadastros principais ativos |
| total_negros_ativos | int unsigned | não |  | 0 |  | Ativos da população negra |
| total_lgbt_ativos | int unsigned | não |  | 0 |  | Ativos do público LGBTQIAPN+ |
| dt_processamento | datetime | não |  | CURRENT_TIMESTAMP (ON UPDATE CURRENT_TIMESTAMP) |  | Última atualização do resumo |

## LOG_ALTERACAO_PESSOA

(Etapa 05) Log de alterações em PESSOA, gravado pelo trigger G1.

| Coluna | Tipo | Nulo | Chave | Padrão | Restrições | Descrição |
|---|---|---|---|---|---|---|
| id_log | bigint | não | PK |  | AUTO_INCREMENT | Identificador (sequência) |
| cns | char(15) | não |  |  |  | Pessoa alterada (sem FK, para preservar o histórico) |
| campo | varchar(30) | não |  |  |  | Campo alterado |
| valor_anterior | varchar(120) | sim |  |  |  | Valor antes (CPF mascarado) |
| valor_novo | varchar(120) | sim |  |  |  | Valor depois (CPF mascarado) |
| usuario_bd | varchar(100) | não |  |  |  | Usuário do banco que fez a alteração |
| dt_hora_alteracao | datetime | não |  | CURRENT_TIMESTAMP |  | Data e hora da alteração |

