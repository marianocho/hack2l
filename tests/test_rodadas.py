"""Cada rodada na sua pasta. Rodada nao apaga rodada.

Ate' 13/08 toda rodada escrevia nos MESMOS caminhos -- saidas/veredictos.json e
artefatos/<tipo>_<id> -- entao a rodada N apagava a N-1. Medido no commit
cfeb64b: 11 artefatos sobrescritos, e as rodadas de 11/08 16h e 21h so'
sobreviveram no que a seguinte nao pisou. A US$~1,30 a rodada, e sem recuperacao
possivel.

O que estes testes travam nao e' "existe uma pasta por rodada" -- e' que a
rodada anterior CONTINUA LEGIVEL depois da seguinte, e que o ponteiro nunca
entrega uma pasta que nao esta la.
"""

from pathlib import Path

import pytest

from veredito import config as cfg


@pytest.fixture
def saidas(tmp_path, monkeypatch):
    """Redireciona as saidas para tmp_path e RESTAURA os globais depois.

    nova_rodada() rebinda cfg.RODADA e cfg.ARTEFATOS. Sem restaurar, o primeiro
    teste que roda deixaria os outros -- e o resto da suite -- apontando para um
    tmp_path que o pytest ja apagou.
    """
    monkeypatch.setattr(cfg, "SAIDAS", tmp_path / "saidas")
    monkeypatch.setattr(cfg, "RODADAS", tmp_path / "saidas" / "rodadas")
    monkeypatch.setattr(cfg, "PONTEIRO", tmp_path / "saidas" / "rodadas" / "ULTIMA")
    monkeypatch.setattr(cfg, "RODADA", tmp_path / "saidas")
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path / "artefatos")
    monkeypatch.setattr(cfg, "WORKTREES", tmp_path / "wt")
    return tmp_path


# ------------------------------------------------------- a regressao de cfeb64b

def test_rodada_seguinte_nao_apaga_a_anterior(saidas):
    """O defeito, reproduzido: duas rodadas, o MESMO nome de arquivo."""
    cfg.nova_rodada("20260813T0100-aaaaaaa")
    (cfg.RODADA / "veredictos.json").write_text('["primeira"]', encoding="utf-8")
    (cfg.ARTEFATOS / "prova_injection_01.json").write_text('{"id": "um"}', encoding="utf-8")
    primeira = cfg.RODADA

    cfg.nova_rodada("20260813T0200-bbbbbbb")
    (cfg.RODADA / "veredictos.json").write_text('["segunda"]', encoding="utf-8")
    (cfg.ARTEFATOS / "prova_injection_01.json").write_text('{"id": "dois"}', encoding="utf-8")

    assert cfg.RODADA != primeira
    # O ponto todo: a primeira continua inteira, com o mesmo nome de arquivo.
    assert (primeira / "veredictos.json").read_text(encoding="utf-8") == '["primeira"]'
    assert (primeira / "artefatos" / "prova_injection_01.json").read_text(
        encoding="utf-8") == '{"id": "um"}'
    assert (cfg.RODADA / "veredictos.json").read_text(encoding="utf-8") == '["segunda"]'


def test_artefatos_acompanham_a_rodada(saidas):
    """Sao a EVIDENCIA. Guardar o veredito e perder o artefato guarda a metade
    que nao vale nada -- num produto cuja regra e' "sem artefato nao ha prova".
    """
    cfg.nova_rodada("20260813T0300-ccccccc")
    assert cfg.ARTEFATOS == cfg.RODADA / "artefatos"
    assert cfg.ARTEFATOS.is_dir()


# ----------------------------------------------------------------- o ponteiro

