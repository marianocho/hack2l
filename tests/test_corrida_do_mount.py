"""A corrida do bind-mount, ROTULADA -- opcao 2 da fila (19/08).

O sintoma: o arquivo de teste esta gravado no worktree do host e o container
nao o enxerga. `ERROR: file or directory not found`, exit 4, um lado so'.
Intermitente, medido -- tres execucoes do mesmo arquivo sem tocar em codigo
deram conjuntos DIFERENTES de falha.

✅ Ela ja falha para o lado seguro (exit 4 => sem resumo => `rodou` False =>
`erro` => R3 => INCONCLUSIVO). Nada aqui afrouxa isso, e ha trava para o caso.
🚨 O que ela custa e' o motivo APONTAR PARA O PR. Este modulo so' NOMEIA.

🚨 O QUE ESTAS TRAVAS PRECISAM PROVAR, e nao e' "o rotulo aparece":

    1. que ele aparece quando e' corrida               (test_rotulada_*)
    2. que ele NAO aparece quando e' `veredito.yml` torto -- que produz a
       assinatura IDENTICA, e onde culpar o Docker mandaria o operador
       consertar a coisa errada                        (test_os_dois_lados_*)
    3. que ele NAO aparece quando o arquivo realmente nao foi gravado, que e'
       defeito de verdade e tem que continuar gritando (test_arquivo_ausente_*)
    4. que ele consegue ficar QUIETO numa rodada sadia (test_rodada_sadia_*)
    5. que ele nao muda veredito nenhum                (test_o_rotulo_nao_muda_*)

⚠️ O dublê do pytest NAO escolhe o terceiro valor a mao: ele passa a saida pelo
`_RESUMO_PYTEST` DE VERDADE. Escolher `rodou` no dublê seria medir a minha
opiniao sobre o que conta como "o pytest rodou", e a corrida vive justamente na
diferenca entre o exit code do docker e o do pytest.
"""
import pathlib

import pytest

from veredito import config as cfg
from veredito import ferramentas as f
from veredito import juiz


# ------------------------------------------------------------------ saidas
# Texto de pytest de verdade, verbatim no que importa: a linha de resumo (que o
# `_RESUMO_PYTEST` procura) e a linha de erro de uso (que o rotulo procura).

PASSOU = ".                                                  [100%]\n1 passed in 0.31s\n"
FALHOU = "F                                                  [100%]\n1 failed in 0.29s\n"
NAO_ACHOU = "ERROR: file or directory not found: {alvo}\n\n"
NAO_ACHOU_OUTRO = "ERROR: file or directory not found: conftest.py\n\n"


@pytest.fixture
def projeto(monkeypatch, tmp_path):
    """Dois worktrees com o diretorio de testes, e o layout declarado."""
    wts = {}
    for lado in ("base", "head"):
        wt = tmp_path / lado
        (wt / "app" / "tests").mkdir(parents=True)
        wts[lado] = wt
    monkeypatch.setattr(cfg, "TEM_PROVA_DIFERENCIAL", True)
    monkeypatch.setattr(cfg, "CODIGO_TESTES", "tests")
    monkeypatch.setattr(cfg, "CODIGO_TESTES_NO_REPO", "app/tests")
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path / "art")
    monkeypatch.setattr(cfg, "PERMITIR_REDE_NO_BASE", True)  # sem contencao no dublê
    monkeypatch.setattr(f, "commit_base", lambda: "a" * 40)
    monkeypatch.setattr(f, "commit_head", lambda: "b" * 40)
    monkeypatch.setattr(f, "_garante_worktree", lambda commit, nome: wts[nome])
    # O canario tem trava propria; aqui ele so' nao pode atrapalhar.
    monkeypatch.setattr(f, "_canario_das_montagens",
                        lambda lado="head": {"aplica": False, "ok": True, "erro": None})
    return wts


def _duble_do_pytest(monkeypatch, wts, plano, apaga=()):
    """`plano`: {lado: (exit, texto)}. `apaga`: lados cujo arquivo some do disco.

    O texto passa pelo `_RESUMO_PYTEST` real para produzir o terceiro valor.
    """
    inverso = {v: k for k, v in wts.items()}
    chamadas = []

    def duble(worktree, alvo="tests", contido=False):
        lado = inverso[pathlib.Path(worktree)]
        chamadas.append(lado)
        codigo, texto = plano[lado]
        texto = texto.format(alvo=alvo)
        if lado in apaga:
            # "o arquivo nunca chegou a ser gravado" -- o defeito de verdade.
            pasta = pathlib.Path(worktree) / cfg.CODIGO_TESTES_NO_REPO
            for p in pasta.glob("*.py"):
                p.unlink()
        return codigo, texto, bool(f._RESUMO_PYTEST.search(texto))

    monkeypatch.setattr(f, "_roda_pytest", duble)
    return chamadas


