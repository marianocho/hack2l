"""Tres achados que sao um defeito viram um. E o que NAO e' um defeito, nao.

O peso destes testes esta no lado negativo de proposito. Fundir demais apaga um
achado real do comentario do PR, e o `CLAUDE.md` e' explicito: "passar um
defeito real e' mais problematico do que um falso alarme". Fundir de menos so'
deixa o texto repetitivo.

O fixture vem das DUAS rodadas de verdade da Action (18/08), nao de um exemplo
inventado: cada uma publicou 3 achados que eram 1 IDOR em `app/main.py:103-104`.
"""
import pytest

from veredito import fusao


def _a(id_, local, onde=None, categoria="correcao", regra="a regra"):
    arb = {"regra": regra, "onde": onde} if onde else None
    return {"id": id_, "local": local, "local_normalizado": local,
            "categoria": categoria, "arbitro": arb}


def _grupos(acusacoes):
    condenados = [{"id": a["id"]} for a in acusacoes]
    return fusao.agrupa(condenados, {a["id"]: a for a in acusacoes})


REGRAS = "docs/REGRAS.md:Acesso e isolamento"


# ------------------------------------------- funde: as duas rodadas reais

def test_rodada_1_tres_lentes_um_defeito():
    """`correcao:103` + `padroes:104` + `performance:103`, as tres citando a
    mesma secao com pontuacao diferente. Publicado como "3 achados"."""
    g = _grupos([
        _a("correcao_01", "app/main.py:103", "docs/REGRAS.md:Acesso e isolamento"),
        _a("padroes_01", "app/main.py:104", "docs/REGRAS.md (Acesso e isolamento)",
           categoria="padroes"),
        _a("performance_01", "app/main.py:103",
           "docs/REGRAS.md:Acesso e isolamento (linhas ~13-14)", categoria="performance"),
    ])
    assert len(g) == 1, "o PR tem UM defeito e o comentario dizia tres"
    assert len(g[0]) == 3


def test_rodada_2_faixa_e_ponto_fundem():
    """`:104` + `:103-106` + `:104`, com "md - Acesso" e "md (Acesso)"."""
    g = _grupos([
        _a("correcao_01", "app/main.py:104", "docs/REGRAS.md - Acesso e isolamento"),
        _a("correcao_02", "app/main.py:103-106", "docs/REGRAS.md - Acesso e isolamento"),
        _a("padroes_01", "app/main.py:104", "docs/REGRAS.md (Acesso e isolamento)",
           categoria="padroes"),
    ])
    assert len(g) == 1
    assert len(g[0]) == 3


def test_a_regra_pode_ser_outra_FRASE_da_mesma_secao():
    """Na rodada 2 as duas `correcao` citaram frases diferentes da mesma secao.

    A chave nao olha a parafrase da regra de proposito: o que e' fato do
    repositorio e' ONDE a regra esta escrita, nao como o modelo a resumiu.
    """
    g = _grupos([
        _a("a1", "app/main.py:103", REGRAS, regra="Ler uma tarefa exige ver o projeto"),
        _a("a2", "app/main.py:104", REGRAS, regra="O identificador nao e' segredo"),
    ])
    assert len(g) == 1


# ------------------------------------------- 🚨 NAO funde

def test_sem_arbitro_NAO_funde():
    """O contraexemplo medido: no `encode/httpx#3730` quatro acusacoes
    apontavam a MESMA linha e eram quatro preocupacoes diferentes. Local igual
    nao e' defeito igual -- sao os DOIS fatos concordando que sustentam."""
    g = _grupos([_a("a1", "app/x.py:10"), _a("a2", "app/x.py:10")])
    assert len(g) == 2, "fundiu por local, sem procedencia nenhuma"


def test_mesma_linha_com_procedencias_DIFERENTES_nao_funde():
    g = _grupos([
        _a("a1", "app/x.py:10", "docs/REGRAS.md:Acesso e isolamento"),
        _a("a2", "app/x.py:10", "docs/REGRAS.md:Limite de membros"),
    ])
    assert len(g) == 2, "duas regras distintas na mesma linha viraram uma"


def test_digito_da_secao_NAO_e_decoracao():
    """`docs/PRD.md:43` e `docs/PRD.md:99` sao regras DIFERENTES.

    A forma `arquivo:linha` esta no esquema da acusacao (CLAUDE.md). Uma
    normalizacao que jogasse digito fora fundiria as duas -- e a tentacao e'
    real, porque `(linhas ~13-14)` tambem e' digito e aquele SAI.
    """
    g = _grupos([
        _a("a1", "app/x.py:10", "docs/PRD.md:43"),
        _a("a2", "app/x.py:11", "docs/PRD.md:99"),
    ])
    assert len(g) == 2


