"""Uma fonte de verdade para a configuracao -- e aviso quando nao ha.

🚨 Custou quatro tentativas em 14/08. A chave da Anthropic estava na variavel de
ambiente do Windows (via `setx`) E no `.env`. `load_dotenv` nao sobrescreve
variavel que ja existe, entao a do Windows vencia: trocar o `.env` nao mudava
nada e o 401 continuava IDENTICO, parecendo problema de conta.

Nao da' para ligar `override=True` -- e' o que faz
`APP_EM_BANCO_DESCARTAVEL=1 py -3.12 ...` funcionar na linha de comando. Entao
a saida e' AVISAR, e o aviso e' o que estes testes travam.
"""

import pytest

from veredito import config as cfg


@pytest.fixture
def env_falso(tmp_path, monkeypatch):
    """Um .env de mentira, e o config apontado para ele."""
    monkeypatch.setattr(cfg, "RAIZ", tmp_path)
    return tmp_path / ".env"


def test_valor_do_sistema_diferente_e_denunciado(env_falso, monkeypatch):
    env_falso.write_text("ANTHROPIC_API_KEY=chave-do-arquivo\n", encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-do-sistema")
    assert cfg.variaveis_ensombradas() == ["ANTHROPIC_API_KEY"]


def test_valores_iguais_nao_sao_denunciados(env_falso, monkeypatch):
    """Duplicado mas concordando nao atrapalha ninguem -- barulho a toa treina o
    operador a ignorar o aviso, e ai ele nao serve quando importa."""
    env_falso.write_text("ANTHROPIC_API_KEY=mesma\n", encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "mesma")
    assert cfg.variaveis_ensombradas() == []


def test_variavel_so_no_arquivo_nao_e_ensombrada(env_falso, monkeypatch):
    """O caso normal: o .env e' a unica fonte."""
    env_falso.write_text("SO_NO_ARQUIVO=x\n", encoding="utf-8")
    monkeypatch.delenv("SO_NO_ARQUIVO", raising=False)
    assert cfg.variaveis_ensombradas() == []


def test_variavel_so_no_sistema_nao_e_ensombrada(env_falso, monkeypatch):
    """Nada no .env para ser ensombrado. Passar variavel na linha de comando
    para uma chave que o arquivo nao define e' uso normal."""
    env_falso.write_text("OUTRA=1\n", encoding="utf-8")
    monkeypatch.setenv("APP_EM_BANCO_DESCARTAVEL", "1")
    assert "APP_EM_BANCO_DESCARTAVEL" not in cfg.variaveis_ensombradas()


def test_denuncia_todas_e_em_ordem(env_falso, monkeypatch):
    env_falso.write_text("B=1\nA=1\nC=1\n", encoding="utf-8")
    monkeypatch.setenv("A", "2")
    monkeypatch.setenv("B", "2")
    monkeypatch.setenv("C", "1")      # concorda, fica de fora
    assert cfg.variaveis_ensombradas() == ["A", "B"]


def test_sem_env_nao_levanta(tmp_path, monkeypatch):
    """Maquina recem-clonada nao tem .env. Nao pode explodir no pre-voo."""
    monkeypatch.setattr(cfg, "RAIZ", tmp_path)
    assert cfg.variaveis_ensombradas() == []


# ------------------------------------------------ 🚨 o segredo nao vaza

def test_devolve_so_nomes_nunca_valores(env_falso, monkeypatch):
    """Imprimir os dois lados para comparar seria vazar a chave no log da
    rodada -- e o log e' o que a gente cola em relatorio e manda para o socio.
    """
    env_falso.write_text("ANTHROPIC_API_KEY=sk-ant-SEGREDO-DO-ARQUIVO\n",
                         encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-SEGREDO-DO-SISTEMA")
    saida = cfg.variaveis_ensombradas()
    junto = " ".join(saida)
    assert "SEGREDO" not in junto, "o valor da variavel vazou no retorno"
    assert saida == ["ANTHROPIC_API_KEY"]


# ------------------------------------------- o override continua desligado

def test_o_dotenv_nao_sobrescreve_o_ambiente():
    """Se alguem ligar `override=True` para "resolver" a divergencia, quebra
    `APP_EM_BANCO_DESCARTAVEL=1 py -3.12 ...` -- que e' como se liga a contencao
    para uma rodada so'. O aviso existe JUSTAMENTE para nao precisar do override.
    """
    # ⚠️ Estrutural, nao substring: o proprio comentario do config explica por
    # que NAO usa override=True, e um `in fonte` casaria com a explicacao. Foi
    # exatamente assim que a primeira versao deste teste falhou.
    import ast
    from pathlib import Path
    fonte = Path(cfg.__file__).read_text(encoding="utf-8-sig")

    chamadas = [n for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call)
                and getattr(n.func, "id", None) == "load_dotenv"]
    assert chamadas, "config.py deixou de carregar o .env"
    for c in chamadas:
        ligado = [k for k in c.keywords
                  if k.arg == "override" and getattr(k.value, "value", False) is True]
        assert not ligado, (
            "load_dotenv(override=True) faz o .env vencer a linha de comando e "
            "mata `APP_EM_BANCO_DESCARTAVEL=1 py -3.12 ...`, que e' a forma "
            "documentada de ligar a contencao por uma rodada so'")
