"""A acusacao fundida como duplicata aparece com HIPOTESE, nao como contagem.

🚨 O desequilibrio que isto conserta: uma acusacao que nao coube no orcamento
sempre saiu do parecer inteira -- categoria, local, hipotese, motivo. Uma
acusacao FUNDIDA saia como "(Outras 3 eram duplicatas)".

Ou seja, a que o dedup engoliu POR ENGANO ficava menos visivel que a que
simplesmente nao coube -- e o engano e' o caso grave dos dois. Enquanto a chave
do pre-advogado for heuristica (medido em 18/08: afrouxa-la funde defeitos
distintos em ~metade dos casos), esta lista e' a unica defesa daquele estagio.
"""
import pytest

from veredito import juiz, promotores


def _a(id_, local, hipotese, categoria="correcao", confianca="alta", onde="docs/R.md:S"):
    return {"id": id_, "local": local, "hipotese": hipotese, "categoria": categoria,
            "confianca": confianca, "arbitro": {"regra": "a regra", "onde": onde}}


def _fila_com_duplicata():
    """Duas acusacoes com local E arbitro identicos -- a chave rigida funde."""
    brutas = [
        _a("correcao_01", "app/main.py:103", "o limite nunca e' verificado"),
        _a("padroes_01", "app/main.py:103", "config lida com os.getenv solto",
           categoria="padroes", confianca="media"),
    ]
    return brutas, promotores.deduplica([dict(b) for b in brutas])


def test_o_dedup_realmente_funde_estas_duas():
    """Sem isto, o resto do arquivo testaria um cenario que nao acontece."""
    brutas, fila = _fila_com_duplicata()
    assert len(fila) == 1, "as duas nao fundiram; o fixture nao exercita nada"
    assert fila[0].get("_duplicatas"), "fundiu sem registrar a duplicata"


def test_a_fundida_entra_no_escopo_com_hipotese():
    brutas, fila = _fila_com_duplicata()
    esc = promotores.escopo(brutas, fila, teto=10)
    fundidas = esc["fundidas"]
    assert len(fundidas) == 1
    assert fundidas[0]["hipotese"] == "config lida com os.getenv solto"
    assert fundidas[0]["local"] == "app/main.py:103"
    assert fundidas[0]["fundida_em"] == "correcao_01"


def test_a_CONTAGEM_e_a_LISTA_tem_que_bater():
    """🚨 A invariante. Contagem 3 com lista de 1 seria a metrica medindo outra
    coisa -- o erro dos 45% de arbitro, na divulgacao."""
    brutas, fila = _fila_com_duplicata()
    esc = promotores.escopo(brutas, fila, teto=10)
    assert esc["fundidas_por_duplicata"] == len(esc["fundidas"])


def test_a_conta_do_escopo_continua_fechando():
    """levantadas = fundidas + testadas + nao testadas."""
    brutas, fila = _fila_com_duplicata()
    esc = promotores.escopo(brutas, fila, teto=10)
    assert esc["levantadas"] == (esc["fundidas_por_duplicata"]
                                 + esc["testadas"] + esc["nao_testadas"])


def test_a_hipotese_da_fundida_chega_ao_parecer():
    """O texto que o autor do PR le. Sem isto ela existe so' no JSON."""
    brutas, fila = _fila_com_duplicata()
    esc = promotores.escopo(brutas, fila, teto=10)
    esc["nao_testadas"] = 1          # a secao so' abre quando ha o que listar
    texto = "\n".join(juiz._secao_nao_testadas(esc))
    assert "config lida com os.getenv solto" in texto, (
        "a fundida virou contagem; o autor nunca sabe que a suspeita existiu")
    assert "correcao_01" in texto, "nao diz em qual acusacao ela foi fundida"


def test_sem_fundida_nenhuma_a_secao_fica_QUIETA():
    """⚠️ Guarda que fala sempre morre de excesso -- foi o `NAO MEDIDO` do
    banco. Rodada sem duplicata nao ganha secao de duplicata."""
    esc = {"nao_testadas": 1, "fora_do_orcamento": [], "levantadas": 1,
           "fundidas_por_duplicata": 0, "fundidas": [], "teto": 10}
    texto = "\n".join(juiz._secao_nao_testadas(esc))
    assert "Fundidas como duplicata" not in texto


def test_hipotese_muito_longa_e_cortada():
    brutas, fila = _fila_com_duplicata()
    fila[0]["_duplicatas"][0]["hipotese"] = "x" * 400
    esc = promotores.escopo(brutas, fila, teto=10)
    esc["nao_testadas"] = 1
    texto = "\n".join(juiz._secao_nao_testadas(esc))
    assert "..." in texto and "x" * 200 not in texto


def test_rodada_antiga_com_contagem_e_sem_lista_DIZ_que_nao_sabe():
    """Escopo gravado antes de 18/08 tem o numero e nao a lista. Calar deixaria
    o leitor achar que a contagem 1 e' zero detalhe por nao haver nada."""
    esc = {"nao_testadas": 1, "fora_do_orcamento": [], "levantadas": 3,
           "fundidas_por_duplicata": 1, "teto": 10}   # sem a chave `fundidas`
    texto = "\n".join(juiz._secao_nao_testadas(esc))
    assert "não foi gravado nesta rodada" in texto
