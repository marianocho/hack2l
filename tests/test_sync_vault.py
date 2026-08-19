"""A trava contra a copia que envelhece em silencio.

🚨 O CASO REAL, 19/08. O mesmo quadro vivia em tres lugares, e o `Onde
retomar.md` declarava como sua FONTE um `fontes/PROXIMOS_PASSOS.md` que estava
em **11/08** -- oito dias atras do repo. A fonte declarada era a copia mais
velha das tres, e nada avisava.

⚠️ ESTE ARQUIVO TESTA A LOGICA, NAO A MAQUINA. Quase tudo aqui roda contra
diretorios sinteticos em `tmp_path`, sem vault nenhum. So' UM teste olha o vault
de verdade, e ele PULA quando a variavel nao esta definida.

Isso e' deliberado e e' a licao 5 do "como procurar": trava que so' funciona
onde o vault existe seria trava que nao existe para o Mariano, nem na CI, nem em
maquina nova -- e o `hack2l` e' publico. A logica tem que ser conferivel sem
nada instalado.
"""
import importlib.util
import os
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "sync_vault", RAIZ / "scripts" / "sync_vault.py")
sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync)


@pytest.fixture
def espelho(tmp_path, monkeypatch):
    """Um repo de mentira e um `fontes/` de mentira, em dia."""
    repo, fontes = tmp_path / "repo", tmp_path / "fontes"
    repo.mkdir()
    fontes.mkdir()
    for nome, texto in [("A.md", "# A\n\nlinha um\n"), ("B.md", "# B\n\noutra\n")]:
        (repo / nome).write_text(texto, encoding="utf-8")
        (fontes / nome).write_text(texto, encoding="utf-8")
    monkeypatch.setattr(sync, "RAIZ", repo)
    monkeypatch.setattr(sync, "ESPELHOS_DE_FORA", {})
    return repo, fontes


# ------------------------------------------------ a trava, VISTA FALHANDO

def test_em_dia_nao_acusa(espelho):
    _, fontes = espelho
    e = sync.confere(fontes)
    assert e["divergentes"] == []
    assert sorted(e["iguais"]) == ["A.md", "B.md"]


def test_conteudo_diferente_E_PEGO(espelho):
    """🚨 A violacao injetada: o repo andou e o espelho ficou."""
    repo, fontes = espelho
    (repo / "A.md").write_text("# A\n\nlinha um\nlinha DOIS, nova\n", encoding="utf-8")
    e = sync.confere(fontes)
    assert e["divergentes"] == ["A.md"]
    assert e["iguais"] == ["B.md"], "so' o que mudou pode ser acusado"


def test_espelho_vazio_e_pego(espelho):
    repo, fontes = espelho
    (fontes / "B.md").write_text("", encoding="utf-8")
    assert sync.confere(fontes)["divergentes"] == ["B.md"]


# ------------------------------ a guarda consegue ficar QUIETA (licao 0)

@pytest.mark.parametrize("ruido, apelido", [
    ("\r\n", "CRLF contra LF"),
    ("   \n", "espaco no fim da linha"),
])
def test_fim_de_linha_e_espaco_NAO_sao_divergencia(espelho, ruido, apelido):
    """🚨 Medido em 19/08: 5 das 6 divergencias que o `cmp` acusava eram SO'
    fim de linha -- o repo tem CRLF (git no Windows) e o vault tem LF.

    Trava por byte acusaria os 6 em toda execucao, para sempre. Alarme que
    dispara sempre ensina a pular justamente a linha que existe para o caso
    raro: a guarda morrendo de EXCESSO, que da' no mesmo que morrer de falta.
    """
    repo, fontes = espelho
    base = "# A\n\nlinha um\n"
    (repo / "A.md").write_bytes(base.replace("\n", ruido).encode("utf-8"))
    (fontes / "A.md").write_bytes(base.encode("utf-8"))
    assert sync.confere(fontes)["divergentes"] == [], f"{apelido} nao e' divergencia"


def test_BOM_nao_e_divergencia(espelho):
    repo, fontes = espelho
    (repo / "A.md").write_bytes(b"\xef\xbb\xbf" + b"# A\n\nlinha um\n")
    assert sync.confere(fontes)["divergentes"] == []


def test_sem_variavel_e_NAO_SE_APLICA_e_sai_zero(monkeypatch, capsys):
    """🚫 NAO SE APLICA nao e' NAO MEDIDO, e nao e' falha.

    O `hack2l` e' publico. Maquina sem vault -- a do Mariano, a CI, uma nova --
    nao tem divergencia de vault. Fazer isso falhar transformaria um limite
    honesto em erro vermelho que todo mundo aprende a ignorar.
    """
    monkeypatch.delenv(sync.VARIAVEL, raising=False)
    assert sync.main([]) == 0
    saida = capsys.readouterr().out
    assert "NAO SE APLICA" in saida
    # 🚫 e nunca MUDO: some porque a maquina nao tem vault, e isso e' dito.
    assert sync.VARIAVEL in saida


