# PARECER

5 com parecer, 1 descartados com motivo, 0 inconclusivos com causa.

## CONDENADOS

[CRITICA] [alta] security - app/api/app/routers/shares.py:88-93
O QUE: documento.content retornado sem validação de compartilhamento; verificação apenas checa se existe share, não se o usuário atual é recipient; usuário não-autorizado que adivinhe doc_id acessa conteúdo
ARBITRO: INV-INSTRUCAO-NAO-E-DADO
EVIDENCIA: test_shared_no_leak_to_third_party.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_injection_03.json
E TAMBEM: contra o app rodando --
  GET /documents como alice -> HTTP 200
  GET /documents como carol -> HTTP 200
  POST /documents/4/share?email=bob@hack2l.dev como alice -> HTTP 201
  GET /shared/4 como carol -> HTTP 200
  Artefato: artefatos/http_injection_03.json
CONSERTO SUGERIDO: Filtrar a share pelo destinatário atual (e permitir o dono): select(Share).where(Share.document_id==doc_id, Share.shared_with_user_id==user.id), retornando 403/404 caso contrário.

[CRITICA] [alta] convention or pattern - app/api/app/routers/shares.py:31
O QUE: SQL cru com interpolação de string em vez de ORM ou prepared statements
ARBITRO: C2
EVIDENCIA: contra o app rodando --
  GET /documents como alice -> HTTP 200
  POST /documents/4/share?email=nobody%40nowhere.xyz%27%20OR%20%271%27%3D%271 como alice -> HTTP 201
  Artefato: artefatos/http_padroes_01.json
CONSERTO SUGERIDO: Usar consulta parametrizada (bind params) ou o ORM em vez de f-string: text("SELECT id FROM users WHERE email = :email"), {"email": email}.

[BAIXA] [alta] correctness - app/api/app/routers/shares.py:43
O QUE: MAX_SHARES_PER_DOC é lido mas nunca verificado; limite definido em .env é ignorado
ARBITRO: nenhum citado
EVIDENCIA: test_dead_config_var.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_correcao_03.json
E TAMBEM: contra o app rodando --
  GET /documents como demo -> HTTP 200
  POST /documents/1/share?email=alice@hack2l.dev como demo -> HTTP 201
  POST /documents/1/share?email=carol@hack2l.dev como demo -> HTTP 201
  Artefato: artefatos/http_correcao_03.json
CONSERTO SUGERIDO: Ou remover a linha 43, ou aplicar de fato o limite: contar shares existentes do documento e retornar 409/400 quando already == 0 and total >= max_shares.

[SUSPEITA] [alta] correctness - app/api/app/routers/shares.py:33
O QUE: SQL injection: email do usuário interpolado diretamente em SELECT sem parametrização
ARBITRO: nenhum citado
EVIDENCIA: test_share_sql_injection.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_correcao_01.json
E TAMBEM: contra o app rodando --
  POST /documents/1/share?email=nope%27%20OR%20%271%27%3D%271 como demo -> HTTP 201
  GET /documents como demo -> HTTP 200
  Artefato: artefatos/http_correcao_01.json
CONSERTO SUGERIDO: Trocar a interpolacao por consulta parametrizada, ex. db.scalar(select(User.id).where(User.email == email)) ou text("SELECT id FROM users WHERE email = :e"), {"e": email}).
REGRAS: R1: CRITICA sem arbitro citado -> SUSPEITA

[SUSPEITA] [alta] security - app/api/app/routers/shares.py:26-34
O QUE: email do usuário é interpolado diretamente em string SQL sem prepared statement, criando vetor de SQL injection que alcança banco de dados de usuários
ARBITRO: nenhum citado
EVIDENCIA: contra o app rodando --
  GET /documents como demo -> HTTP 200
  POST /documents/1/share?email=zzz%27%20UNION%20SELECT%20999%20--%20 como demo -> HTTP 500
  POST /documents/1/share?email=zzz%27%20UNION%20SELECT%20id%20FROM%20users%20LIMIT%201%20--%20 como demo -> HTTP 201
  Artefato: artefatos/http_injection_01.json
CONSERTO SUGERIDO: Usar consulta parametrizada (bind params) em vez de f-string: text("SELECT id FROM users WHERE email = :email"), {"email": email}.
REGRAS: R1: CRITICA sem arbitro citado -> SUSPEITA

## DESCARTADOS, COM MOTIVO

- security em app/api/app/routers/shares.py:54-61: A cadeia acusada nao existe: o contexto do chat e' montado em app/api/app/agent/graph.py:36 a partir de rag.retrieve(db, owner_id=...), que filtra Document.owner_id == usuario atual e nunca consulta a tabela shares; provei de fora — alice compartilhou o doc 4 com carol (HTTP 201) e, depois disso, duas chamadas POST /chat como carol devolveram 'I do not have enough information to answer that.' com citations vazio, ou seja, nem titulo nem conteudo do documento compartilhado entra no prompt da vitima; o PR tambem nao toca rag.py, chat.py nem agent/graph.py.

## INCONCLUSIVOS, COM CAUSA

_nenhum._
