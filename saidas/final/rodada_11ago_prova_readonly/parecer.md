# PARECER

10 com parecer, 0 descartados com motivo, 0 inconclusivos com causa.

## CONDENADOS

[CRITICA] [alta] security - app/api/app/routers/shares.py:29-31
O QUE: email do usuário é interpolado diretamente em SQL sem parametrização
ARBITRO: Persistência passa pelos modelos do ORM; não há SQL cru no app (docs/REFERENCE_GUIDE.md:70)
EVIDENCIA: test_share_email_injection.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_injection_01.json
E TAMBEM: contra o app rodando --
  GET /documents como alice -> HTTP 200
  POST /documents/4/share?email=%27%20UNION%20SELECT%20999999%20--%20 como alice -> HTTP 500
  Artefato: artefatos/http_injection_01.json
CONSERTO SUGERIDO: Trocar o f-string por consulta parametrizada/ORM: db.scalar(select(User.id).where(User.email == email)) ou text("SELECT id FROM users WHERE email = :e"), {"e": email}.

[CRITICA] [alta] security - app/api/app/routers/shares.py:89-93
O QUE: validação de acesso em read_shared_document não valida se quem está lendo é o destinatário da share; só checa se EXISTE uma share, sem validar shared_with_user_id
ARBITRO: Um usuário pode ler um documento compartilhado com ELE; quem não é dono nem destinatário não pode ler (docs/REVIEW_TASK.md:43)
EVIDENCIA: test_terceiro_nao_le_documento.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_injection_03.json
E TAMBEM: contra o app rodando --
  GET /documents como alice -> HTTP 200
  GET /documents como carol -> HTTP 200
  GET /shared/4 como carol -> HTTP 200
  Artefato: artefatos/http_injection_03.json
CONSERTO SUGERIDO: Filtrar o share pelo destinatario, ex. select(Share).where(Share.document_id == doc_id, Share.shared_with_user_id == user.id) (permitindo tambem o proprio dono), retornando 403/404 caso contrario.

[ALTA] [alta] correctness - app/api/app/routers/shares.py:31
O QUE: SQL injection na busca de usuário por email: interpolação direta de parâmetro de usuário em query raw sem prepared statement
ARBITRO: Persistência passa pelos modelos do ORM; não há SQL cru no app (docs/REFERENCE_GUIDE.md:70)
EVIDENCIA: test_share_sql_injection.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_correcao_01.json
E TAMBEM: contra o app rodando --
  GET /documents como demo -> HTTP 200
  POST /documents/1/share?email=x%27%20AND%20%271%27%3D%272 como demo -> HTTP 404
  POST /documents/1/share?email=x%27 como demo -> HTTP 500
  Artefato: artefatos/http_correcao_01.json
CONSERTO SUGERIDO: Usar query parametrizada: text('SELECT id FROM users WHERE email = :email') com bind param, ou o ORM (select(User).where(User.email == email)).

[ALTA] [alta] correctness - app/api/app/routers/shares.py:51-59
O QUE: list_shared_with_me retorna documentos do próprio usuário, viola requisito de não devolver os documentos dele
ARBITRO: GET /shared-with-me retorna o que outros compartilharam com o usuário atual. Não pode devolver os documentos do próprio usuário (docs/REVIEW_TASK.md:45)
EVIDENCIA: test_shared_with_me_nao_lista_proprios.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_correcao_02.json
E TAMBEM: contra o app rodando --
  GET /shared-with-me como alice -> HTTP 200
  GET /documents como alice -> HTTP 200
  Artefato: artefatos/http_correcao_02.json
CONSERTO SUGERIDO: Trocar o WHERE para `Share.shared_with_user_id == user.id` (mantendo o join para obter title/owner_email do documento de terceiros), o que também elimina as linhas duplicadas.

[ALTA] [alta] convention or pattern - app/api/app/routers/shares.py:30
O QUE: SQL cru com string interpolation em vez de ORM ou prepared statements
ARBITRO: Persistência passa pelos modelos do ORM; não há SQL cru no app (docs/REFERENCE_GUIDE.md:70)
EVIDENCIA: contra o app rodando --
  GET /documents como demo -> HTTP 200
  POST /documents/1/share?email=naoexiste_xyz_%40nada.dev como demo -> HTTP 404
  POST /documents/1/share?email=%27%20OR%20%271%27%3D%271 como demo -> HTTP 201
  Artefato: artefatos/http_padroes_01.json
CONSERTO SUGERIDO: Trocar text(f"...email = '{email}'") por query parametrizada, ex. text("SELECT id FROM users WHERE email = :e"), {"e": email}, ou usar o ORM.

