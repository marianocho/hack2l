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

from . import fusao
from . import superficie
from . import prova_de_fusao as pfus
from . import segredo
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
        "**provado** = há artefato reproduzível (um teste que passa no commit "
        "base e falha com esta mudança, ou chamadas HTTP registradas). "
        "**descartado** = a suspeita foi levantada e a verificação a derrubou "
        "&mdash; não é um problema no seu PR, é ruído que já foi filtrado. "
        "**inconclusivo** = não deu para decidir, e a causa está dita.",
        "</sub>",
        "",
    ]


def _maiuscula(frase: str) -> str:
    """Primeira letra em caixa alta, sem mexer no resto.

    `str.capitalize()` abaixaria o resto da frase, e a frase carrega sigla e
    nome de arquivo dentro.
    """
    return frase[:1].upper() + frase[1:] if frase else frase


def _resumo(c: int, d: int, i: int) -> str:
    """Uma linha, e ela é a única que muita gente vai ler.

    🚨 As contagens ZERO saem da frase, em vez de virarem "Outras 0 suspeita(s)".
    Não é economia de texto: um zero numa frase afirmativa faz o leitor parar
    para conferir se o robô contou certo -- e ele para justamente na linha que
    devia entregar o veredito. As listas colapsadas já aparecem só quando têm
    conteúdo; o resumo passa a seguir a mesma regra.

    ⚠️ O que NÃO sai é a legenda. Ela explica as três palavras do produto, e é
    o enquadramento que impede "descartado" de ser lido como acusação.
    """
    caudas = []
    if d:
        caudas.append("1 outra suspeita foi verificada e descartada" if d == 1
                      else f"{d} outras suspeitas foram verificadas e descartadas")
    if i:
        caudas.append("1 ficou inconclusiva" if i == 1
                      else f"{i} ficaram inconclusivas")
    cauda = f" {_maiuscula('; '.join(caudas))}." if caudas else ""

    if c:
        return f"**{superficie.conta(c, 'achado')} com evidência.**{cauda}"
    if d and not i:
        return ("**Nada a apontar neste PR.** " + (
            "1 suspeita foi levantada, e a verificação a derrubou."
            if d == 1 else
            f"{d} suspeitas foram levantadas, e a verificação derrubou todas."))
    if d or i:
        return f"**Nenhum achado sustentado por evidência.**{cauda}"
    return "**Nenhuma suspeita chegou a ser verificada nesta rodada.**"


def _sem_cabecalho(linhas: list[str]) -> list[str]:
    """Tira o titulo `##` do parecer de terminal, e as bordas em branco.

    ⚠️ As linhas em branco do MEIO ficam: sao elas que separam paragrafo em
    markdown. Ver o comentario em `monta`.
    """
    corpo = [l for l in linhas if not l.startswith("## ")]
    while corpo and not corpo[0].strip():
        corpo.pop(0)
    while corpo and not corpo[-1].strip():
        corpo.pop()
    return corpo


def _detalhes(titulo: str, linhas: list[str], aberto: bool = False) -> list[str]:
    if not linhas:
        return []
    return ["", f"<details{' open' if aberto else ''}>",
            f"<summary>{titulo}</summary>", "", *linhas, "", "</details>"]


