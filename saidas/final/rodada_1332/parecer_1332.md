# PARECER

1 com parecer, 0 descartados com motivo, 0 inconclusivos com causa.

## CONDENADOS

[CRITICA] [media] security - app/api/app/routers/
O QUE: um usuario consegue alcancar documento que nao e' dele
ARBITRO: INV-ISOLAMENTO
EVIDENCIA: test_isolamento_terceiro_usuario.py passa em 32a5241 e falha em 1dd2e5c (exit 0 -> 1). Artefato: artefatos/prova_bancada_isolamento.json
E TAMBEM: contra o app rodando --
  GET /documents como alice -> HTTP 200
  GET /documents como carol -> HTTP 200
  POST /documents/4/share?email=bob@hack2l.dev como alice -> HTTP 201
  GET /shared/4 como carol -> HTTP 200
  Artefato: artefatos/http_bancada_isolamento.json
CONSERTO SUGERIDO: Filtrar o share pelo destinatario, ex. select(Share).where(Share.document_id == doc_id, Share.shared_with_user_id == user.id) (permitindo tambem o dono), e corrigir /shared-with-me que filtra por Document.owner_id == user.id em vez de Share.shared_with_user_id == user.id.

## DESCARTADOS, COM MOTIVO

_nenhum._

## INCONCLUSIVOS, COM CAUSA

_nenhum._
