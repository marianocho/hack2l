"""Tres achados que sao UM defeito viram um achado.

🚨 Medido ao vivo em 18/08, nas duas rodadas da Action contra o PR da bancada.
Cada uma publicou TRES achados no comentario do PR, e os tres eram o mesmo IDOR
em `app/main.py:103-104`, com o mesmo conserto:

    rodada 1: correcao:103        padroes:104           performance:103
    rodada 2: correcao:104        correcao:103-106      padroes:104

O produto inteiro existe para nao inflar acusacao. Este era o unico lugar em
que ele inflava -- e justamente no texto que o cliente le. Um PR com UM defeito
saia com "3 achados com evidencia".

## Por que a deduplicacao que ja existe nao pegava

`promotores.deduplica` funde ANTES do advogado, por `(local, arbitro)`, e o
casamento e' exato nos dois campos. Os dois oscilam:

    local : 103, 104, 103-106                     -- a linha anda
    onde  : "REGRAS.md:Acesso e isolamento"
            "REGRAS.md (Acesso e isolamento)"
            "REGRAS.md - Acesso e isolamento"
            "REGRAS.md:Acesso e isolamento (linhas ~13-14)"

Na rodada 2, CADA PAR acerta um eixo e erra o outro. A chave esta certa no
espirito e rigida na letra.

## 🚫 "Fundir por conserto" NAO pode ser casar o texto do conserto

O handoff pediu fusao "por conserto", e a leitura literal repetiria o bug. Os
tres consertos da rodada 1 dizem a mesma coisa em tres redacoes ("Restaurar a
checagem ...", "Restaurar a checagem `if t is None or ...`", "Restaurar a
condicao ..."). Casar essa string falha exatamente como a chave do arbitro.

O que e' FATO embaixo das tres redacoes sao duas coisas:

  1. mesmo arquivo, em linhas vizinhas
  2. mesma PROCEDENCIA -- o arquivo e a secao onde a regra esta escrita

> **A procedencia e' fato do repositorio; a parafrase da regra e do conserto e'
> opiniao do modelo.** A chave se constroi do fato. E' a mesma distincao que o
> arbitro comprou em 09/08, aplicada um nivel acima.

## Por que EXIGIR procedencia, e nao fundir so' por local

Sem arbitro, nao funde. Conservador de proposito, e ha' contraexemplo medido:
no `encode/httpx#3730` quatro acusacoes apontavam a MESMA linha e eram quatro
preocupacoes DIFERENTES (metadados, aviso de versao, titulo, ...). Local igual
nao e' defeito igual. Sao os DOIS fatos concordando que sustentam a fusao.

## E a fusao nao descarta nada

Cada achado fundido continua com id, artefato e evidencia visiveis. A fusao
junta a APRESENTACAO; ela nao apaga verificacao. E o resultado e' mais forte,
nao mais fraco: "tres lentes independentes convergiram, com tres provas
diferentes" vale mais que tres achados que o leitor conta como tres problemas.

⚠️ Fundir na apresentacao e' seguro; fundir antes do advogado nao e'. La', uma
fusao errada custa uma vaga de verificacao -- e deixar passar defeito real custa
mais que falso alarme. Por isso esta peca mora DEPOIS do laco caro, e a chave de
`promotores.deduplica` fica como esta ate' ser medida em separado.
"""

from __future__ import annotations

import re

from . import arbitro
from .fontes import LARGURA_MAX_PARA_CORROBORAR, TOLERANCIA_LINHAS, _faixa

# A tolerancia de linha e a largura maxima vem de `fontes.py`, onde ja foram
# medidas contra ESTE fenomeno: "os promotores emitem FAIXAS e a linha oscila --
# para o mesmo defeito escreveram :30, :31, :32, :30-34, :32-35 e :23-35".
#
# 🚫 Nao redefinir aqui. Duas nocoes de proximidade para a mesma coisa divergem
# em silencio -- e' a regra do "um arquivo so'" valendo para logica.

# Parenteses no fim de `onde` que sao DECORACAO de linha, nao a secao.
# `REGRAS.md:Acesso e isolamento (linhas ~13-14)` e' a mesma procedencia que
# `REGRAS.md:Acesso e isolamento`.
_DECORACAO = re.compile(r"\s*\((?=[^)]*(?:linhas?|lines?|\d))[^)]*\)\s*$", re.I)

# O caminho do arquivo no comeco de `onde`, ate' a extensao.
_CAMINHO = re.compile(r"^\s*([\w./\\-]+\.\w+)")


def procedencia(bruto) -> tuple[str, str] | None:
    """(arquivo, secao) da citacao do arbitro, sem a decoracao. Ou None.

    🚨 Os digitos FICAM. A forma `docs/PRD.md:43` esta no esquema da acusacao e
    ali a "secao" E' o numero da linha: descartar digito fundiria a regra da
    linha 43 com a da linha 99 -- duas regras diferentes do mesmo arquivo, que
    e' exatamente o erro que esta funcao existe para nao cometer.

    Só sai o parenteses final que fala de LINHA, e mesmo assim so' quando sobra
    secao depois dele: em `REGRAS.md (Acesso)` o parenteses E' a secao, e
    remove-lo deixaria a chave casando com qualquer citacao daquele arquivo.
    """
    a = arbitro.normaliza(bruto)
    if a is None or not a.get("onde"):
        return None
    texto = str(a["onde"]).strip()
    m = _CAMINHO.match(texto)
    if not m:
        return None
    arquivo = m.group(1).replace("\\", "/").casefold()
    resto = texto[m.end():]

    sem_decoracao = _DECORACAO.sub("", resto)
    # So' aceita a poda se sobrou secao. Senao o parenteses era a secao.
    if _norma(sem_decoracao):
        resto = sem_decoracao
    return (arquivo, _norma(resto))


