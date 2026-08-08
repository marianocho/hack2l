"""Teste da checagem que impede o falso negativo mais caro entre as maquinas.

O app no ar serve o codigo ASSADO NA IMAGEM, nao o checkout do repo. Uma maquina
com a imagem construida a partir da `main` roda o Veredito inteiro sem erro e
devolve TUDO em MEDIA -- `http_request` nunca alcanca o codigo do PR,
`prova_ponta_a_ponta` fica falsa, a R2 rebaixa. O sintoma nao parece ambiente:
parece o produto nao funcionando.
"""

import pytest

import checar_paridade as cp


def test_imagem_do_base_e_pega_pelo_router_que_falta():
    """O caso real: a imagem foi construida antes do checkout do PR, entao o
    router que o PR adiciona simplesmente nao existe dentro do container."""
    esperado = {"auth.py": 40, "documents.py": 120, "shares.py": 96}
    servido = {"auth.py": 40, "documents.py": 120}
    with pytest.raises(AssertionError) as e:
        cp.compara_routers(esperado, servido, "1dd2e5c0000")
    assert "shares.py" in str(e.value)
    assert "up -d --build" in str(e.value), "a mensagem precisa dizer o que fazer"


def test_imagem_velha_e_pega_pelo_tamanho_diferente():
    """Arquivo existe mas e' de outro commit -- rebuild esquecido depois de um
    fetch. Sem isto, a prova roda contra codigo que ninguem esta revisando."""
    esperado = {"shares.py": 96}
    servido = {"shares.py": 71}
    with pytest.raises(AssertionError) as e:
        cp.compara_routers(esperado, servido, "1dd2e5c0000")
    assert "tamanho diferente" in str(e.value)


def test_router_a_mais_no_container_nao_e_erro():
    """Assimetria deliberada: sobra de outro branch nao impede a prova. Cobrar
    igualdade exata daria falha em maquina saudavel, e alarme que mente uma vez
    para de ser lido."""
    esperado = {"auth.py": 40}
    servido = {"auth.py": 40, "sobra.py": 10}
    assert "1 routers" in cp.compara_routers(esperado, servido, "1dd2e5c0000")


def test_igualdade_passa_e_diz_o_commit():
    detalhe = cp.compara_routers({"a.py": 1, "b.py": 2}, {"a.py": 1, "b.py": 2}, "abcdef01234")
    assert "2 routers" in detalhe and "abcdef0" in detalhe
