# PARECER

2 com parecer, 1 descartados com motivo, 0 inconclusivos com causa.

## CONDENADOS

[MEDIA] [alta] correctness - app/main.py:119
O QUE: A query usa select(Member.user_id) mas depois faz len(set(atuais)) para contar únicos; se houver duplicatas na tabela (agora permitidas após remover UniqueConstraint), o set mascarará a inconsistência e a contagem será incorreta
ARBITRO: Adicionar um membro que já participa é idempotente: repetir a chamada não cria linha duplicada (docs/REGRAS.md (Persistência))
EVIDENCIA: test_unicidade_membro.py passa em 93f69d1 e falha em 2a44231 (exit 0 -> 1). Artefato: artefatos/prova_correcao_02.json
CONSERTO SUGERIDO: Restaurar __table_args__ = (UniqueConstraint("project_id", "user_id"),) em Member (com migracao que limpe duplicatas) e, se a reconvite era o problema, resolver com remocao explicita da linha ou coluna de estado, nao removendo a restricao.

[BAIXA] [alta] convention or pattern - app/main.py:126
O QUE: resposta do endpoint adiciona campo novo 'convidado_por' ao contrato declarado, violando o contrato de saída
ARBITRO: todo endpoint declara um modelo de resposta e devolve apenas os campos desse modelo (docs/REGRAS.md)
EVIDENCIA: test_contrato_resposta_membros.py passa em 93f69d1 e falha em 2a44231 (exit 0 -> 1). Artefato: artefatos/prova_padroes_01.json
CONSERTO SUGERIDO: Declarar um response_model (ex. MembroOut com project_id, user_id, novo) na rota e nao devolver o email do dono, ou incluir 'convidado_por' explicitamente no modelo se ele fizer parte do contrato acordado.

## DESCARTADOS, COM MOTIVO

- correctness em app/main.py:125-127: O cenario do provado_se e' impossivel: a FK projects.dono_id -> users.id rejeita tanto inserir projeto com dono inexistente quanto apagar o dono de um projeto (IntegrityError comprovado), e o endpoint so' chega na linha `dono = ...` depois de exigir p.dono_id == user.id, ou seja, o dono e' o proprio autenticado que acabou de ser carregado do banco; o teste test_dono_ausente_refuta.py passa identico no base e no head, e a primeira tentativa de reproduzir o AttributeError nem conseguiu criar o projeto orfao.

## INCONCLUSIVOS, COM CAUSA

_nenhum._
