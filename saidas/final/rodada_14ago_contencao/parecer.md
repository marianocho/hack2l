# PARECER

4 com parecer, 1 descartados com motivo, 1 inconclusivos com causa.

## CONDENADOS

[CRITICA] [alta] security - app/api/app/routers/shares.py:84-95
O QUE: endpoint GET /shared/{doc_id} valida apenas se um share existe para qualquer usuário do documento, não se o share é para o usuário atual; terceiro usuário C consegue ler documento compartilhado entre A e B
ARBITRO: Um usuário pode ler um documento compartilhado com ele. Quem não é dono nem destinatário não pode ler (docs/REVIEW_TASK.md:43)
EVIDENCIA: contra o app rodando --
  GET /documents como alice -> HTTP 200
  POST /documents/4/share?email=bob@hack2l.dev como alice -> HTTP 201
  GET /shared/4 como carol -> HTTP 200
  Artefato: artefatos/http_injection_03.json
CONSERTO SUGERIDO: Filtrar o select por Share.shared_with_user_id == user.id (ou dono) em read_shared_document, retornando 403/404 caso contrario.

[ALTA] [alta] correctness - app/api/app/routers/shares.py:31
O QUE: SQL injection no lookup de email: string não é escapada, permite extrair ou modificar dados via email = 'admin@x.com' OR '1'='1
ARBITRO: Persistência passa pelos modelos do ORM; não há SQL cru no app (docs/REFERENCE_GUIDE.md:70)
CORROBORADO POR: bandit (analise estatica de seguranca) em app/api/app/routers/shares.py:31 -- "Possible SQL injection vector through string-based query construction."
CORROBORADO POR: semgrep (analise de fluxo / taint) em app/api/app/routers/shares.py:31 -- "O parametro email, controlado pelo cliente na rota share_document, alcanca db.execute() por um caminho que nao"
EVIDENCIA: contra o app rodando --
  POST /documents/1/share?email=x%40x.com'%20OR%20'1'%3D'1 como demo -> HTTP 201
  Artefato: artefatos/http_correcao_01.json
CONSERTO SUGERIDO: Usar parâmetro bindado (text("...WHERE email = :e"), {"e": email}) ou o ORM em vez de interpolar a string diretamente no SQL

[ALTA] [alta] security - app/api/app/routers/shares.py:30
O QUE: email do usuário é concatenado diretamente em SQL cru sem parametrização; usuário malicioso pode injetar SQL no campo email
ARBITRO: Persistência passa pelos modelos do ORM; não há SQL cru no app (docs/REFERENCE_GUIDE.md:70)
CORROBORADO POR: bandit (analise estatica de seguranca) em app/api/app/routers/shares.py:31 -- "Possible SQL injection vector through string-based query construction."
CORROBORADO POR: semgrep (analise de fluxo / taint) em app/api/app/routers/shares.py:31 -- "O parametro email, controlado pelo cliente na rota share_document, alcanca db.execute() por um caminho que nao"
EVIDENCIA: contra o app rodando --
  POST /documents/1/share?email=nao-existe%40x.dev%27%20OR%20%271%27%3D%271 como demo -> HTTP 201
  POST /documents/1/share?email=nao-existe%40x.dev como demo -> HTTP 404
  Artefato: artefatos/http_injection_01.json
CONSERTO SUGERIDO: Trocar o f-string por consulta parametrizada/ORM: db.scalar(select(User).where(User.email == email)).

[BAIXA] [alta] convention or pattern - app/api/app/routers/shares.py:17
O QUE: endpoint novo não devolve schema Pydantic declarado em schemas.py
ARBITRO: Todo endpoint devolve um schema Pydantic de schemas.py (docs/REFERENCE_GUIDE.md:71)
EVIDENCIA: nao fechou. grep confirma que todos os endpoints pre-existentes (auth.py:14,26; chat.py:26; documents.py:23,43,52) declaram response_model com schemas de schemas.py, enquanto os tres endpoints novos em shares.py (POST /documents/{doc_id}/share, GET /shared-with-me, GET /shared/{doc_id}) nao declaram response_model algum e devolvem dicts literais, violando a regra de docs/REFERENCE_GUIDE.md:71; nenhum schema de share existe em schemas.py.
CONSERTO SUGERIDO: Adicionar ShareOut/SharedListEntry/SharedDocumentOut em schemas.py e declarar response_model nos tres endpoints de shares.py (aproveitando para incluir email do destinatario e titulo do documento, como pede o PRD).

## DESCARTADOS, COM MOTIVO

- security em app/api/app/routers/shares.py:54-60: GET /shared-with-me como carol (controle negativo, sem documentos) devolveu 200 [] — nenhum titulo ou email de terceiros vazou; como demo devolveu apenas o proprio documento (owner_email demo@hack2l.dev), pois o filtro e' Document.owner_id == user.id: o defeito real e' o filtro invertido (lista os proprios docs em vez dos compartilhados comigo, com duplicatas/position redundante), uma divergencia de PRD/correctness, nao vazamento nem injection como acusado.

## INCONCLUSIVOS, COM CAUSA

- correctness em app/api/app/routers/shares.py:36-40: A duplicidade so ocorreria sob concorrencia real (duas transacoes simultaneas passando pelo COUNT(*)==0 antes do INSERT); as ferramentas disponiveis (http_request sequencial e prova_diferencial em um unico processo/sessao contra kb_test) nao permitem produzir um artefato deterministico e reproduzivel dessa janela, e chamadas sequenciais sao de fato idempotentes, entao a acusacao nao foi nem confirmada nem derrubada por experimento.
