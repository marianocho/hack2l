# PARECER

8 com parecer, 0 descartados com motivo, 2 inconclusivos com causa.

## CONDENADOS

[CRITICA] [alta] security - app/api/app/routers/shares.py:30
O QUE: email do usuário é interpolado diretamente em SQL cru sem parametrização, abrindo brecha para SQL injection
ARBITRO: Persistência passa pelos modelos do ORM; não há SQL cru no app (docs/REFERENCE_GUIDE.md:70)
EVIDENCIA: test_share_email_sql_injection.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_injection_01.json
E TAMBEM: contra o app rodando --
  GET /documents como alice -> HTTP 200
  GET /documents como carol -> HTTP 200
  POST /documents/4/share?email=nobody%40x.dev%27%20OR%20%271%27%3D%271 como alice -> HTTP 201
  POST /documents/4/share?email=nobody%40x.dev como alice -> HTTP 404
  Artefato: artefatos/http_injection_01.json
CONSERTO SUGERIDO: Trocar a interpolação por consulta parametrizada/ORM, ex. `db.scalar(select(User).where(User.email == email))` ou `text("SELECT id FROM users WHERE email = :e"), {"e": email}`.

[CRITICA] [alta] security - app/api/app/routers/shares.py:82-92
O QUE: endpoint /shared/{doc_id} não valida se o documento foi compartilhado especificamente COM o usuário atual; query SELECT Share retorna qualquer share do documento, sem filtrar por shared_with_user_id
ARBITRO: Um usuário pode ler um documento que tem sido compartilhado com ele. Quem não é dono nem destinatário não pode ler o documento (docs/REVIEW_TASK.md:43)
EVIDENCIA: test_shared_third_party_leak.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_injection_03.json
E TAMBEM: contra o app rodando --
  GET /documents como alice -> HTTP 200
  GET /documents como bob -> HTTP 200
  POST /documents/4/share?email=bob@hack2l.dev como alice -> HTTP 201
  GET /shared/4 como carol -> HTTP 200
  Artefato: artefatos/http_injection_03.json
CONSERTO SUGERIDO: Filtrar a consulta por destinatário: select(Share).where(Share.document_id == doc_id, Share.shared_with_user_id == user.id) (permitindo também o dono), retornando 403/404 caso contrário.

[ALTA] [alta] correctness - app/api/app/routers/shares.py:54-60
O QUE: list_shared_with_me retorna documentos do próprio usuário, viola requisito 3
ARBITRO: GET /shared-with-me devolve o que outros compartilharam com o usuário atual. Não pode devolver os documentos do próprio usuário (docs/REVIEW_TASK.md:45)
EVIDENCIA: test_shared_with_me_nao_lista_proprios.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_correcao_02.json
E TAMBEM: contra o app rodando --
  GET /documents como demo -> HTTP 200
  GET /shared-with-me como demo -> HTTP 200
  Artefato: artefatos/http_correcao_02.json
CONSERTO SUGERIDO: Trocar o filtro da query para .where(Share.shared_with_user_id == user.id) (juntando Document apenas para título/dono), garantindo que só apareçam documentos de outros donos compartilhados com o usuário atual.

[MEDIA] [alta] security - app/api/app/routers/shares.py:56-60
O QUE: query no endpoint /shared-with-me filtra por Document.owner_id == user.id, mas retorna Share records que o usuário controla; se documento for compartilhado COM o usuário, ele não é owner, então logica inverte o que deveria retornar
ARBITRO: Um usuário pode ler um documento compartilhado com ele. GET /shared-with-me devolve o que outros compartilharam com o usuário atual. Não pode devolver os documentos do próprio usuário (docs/REVIEW_TASK.md:43,45)
EVIDENCIA: test_shared_with_me_inversion.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_injection_02.json
E TAMBEM: contra o app rodando --
  (+1 chamada(s) antes, no artefato)
  GET /shared-with-me como carol -> HTTP 200
  POST /documents/4/share?email=carol@hack2l.dev como alice -> HTTP 201
  GET /shared-with-me como carol -> HTTP 200
  GET /shared-with-me como alice -> HTTP 200
  Artefato: artefatos/http_injection_02.json