def test_ultima_encontra_a_rodada_recem_gravada(saidas):
    """Disciplina no 2: ajustar o juiz 30 vezes nao pode re-executar o advogado.

    `python -m veredito.juiz` roda em OUTRO processo e tem que achar sozinho.
    """
    cfg.nova_rodada("20260813T0400-ddddddd")
    (cfg.RODADA / "veredictos.json").write_text("[]", encoding="utf-8")
    esperada = cfg.RODADA

    # Simula o processo novo: os globais voltam ao estado de importacao.
    cfg.RODADA = cfg.SAIDAS
    cfg.ARTEFATOS = saidas / "artefatos"

    assert cfg.usa_ultima_rodada() == esperada
    assert cfg.RODADA == esperada
    assert cfg.ARTEFATOS == esperada / "artefatos"


def test_ponteiro_pendurado_nao_entrega_pasta_que_sumiu(saidas):
    """🚨 O padrao de bug do projeto, na versao ponteiro.

    O ponteiro e' uma STRING; a pasta pode ter sido apagada a mao. Se
    usa_ultima_rodada devolvesse o caminho sem conferir, o juiz leria uma rodada
    vazia e imprimiria "0 com parecer, 0 descartados" -- absolvicao limpa por
    acidente de arquivo. E' o modo de falha exato que o produto existe para
    impedir, apontado para nos.
    """
    import shutil
    cfg.nova_rodada("20260813T0500-eeeeeee")
    shutil.rmtree(cfg.RODADA)

    cfg.RODADA = cfg.SAIDAS
    assert cfg.usa_ultima_rodada() is None
    assert cfg.RODADA == cfg.SAIDAS, "caiu no legado, sem inventar pasta"


@pytest.mark.parametrize("conteudo", ["", "   \n", "nao_existe_essa_pasta"])
def test_ponteiro_ilegivel_cai_no_legado(saidas, conteudo):
    cfg.RODADAS.mkdir(parents=True, exist_ok=True)
    cfg.PONTEIRO.write_text(conteudo, encoding="utf-8")
    assert cfg.usa_ultima_rodada() is None


@pytest.mark.parametrize("nome", ["../fora", "..\\fora", "a/b"])
def test_ponteiro_nao_escapa_da_pasta_de_rodadas(saidas, nome):
    """Ponteiro e' nome de pasta, nao caminho. Sem isso, um ULTIMA com `../..`
    faria o juiz gravar parecer.md em cima de qualquer coisa.
    """
    cfg.RODADAS.mkdir(parents=True, exist_ok=True)
    cfg.PONTEIRO.write_text(nome, encoding="utf-8")
    assert cfg.usa_ultima_rodada() is None


def test_sem_rodada_nenhuma_o_legado_continua_legivel(saidas):
    """Quem tem saidas/veredictos.json da epoca anterior nao perde o acesso."""
    assert cfg.usa_ultima_rodada() is None
    assert cfg.RODADA == cfg.SAIDAS
    assert cfg.ARTEFATOS == saidas / "artefatos"


# ------------------------------------------------------------- prepara_pastas

def test_prepara_pastas_cria_a_rodada_atual_e_nao_a_anterior(saidas):
    """A funcao le cfg.RODADA no momento da chamada, e nao no import.

    Capturar no topo do modulo criaria a pasta da rodada ANTERIOR e deixaria a
    atual sem existir -- o primeiro write_text morreria com FileNotFoundError.
    """
    cfg.nova_rodada("20260813T0600-fffffff")
    atual = cfg.RODADA
    cfg.prepara_pastas()
    assert atual.is_dir() and (atual / "artefatos").is_dir()
    assert cfg.RODADAS.is_dir()


def test_carimbo_ordena_sozinho():
    """`<data>T<hora>-<commit>` ordena alfabeticamente = ordena no tempo. E' o
    que faz `ls saidas/rodadas` ser util sem ferramenta nenhuma.
    """
    nomes = ["20260813T0200-bbbbbbb", "20260813T0100-aaaaaaa", "20260812T2300-ccccccc"]
    assert sorted(nomes) == ["20260812T2300-ccccccc",
                             "20260813T0100-aaaaaaa",
                             "20260813T0200-bbbbbbb"]
