"""O parecer como comentario de PR -- a SAIDA que faltava.

O motor esta medido nos dois sentidos e a entrada existe desde 17/08
(`revisa_pr.py <url>`). O parecer, porem, saia no terminal: quem revisa codigo
nao le terminal, entao o trabalho todo -- as suspeitas levantadas, as refutadas
com motivo, as inconclusivas com causa -- morria na tela de quem rodou. Enquanto
isso, o produto era uma demo com copia e cola no meio.

## 🚨 O leitor AQUI e' outro, e isso muda o texto

No terminal quem le e' quem rodou, e sabe o que as palavras significam. No PR
quem le e' o AUTOR, que nunca ouviu falar deste produto.

Medido do jeito mais direto possivel: o proprio dono do projeto, olhando um
parecer com "4 descartados", perguntou se aquilo era boa noticia. Se quem
construiu o Veredito precisa perguntar, o autor de um PR de terceiro nao tem
chance nenhuma -- ele vai ler "4 descartados" como "achou 4 problemas no meu
PR".

Por isso o comentario abre dizendo o que aconteceu em UMA linha, e traz a
legenda das tres palavras. O `CLAUDE.md` ja dizia que as duas listas "precisam
ser enquadradas em voz alta, senao soam como confissao de erro"; aqui elas
precisam ser enquadradas em voz alta OU VIRAM ACUSACAO.

## O resto do que muda em relacao ao terminal

- **teto de 65.536 caracteres** por comentario. A lista de nao-testadas do
  `pallets/flask` sozinha tem 32 itens. Corta, e DIZ que cortou.
- **`<details>`** no que e' longo: o autor ve o veredito primeiro.
- **marca invisivel** para a proxima rodada ATUALIZAR em vez de empilhar. Bot
  que deixa doze comentarios num PR e' bot que o time desliga.
- **silencio proporcional**: rodada sem condenado nao merece 200 linhas. E' a
  licao do alarme do banco -- guarda que fala demais morre igual a que fala de
  menos.
"""

from __future__ import annotations

from . import juiz

# Achada pela rodada seguinte para atualizar este mesmo comentario. Invisivel no
# markdown renderizado, e e' o que impede o bot de empilhar.
MARCA = "<!-- veredito:parecer -->"

# Teto do GitHub para um comentario de issue/PR.
TETO = 65_536

# Folga para o rodape, que e' acrescentado DEPOIS do corte. Sem ela, cortar no
# teto exato e depois somar o rodape estoura -- e o erro so' apareceria contra a
# API, num PR de verdade.
FOLGA_RODAPE = 2_000


def _legenda() -> list[str]:
    """As tres palavras, ditas antes de serem usadas.

    ⚠️ `descartado` explicado com "nao e' um problema no seu PR" de proposito.
    E' a palavra que o leitor mais encontra e a que ele mais provavelmente
    entende ao contrario.
    """
    return [
        "<sub>",
        "**provado** = ha artefato reproduzivel (um teste que passa no commit "
        "base e falha com esta mudanca, ou chamadas HTTP registradas). "
        "**descartado** = a suspeita foi levantada e a verificacao a derrubou "
        "&mdash; nao e' um problema no seu PR, e' ruido que ja foi filtrado. "
        "**inconclusivo** = nao deu para decidir, e a causa esta dita.",
        "</sub>",
        "",
    ]


def _resumo(c: int, d: int, i: int) -> str:
    """Uma linha, e ela e' a unica que muita gente vai ler."""
    if c:
        return (f"**{c} achado(s) com evidencia.** "
                f"Outras {d} suspeita(s) foram verificadas e descartadas; "
                f"{i} ficaram inconclusivas.")
    if d and not i:
        return (f"**Nada a apontar neste PR.** {d} suspeita(s) foram levantadas "
                "e a verificacao derrubou todas.")
    if d or i:
        return (f"**Nenhum achado sustentado por evidencia.** {d} suspeita(s) "
                f"foram descartadas com motivo e {i} ficaram inconclusivas.")
    return "**Nenhuma suspeita chegou a ser verificada nesta rodada.**"


def _detalhes(titulo: str, linhas: list[str], aberto: bool = False) -> list[str]:
    if not linhas:
        return []
    return ["", f"<details{' open' if aberto else ''}>",
            f"<summary>{titulo}</summary>", "", *linhas, "", "</details>"]


def _lista(veredictos: list[dict], acusacoes: dict) -> list[str]:
    fora = []
    for v in veredictos:
        a = acusacoes.get(v["id"], {})
        rotulo = juiz._CATEGORIA_DO_DESAFIO.get(a.get("categoria"),
                                                a.get("categoria", "?"))
        fora.append(f"- **{rotulo}** em `{juiz._local(a)}`  \n  {v.get('motivo', '-')}")
    return fora


