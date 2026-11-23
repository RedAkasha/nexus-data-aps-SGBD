# Etapa 03 – Interface funcional com dashboard (primeira versão)

| Entregável | Onde está |
|---|---|
| SQL das consultas C1–C8 | [`01_consultas.sql`](01_consultas.sql) |
| Evolução entre cargas: tabela de resumo, trigger e visão | [`02_evolucao_cargas.sql`](02_evolucao_cargas.sql) |
| Interface (backend + frontend) | [`../app`](../app) – a mesma aplicação evoluiu até a versão final da Etapa 06 |

## Consultas

| # | Pergunta | Técnica |
|---|---|---|
| C1 | População negra ativa por distrito | JOIN de 6 tabelas + agregação |
| C2 | Público LGBTQIAPN+ × sem informação × demais | CTE + LEFT JOIN + função de janela |
| C3 | Completude dos campos voluntários por distrito | JOIN + `AVG` de expressão booleana |
| C4 | Inconsistências por distrito e tipo | CTE + janela `PARTITION BY` |
| C5 | Equipes com/sem ação formativa × média de inconsistências | CTEs agregadas + LEFT JOIN |
| C6 | Pessoas com deficiência por distrito e tipo | JOIN de 7 tabelas + `COUNT(DISTINCT)` |
| C7 | Perfil etário por distrito | JOIN + `CASE` + `TIMESTAMPDIFF` |
| C8 | Inconsistências por campo | CTE + janela sobre o total |

Regras comuns: carga corrente = maior `id_carga` com registros; só `ATIVO` entra; duplicidades ficam fora (`cns_principal IS NULL`).

## Evolução entre cargas

`RESUMO_CARGA` guarda contagens agregadas por carga (sem CNS). O trigger `trg_resumo_carga_ai` (AFTER INSERT em `SITUACAO_CADASTRAL`) soma cada registro novo, e a visão `VW_EVOLUCAO_CARGAS` compara cada carga com a anterior usando `LAG`.

**Correção feita na entrega final:** as colunas do resumo são `UNSIGNED`, então a diferença `total_ativos - LAG(total_ativos)` gerava o erro 1690 (*BIGINT UNSIGNED value is out of range*) sempre que uma carga tinha menos ativos que a anterior – a visão parava de funcionar justamente quando havia queda a mostrar. A visão agora converte para `SIGNED` antes de subtrair, e o arquivo traz um teste com variação negativa.

O arquivo consolidado com o trigger sem `DELIMITER` (versão para o DBeaver) foi unificado neste formato: no DBeaver, use **Executar script (Alt+X)**.

## Interface

A interface pedida na Etapa 03 é a aplicação Streamlit em [`../app`](../app), com backend em Python que fala com o MySQL por **SQL explícito** (PyMySQL, sem ORM; cada comando aparece na tela):

* **Inserção/alteração/exclusão** – página *Cadastros (CRUD)*; na Etapa 06 ela chegou a 5 tabelas.
* **Visualização de dados e gráficos** – página *Painel*.
* **Resultados das consultas** – página *Consultas e visões*, com C1–C8 (e as da Etapa 04), parâmetros de carga e distrito, tabela, gráfico e o SQL executado. Ao menos uma consulta com JOIN: todas, exceto C5 e C8, usam JOIN de 6 ou mais tabelas.

Instruções de instalação e execução no [README principal](../README.md).