def _lista(veredictos: list[dict], acusacoes: dict, estilo=None) -> list[str]:
    estilo = estilo or superficie.TERMINAL
    fora = []
    for v in veredictos:
        a = acusacoes.get(v["id"], {})
        rotulo = juiz._CATEGORIA_DO_DESAFIO.get(a.get("categoria"),
                                                a.get("categoria", "?"))
        fora.append(f"- **{rotulo}** em {estilo.local(juiz._local(a))}  \n  {v.get('motivo', '-')}")
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
            "<sub><b>Veredito</b> &mdash; cada suspeita é tratada como "
            "acusação, e nada vira parecer sem prova reproduzível. "
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
    aviso = ("\n\n> [!WARNING]\n> **Comentário truncado** no limite de "
             f"{teto:,} caracteres do GitHub. O parecer completo está nos "
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

    # 🚨 A contagem e' de DEFEITOS, nao de vereditos. As duas rodadas de 18/08
    # publicaram "3 achados com evidencia" para UM defeito visto por tres
    # lentes -- o unico lugar em que este produto inflava acusacao, e no texto
    # que o cliente le.
    # Refinado pela PROVA quando ela existe no disco; senao, a heuristica --
    # e o bloco diz qual das duas foi. Ler do arquivo mantem esta funcao pura.
    # 🚨 AQUI o parecer deixa de ser tela de terminal. Até 20/08 este corpo saía
    # com `O QUE:` e `[ALTA] [alta]` -- tipografia de console dentro de um
    # navegador -- e com `app/main.py:103-106` como TEXTO, mandando o autor
    # procurar à mão a linha que o produto já sabia.
    #
    # A `Ligacao` pode ser None (rodada local, sem repo/commit conhecidos): aí o
    # markdown continua e só o link não sai. 🚫 Nunca um link chutado -- um 404
    # é o mesmo defeito do caminho morto, com roupa melhor.
    estilo = superficie.Markdown(superficie.Ligacao.de(meta))

    grupos = pfus.aplica(fusao.agrupa(c, acusacoes), pfus.do_disco())
    p: list[str] = [MARCA, "", "## Veredito", ""]
    p += [_resumo(len(grupos), len(d), len(i)), ""]
    p += _legenda()

    if levantadas:
        examinadas = len(c) + len(d) + len(i)
        p += [f"<sub>{superficie.conta(levantadas, 'suspeita')} "
              f"{superficie.plural(levantadas, 'levantada')}, {examinadas} "
              f"{superficie.plural(examinadas, 'verificada')} dentro do "
              "orçamento desta rodada.</sub>", ""]

    # Condenados ABERTOS e por extenso: e' o que o autor precisa agir.
    for grupo, ver, det in grupos:
        p += [juiz.bloco_agrupado(grupo, acusacoes, artefatos, http, (ver, det),
                                  estilo), ""]

    # E o resto colapsado. Presente, nunca omitido -- as duas listas sao a peca
    # que o produto tem e ninguem mais tem -- mas sem competir com o achado.
    p += _detalhes(f"{superficie.conta(len(d), 'suspeita')} "
                   f"{superficie.plural(len(d), 'verificada')} e "
                   f"{superficie.plural(len(d), 'descartada')}, com motivo",
                   _lista(d, acusacoes, estilo))
    p += _detalhes(f"{superficie.conta(len(i), 'inconclusiva')}, com a causa",
                   _lista(i, acusacoes, estilo))

    nao_testadas = juiz._secao_nao_testadas(escopo, estilo)
    if nao_testadas:
        # Sem o cabecalho `##` do parecer de terminal: dentro do <details> ele
        # viraria um titulo solto no meio do comentario.
        #
        # 🚨 Mas as linhas EM BRANCO ficam. Ate' 20/08 este filtro tirava toda
        # linha vazia junto com o titulo, e em markdown isso cola os paragrafos:
        # o aviso das duplicatas, a nota do detalhamento e a lista viravam um
        # bloco unico de texto corrido. Tirar o titulo e tirar a estrutura eram
        # a mesma linha de codigo, e so' a segunda era de proposito.
        corpo = _sem_cabecalho(nao_testadas)
        p += _detalhes("Levantadas e não testadas (fora do orçamento da rodada)",
                       corpo)

    banco = juiz._secao_efeito_no_banco()
    if banco:
        p += _detalhes("Efeito no banco do app", _sem_cabecalho(banco))

    corpo, _ = corta("\n".join(p), TETO - FOLGA_RODAPE)
    corpo = corpo + "\n".join(_rodape(meta)) + "\n"

    # 🚨 A ULTIMA PORTA ANTES DO PUBLICO -- 19/08.
    #
    # A frente da ENTRADA (`segredo.caminho_sensivel` no `read_file`/`grep`)
    # impede o advogado de ABRIR um `.env`. Ela nao alcanca o que chegou por
    # outro caminho: o diff do PR entra no prompt inteiro, e credencial
    # commitada NAQUELE diff passa por fora da leitura de arquivo. Se o parecer
    # citar o trecho, ele vira comentario publico.
    #
    # Por isso a redacao mora AQUI, no que vira `body` do comentario, e nao em
    # `posta()`: tudo que renderiza o comentario passa por este ponto, inclusive
    # o `do_disco` usado para reajustar formato sem gastar API.
    #
    # ⚠️ A contagem e' DITA, nunca silenciosa: "0 redacoes" e' informacao tanto
    # quanto "3", e redacao muda nao da' para auditar.
    corpo, n = segredo.redige(corpo)
    if n:
        corpo += (f"\n<sub>🔒 {n} trecho(s) com forma de credencial foram "
                  "mascarados neste comentario. O artefato local guarda o "
                  "original.</sub>\n")
    return corpo


def do_disco(meta: dict | None = None) -> str:
    """Monta o comentario a partir do que a rodada gravou.

    Mesma disciplina do juiz: ajustar o formato do comentario pela trigesima vez
    nao pode re-executar o advogado nem gastar API.
    """
    veredictos, acusacoes, artefatos, avisos, http, escopo = juiz.carrega_do_disco()
    organizado = juiz.organiza(veredictos, acusacoes, artefatos, avisos, http)
    return monta(organizado, acusacoes, artefatos, http, escopo, meta)
