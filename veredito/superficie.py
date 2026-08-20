"""Onde o parecer e' LIDO -- e o que muda de uma superficie para a outra.

O conteudo do parecer e' um so'. A apresentacao nao: no terminal quem le e' quem
rodou, e a tela nao tem link nem negrito; num comentario de PR quem le e' o
AUTOR, num navegador, em markdown.

Ate' 20/08 havia uma superficie so' -- a do terminal -- e ela vazava inteira
para dentro do comentario. O resultado esta no `bancada#1`, publicado:

    [ALTA] [alta] correctness - app/main.py:103-106
    O QUE: ...
    ARBITRO: ...
    EVIDENCIA: ... Artefato: artefatos/prova_correcao_01.json

Quatro defeitos numa tela so', e todos da mesma familia: **restricao de uma
superficie aplicada onde ela nao vale.**

- `evidencia` sem acento ao lado de `Remoção` com acento, na mesma linha. A
  regra que produziu isso e' `tests/test_saida_no_console.py`, e ela fala do
  console cp1252 do Windows -- que nao tem nada a ver com um navegador.
  🚨 E nem no console ela pedia isso: acento CABE em cp1252; so' emoji nao cabe.
  A restricao real era estreita, a pratica virou larga, e a pratica viajou.
- `[ALTA] [alta]`: severidade e confianca sao coisas DIFERENTES desenhadas como
  duas etiquetas iguais. Le como bug, e esconde a regra central do produto --
  a severidade acompanha a forca da prova, a confianca e' o que a lente achava
  ANTES de testar.
- `O QUE:` em caixa alta e' cabecalho de terminal. Em markdown existe cabecalho
  de verdade.
- `app/main.py:103-106` e `artefatos/prova_correcao_01.json` sao enderecos que
  so' significam alguma coisa na maquina que rodou. Para o autor do PR, o
  primeiro e' um lugar para procurar a mao e o segundo e' um caminho morto.

## O que este modulo NAO faz

🚫 Nao decide nada. Nenhuma funcao aqui olha veredito, severidade ou artefato
para mudar o que o parecer AFIRMA -- so' para escolher como aquilo aparece.
Acento, plural e link sao texto. Quem decide continua em `juiz.aplica_regras`.

## 🚨 Link que nao da' para sustentar nao e' emitido

O defeito do `artefatos/prova_correcao_01.json` e' mandar o autor a um lugar que
nao existe para ele. Um permalink construido com commit errado -- ou com o
`repo` de outra rodada -- e' o MESMO defeito com roupa melhor: um 404 se le como
"o Veredito apontou um arquivo que nao existe", e a proxima linha do parecer
perde a credibilidade junto.

Por isso `Ligacao` so' nasce com procedencia completa, e sem ela o parecer volta
ao texto puro em vez de inventar endereco. E' a mesma doutrina do arbitro: sem
poder apontar ONDE, a resposta honesta e' nao apontar.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import quote

from .fontes import _faixa

# ------------------------------------------------------------------- o plural
#
# `1 achado(s)`, `2 lente(s)`, `0 suspeita(s)` sao plural de formulario -- o
# leitor le "o robo nao sabe contar" antes de ler o achado. Custa quatro linhas.


def plural(n: int, singular: str, muitos: str | None = None) -> str:
    """A palavra concordando com o numero. `muitos` so' para o que nao faz +s."""
    return singular if abs(n) == 1 else (muitos or singular + "s")


def conta(n: int, singular: str, muitos: str | None = None) -> str:
    """`1 achado`, `8 suspeitas`, `0 suspeitas`."""
    return f"{n} {plural(n, singular, muitos)}"


# ------------------------------------------------------------------ a ligacao

_HEAD_NO_CARIMBO = re.compile(r"^\d{8}T\d{4}-([0-9a-f]{7,40})$")


def head_do_carimbo(nome: str) -> str | None:
    """O commit revisado, lido do nome da pasta da rodada. Ou None.

    `20260818T1928-61cc0a7` -> `61cc0a7`.

    🚨 Estrito de proposito. `orquestrador._carimbo_da_rodada` DEIXA CAIR o
    sufixo quando o git nao responde ("carimbo nunca derruba rodada"), e ai o
    nome e' so' o horario. Um casamento frouxo transformaria `20260818T1928` num
    "commit" e produziria permalink para um sha que nao existe -- o caminho
    morto de novo, agora clicavel.
    """
    m = _HEAD_NO_CARIMBO.match(str(nome or "").strip())
    return m.group(1) if m else None


