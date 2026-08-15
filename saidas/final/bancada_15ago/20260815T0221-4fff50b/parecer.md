# PARECER

2 com parecer, 0 descartados com motivo, 1 inconclusivos com causa.

## CONDENADOS

[ALTA] [alta] correctness - app/main.py:79-88
O QUE: Quando `nome` é filtrado, retorna apenas linhas da query raw sem validar se o usuário tem realmente acesso aos projetos encontrados, bypass de _projetos_visiveis
ARBITRO: Um usuário vê um projeto se for o dono dele ou se participar dele. Listar projetos devolve os projetos que o usuário pode ver. (docs/REGRAS.md (Acesso e isolamento))
CORROBORADO POR: bandit (analise estatica de seguranca) em app/main.py:82 -- "Possible SQL injection vector through string-based query construction."
EVIDENCIA: test_injecao_nome_vaza_projeto.py passa em 93f69d1 e falha em 4fff50b (exit 0 -> 1). Artefato: artefatos/prova_correcao_03.json
E TAMBEM: contra o app rodando --
  GET /projects?nome=%25%27%20or%20p.id%3E0%20or%20p.nome%20like%20%27%25 como clara -> HTTP 200
  Artefato: artefatos/http_correcao_03.json
CONSERTO SUGERIDO: Usar parametros vinculados (bindparams) para o nome e manter o filtro de ids pelo ORM in_, nunca interpolando entrada do cliente na string SQL.

[ALTA] [alta] security - app/main.py:80-86
O QUE: parâmetro `nome` controlado pelo cliente é concatenado diretamente em SQL via f-string, violando isolamento de dados
ARBITRO: Toda consulta ao banco passa pelo ORM com parâmetros ligados. Valor vindo do cliente nunca é concatenado em SQL. (docs/REGRAS.md:Persistência)
CORROBORADO POR: bandit (analise estatica de seguranca) em app/main.py:82 -- "Possible SQL injection vector through string-based query construction."
EVIDENCIA: contra o app rodando --
  GET /projects?nome=%25%27%20or%20%271%27%3D%271 como ana -> HTTP 200
  GET /projects como ana -> HTTP 200
  Artefato: artefatos/http_injection_01.json
CONSERTO SUGERIDO: Usar consulta parametrizada com bind params (ex. text(...).bindparams ou ORM ilike com parametro) em vez de interpolar `nome` na string SQL.

## DESCARTADOS, COM MOTIVO

_nenhum._

## INCONCLUSIVOS, COM CAUSA

- correctness em app/main.py:79-85: recusa do classificador | categoria cyber | nenhum dos tres sinais de fallback apareceu (servido por claude-opus-5) -- nao da' para afirmar se a cadeia recusou ou se o fallback nao chegou a ser tentado