def test_parenteses_sem_digito_nunca_chega_a_ser_podado():
    """`(Acesso)` vs `(Limite)`: o parenteses e' a SECAO.

    ⚠️ Este caso passa pela GUARDA DE CIMA -- o regex de decoracao exige
    linha/digito dentro do parenteses e nem tenta podar aqui. Nao confunda com
    o teste seguinte, que e' o que exercita a poda de verdade.
    """
    g = _grupos([
        _a("a1", "app/x.py:10", "docs/REGRAS.md (Acesso)"),
        _a("a2", "app/x.py:11", "docs/REGRAS.md (Limite)"),
    ])
    assert len(g) == 2


def test_parenteses_que_E_a_secao_E_TEM_DIGITO_nao_e_podado():
    """`docs/PRD.md (43)` vs `docs/PRD.md (99)`: o parenteses tem digito, entao
    a poda TENTA agir -- e se agisse deixaria as duas com secao vazia, fazendo
    qualquer citacao daquele arquivo casar com qualquer outra.

    🚨 Este teste existe porque o anterior era decoracao: injetei a poda
    incondicional e a suite ficou verde, 15 de 15. O caso `(Acesso)` nunca
    alcanca a guarda; este alcanca.
    """
    g = _grupos([
        _a("a1", "app/x.py:10", "docs/PRD.md (43)"),
        _a("a2", "app/x.py:11", "docs/PRD.md (99)"),
    ])
    assert len(g) == 2


def test_linhas_distantes_nao_fundem():
    """Mesma regra citada, mas o defeito e' em outro lugar do arquivo.

    ⚠️ O vao e' 10 e nao 70 de proposito: com 70, uma tolerancia afrouxada de 2
    para 50 continuaria passando neste teste, e a trava nao veria a mudanca.
    O vao tem que ficar logo acima da tolerancia para medi-la.
    """
    g = _grupos([
        _a("a1", "app/x.py:10", REGRAS),
        _a("a2", "app/x.py:20", REGRAS),
    ])
    assert len(g) == 2


def test_arquivos_diferentes_nao_fundem():
    g = _grupos([
        _a("a1", "app/x.py:10", REGRAS),
        _a("a2", "app/y.py:10", REGRAS),
    ])
    assert len(g) == 2


def test_regiao_larga_nao_arrasta_as_vizinhas():
    """Uma acusacao de 82 linhas engoliria o arquivo. Mesmo teto e mesmo motivo
    do `LARGURA_MAX_PARA_CORROBORAR` de fontes.py: inflar o sinal e' o erro de
    sempre deste projeto."""
    g = _grupos([
        _a("a1", "app/x.py:15-96", REGRAS),
        _a("a2", "app/x.py:20", REGRAS),
    ])
    assert len(g) == 2, "a regiao larga fundiu com um ponto dentro dela"


# ------------------------------------------- o comportamento real, documentado

def test_a_vizinhanca_ENCADEIA():
    """103 funde com 105, e 107 funde com 105 -- entao os tres viram um.

    ⚠️ Este teste existe porque eu escrevi no `_vizinho` que comparar por
    MEMBRO evitava a cadeia. Nao evita. O comentario errado ficaria de heranca
    para quem lesse depois; o teste fixa o que o codigo faz DE VERDADE.

    A cadeia so' anda dentro do mesmo balde -- mesma regra, mesmo arquivo de
    documentacao -- e e' o que faz um defeito espalhado por um corpo de funcao
    fundir como um so'.
    """
    g = _grupos([
        _a("a1", "app/x.py:103", REGRAS),
        _a("a2", "app/x.py:105", REGRAS),
        _a("a3", "app/x.py:107", REGRAS),
    ])
    assert len(g) == 1 and len(g[0]) == 3


# ------------------------------------------- o que o leitor recebe

def test_local_do_grupo_cobre_a_extensao_toda():
    """O leitor recebe UM lugar, e ele cobre o que as lentes apontaram."""
    ac = [_a("a1", "app/main.py:103", REGRAS), _a("a2", "app/main.py:104", REGRAS)]
    g = _grupos(ac)
    assert fusao.local_do_grupo(g[0], {a["id"]: a for a in ac}) == "app/main.py:103-104"


def test_local_de_um_achado_so_nao_vira_faixa():
    ac = [_a("a1", "app/main.py:103", REGRAS)]
    g = _grupos(ac)
    assert fusao.local_do_grupo(g[0], {a["id"]: a for a in ac}) == "app/main.py:103"


def test_lentes_nao_repetem():
    """A rodada 2 teve DUAS `correcao`. Dizer "3 lentes convergiram" quando
    duas sao a mesma lente e' inflar o sinal -- o erro dos 45% de arbitro."""
    ac = [_a("a1", "app/main.py:103", REGRAS, categoria="correcao"),
          _a("a2", "app/main.py:104", REGRAS, categoria="correcao"),
          _a("a3", "app/main.py:104", REGRAS, categoria="padroes")]
    g = _grupos(ac)
    assert fusao.lentes(g[0], {a["id"]: a for a in ac}) == ["correcao", "padroes"]


