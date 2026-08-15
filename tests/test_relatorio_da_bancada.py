"""O relatorio da rodada paga sobrevive a um acento? -- travas de 15/08.

🚨 O caso real, e ele custou uma rodada inteira. O orquestrador rodou, gastou,
gravou tudo em `saidas/rodadas/20260815T2043-7df223d/` -- e o `roda_bancada`
morreu na linha que IMPRIME a saida dele:

    UnicodeEncodeError: 'charmap' codec can't encode character '\\ufffd'

O confronto com o gabarito teve que ser reconstruido do disco a mao. A medicao
nao se perdeu por sorte: os artefatos ja estavam gravados quando a impressao
quebrou.

A cadeia tem duas camadas, e travar so' uma nao resolve:

  causa     no Windows, stdout de processo Python ligado a PIPE assume a
            localidade (cp1252), nao UTF-8. O pai decodifica como UTF-8, entao
            todo acento vira `\\ufffd` -- e o relatorio sai ilegivel mesmo
            quando nao levanta.
  sintoma   imprimir esse `\\ufffd` num console cp1252 levanta.

⚠️ O `errors="replace"` do `subprocess.run` protegia a DECODIFICACAO e nao a
impressao. Guarda que existe e fica muda exatamente onde precisa falar: o
padrao de bug do projeto, desta vez no arnes de medicao.
"""

import os
import subprocess
import sys
import textwrap

import pytest

_ENV = dict(os.environ)
import roda_bancada as rb  # noqa: E402
os.environ.clear()
os.environ.update(_ENV)


# --------------------------------------------------- a causa, no filho

def test_o_filho_recebe_PYTHONIOENCODING(monkeypatch):
    """Sem isto o filho escreve cp1252 e cada acento chega como `\\ufffd`.

    ⚠️ A primeira versao desta trava vasculhava o bytecode de `roda` atras do
    nome. Errado por dois motivos: `PYTHONIOENCODING` entra como keyword de
    `dict()` e mora numa tupla de `co_consts`, e mesmo achando, presenca no
    fonte nao e' entrega ao filho. A pergunta certa e' o que o subprocess
    RECEBE, entao a trava intercepta a chamada.
    """
    visto = {}

    class _R:
        stdout, stderr, returncode = "", "", 1

    monkeypatch.setattr(rb, "prepara_o_app", lambda ramo: None)
    monkeypatch.setattr(rb.subprocess, "run",
                        lambda *a, **k: (visto.update(k), _R())[1])
    rb.roda("pr/x", 3)

    env = visto.get("env") or {}
    assert env.get("PYTHONIOENCODING", "").lower() in ("utf-8", "utf8"), (
        f"o orquestrador foi chamado sem PYTHONIOENCODING=utf-8: {env.get('PYTHONIOENCODING')!r}"
    )
    # A leitura do lado do pai tem que casar com o que o filho passa a escrever.
    enc = visto.get("encoding")
    assert enc and enc.lower() in ("utf-8", "utf8"), (
        f"o pai le como {enc!r}, mas manda o filho escrever utf-8"
    )


def test_python_num_pipe_sem_a_variavel_NAO_e_utf8():
    """A premissa do conserto, medida em vez de suposta.

    Se um dia o Python passar a usar UTF-8 em pipe por padrao (PEP 686), este
    teste vira vermelho e avisa que a causa mudou -- em vez de o conserto virar
    supersticao que ninguem ousa remover.
    """
    r = subprocess.run(
        [sys.executable, "-c", "import sys; print(sys.stdout.encoding)"],
        capture_output=True, text=True,
    )
    atual = r.stdout.strip().lower()
    r2 = subprocess.run(
        [sys.executable, "-c", "import sys; print(sys.stdout.encoding)"],
        capture_output=True, text=True,
        env=dict(os.environ, PYTHONIOENCODING="utf-8"),
    )
    assert r2.stdout.strip().lower() in ("utf-8", "utf8"), (
        f"PYTHONIOENCODING nao surtiu efeito (deu {r2.stdout.strip()})"
    )
    if atual in ("utf-8", "utf8"):
        pytest.skip("esta plataforma ja usa UTF-8 em pipe; o conserto virou rede")


# --------------------------------------------------- o sintoma, vendo falhar

_IMPRIME = "import sys; sys.stdout.write('acento: \\ufffd\\n')"


def _roda_com_console_cp1252(preludio: str) -> subprocess.CompletedProcess:
    """Reproduz o console do Windows: stdout em cp1252, sem PYTHONIOENCODING."""
    env = dict(os.environ)
    env.pop("PYTHONIOENCODING", None)
    return subprocess.run(
        [sys.executable, "-c", preludio + "; " + _IMPRIME],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env,
    )


def test_a_guarda_vista_FALHANDO_sem_o_conserto():
    """O controle. Sem reconfigurar o stdout, imprimir `\\ufffd` levanta.

    Sem este teste nao ha como saber se o de baixo passa pelo conserto ou
    porque a plataforma nunca teve o problema.
    """
    r = _roda_com_console_cp1252(
        "import sys, io; "
        "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='cp1252')"
    )
    if r.returncode == 0:
        pytest.skip("cp1252 indisponivel nesta plataforma: o defeito nao existe aqui")
    assert "UnicodeEncodeError" in r.stderr, r.stderr[-300:]


def test_com_o_conserto_o_relatorio_sai_em_vez_de_matar_a_rodada():
    """A trava. Mesmo console, mesmo caractere, com o `errors='replace'`.

    O `?` no lugar do acento e' aceitavel; perder o relatorio de uma rodada
    paga nao e'.
    """
    r = _roda_com_console_cp1252(
        "import sys, io; "
        "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='cp1252'); "
        "sys.stdout.reconfigure(encoding='cp1252', errors='replace')"
    )
    assert r.returncode == 0, f"a impressao ainda derruba: {r.stderr[-300:]}"
    assert "acento:" in r.stdout


def test_o_modulo_reconfigura_os_dois_fluxos():
    """stderr tambem: o diagnostico de rodada que falhou sai por la.

    Travar so' o stdout deixaria a mensagem de erro -- justamente a que carrega
    o caminho e o motivo -- morrendo pelo mesmo bug.
    """
    codigo = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(rb.RAIZ)!r})
        import roda_bancada
        print(sys.stdout.errors, sys.stderr.errors)
    """)
    r = subprocess.run([sys.executable, "-c", codigo],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    assert r.returncode == 0, r.stderr[-400:]
    assert r.stdout.split() == ["replace", "replace"], r.stdout
