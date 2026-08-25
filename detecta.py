"""`veredito init` -- le o repositorio e escreve o `veredito.yml` que der.

    py -3.12 detecta.py [raiz-do-projeto]

Irmao do `revisa_pr.py`: entra pela porta da frente, sem saber nada deste
repositorio em particular.

O que ele resolve: o `veredito.yml` tem ~26 campos, e pedir os 26 a mao antes de
o cliente ver valor derruba a conversao. Medido: 12 saem de
`docker-compose.yml` + `Dockerfile` com zero erro.

🚨 O QUE ELE NAO RESOLVE, E DIZ EM VOZ ALTA

Os dois campos que sobram -- `contas` e `contexto` -- sao exatamente os que
sustentam CRITICA, cada um fechando uma via da R1. Um gerador perfeito nos
outros 24 entrega uma rodada onde nada passa de MEDIA. Terminar com "pronto,
seu veredito.yml esta feito" seria vender onboarding curto e entregar rodada
morna -- por isso as duas perguntas saem no fim, depois de tudo, e nao como
rodape.

⚠️ A saida passa por `_diz`, que troca o que o console nao imprime. O console
do Windows e' cp1252 e emoji nao cabe la' -- mas a RESTRICAO E' DA SUPERFICIE,
nao do conteudo: em 20/08 a mesma confusao tirou os acentos do comentario de PR,
que e' markdown e aceita acento. O texto fica inteiro; quem adapta e' a saida.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from veredito import detector
from veredito.superficie import conta

_PRECISA_DO_APP = "precisa do app no ar"
_SO_VOCE = "SO' VOCE SABE"


def _diz(*pedacos) -> None:
    texto = " ".join(str(p) for p in pedacos)
    saida = sys.stdout
    codec = getattr(saida, "encoding", None) or "utf-8"
    try:
        texto.encode(codec)
    except (UnicodeEncodeError, LookupError):
        texto = texto.encode(codec, errors="replace").decode(codec, errors="replace")
    print(texto)


def _grupo(motivo: str) -> str:
    if _PRECISA_DO_APP in motivo:
        return "precisa do app no ar"
    if _SO_VOCE in motivo:
        return "so' voce sabe"
    return "nao esta escrito neste repositorio"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Detecta o veredito.yml de um projeto.")
    p.add_argument("raiz", nargs="?", default=".",
                   help="raiz do projeto a descrever (padrao: diretorio atual)")
    p.add_argument("--saida", default="",
                   help="onde escrever (padrao: <raiz>/veredito.yml.detectado)")
    p.add_argument("--so-olhar", action="store_true",
                   help="nao escreve arquivo nenhum, so' mostra")
    a = p.parse_args(argv)

    raiz = Path(a.raiz).expanduser().resolve()
    if not raiz.is_dir():
        _diz(f"nao existe: {raiz}")
        return 2

    det = detector.detecta(raiz)
    lidos = {c: d for c, d in det.campos.items() if d.de != "convencao do Veredito"}
    nossos = {c: d for c, d in det.campos.items() if d.de == "convencao do Veredito"}

    _diz(f"\nprojeto: {raiz}")
    _diz("-" * 72)

    if not lidos:
        _diz("nao derivei NADA deste repositorio.")
        for campo, motivo in det.ausentes.items():
            if _grupo(motivo) == "nao esta escrito neste repositorio":
                _diz(f"  {campo}: {motivo}")
                break
        _diz("\nIsto nao e' erro: o detector le contratos de maquina (compose,")
        _diz("Dockerfile). Repositorio que nao tem um nao da' o que ler -- e' o mesmo")
        _diz("repositorio em que uma pessoa tambem nao escreveria o arquivo de cabeca.")
        _diz("O Veredito continua rodando com leitura e grep, e o pre-voo diz o que")
        _diz("perdeu.")
        return 1

    _diz(f"\nDERIVADO do seu repositorio -- {conta(len(lidos), 'campo')}:\n")
    largura = max(len(c) for c in lidos)
    for campo, d in lidos.items():
        _diz(f"  {campo.ljust(largura)}  = {_curto(d.valor)}")
        _diz(f"  {' ' * largura}    de {d.de}")

    if nossos:
        _diz(f"\nNOSSO, nao detectado -- {conta(len(nossos), 'campo')}:")
        _diz("  (convencao do Veredito: nao ha o que ler no seu repositorio sobre")
        _diz("   isto, e nao e' chute -- sao nomes que nos escolhemos)\n")
        for campo, d in nossos.items():
            _diz(f"  {campo.ljust(largura)}  = {_curto(d.valor)}")

    _ausentes(det)

    for aviso in det.avisos:
        _diz(f"\n  ATENCAO: {aviso}")

    escrito = None
    if not a.so_olhar:
        escrito = Path(a.saida) if a.saida else detector.destino(raiz)
        escrito.write_text(detector.para_yaml(det), encoding="utf-8")

    _o_diff(raiz, det, escrito)
    _as_duas_perguntas(det)

    if escrito:
        _diz(f"\nescrevi: {escrito}")
        _diz("  Complete as duas respostas acima, confira o resto, e renomeie para")
        _diz("  `veredito.yml` na raiz do projeto.")
    return 0


def _curto(valor) -> str:
    if isinstance(valor, list):
        return "[" + ", ".join(f"{v[0]} -> {v[1]}" if isinstance(v, list) and len(v) == 2
                               else str(v) for v in valor) + "]"
    return str(valor)


def _ausentes(det: detector.Deteccao) -> None:
    por_grupo: dict[str, list[tuple[str, str]]] = {}
    for campo, motivo in det.ausentes.items():
        por_grupo.setdefault(_grupo(motivo), []).append((campo, motivo))

    _diz(f"\nAUSENTE -- {conta(len(det.ausentes), 'campo')}, cada um com a causa:")
    _diz("  (ausente nao e' vazio: campo chutado nao levanta erro, ele PARECE")
    _diz("   declarado -- e e' assim que uma rodada sai boa por engano)")
    for grupo in ("nao esta escrito neste repositorio", "precisa do app no ar",
                  "so' voce sabe"):
        itens = por_grupo.get(grupo)
        if not itens:
            continue
        _diz(f"\n  {grupo}:")
        for campo, motivo in itens:
            _diz(f"    {campo}")
            for linha in _quebra(motivo, 66):
                _diz(f"        {linha}")


def _quebra(texto: str, largura: int) -> list[str]:
    palavras, linhas, atual = texto.split(), [], ""
    for palavra in palavras:
        if len(atual) + len(palavra) + 1 > largura:
            linhas.append(atual)
            atual = palavra
        else:
            atual = f"{atual} {palavra}".strip()
    if atual:
        linhas.append(atual)
    return linhas


def _o_diff(raiz: Path, det: detector.Deteccao, escrito: Path | None) -> None:
    """🚫 NUNCA sobrescreve um `veredito.yml` existente.

    O ajuste a mao e' justamente onde moram `contas` e `contexto`. Sobrescrever
    faria os dois campos que sustentam CRITICA sumirem sem sinal -- e a rodada
    seguinte sairia toda em MEDIA sem ninguem saber por que.
    """
    jaexiste = raiz / "veredito.yml"
    if not jaexiste.is_file():
        return
    _diz("\n" + "-" * 72)
    _diz("JA EXISTE um veredito.yml aqui. Nao toquei nele.")
    try:
        atual = yaml.safe_load(
            jaexiste.read_text(encoding="utf-8-sig", errors="replace")) or {}
    except yaml.YAMLError as e:
        _diz(f"  (nao consegui ler para comparar: {e})")
        return
    briga = detector.divergencias(det, atual)
    if not briga:
        _diz("  E onde os dois falam do mesmo campo, eles concordam.")
        return
    _diz(f"  Discordamos em {conta(len(briga), 'campo')}. Isso NAO quer dizer que o")
    _diz("  seu esta errado -- quer dizer que os dois nao contam a mesma historia,")
    _diz("  e um dos dois esta desatualizado. Eu so' leio compose e Dockerfile.\n")
    for campo, humano, meu in briga:
        _diz(f"    {campo}")
        _diz(f"       seu: {_curto(humano)}")
        _diz(f"       eu : {_curto(meu)}  ({det.campos[campo].de})")


def _as_duas_perguntas(det: detector.Deteccao) -> None:
    if not det.perguntas:
        return
    _diz("\n" + "=" * 72)
    _diz("FALTAM DUAS RESPOSTAS, E SAO AS QUE MAIS VALEM")
    _diz("=" * 72)
    _diz("")
    for linha in _quebra(
            "Conferido no codigo do juiz, nao deduzido: a R1 so' aceita severidade "
            "CRITICA com arbitro de procedencia (vem de `contexto`) ou com prova "
            "ponta a ponta (vem de `contas`, porque chamada autenticada precisa de "
            "token). A R2 rebaixa todo o resto para MEDIA.", 70):
        _diz(f"  {linha}")
    _diz("")
    for linha in _quebra(
            "Ou seja: com tudo o que eu detectei e nenhuma das duas, o Veredito "
            "roda, refuta com motivo e nao absolve em silencio -- mas nada dele "
            "passa de MEDIA. Estas duas perguntas sao o produto.", 70):
        _diz(f"  {linha}")
    _diz("")
    for pergunta in det.perguntas:
        for bruta in pergunta.splitlines():
            for linha in _quebra(bruta.strip(), 68):
                _diz(f"  {linha}")
        _diz("")


if __name__ == "__main__":
    raise SystemExit(main())