@dataclass(frozen=True)
class Ligacao:
    """De onde sai um endereco que o autor do PR consegue abrir.

    `repo` e `head` sustentam o permalink de codigo; `execucao` sustenta o link
    do rastro. Sao independentes: uma rodada na maquina de alguem tem os dois
    primeiros e nao tem o terceiro, e o parecer nao perde o permalink por causa
    disso.
    """

    repo: str                       # `dono/repositorio`
    head: str                       # o commit revisado
    servidor: str = "https://github.com"
    execucao: str = ""              # o id da execucao da Action, quando ha'

    @classmethod
    def de(cls, meta: dict | None) -> "Ligacao | None":
        """A ligacao que o `meta` da rodada sustenta, ou None.

        ⚠️ Pura: le o dicionario, nunca o ambiente. Quem junta ambiente, URL do
        PR e carimbo e' `posta_parecer`, que e' onde as tres coisas existem ao
        mesmo tempo -- e assim esta funcao continua conferivel em
        milissegundos, sem GitHub e sem variavel de ambiente.
        """
        meta = meta or {}
        repo, head = str(meta.get("repo") or ""), str(meta.get("head") or "")
        if not repo or not head or repo.count("/") != 1:
            return None
        return cls(
            repo=repo.strip("/"),
            head=head,
            servidor=str(meta.get("servidor") or "https://github.com").rstrip("/"),
            execucao=str(meta.get("execucao") or ""),
        )

    def arquivo(self, local: str) -> str | None:
        """O permalink de `app/main.py:103-106`, ou None se nao der para montar.

        Ancorado no COMMIT, nunca no ramo: o ramo anda, e um link para
        `blob/main` apontaria para outro codigo daqui a uma semana -- o parecer
        e' sobre um commit especifico e o link precisa dizer isso.
        """
        faixa = _faixa(local)
        if faixa is None:
            return None
        caminho, primeira, ultima = faixa
        ancora = f"#L{primeira}" if primeira == ultima else f"#L{primeira}-L{ultima}"
        return (f"{self.servidor}/{self.repo}/blob/{self.head}/"
                f"{quote(caminho)}{ancora}")

    def rastro(self) -> str | None:
        """A pagina da execucao, onde o `upload-artifact` deixou o rastro.

        ⚠️ E' a pagina da execucao, e nao o arquivo. O GitHub so' publica o
        artefato como um zip da execucao inteira, e prometer mais que isso no
        texto ("o arquivo X esta em <link>") mandaria o autor procurar um
        endereco que o produto nao tem.
        """
        if not self.execucao:
            return None
        return f"{self.servidor}/{self.repo}/actions/runs/{self.execucao}"


def do_ambiente(env: dict | None = None) -> dict:
    """O que a Action ja poe no ambiente de TODO passo, sem tocar no workflow.

    `.github/workflows/` e' da T2. Nao precisa mudar: `GITHUB_REPOSITORY`,
    `GITHUB_SERVER_URL` e `GITHUB_RUN_ID` sao postos pelo proprio GitHub em
    cada passo, e sao exatamente o que falta para o link existir.

    🚫 `GITHUB_SHA` NAO entra. Em evento de `pull_request` ele e' o commit de
    MERGE que o GitHub fabrica, e nao o head do PR -- um permalink montado com
    ele abre um commit que nao esta no ramo do autor. O head sai do carimbo da
    rodada, que e' o commit que foi de fato revisado.
    """
    env = os.environ if env is None else env
    fora = {}
    if env.get("GITHUB_REPOSITORY"):
        fora["repo"] = env["GITHUB_REPOSITORY"]
    if env.get("GITHUB_SERVER_URL"):
        fora["servidor"] = env["GITHUB_SERVER_URL"]
    if env.get("GITHUB_RUN_ID"):
        fora["execucao"] = env["GITHUB_RUN_ID"]
    return fora


# ------------------------------------------------------------------- o estilo
#
# Um bloco do parecer e' uma CABECA (severidade, confianca, categoria, local) e
# uma lista de campos rotulados. Quem monta os fatos e' o juiz; quem escolhe a
# tipografia e' o estilo.
#
# 🚨 Campo e' `(rotulo, valor)`, e o valor pode ser lista de linhas. Ate' aqui a
# fusao remontava o bloco procurando `"O QUE:"` dentro do texto ja' formatado --
# convencao de string decidindo estrutura, que e' o item 4 do "como procurar" do
# CLAUDE.md. Com campos, inserir a convergencia depois do "O que" e' indice de
# lista, e nao casamento de prefixo que muda quando o rotulo muda.