def _rodape(meta: dict) -> list[str]:
    """Quem rodou, sobre qual commit, a que custo.

    Auditabilidade no lugar onde a decisao acontece -- nao num log que so' nos
    temos.
    """
    partes = []
    if meta.get("head"):
        partes.append(f"commit `{str(meta['head'])[:7]}`")
    if meta.get("base"):
        partes.append(f"base `{str(meta['base'])[:7]}`")
    if meta.get("segundos"):
        partes.append(f"{float(meta['segundos']):.0f}s")
    if meta.get("rodada"):
        partes.append(f"rodada `{meta['rodada']}`")
    linha = " &middot; ".join(partes) if partes else "sem metadados da rodada"
    return ["", "---", "",
            "<sub><b>Veredito</b> &mdash; cada suspeita e' tratada como "
            "acusacao, e nada vira parecer sem prova reproduzivel. "
            f"{linha}</sub>"]


def corta(corpo: str, teto: int) -> tuple[str, bool]:
    """Corta no limite do GitHub, e DIZ que cortou.

    🚫 Nunca em silencio: comentario truncado sem aviso le como parecer
    completo, e a primeira coisa a sumir e' justamente a lista de suspeitas NAO
    TESTADAS -- ou seja, o leitor concluiria que o Veredito examinou tudo. E'
    a mesma familia do `limpo` mudo de 15/08.
    """
    if len(corpo) <= teto:
        return corpo, False
    aviso = ("\n\n> [!WARNING]\n> **Comentario truncado** no limite de "
             f"{teto:,} caracteres do GitHub. O parecer completo esta nos "
             "artefatos da rodada.")
    # ⚠️ Teto menor que o proprio aviso so' acontece em teste -- e e' justamente
    # por isso que precisa estar certo: guarda vista respeitar o limite apenas
    # no tamanho de producao nunca foi vista respeitando limite nenhum.
    #
    # 🚫 E as DUAS metades do contrato valem ao mesmo tempo. A primeira tentativa
    # deste ramo cabia no teto CALANDO o aviso, e o teste pegou: comentario
    # truncado em silencio le como parecer completo, que e' o defeito inteiro.
    # Por isso o aviso curto, que cabe em qualquer teto util.
    curto = "\n\n**[truncado no limite do GitHub]**"
    escolhido = aviso if len(aviso) < teto else curto
    if len(escolhido) >= teto:
        return escolhido[:teto], True
    return corpo[:teto - len(escolhido)] + escolhido, True


def monta(organizado: dict, acusacoes: dict, artefatos: dict,
          http: dict | None = None, escopo: dict | None = None,
          meta: dict | None = None) -> str:
    """O corpo do comentario, em markdown do GitHub."""
    http, meta = http or {}, meta or {}
    c = organizado["condenados"]
    d = organizado["descartados"]
    i = organizado["inconclusivos"]
    levantadas = (escopo or {}).get("levantadas")

    p: list[str] = [MARCA, "", "## Veredito", ""]
    p += [_resumo(len(c), len(d), len(i)), ""]
    p += _legenda()

    if levantadas:
        p += [f"<sub>{levantadas} suspeita(s) levantadas, "
              f"{len(c) + len(d) + len(i)} verificadas dentro do orcamento "
              "desta rodada.</sub>", ""]

    # Condenados ABERTOS e por extenso: e' o que o autor precisa agir.
    for v in c:
        p += [juiz._bloco(v, acusacoes.get(v["id"], {}), artefatos.get(v["id"]),
                          http.get(v["id"])), ""]

    # E o resto colapsado. Presente, nunca omitido -- as duas listas sao a peca
    # que o produto tem e ninguem mais tem -- mas sem competir com o achado.
    p += _detalhes(f"{len(d)} suspeita(s) verificadas e descartadas, com motivo",
                   _lista(d, acusacoes))
    p += _detalhes(f"{len(i)} inconclusiva(s), com a causa",
                   _lista(i, acusacoes))

    nao_testadas = juiz._secao_nao_testadas(escopo)
    if nao_testadas:
        # Sem o cabecalho `##` do parecer de terminal: dentro do <details> ele
        # viraria um titulo solto no meio do comentario.
        corpo = [l for l in nao_testadas if l.strip() and not l.startswith("## ")]
        p += _detalhes("Levantadas e nao testadas (fora do orcamento da rodada)",
                       corpo)

    banco = juiz._secao_efeito_no_banco()
    if banco:
        p += _detalhes("Efeito no banco do app",
                       [l for l in banco if l.strip() and not l.startswith("## ")])

    corpo, _ = corta("\n".join(p), TETO - FOLGA_RODAPE)
    return corpo + "\n".join(_rodape(meta)) + "\n"


def do_disco(meta: dict | None = None) -> str:
    """Monta o comentario a partir do que a rodada gravou.

    Mesma disciplina do juiz: ajustar o formato do comentario pela trigesima vez
    nao pode re-executar o advogado nem gastar API.
    """
    veredictos, acusacoes, artefatos, avisos, http, escopo = juiz.carrega_do_disco()
    organizado = juiz.organiza(veredictos, acusacoes, artefatos, avisos, http)
    return monta(organizado, acusacoes, artefatos, http, escopo, meta)