def _prova(nome="test_alvo.py"):
    f.define_acusacao("corrida_" + nome.replace(".py", ""))
    return f._prova_diferencial("def test_x():\n    assert True\n", nome)


# ------------------------------------------------ 1. a guarda, quando e' corrida

def test_rotulada_quando_um_lado_so_nao_ve_o_arquivo(projeto, monkeypatch):
    """O caso capturado em 19/08: base roda, head nao enxerga o arquivo."""
    _duble_do_pytest(monkeypatch, projeto,
                     {"base": (0, PASSOU), "head": (4, NAO_ACHOU)})
    art = _prova()

    assert art["corrida_do_mount"] is True, art["erro"]
    d = art["corrida_do_mount_detalhe"]
    assert d["lado"] == "head"
    assert d["alvo"] == "tests/test_alvo.py"
    assert "app/tests" in d["no_disco"].replace("\\", "/")
    assert d["exit"] == 4

    # O texto tem que dizer de quem e' a culpa, e nao so' que algo falhou.
    assert "NAO e' defeito do PR" in art["erro"]
    assert "pytest nao executou" not in art["erro"], (
        "a frase antiga se le como culpa do repositorio -- e' o que se conserta aqui")
    # A saida crua continua no `erro`: rotulo nao substitui evidencia.
    assert "file or directory not found" in art["erro"]


def test_a_corrida_tambem_e_pega_no_lado_base(projeto, monkeypatch):
    """E' corrida, nao propriedade do head. O rotulo nao pode ser assimetrico."""
    _duble_do_pytest(monkeypatch, projeto,
                     {"base": (4, NAO_ACHOU), "head": (1, FALHOU)})
    art = _prova("test_no_base.py")
    assert art["corrida_do_mount"] is True
    assert art["corrida_do_mount_detalhe"]["lado"] == "base"


# ------------------------- 2. a violacao que a guarda NAO pode chamar de corrida

def test_os_dois_lados_negando_o_alvo_NAO_e_corrida(projeto, monkeypatch):
    """🚨 A trava mais importante do arquivo.

    `codigo.testes` apontando para fora do que `codigo.montagens` monta produz
    a assinatura IDENTICA -- mesma frase, mesmo exit 4, e o arquivo TAMBEM esta
    no worktree do host. E' o item 3 das cinco suposicoes chumbadas que o
    `pallets/flask` expos em 17/08.

    O que separa os dois: config errada falha nos DOIS lados, sempre; corrida
    falha em UM. Sem esta distincao o rotulo mandaria o operador culpar o
    Docker Desktop por um `veredito.yml` torto -- guarda condicionada a um
    sinal VIZINHO do que ela deveria vigiar, o padrao de bug da casa.
    """
    _duble_do_pytest(monkeypatch, projeto,
                     {"base": (4, NAO_ACHOU), "head": (4, NAO_ACHOU)})
    art = _prova("test_config_torta.py")

    assert art["corrida_do_mount"] is False
    assert art["corrida_do_mount_detalhe"] is None
    # E continua gritando, nomeando o alvo que nao resolveu: e' por ele que o
    # operador acha o campo errado no veredito.yml.
    assert "tests/test_config_torta.py" in art["erro"]
    assert art["estado"] == "INCONCLUSIVO"


def test_arquivo_ausente_no_worktree_NAO_e_corrida(projeto, monkeypatch):
    """O defeito de VERDADE: o arquivo nao foi gravado. Tem que continuar cru.

    E' o caso que a recusa de 17/08 (`testes_no_repo` errado) existe para
    gritar, e e' exatamente o que um retry cego esconderia.
    """
    _duble_do_pytest(monkeypatch, projeto,
                     {"base": (0, PASSOU), "head": (4, NAO_ACHOU)},
                     apaga=("head",))
    art = _prova("test_sumiu.py")

    assert art["corrida_do_mount"] is False
    assert "pytest nao executou no head" in art["erro"]


def test_not_found_de_OUTRO_caminho_NAO_e_corrida(projeto, monkeypatch):
    """Conftest, plugin, `-p` de alguem: mesma frase, outro alvo.

    Chamar tudo de corrida seria a guarda morrendo de EXCESSO -- o modo de
    falha do `NAO MEDIDO` do banco, em 17/08. Alarme que dispara sempre ensina
    a pular a linha.
    """
    _duble_do_pytest(monkeypatch, projeto,
                     {"base": (0, PASSOU), "head": (4, NAO_ACHOU_OUTRO)})
    art = _prova("test_outro.py")
    assert art["corrida_do_mount"] is False