class Estilo:
    """O terminal: caixa alta, sem link, uma linha por campo.

    Continua sendo o padrao de `formata_parecer`. Quem le ali sabe o que as
    palavras significam e nao tem onde clicar.
    """

    ligacao: Ligacao | None = None

    def cabecalho(self, cabeca: dict) -> list[str]:
        return [f"[{cabeca.get('severidade', '?')}] "
                f"[{cabeca.get('confianca', '?')}] "
                f"{cabeca.get('categoria', '?')} - {cabeca.get('local', '?')}"]

    def rotulo(self, rotulo: str) -> str:
        """Como o rotulo aparece nesta superficie -- caixa alta e dois pontos.

        🚨 Existe para ser PERGUNTADO, e nao reproduzido. `juiz.CONVERGENCIA` e'
        `"Convergência"`, e no terminal sai `"CONVERGÊNCIA:"`: quem conferir o
        bloco procurando a constante crua nao acha nada, e quem escrever
        `.upper()` na conferencia copia a convencao para um segundo lugar --
        exatamente a "checagem que depende de convencao de string" do CLAUDE.md.
        Um lugar responde, e o teste pergunta a ele.
        """
        return f"{rotulo.upper()}:"

    def campo(self, rotulo: str, valor) -> list[str]:
        if isinstance(valor, (list, tuple)):
            if not valor:
                return []
            return ([f"{self.rotulo(rotulo)} {valor[0]}"]
                    + [f"  {l}" for l in valor[1:]])
        return [f"{self.rotulo(rotulo)} {valor}"]

    def local(self, texto: str) -> str:
        return texto

    def monoespaco(self, texto: str) -> str:
        return texto

    def artefato(self, caminho: str) -> str:
        return f"Artefato: {caminho}"

    def bloco(self, cabeca: dict, campos: list[tuple[str, object]]) -> str:
        linhas = list(self.cabecalho(cabeca))
        for rotulo, valor in campos:
            linhas += self.campo(rotulo, valor)
        return "\n".join(linhas)


class Markdown(Estilo):
    """O comentario de PR: cabecalho de verdade, negrito, e endereco clicavel.

    ⚠️ Cada campo vira um PARAGRAFO, separado por linha em branco. GitHub
    quebra linha simples dentro de comentario, mas nem todo renderizador de
    markdown quebra -- e o parecer tambem e' gravado como `.md` em disco. Linha
    em branco funciona nos dois, e depender do contrario seria escolher uma
    convencao de renderizador para carregar a estrutura do texto.
    """

    def __init__(self, ligacao: Ligacao | None = None):
        self.ligacao = ligacao

    def cabecalho(self, cabeca: dict) -> list[str]:
        sev = cabeca.get("severidade", "?")
        conf = cabeca.get("confianca", "?")
        local = self.local(cabeca.get("local", "?"))
        return [
            f"#### {sev} &middot; {cabeca.get('categoria', '?')} em {local}",
            "",
            # 🚨 Os dois numeros DITOS, e nao so' separados. `[ALTA] [alta]`
            # nao era feio -- era ilegivel: nada na tela dizia que a primeira
            # etiqueta e' sobre a PROVA e a segunda e' sobre a suspeita antes
            # de haver prova. E' a regra central do produto, e ela estava
            # escondida atras de duas palavras iguais.
            f"<sub>severidade **{sev}** &mdash; acompanha a força da prova, "
            f"não a gravidade teórica &middot; a lente que acusou tinha "
            f"confiança <b>{conf}</b>, antes de qualquer teste</sub>",
        ]

    def rotulo(self, rotulo: str) -> str:
        return f"**{rotulo}.**"

    def campo(self, rotulo: str, valor) -> list[str]:
        if isinstance(valor, (list, tuple)):
            if not valor:
                return []
            corpo = [f"{self.rotulo(rotulo)} {valor[0]}", ""]
            corpo += [f"- {l}" for l in valor[1:]]
            return corpo + [""]
        return [f"{self.rotulo(rotulo)} {valor}", ""]

    def local(self, texto: str) -> str:
        url = self.ligacao.arquivo(texto) if self.ligacao else None
        return f"[`{texto}`]({url})" if url else f"`{texto}`"

    def monoespaco(self, texto: str) -> str:
        return f"`{texto}`"

    def artefato(self, caminho: str) -> str:
        """O artefato como algo que o autor CONSEGUE abrir.

        Sem execucao conhecida o caminho continua saindo cru -- quem rodou na
        propria maquina tem o arquivo, e apagar a informacao seria pior que
        deixa-la sem link.
        """
        url = self.ligacao.rastro() if self.ligacao else None
        if not url:
            return f"artefato: `{caminho}`"
        return f"artefato [no rastro desta rodada]({url}): `{caminho}`"

    def bloco(self, cabeca: dict, campos: list[tuple[str, object]]) -> str:
        linhas = self.cabecalho(cabeca) + [""]
        for rotulo, valor in campos:
            linhas += self.campo(rotulo, valor)
        while linhas and not linhas[-1].strip():
            linhas.pop()
        return "\n".join(linhas)


TERMINAL = Estilo()