def test_variavel_apontando_para_lugar_nenhum_tambem_nao_quebra(monkeypatch, capsys, tmp_path):
    """⚠️ Mas DIZ que o caminho esta errado -- "nao declarei" e "declarei errado"
    sao coisas diferentes, e so' a segunda e' engano do operador."""
    monkeypatch.setenv(sync.VARIAVEL, str(tmp_path / "nao-existe"))
    assert sync.main([]) == 0
    saida = capsys.readouterr().out
    assert "nao e' um diretorio" in saida


# ------------------------------------------------------- escrever e recusar

def test_conferir_e_o_PADRAO_e_nao_escreve(espelho, monkeypatch, capsys):
    """Sobrescrever arquivo do vault apaga trabalho de alguem. Se pergunta antes."""
    repo, fontes = espelho
    (repo / "A.md").write_text("# A\n\nmudou\n", encoding="utf-8")
    antes = (fontes / "A.md").read_text(encoding="utf-8")
    monkeypatch.setenv(sync.VARIAVEL, str(fontes))

    assert sync.main([]) == 1, "divergencia sem sincronizar tem que sair != 0"
    assert (fontes / "A.md").read_text(encoding="utf-8") == antes, "escreveu sem mandar"
    assert "--sincronizar" in capsys.readouterr().out


def test_sincronizar_escreve_e_confere_DEPOIS(espelho, monkeypatch):
    repo, fontes = espelho
    (repo / "A.md").write_text("# A\n\nmudou\n", encoding="utf-8")
    monkeypatch.setenv(sync.VARIAVEL, str(fontes))

    assert sync.main(["--sincronizar"]) == 0
    assert sync.confere(fontes)["divergentes"] == []
    assert "mudou" in (fontes / "A.md").read_text(encoding="utf-8")


def test_sincronizar_escreve_LF_e_nao_CRLF(espelho, monkeypatch):
    """O vault usa LF; escrever CRLF faria o OneDrive sincronizar por nada."""
    repo, fontes = espelho
    (repo / "A.md").write_bytes(b"# A\r\n\r\nmudou\r\n")
    monkeypatch.setenv(sync.VARIAVEL, str(fontes))
    sync.main(["--sincronizar"])
    assert b"\r\n" not in (fontes / "A.md").read_bytes()


def test_nunca_apaga_nem_cria_arquivo_no_vault(espelho, monkeypatch):
    """🚫 So' escreve por cima de espelho que ja existe."""
    repo, fontes = espelho
    (repo / "NOVO.md").write_text("nao deve aparecer no vault\n", encoding="utf-8")
    (fontes / "SO_NO_VAULT.md").write_text("nota propria\n", encoding="utf-8")
    monkeypatch.setenv(sync.VARIAVEL, str(fontes))

    sync.main(["--sincronizar"])
    assert not (fontes / "NOVO.md").exists(), "criou espelho que ninguem pediu"
    assert (fontes / "SO_NO_VAULT.md").is_file(), "apagou nota do vault"


def test_arquivo_sem_par_no_repo_e_DITO_e_nao_tocado(espelho, monkeypatch):
    repo, fontes = espelho
    (fontes / "SO_NO_VAULT.md").write_text("nota propria\n", encoding="utf-8")
    e = sync.confere(fontes)
    assert e["sem_origem"] == ["SO_NO_VAULT.md"]
    assert "SO_NO_VAULT.md" not in e["divergentes"], "sem par nao e' divergencia"


def test_a_lista_de_espelhos_e_derivada_do_vault_nao_mantida_no_codigo(espelho):
    """⚠️ *lista mantida -> criterio derivado*, a troca de sempre.

    Quem decide o que merece espelho e' o dono do vault. Documento novo no repo
    NAO vira espelho sozinho -- e isso e' correto, nao um vao.
    """
    repo, fontes = espelho
    (repo / "DOC_NOVO.md").write_text("recem criado\n", encoding="utf-8")
    nomes = [n for n, _, _ in sync.pares(fontes)]
    assert "DOC_NOVO.md" not in nomes
    assert sorted(nomes) == ["A.md", "B.md"]


# ------------------------------------------- e o vault DESTA maquina, se houver

def test_o_vault_desta_maquina_esta_em_dia():
    """🚨 A unica que olha o disco de verdade -- e PULA quando nao ha vault.

    E' ela que teria gritado em 11/08 e evitado os oito dias de defasagem.
    """
    fontes = sync.caminho_do_vault()
    if fontes is None:
        pytest.skip(f"{sync.VARIAVEL} nao definida -- esta maquina nao espelha vault")
    e = sync.confere(fontes)
    assert e["total"] > 0, "vault declarado mas sem nenhum espelho -- conferiu o quе?"
    assert not e["divergentes"], (
        f"espelho do vault defasado: {e['divergentes']}. "
        "Rode: py -3.12 scripts/sync_vault.py --sincronizar")