def test_o_outro_lado_tambem_mudo_NAO_e_corrida(projeto, monkeypatch):
    """Ninguem provou que o alvo resolve. Sem isso nao da para culpar o host.

    Docker caindo entre as duas execucoes produz exit sem resumo dos dois
    lados; atribuir ao bind-mount seria inventar uma causa.
    """
    _duble_do_pytest(monkeypatch, projeto,
                     {"base": (1, "Cannot connect to the Docker daemon\n"),
                      "head": (4, NAO_ACHOU)})
    art = _prova("test_docker_fora.py")
    assert art["corrida_do_mount"] is False


# --------------------------------- 3. ela consegue ficar QUIETA? (pergunta 0)

@pytest.mark.parametrize("plano,estado", [
    ({"base": (0, PASSOU), "head": (1, FALHOU)}, "PROVADO"),
    ({"base": (0, PASSOU), "head": (0, PASSOU)}, "REFUTADO"),
])
def test_rodada_sadia_fica_quieta(projeto, monkeypatch, plano, estado):
    """Guarda que alarma em todo caso ensina o leitor a pular justamente ela."""
    _duble_do_pytest(monkeypatch, projeto, plano)
    art = _prova("test_sadio.py")
    assert art["estado"] == estado, art["motivo"]
    assert art["corrida_do_mount"] is False
    assert art["corrida_do_mount_detalhe"] is None


def test_o_campo_existe_mesmo_nas_saidas_que_voltam_cedo(projeto, monkeypatch):
    """Chave derivada de campo que some e' o dedup de novo. Ela nasce no molde."""
    monkeypatch.setattr(cfg, "TEM_PROVA_DIFERENCIAL", False)
    art = _prova("test_sem_layout.py")
    assert art["indisponivel"]
    assert art["corrida_do_mount"] is False, "ausente nao pode virar KeyError na T1"


# ------------------------------------ 4. rotulo nao e' regra: o veredito nao muda

def test_o_rotulo_nao_muda_o_veredito_nem_afrouxa_a_R3(projeto, monkeypatch):
    """A corrida continua custando um INCONCLUSIVO. E' o preco da opcao 2.

    🚨 Se o rotulo esvaziasse o `erro`, a R3 pararia de converter e a corrida
    viraria REFUTADO -- absolvicao falsa produzida pelo conserto. Esta trava
    prende as duas pontas: o campo aparece E a R3 continua disparando.
    """
    _duble_do_pytest(monkeypatch, projeto,
                     {"base": (0, PASSOU), "head": (4, NAO_ACHOU)})
    art = _prova("test_r3.py")

    assert art["corrida_do_mount"] is True
    assert art["estado"] == "INCONCLUSIVO"
    assert art["provado"] is False
    assert art["erro"], "sem `erro` a R3 nao converte, e a corrida viraria absolvicao"

    v = juiz.aplica_regras(
        {"veredito": "REFUTADO", "severidade": "MEDIA", "confianca": "alta"},
        {"id": "x", "categoria": "correcao", "local": "app/main.py:10"},
        art,
    )
    assert v["veredito"] == "INCONCLUSIVO", v


def test_o_advogado_e_avisado_para_nao_reescrever_o_teste(projeto, monkeypatch):
    """Sem isto ele le "not found", conclui que errou o teste, e gasta voltas."""
    _duble_do_pytest(monkeypatch, projeto,
                     {"base": (0, PASSOU), "head": (4, NAO_ACHOU)})
    art = _prova("test_aviso.py")
    texto = f._formata_prova(art)
    assert "CORRIDA DO BIND-MOUNT" in texto
    assert "NAO o reescreva" in texto


# ------------------------------------------------- 5. o detector, na unidade

def test_sinal_exige_o_alvo_EXATO_e_o_arquivo_em_disco(tmp_path):
    alvo = "tests/test_x.py"
    existe = tmp_path / "test_x.py"
    existe.write_text("x", encoding="utf-8")
    sumiu = tmp_path / "nao_existe.py"

    assert f._sinal_da_corrida(NAO_ACHOU.format(alvo=alvo), alvo, existe) is True
    assert f._sinal_da_corrida(NAO_ACHOU.format(alvo=alvo), alvo, sumiu) is False
    assert f._sinal_da_corrida(NAO_ACHOU_OUTRO, alvo, existe) is False
    assert f._sinal_da_corrida(PASSOU, alvo, existe) is False
    assert f._sinal_da_corrida("", alvo, existe) is False
