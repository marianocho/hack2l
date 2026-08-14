"""As regras de taint. Nenhum teste aqui roda o semgrep.

O que se trava e' o CONTRATO do arquivo de regras, que quebra em silencio de
tres jeitos diferentes -- e nos tres o semgrep continua rodando e devolvendo
achado, so' que pior. Achado pior nao falha nada: ele so' faz o advogado gastar
volta de laco descobrindo o que a regra ja sabia.
"""

import re
from pathlib import Path

import pytest
import yaml

from veredito import config as cfg

REGRAS = cfg.RAIZ / "regras_semgrep" / "taint.yml"


def _bruto() -> str:
    return REGRAS.read_text(encoding="utf-8")


def _regras() -> list[dict]:
    return yaml.safe_load(_bruto())["rules"]


def test_o_arquivo_de_regras_existe():
    assert REGRAS.is_file(), f"sem {REGRAS}, fontes._semgrep devolve [] em silencio"


# ------------------------------------------------- o ganho de 14/08: $PARAM

def test_toda_mensagem_diz_qual_e_o_parametro():
    """A mensagem tem que nomear a variavel suspeita, nao so' dizer que existe.

    O semgrep JA sabe qual parametro casou -- e' o `$PARAM` do pattern. Ate'
    13/08 ele jogava fora na hora de escrever a mensagem, e o texto que chegava
    ao advogado era "Parametro controlado pelo cliente alcanca db.execute()".
    Qual parametro? Ele tinha que abrir o arquivo para descobrir, e essa e' uma
    volta do laco do modelo caro, gasta para redescobrir o que a ferramenta ja
    tinha na mao.
    """
    sem = [r["id"] for r in _regras() if "$PARAM" not in r.get("message", "")]
    assert not sem, (
        f"regra cuja mensagem nao nomeia o parametro: {sem}. "
        "O semgrep interpola metavariavel na mensagem -- use $PARAM.")


def test_metavariavel_da_mensagem_existe_na_regra():
    """🚨 Typo em metavariavel degrada em SILENCIO.

    `$PARM` no lugar de `$PARAM` nao e' erro para o semgrep: ele nao encontra o
    que substituir e imprime o texto literal. A acusacao chega ao advogado
    dizendo "O parametro $PARM alcanca..." -- pior que a mensagem generica que
    havia antes, e nada falha. E' o padrao de bug do projeto: a regra continua
    valendo, so' que muda.
    """
    problemas = {}
    for r in _regras():
        msg = r.get("message", "")
        # O corpo da regra sem a mensagem: e' onde as metavariaveis nascem.
        corpo = yaml.safe_dump({k: v for k, v in r.items() if k != "message"})
        soltas = {m for m in re.findall(r"\$[A-Z_]+", msg) if m not in corpo}
        if soltas:
            problemas[r["id"]] = sorted(soltas)
    assert not problemas, (
        f"metavariavel usada na mensagem e nunca casada na regra: {problemas}. "
        "O semgrep vai imprimir o cifrao literal na acusacao.")


# --------------------------------------------- a armadilha ja documentada

def test_o_arquivo_nao_tem_acento():
    """Medido em 11/08 e anotado no cabecalho do proprio arquivo: no Windows o
    semgrep le o config com o codepage ANSI (cp1252) e morre com
    UnicodeDecodeError se houver acento. A rodada perde a fonte externa inteira
    -- e perde CALADA, porque `fontes._semgrep` devolve [] quando nao consegue
    parsear a saida.
    """
    fora = [(i, l) for i, l in enumerate(_bruto().splitlines(), 1)
            if not l.isascii()]
    assert not fora, (
        f"caractere nao-ASCII em taint.yml (linha, conteudo): {fora[:5]}. "
        "O semgrep no Windows le este arquivo como cp1252 e nao sobe.")


# ------------------------------------------------------- sanidade estrutural

def test_toda_regra_tem_fonte_e_sink():
    """Regra de taint sem os dois lados nao afirma caminho nenhum -- e caminho
    e' o motivo de existir taint aqui, em vez de padrao."""
    faltando = {}
    for r in _regras():
        ausentes = [c for c in ("pattern-sources", "pattern-sinks") if not r.get(c)]
        if ausentes:
            faltando[r["id"]] = ausentes
    assert not faltando, f"regra de taint incompleta: {faltando}"


@pytest.mark.parametrize("campo", ["categoria", "tipo-de-alegacao"])
def test_toda_regra_traz_metadado_de_categoria(campo):
    """`categoria` roteia a acusacao para a cota certa do juiz. Sem ela o
    achado do scanner cai fora do sistema de cotas."""
    sem = [r["id"] for r in _regras() if campo not in (r.get("metadata") or {})]
    assert not sem, f"regra sem metadata.{campo}: {sem}"
