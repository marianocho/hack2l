"""Invariante da acusacao: a reescrita de URL feita no conftest do head so' pode
trocar o ULTIMO segmento da URL (o nome do banco) e nunca o destino (host/porta/
usuario). Teste puramente sobre strings genericas: nao abre conexao nenhuma, nao
importa engine, nao toca em banco.
"""

APP_NAME = "appdb"
TEST_NAME = "testdb"


def _rewrite(u: str) -> str:
    """Mesma logica das linhas 26-28 do conftest do head, com nomes genericos."""
    if u and u.rsplit("/", 1)[-1] == APP_NAME:
        return u.rsplit("/", 1)[0] + "/" + TEST_NAME
    return u


def test_prefixo_da_url_e_imutavel():
    entrada = "proto://user:pw@host-interno:5432/" + APP_NAME
    saida = _rewrite(entrada)
    assert saida.rsplit("/", 1)[0] == entrada.rsplit("/", 1)[0]
    assert saida.rsplit("/", 1)[-1] == TEST_NAME


def test_host_de_terceiro_vindo_do_ambiente_nao_e_criado_nem_alterado():
    hostil = "proto://user:pw@host-de-terceiro:5432/" + APP_NAME
    saida = _rewrite(hostil)
    # o destino continua sendo exatamente o que a variavel do operador ja dizia
    assert saida.rsplit("/", 1)[0] == hostil.rsplit("/", 1)[0]
    assert "host-de-terceiro" in saida


def test_url_com_outro_nome_final_fica_intacta():
    outra = "proto://user:pw@host-de-terceiro:5432/outracoisa"
    assert _rewrite(outra) == outra