def test_ordem_de_severidade_do_juiz_sobrevive():
    """O juiz ja ordenou por severidade; o grupo aparece na posicao do seu
    primeiro membro, e quem nao funde sai sozinho no lugar dele."""
    ac = [_a("grave", "app/a.py:10", REGRAS),
          _a("outro", "app/b.py:50", "docs/REGRAS.md:Limite de membros"),
          _a("grave2", "app/a.py:11", REGRAS)]
    g = _grupos(ac)
    assert [x["id"] for x in g[0]] == ["grave", "grave2"]
    assert [x["id"] for x in g[1]] == ["outro"]



# ------------------------------------------- o bloco que o autor le

from veredito import juiz
from veredito import superficie  # noqa: E402


def _v(id_, sev="ALTA", conserto="restaurar a checagem"):
    return {"id": id_, "veredito": "PROVADO", "severidade": sev, "conserto": conserto}


def _art(id_, teste):
    return {"id": id_, "estado": "PROVADO", "arquivo_do_teste": teste,
            "commit_base": "f3bdd65", "commit_head": "61cc0a7",
            "exit_base": 0, "exit_head": 1}


def _cena():
    ac = {a["id"]: a for a in [
        _a("correcao_01", "app/main.py:103", REGRAS),
        _a("padroes_01", "app/main.py:104", REGRAS, categoria="padroes"),
        _a("performance_01", "app/main.py:103", REGRAS, categoria="performance"),
    ]}
    cond = [_v("correcao_01"), _v("padroes_01"), _v("performance_01")]
    art = {"correcao_01": _art("correcao_01", "test_isolamento.py"),
           "padroes_01": _art("padroes_01", "test_isolamento.py"),
           "performance_01": _art("performance_01", "test_idor.py")}
    return cond, ac, art


def test_nenhum_membro_some_do_bloco():
    """🚨 A fusao junta a APRESENTACAO; nao apaga verificacao. Se um id sumir,
    o parecer esconde uma prova que foi paga e produzida."""
    cond, ac, art = _cena()
    bloco = juiz.bloco_agrupado(fusao.agrupa(cond, ac)[0], ac, art)
    for id_ in ("correcao_01", "padroes_01", "performance_01"):
        assert id_ in bloco, f"{id_} desapareceu do bloco fundido"
    assert "test_idor.py" in bloco, "o artefato de uma lente sumiu"


def test_convergencia_vem_antes_do_conserto():
    """A ordem e' do leitor: primeiro "e' um defeito", por ultimo a acao."""
    cond, ac, art = _cena()
    bloco = juiz.bloco_agrupado(fusao.agrupa(cond, ac)[0], ac, art)
    # ⚠️ Pergunta ao ESTILO como o rotulo sai, em vez de repetir a convencao:
    # a constante e' "Convergência" e o terminal imprime "CONVERGÊNCIA:".
    r = superficie.TERMINAL.rotulo
    assert bloco.index(r(juiz.CONVERGENCIA)) < bloco.index(r(juiz.CONSERTO))
    assert bloco.index(r(juiz.O_QUE)) < bloco.index(r(juiz.CONVERGENCIA))


def test_cabecalho_mostra_a_extensao_do_defeito():
    """E nao a linha do membro que por acaso liderou o grupo."""
    cond, ac, art = _cena()
    bloco = juiz.bloco_agrupado(fusao.agrupa(cond, ac)[0], ac, art)
    assert bloco.splitlines()[0].endswith("app/main.py:103-104")


def test_convergencia_nao_conta_a_mesma_lente_duas_vezes():
    ac = {a["id"]: a for a in [
        _a("c1", "app/main.py:103", REGRAS),
        _a("c2", "app/main.py:104", REGRAS),
    ]}
    bloco = juiz.bloco_agrupado(fusao.agrupa([_v("c1"), _v("c2")], ac)[0], ac, {})
    # ⚠️ `1 lente`, e nao `1 lente(s)`: o plural de formulario saiu em 20/08.
    assert "1 lente " in bloco, "duas acusacoes da MESMA lente viraram duas lentes"
    assert "lente(s)" not in bloco


def test_achado_solitario_sai_igual_ao_bloco_de_sempre():
    """Sem fusao, byte a byte o que o parecer sempre imprimiu -- senao esta
    mudanca reescreve o formato de todo achado do produto."""
    ac = {"a1": _a("a1", "app/x.py:10", REGRAS)}
    v = _v("a1")
    assert juiz.bloco_agrupado([v], ac, {}) == juiz._bloco(v, ac["a1"], None)


def test_sem_conserto_o_conteudo_nao_se_perde():
    """Guarda da ancora: sem `CONSERTO SUGERIDO` para ancorar, as provas extras
    vao para o fim. Perder a ordem e' aceitavel; perder conteudo nao e'."""
    cond, ac, art = _cena()
    for v in cond:
        v.pop("conserto")
    bloco = juiz.bloco_agrupado(fusao.agrupa(cond, ac)[0], ac, art)
    assert "padroes_01" in bloco and "performance_01" in bloco
    assert superficie.TERMINAL.rotulo(juiz.CONVERGENCIA) in bloco