CONSERTO SUGERIDO: Filtrar por Share.shared_with_user_id == user.id (e excluir Document.owner_id == user.id), retornando os documentos que outros compartilharam com o usuario atual.

[MEDIA] [alta] performance - app/api/app/routers/shares.py:53-61
O QUE: list_shared_with_me executa N+2 queries adicionais (uma por share para buscar Document, outra para buscar User) em lugar de um join com prefetch
ARBITRO: nenhum citado
EVIDENCIA: test_shared_with_me_query_count.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_performance_01.json
E TAMBEM: contra o app rodando --
  GET /shared-with-me como demo -> HTTP 200
  Artefato: artefatos/http_performance_01.json
CONSERTO SUGERIDO: Trocar o loop por uma única consulta com join/selectinload, ex. select(Share, Document, User).join(Document, Share.document_id==Document.id).join(User, Document.owner_id==User.id), montando os resultados a partir dessa linha única.

[MEDIA] [alta] PRD divergence - app/api/app/routers/shares.py:23-47
O QUE: share_document não devolve schema Pydantic, apenas dict, violando convenção
ARBITRO: Todo endpoint devolve um schema Pydantic de schemas.py (docs/REFERENCE_GUIDE.md:71)
EVIDENCIA: test_response_model_convention.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_prd_02.json
E TAMBEM: contra o app rodando --
  POST /documents/1/share?email=carol@hack2l.dev como demo -> HTTP 201
  Artefato: artefatos/http_prd_02.json
CONSERTO SUGERIDO: Adicionar ShareResult (document_id, shared_with_email, title), SharedListEntry e SharedDocument em schemas.py e declará-los como response_model nos três endpoints de shares.py, preenchendo email e título na resposta do share.

[BAIXA] [alta] convention or pattern - app/api/app/routers/shares.py:37
O QUE: SQL cru em query de contagem em vez de usar ORM, violando convenção de persistência
ARBITRO: Persistência passa pelos modelos do ORM; não há SQL cru no app (docs/REFERENCE_GUIDE.md:70)
EVIDENCIA: test_no_raw_sql_in_routers.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_padroes_02.json
CONSERTO SUGERIDO: Trocar o COUNT cru por consulta ORM, ex. db.scalar(select(func.count()).select_from(Share).where(Share.document_id == doc_id, Share.shared_with_user_id == recipient_id)), e igualmente resolver o usuário por select(User).where(User.email == email).

[BAIXA] [alta] convention or pattern - app/api/app/routers/shares.py:44
O QUE: lê MAX_SHARES_PER_DOC diretamente de os.getenv em vez de usar módulo de configuração
ARBITRO: Configuração se lê só por settings em config.py, nunca os.getenv solto (docs/REFERENCE_GUIDE.md:69)
EVIDENCIA: test_config_centralizada.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_padroes_03.json
CONSERTO SUGERIDO: Declarar max_shares_per_doc em Settings (app/config.py) e usar settings.max_shares_per_doc em shares.py — ou remover a linha, já que o limite não é aplicado em lugar nenhum.

## DESCARTADOS, COM MOTIVO

_nenhum._

## INCONCLUSIVOS, COM CAUSA

- correctness em app/api/app/routers/shares.py:32: recusa do classificador | categoria cyber | nenhum dos tres sinais de fallback apareceu (servido por claude-opus-5) -- nao da' para afirmar se a cadeia recusou ou se o fallback nao chegou a ser tentado
- PRD divergence em app/api/app/routers/shares.py:29: recusa do classificador | categoria cyber | nenhum dos tres sinais de fallback apareceu (servido por claude-opus-5) -- nao da' para afirmar se a cadeia recusou ou se o fallback nao chegou a ser tentado
