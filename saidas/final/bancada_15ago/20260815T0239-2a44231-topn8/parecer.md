# PARECER

4 com parecer, 4 descartados com motivo, 0 inconclusivos com causa.

## CONDENADOS

[MEDIA] [alta] correctness - app/main.py:118-121
O QUE: Race condition: verificação de limite com `len(set(atuais))` e insert de Member não são atômicos; duas requisições simultâneas podem passar ambas pela contagem, inserir duas linhas quando limite é 50
ARBITRO: Adicionar um membro que já participa é idempotente: repetir a chamada não cria linha duplicada nem devolve erro (docs/REGRAS.md:Persistência)
EVIDENCIA: test_membro_unico.py passa em 93f69d1 e falha em 2a44231 (exit 0 -> 1). Artefato: artefatos/prova_correcao_02.json
CONSERTO SUGERIDO: Restaurar UniqueConstraint('project_id','user_id') em Member (usando ON CONFLICT DO NOTHING / tratando IntegrityError como 'novo: False') ou marcar saida com coluna de status em vez de apagar a restricao.

[MEDIA] [alta] convention or pattern - app/models.py:34-40
O QUE: remoção de UniqueConstraint permite inserir duplicatas (project_id, user_id); comentário afirma que o endpoint confere, mas confere apenas ja_is_not_none (presença), não ausência após saída
ARBITRO: adicionar um membro que já participa é idempotente: repetir a chamada não cria linha duplicada (docs/REGRAS.md)
EVIDENCIA: test_membro_duplicado.py passa em 93f69d1 e falha em 2a44231 (exit 0 -> 1). Artefato: artefatos/prova_padroes_04.json
CONSERTO SUGERIDO: Restaurar __table_args__ = (UniqueConstraint("project_id", "user_id"),) em Member (com migracao que limpe duplicatas) e, se o caso de reconvite importa, tratar saida com remocao da linha ou um campo de status em vez de abrir mao da restricao.

[BAIXA] [alta] convention or pattern - app/main.py:128
O QUE: resposta do endpoint adiciona novo campo 'convidado_por' ao dict, divergindo do contrato declarado
ARBITRO: todo endpoint declara um modelo de resposta e devolve apenas os campos desse modelo (docs/REGRAS.md)
EVIDENCIA: test_contrato_resposta_membro.py passa em 93f69d1 e falha em 2a44231 (exit 0 -> 1). Artefato: artefatos/prova_padroes_01.json
CONSERTO SUGERIDO: Declarar um response_model (ex. MembroOut com project_id, user_id, novo) no endpoint e remover o campo 'convidado_por' da resposta, ou incluir a origem apenas em um modelo explicitamente versionado.

[BAIXA] [alta] performance - app/main.py:121-122
O QUE: A query que valida o teto de membros carrega todos os user_id sem filtro de distinção no banco, depois deduplica em memória com set() — em um projeto com 49 membros, traz 49 registros desnecessariamente
ARBITRO: nenhum citado
EVIDENCIA: test_teto_membros_varre_tabela.py passa em 93f69d1 e falha em 2a44231 (exit 0 -> 1). Artefato: artefatos/prova_performance_01.json
CONSERTO SUGERIDO: Trocar a leitura por uma agregacao no banco, ex. db.scalar(select(func.count(func.distinct(Member.user_id))).where(Member.project_id == project_id)) >= LIMITE_DE_MEMBROS.

## DESCARTADOS, COM MOTIVO

- correctness em app/main.py:119-120: Pela API rodando, POST /projects/1/members?email=davi como ana devolveu 201 {"convidado_por":"ana@bancada.dev"} — a variavel `dono` E' usada (alimenta o campo da resposta) e o valor esta correto; o dado nao 'se perde' porque convidado_por e' derivado de Project.dono_id, sempre recuperavel via GET /projects (dono_email), e a unica discrepancia observada (a segunda chamada, ramo idempotente, responde {"novo":false} sem convidado_por) e' cosmetica e nao causa perda de informacao nem comportamento incorreto; alem disso a 'origem do convite' tambem nao existia no commit base, entao nao ha regressao a provar.
- PRD divergence em app/main.py:124-126: A variavel `dono` NAO fica sem uso: ela alimenta o campo `convidado_por` da resposta (app/main.py:133), e o arbitro citado (docs/REGRAS.md, secoes Persistencia e Respostas) nao promete em lugar nenhum persistir quem convidou -- exige apenas ORM parametrizado, idempotencia e nao vazamento de dado interno; a chamada real POST /projects/2/members?email=davi@bancada.dev como ana devolveu 201 {"convidado_por":"ana@bancada.dev"}, ou seja, o email devolvido e' o do proprio chamador (so' o dono pode invocar a rota, main.py:106), portanto nao ha dado de terceiro exposto nem regressao de comportamento em relacao ao base, onde o campo simplesmente nao existia.
- PRD divergence em app/main.py:119-121: O teste diferencial (49 membros distintos + alvo, remoção da linha do alvo e reconvite) passa tanto no base quanto no head: a contagem usa len(set(atuais)), que deduplica, e a linha de quem saiu deixa de existir ao ser removida, então o teto de 50 não bloqueia a reconvocação; o convite repetido continua idempotente (201 com novo=False, sem linha duplicada).
- security em app/main.py:125: O endpoint POST /projects/{id}/members so' executa para o DONO do projeto (nao-dono e anonimo recebem 404/401 antes de qualquer consulta), logo 'convidado_por' devolve o email do proprio chamador; o teste diferencial (nao-dono nao ve o email do dono, dono so' ve o proprio) passa identico no base e no head, e o email do dono ja era publico para quem enxerga o projeto via GET /projects (dono_email).

## INCONCLUSIVOS, COM CAUSA

_nenhum._