[ALTA] [alta] PRD divergence - app/api/app/routers/shares.py:29-34
O QUE: Endpoint de compartilhamento usa SQL cru com string interpolation em vez de ORM, violando convenção de persistência declarada
ARBITRO: Persistência passa pelos modelos do ORM; não há SQL cru no app (docs/REFERENCE_GUIDE.md:70)
EVIDENCIA: test_share_email_not_interpolated.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_prd_01.json
E TAMBEM: contra o app rodando --
  GET /documents como alice -> HTTP 200
  POST /documents/4/share?email=nosuchuser%40hack2l.dev como alice -> HTTP 404
  POST /documents/4/share?email=nosuchuser%40hack2l.dev%27%20AND%20%271%27%3D%271 como alice -> HTTP 404
  POST /documents/4/share?email=%27 como alice -> HTTP 500
  Artefato: artefatos/http_prd_01.json
CONSERTO SUGERIDO: Trocar a consulta por ORM (db.scalar(select(User).where(User.email == email))) ou, no mínimo, por text("... WHERE email = :email") com bind parameter.

[MEDIA] [alta] security - app/api/app/routers/shares.py:54-60
O QUE: query em list_shared_with_me retorna documentos onde Document.owner_id == user.id, mas o resultado é mapeado como shares pertencentes ao usuário logado (inversão de semântica)
ARBITRO: GET /shared-with-me devolve documentos compartilhados COM o usuário atual, não documentos DELE; não pode devolver seus próprios documentos (docs/REVIEW_TASK.md:45)
EVIDENCIA: test_shared_with_me_inversao2.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_injection_02.json
E TAMBEM: contra o app rodando --
  GET /documents como alice -> HTTP 200
  GET /shared-with-me como alice -> HTTP 200
  GET /shared-with-me como carol -> HTTP 200
  Artefato: artefatos/http_injection_02.json
CONSERTO SUGERIDO: Filtrar por Share.shared_with_user_id == user.id (e excluir Document.owner_id == user.id) em list_shared_with_me, retornando os documentos de outros donos compartilhados com o usuário atual.

[MEDIA] [alta] performance - app/api/app/routers/shares.py:54-61
O QUE: list_shared_with_me carrega N shares e depois executa N queries adicionais (db.get para Document, db.get para User) — N+1 em cascata
ARBITRO: nenhum citado
EVIDENCIA: test_shared_with_me_query_count.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_performance_01.json
E TAMBEM: contra o app rodando --
  GET /shared-with-me como demo -> HTTP 200
  Artefato: artefatos/http_performance_01.json
CONSERTO SUGERIDO: Substituir o loop com db.get por um unico SELECT com join/eager load (ex. select(Share, Document, User).join(...).options(selectinload(...))) e montar a resposta a partir do resultado unico.

[MEDIA] [alta] PRD divergence - app/api/app/routers/shares.py:50-80
O QUE: GET /shared-with-me consulta shares onde owner_id == current_user.id, mas requisito pede docs compartilhados COM o usuário, não documentos do próprio usuário
ARBITRO: GET /shared-with-me devolve o que outros compartilharam com o usuário atual, não pode devolver os documentos do próprio usuário (docs/REVIEW_TASK.md:45)
EVIDENCIA: test_shared_with_me_invariante.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_prd_02.json
E TAMBEM: contra o app rodando --
  GET /shared-with-me como demo -> HTTP 200
  GET /shared-with-me como carol -> HTTP 200
  Artefato: artefatos/http_prd_02.json
CONSERTO SUGERIDO: Trocar o filtro para Share.shared_with_user_id == user.id (e opcionalmente excluir Document.owner_id == user.id), retornando os documentos que outros compartilharam com o usuário.

[BAIXA] [alta] convention or pattern - app/api/app/routers/shares.py:18-47
O QUE: endpoint não devolve schema Pydantic declarado; retorna dict literal
ARBITRO: Todo endpoint devolve um schema Pydantic de schemas.py (docs/REFERENCE_GUIDE.md:71)
EVIDENCIA: test_response_model_convention.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_padroes_02.json
E TAMBEM: contra o app rodando --
  GET /shared-with-me como demo -> HTTP 200
  Artefato: artefatos/http_padroes_02.json
CONSERTO SUGERIDO: Adicionar ShareResult/SharedListEntry/SharedDocument em app/schemas.py e declarar response_model nesses tres endpoints (com list[...] onde aplicavel), mantendo lib/types.ts espelhando os schemas.

## DESCARTADOS, COM MOTIVO

_nenhum._

## INCONCLUSIVOS, COM CAUSA

_nenhum._
