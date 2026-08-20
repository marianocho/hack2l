"""O que a PESSOA escreve no PR nao atravessa para o modelo. E isso e' um canal.

🚨 POR QUE ISTO VIROU TRAVA, e nao ficou sendo so' uma propriedade feliz.

O repositorio de demonstracao precisa de um lugar onde o gabarito seja visivel
para o LEITOR HUMANO e invisivel para o agente. Se o gabarito mora na arvore
(`README`, comentario no codigo), o advogado tem `read_file` e chega nele -- e
a rodada pareceria excelente pelo pior motivo possivel. E' a mesma regra que
mantem o `bancada_gabarito.yml` fora do repositorio da bancada.

Conferido em 20/08: `entrada.resolve` captura `titulo` e `descricao` do PR, e
**nenhum dos dois** e' consumido por qualquer coisa que monte prompt. O `titulo`
so' vai para um `print`; a `descricao` nao vai a lugar nenhum. A fronteira e
estreita e explicita: o que atravessa para o orquestrador e' o que
`entrada.ambiente(info)` devolve, e o orquestrador roda em subprocesso que
herda exatamente isso mais os worktrees.

Entao a DESCRICAO DO PR e' o canal humano do repositorio de demonstracao.

⚠️ Uma propriedade da qual a honestidade da demo depende, e que nada segura,
regride em silencio -- e o sintoma seria uma demo que acerta demais. Por isso a
trava. Ver "toda guarda precisa ser vista FALHANDO" no CLAUDE.md: as mutacoes
que matam cada asserção estao no rodape deste arquivo.
"""
from __future__ import annotations

from veredito import entrada

# Improvavel de aparecer por acaso, e reconhecivel se aparecer.
CANARIO = "CANARIO-GABARITO-NAO-DEVE-VAZAR-7f3a1c"


def _info(**troca) -> dict:
    """Um `info` com a forma que `entrada.resolve` devolve."""
    base = {
        "url": "https://github.com/dono/repo/pull/1",
        "repo": "dono/repo",
        "numero": 1,
        "titulo": "abrir tarefa pelo link",
        "descricao": "texto qualquer do corpo do PR",
        "arquivos": 1, "adicoes": 11, "remocoes": 1,
        "base_do_ramo": "a" * 40,
        "merge_base": "b" * 40,
        "head": "c" * 40,
        "base_deslocou": False,
        "repo_local": r"C:\tmp\clone",
        "worktrees": r"C:\tmp\worktrees",
    }
    base.update(troca)
    return base


def _achatado(d: dict) -> str:
    return "\n".join(f"{k}={v}" for k, v in d.items())


def test_a_descricao_do_PR_nao_atravessa_a_fronteira():
    """O corpo do PR nao entra no ambiente que o orquestrador herda."""
    amb = entrada.ambiente(_info(descricao=f"O defeito esta em {CANARIO}"))
    assert CANARIO not in _achatado(amb), (
        "a descricao do PR atravessou para o ambiente do orquestrador -- "
        "quem escreve o PR passa a escrever no prompt")


def test_o_titulo_do_PR_tambem_nao():
    """Mesmo canal, mesma exigencia: o titulo e' texto de quem abriu o PR."""
    amb = entrada.ambiente(_info(titulo=f"corrige {CANARIO}"))
    assert CANARIO not in _achatado(amb)


def test_a_trava_CONSEGUE_ver_um_valor_que_atravessa():
    """🚨 Sem isto, `ambiente` devolvendo `{}` deixaria tudo acima verde.

    Trava que nao sabe enxergar valor nenhum passa por qualquer implementacao,
    inclusive a quebrada. Esta prova que o canario SERIA encontrado se ele
    estivesse num campo que de fato cruza a fronteira.
    """
    amb = entrada.ambiente(_info(head=CANARIO))
    assert CANARIO in _achatado(amb), (
        "o canario num campo que ATRAVESSA nao foi encontrado -- as outras "
        "assercoes deste arquivo nao estao medindo nada")


def test_a_fronteira_e_exatamente_estas_chaves():
    """O conjunto e' fechado, e crescer nele e' uma decisao, nao um acidente.

    ⚠️ Esta asserção e' de IGUALDADE, nao de continencia. Chave nova que
    carregue texto de quem abriu o PR reabriria o canal sem que as outras tres
    percebessem -- elas so' procuram o canario nos campos que o teste conhece.
    """
    amb = entrada.ambiente(_info())
    assert set(amb) == {
        "CHALLENGE_REPO", "PR_BRANCH", "BASE_BRANCH",
        "WORKTREES_DIR", "BASE_JA_RESOLVIDO",
    }, ("a fronteira entrada->orquestrador mudou. Se a chave nova carrega texto "
        "escrito por quem abriu o PR, o canal humano da demo deixou de existir.")


# --- MAPA DE MUTACOES -------------------------------------------------------
#
# Rodadas em 20/08 por `scripts/mutacao_fronteira_do_pr.py`, cada uma injetada
# sozinha em `veredito/entrada.py::ambiente`. Nao e' tabela escrita de cabeca:
# e' a saida do arnes.
#
#   | injetada                                      | matou                      |
#   |-----------------------------------------------|----------------------------|
#   | `"PR_DESCRICAO": info["descricao"]` (chave nova) | _descricao_ + _chaves_  |
#   | `"PR_TITULO": info["titulo"]` (chave nova)       | _titulo_ + _chaves_     |
#   | `return {}`                                      | _CONSEGUE_ver_ + _chaves_ |
#   | descricao concatenada DENTRO de CHALLENGE_REPO   | **so' _descricao_**     |
#
# 🚨 A QUARTA E' A QUE PROVA QUE ESTE ARQUIVO NAO E' REDUNDANTE. As tres
# primeiras tambem morrem em `_chaves_`, entao daria para achar que a igualdade
# de chaves sozinha bastava. Nao basta: no vazamento realista -- concatenacao
# distraida dentro de uma chave que ja existe -- o conjunto de chaves fica
# IDENTICO, e so' a busca pelo canario ve. Uma mata quatro assercoes; a outra
# mata uma. E' a diferenca entre trava larga e trava que discrimina.
#
# ⚠️ A terceira existe pelo motivo inverso: sem `_CONSEGUE_ver_`, um `return {}`
# deixaria as buscas pelo canario todas verdes -- teste que nao consegue
# enxergar valor nenhum passa por qualquer implementacao, inclusive a quebrada.
