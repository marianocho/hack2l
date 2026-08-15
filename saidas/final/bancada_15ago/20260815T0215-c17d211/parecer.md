# PARECER

3 com parecer, 0 descartados com motivo, 0 inconclusivos com causa.

## CONDENADOS

[ALTA] [alta] correctness - app/main.py:103
O QUE: Remoção da verificação de projeto visível permite qualquer usuário autenticado ler qualquer tarefa apenas conhecendo o ID, violando isolamento de projeto
ARBITRO: Ler uma tarefa exige poder ver o projeto a que ela pertence. O identificador da tarefa não é segredo: adivinhar o número não pode dar acesso. (docs/REGRAS.md:Acesso e isolamento)
EVIDENCIA: test_isolamento_tarefa.py passa em 93f69d1 e falha em c17d211 (exit 0 -> 1). Artefato: artefatos/prova_correcao_01.json
E TAMBEM: contra o app rodando --
  GET /projects como davi -> HTTP 200
  GET /tasks/1 como davi -> HTTP 200
  Artefato: artefatos/http_correcao_01.json
CONSERTO SUGERIDO: Restaurar a verificacao de autorizacao em le_tarefa: `if t is None or t.project_id not in _projetos_visiveis(db, user): raise HTTPException(404)`, e resolver o caso do link compartilhado com convite/token explicito em vez de id adivinhavel.

[ALTA] [alta] correctness - app/main.py:103
O QUE: Condição `t is None` deixa passar quando tarefa existe mas projeto foi deletado ou user foi removido do projeto após ter link aberto, criando estado inconsistente
ARBITRO: Um usuário vê um projeto se for o dono dele ou se participar dele. Quem não é dono nem participante não vê o projeto, nem as tarefas dele. (docs/REGRAS.md:Acesso e isolamento)
EVIDENCIA: test_isolamento_tarefa.py passa em 93f69d1 e falha em c17d211 (exit 0 -> 1). Artefato: artefatos/prova_correcao_03.json
E TAMBEM: contra o app rodando --
  GET /tasks/1 como davi -> HTTP 200
  Artefato: artefatos/http_correcao_03.json
CONSERTO SUGERIDO: Restaurar a condicao `if t is None or t.project_id not in _projetos_visiveis(db, user)` em app/main.py:103, mantendo 404 para quem nao ve o projeto.

[ALTA] [alta] security - app/main.py:104
O QUE: remoção da verificação de visibilidade de projeto permite que usuário autenticado acesse tarefa de projeto ao qual não pertence, se adivinhar ou receber o task_id; conteúdo da tarefa (titulo, detalhe) vaza para quem não deveria ver
ARBITRO: Ler uma tarefa exige poder ver o projeto a que ela pertence. O identificador da tarefa não é segredo: adivinhar o número não pode dar acesso. (docs/REGRAS.md)
EVIDENCIA: test_isolamento_tarefa.py passa em 93f69d1 e falha em c17d211 (exit 0 -> 1). Artefato: artefatos/prova_injection_01.json
E TAMBEM: contra o app rodando --
  GET /tasks/1 como clara -> HTTP 200
  GET /projects como clara -> HTTP 200
  Artefato: artefatos/http_injection_01.json
CONSERTO SUGERIDO: Restaurar a checagem `t.project_id not in _projetos_visiveis(db, user)` em le_tarefa, devolvendo 404 para quem nao ve o projeto da tarefa.

## DESCARTADOS, COM MOTIVO

_nenhum._

## INCONCLUSIVOS, COM CAUSA

_nenhum._
