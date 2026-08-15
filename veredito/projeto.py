"""hack2l / Veredito -- o projeto sob revisao, descrito em `veredito.yml`.

Ate' 14/08 as quatro contas de teste estavam chumbadas em `config.py`. Isso
fazia a prova ponta a ponta -- a unica via que sustenta CRITICA junto com o
arbitro -- funcionar so' no repositorio do desafio. Este modulo tira isso do
codigo e poe num arquivo do PROJETO.

A divisao que vale:

    veredito.yml  ->  o PROJETO revisado: como sobe, como autentica, onde e'
                      seguro escrever
    .env          ->  como NOS operamos: modelo, orcamento, TOP_N, timeouts

⚠️ AUSENTE NAO E' VAZIO. Sem `veredito.yml` o Veredito continua rodando, com
leitura e grep -- e diz em voz alta o que perdeu. Um projeto que nao descreve
suas contas nao ganha prova ponta a ponta, e isso e' um limite honesto, nao um
erro. Cair calado seria pior: a rodada sairia toda em MEDIA e pareceria o
produto nao funcionando.
"""

from __future__ import annotations

from pathlib import Path

import yaml


class ProjetoInvalido(ValueError):
    """O arquivo existe mas descreve algo que nao da' para usar.

    Levanta em vez de degradar: arquivo escrito errado e' engano do operador, e
    seguir com metade dele produziria uma rodada que parece boa e nao e'.
    Ausencia total, essa sim, degrada -- ver o docstring do modulo.
    """


def caminho(raiz_do_projeto: Path, explicito: str = "") -> Path | None:
    """Onde esta o `veredito.yml` deste projeto.

    Ordem: o que o operador mandou > o do proprio projeto > o nosso, em
    `projetos/`. A do meio e' a que vale para o produto -- o arquivo mora junto
    do codigo que descreve, e e' assim que a Action vai achar. `projetos/` so'
    existe porque o `desafio` e' de terceiro e nao da' para commitar dentro.
    """
    if explicito:
        p = Path(explicito).expanduser()
        return p if p.is_file() else None
    no_projeto = raiz_do_projeto / "veredito.yml"
    if no_projeto.is_file():
        return no_projeto
    nosso = Path(__file__).resolve().parents[1] / "projetos" / f"{raiz_do_projeto.name}.yml"
    return nosso if nosso.is_file() else None


def carrega(caminho_do_yml: Path | None) -> dict:
    """Le e valida. Devolve {} quando nao ha arquivo -- ausencia e' legitima."""
    if caminho_do_yml is None:
        return {}
    try:
        dado = yaml.safe_load(caminho_do_yml.read_text(encoding="utf-8-sig"))
    except (OSError, yaml.YAMLError) as e:
        raise ProjetoInvalido(f"{caminho_do_yml}: nao consegui ler ({e})") from e
    if dado is None:
        return {}
    if not isinstance(dado, dict):
        raise ProjetoInvalido(f"{caminho_do_yml}: a raiz precisa ser um mapa")
    _valida(dado, caminho_do_yml)
    return dado


def _valida(d: dict, onde: Path) -> None:
    contas = d.get("contas")
    if contas is None:
        return          # projeto sem contas: perde prova ponta a ponta, e ok
    if not isinstance(contas, list) or not contas:
        raise ProjetoInvalido(f"{onde}: `contas` precisa ser uma lista nao vazia")

    for c in contas:
        if not isinstance(c, dict):
            raise ProjetoInvalido(f"{onde}: cada conta precisa ser um mapa")
        faltando = [k for k in ("nome", "email", "senha") if not c.get(k)]
        if faltando:
            raise ProjetoInvalido(
                f"{onde}: conta {c.get('nome', '?')} sem {', '.join(faltando)}")

    nomes = [c["nome"] for c in contas]
    if len(set(nomes)) != len(nomes):
        raise ProjetoInvalido(f"{onde}: ha contas com o mesmo `nome`")


def usuarios(d: dict) -> dict[str, tuple[str, str]]:
    """{nome: (email, senha)} -- o formato que `ferramentas._token` consome."""
    return {c["nome"]: (c["email"], c["senha"]) for c in d.get("contas") or []}


def controle_negativo(d: dict) -> str | None:
    """A conta que nao possui nada.

    🚨 E' a mais valiosa da lista e a que ninguem lembra de criar. Qualquer dado
    de outro usuario que apareca para ela e' vazamento, sem precisar
    interpretar -- foi ela que provou a CRITICA de 14/08. Deduzida de
    `possui: 0` para o operador nao ter que declarar duas vezes e as duas
    divergirem.
    """
    for c in d.get("contas") or []:
        if c.get("possui") == 0:
            return c["nome"]
    return None


def avisos(d: dict, contexto_resolvido: Path | None = None) -> list[str]:
    """O que este projeto NAO vai conseguir provar, dito antes de gastar.

    Sai no pre-voo. Descobrir no fim da rodada que faltava conta e' pagar
    US$1,30 para aprender uma coisa que o arquivo ja sabia.
    """
    fora = []
    # 🚨 "Nao declarei contexto" e "declarei e o caminho esta errado" sao coisas
    # diferentes, e so' a segunda e' bug. Tratar as duas como silencio faz um
    # caminho digitado errado sair como arbitro `null` -- que parece o
    # repositorio nao documentar nada, e nao um erro de uma linha no yml.
    if d.get("contexto") and contexto_resolvido is not None \
            and not contexto_resolvido.is_file():
        fora.append(f"`contexto` aponta para {contexto_resolvido}, que nao existe "
                    "-- o arbitro vai sair `null` por engano, nao por honestidade")
    contas = d.get("contas") or []
    if not contas:
        fora.append("sem `contas`: nao ha prova ponta a ponta, so' leitura e grep "
                    "-- e nada passa de MEDIA pela R2")
        return fora
    if len(contas) < 3:
        # A regra do Carlos, 06/08: isolamento precisa de tres contas.
        fora.append(f"so' {len(contas)} conta(s): provar isolamento entre usuarios "
                    "pede pelo menos tres")
    if controle_negativo(d) is None:
        fora.append("nenhuma conta com `possui: 0`: sem controle negativo, "
                    "vazamento vira interpretacao em vez de fato")
    if not d.get("contexto"):
        fora.append("sem `contexto`: o arbitro sai `null` e nada sustenta CRITICA "
                    "por regra (R1)")
    return fora
