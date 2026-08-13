"""Alarme que derruba o programa nao e' alarme.

🚨 Achado em 11/08, rodando o controle negativo: o aviso "app fora do ar" no
orquestrador tinha um ⚠ e estourava UnicodeEncodeError no console cp1252 do
Windows -- matando a rodada inteira.

Ele so dispara quando o app esta fora. Como a stack ficou de pe o dia todo, o
bug nunca tinha aparecido. E ao procurar, TODOS os cinco prints com emoji do
projeto estavam em caminho de alarme: contaminacao do arbitro, inconclusivo em
massa, cache zero, regua contaminada. Cada um so' roda quando algo deu errado.

E' o padrao de bug deste projeto (ver CLAUDE.md) na forma mais pura: a guarda
existe, mora no caminho degradado, e quebra exatamente la.

⚠️ Emoji em COMENTARIO e DOCSTRING continua permitido -- nunca vai ao console.
O que nao pode e' emoji dentro de `print`.

Nao bate na API.
"""
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
FONTES = sorted(RAIZ.glob("*.py")) + sorted((RAIZ / "veredito").glob("*.py"))

# O console do Windows nesta maquina e' cp1252. Travessao e aspas curvas cabem;
# emoji nao.
_PRINT = re.compile(r"print\(.*", re.S)


def _linhas_de_print(texto: str):
    for n, linha in enumerate(texto.splitlines(), 1):
        if "print(" in linha:
            yield n, linha


@pytest.mark.parametrize("arq", FONTES, ids=lambda p: p.name)
def test_nenhum_print_tem_caractere_que_o_console_nao_imprime(arq):
    ruins = []
    for n, linha in _linhas_de_print(arq.read_text(encoding="utf-8")):
        try:
            linha.encode("cp1252")
        except UnicodeEncodeError:
            fora = {c for c in linha if not _cabe(c)}
            ruins.append(f"{arq.name}:{n} {''.join(sorted(fora))}")
    assert not ruins, (
        "print com caractere que o console cp1252 nao imprime -- vai estourar "
        f"UnicodeEncodeError quando a linha rodar: {ruins}"
    )


def _cabe(c: str) -> bool:
    try:
        c.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False
