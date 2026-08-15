# PARECER

0 com parecer, 3 descartados com motivo, 0 inconclusivos com causa.

## CONDENADOS

_nenhum achado sobreviveu a pericia._
## DESCARTADOS, COM MOTIVO

- correctness em app/main.py:73: O banco e' PostgreSQL 16 (docker-compose.yml / app/db.py), onde agrupar pela chave primaria (Project.id) satisfaz a dependencia funcional do SQL:1999 e permite projetar todas as colunas de Project sem erro nem indeterminismo; GET /projects como ana devolveu HTTP 200 com dados corretos ([{id:1,...,tarefas:2},{id:2,...,tarefas:1}]) e a suite existente passou (8 passed) contra o head; a premissa de 'sql_mode ONLY_FULL_GROUP_BY' e' do MySQL e nao se aplica.
- correctness em app/main.py:81: O `select()` em app/main.py:74 declara exatamente tres colunas (Project, User.email, func.count(Task.id)), entao cada linha tem sempre 3 elementos; na API rodando, GET /projects devolveu HTTP 200 com o campo `tarefas` correto para ana (2 e 1) e para clara (1), e a suite existente passou inteira (8 passed) no head — o ValueError descrito so ocorreria sob uma mudanca hipotetica de schema/ORM que nao existe neste PR e que quebraria a query antes do desempacotamento.
- convention or pattern em app/main.py:81: O teste diferencial (projetos com 0, 3 tarefas e projeto de terceiro) passa igual no base e no head: a ordem das colunas em db.execute() segue deterministicamente a ordem declarada em select(Project, User.email, func.count(Task.id)), os valores caem nos campos certos de ProjetoOut (construido com argumentos nomeados e validado pelo response_model), sem duplicacao de linhas pelo outer join; a chamada real GET /projects como ana confirmou {id, nome, dono_email, tarefas} corretos (2 e 1 tarefas) e davi, sem projetos, recebeu [].

## INCONCLUSIVOS, COM CAUSA

_nenhum._