def _norma(texto: str) -> str:
    """Casefold, sem pontuacao, espaco colapsado. `:Acesso e isolamento`,
    ` (Acesso e isolamento)` e ` - Acesso e isolamento` viram a mesma coisa."""
    return " ".join(re.sub(r"[^\w\s]", " ", str(texto)).casefold().split())


def chave(acusacao: dict) -> tuple | None:
    """O defeito que esta acusacao aponta, como FATO. None = nao funde.

    Devolve `(arquivo_do_codigo, arquivo_da_regra, secao_da_regra)`. A LINHA
    fica de fora de proposito: ela entra na comparacao de proximidade, nao na
    igualdade -- que e' a diferenca entre esta chave e a que nao pegava nada.
    """
    faixa = _faixa(acusacao.get("local_normalizado") or acusacao.get("local"))
    proc = procedencia(acusacao.get("arbitro"))
    if faixa is None or proc is None:
        return None
    arquivo, primeira, ultima = faixa
    # Acusacao que aponta uma REGIAO, e nao um ponto, nao arrasta as vizinhas.
    # Mesmo motivo do teto em fontes.py: uma faixa de 82 linhas engoliria o
    # arquivo inteiro, e inflar o sinal e' o erro de sempre deste projeto.
    if ultima - primeira > LARGURA_MAX_PARA_CORROBORAR:
        return None
    return (str(arquivo).replace("\\", "/").casefold(), *proc)


def agrupa(condenados: list[dict], acusacoes: dict) -> list[list[dict]]:
    """Os condenados, em grupos. Um grupo = um defeito.

    Preserva a ordem de entrada (que o juiz ja ordenou por severidade): o grupo
    aparece na posicao do seu primeiro membro, e quem nao funde sai sozinho.
    """
    baldes: dict[tuple, list[list[dict]]] = {}
    saida: list[list[dict]] = []
    for v in condenados:
        a = acusacoes.get(v.get("id"), {})
        k = chave(a)
        if k is None:
            saida.append([v])
            continue
        faixa = _faixa(a.get("local_normalizado") or a.get("local"))
        grupos = baldes.setdefault(k, [])
        for g in grupos:
            if _vizinho(g, faixa, acusacoes):
                g.append(v)
                break
        else:
            novo = [v]
            grupos.append(novo)
            saida.append(novo)
    return saida


def _vizinho(grupo: list[dict], faixa, acusacoes: dict) -> bool:
    """A faixa encosta em algum membro do grupo, dentro da tolerancia?

    ⚠️ Compara contra cada MEMBRO, e isso ENCADEIA: 103 e 105 fundem, e ai 107
    funde com 105. Escrevi este comentario dizendo que comparar por membro
    evitava a cadeia -- e' falso, e o teste `test_a_vizinhanca_ENCADEIA` existe
    para o proximo leitor nao herdar a minha versao errada.

    A cadeia e' aceitavel AQUI, e por um motivo que nao vale um nivel acima: o
    balde ja exige procedencia identica, entao o encadeamento so' anda dentro de
    acusacoes que citam a MESMA regra do MESMO arquivo de documentacao. Um
    defeito que ocupa um corpo de funcao inteiro deve mesmo fundir; capar o
    alcance do grupo quebraria a funcao longa e legitima.

    A tolerancia continua 2 porque o erro caro e' o outro: fundir defeitos
    distintos que por acaso moram perto.
    """
    _, primeira, ultima = faixa
    for m in grupo:
        outra = _faixa((acusacoes.get(m.get("id"), {}) or {}).get("local_normalizado")
                       or (acusacoes.get(m.get("id"), {}) or {}).get("local"))
        if outra is None:
            continue
        _, p, u = outra
        if primeira - TOLERANCIA_LINHAS <= u and p - TOLERANCIA_LINHAS <= ultima:
            return True
    return False


def local_do_grupo(grupo: list[dict], acusacoes: dict) -> str:
    """`app/main.py:103-104` -- a extensao real do defeito, nao a de um membro.

    O leitor recebe UM lugar para olhar, e ele cobre o que as lentes apontaram.
    """
    arquivo, menor, maior = None, None, None
    for v in grupo:
        a = acusacoes.get(v.get("id"), {}) or {}
        faixa = _faixa(a.get("local_normalizado") or a.get("local"))
        if faixa is None:
            continue
        arq, p, u = faixa
        arquivo = arquivo or arq
        menor = p if menor is None else min(menor, p)
        maior = u if maior is None else max(maior, u)
    if arquivo is None:
        a = acusacoes.get(grupo[0].get("id"), {}) or {}
        return str(a.get("local_normalizado") or a.get("local") or "?")
    return f"{arquivo}:{menor}" if menor == maior else f"{arquivo}:{menor}-{maior}"


def lentes(grupo: list[dict], acusacoes: dict) -> list[str]:
    """As categorias que convergiram, sem repetir e em ordem estavel.

    ⚠️ Sao lentes do MESMO modelo, nao peritos independentes. Quem imprimir isto
    diz "lentes", nunca "N revisores concordaram" -- a distincao e' a mesma que
    `_corroborado` guarda em promotores.py, e ela ja existe porque alguem quase
    montou slide em cima do campo errado.
    """
    fora, vistas = [], set()
    for v in grupo:
        c = (acusacoes.get(v.get("id"), {}) or {}).get("categoria")
        if c and c not in vistas:
            vistas.add(c)
            fora.append(c)
    return fora
