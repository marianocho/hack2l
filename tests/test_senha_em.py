"""`senha_em`: o yml carrega o NOME da variavel, nunca o valor.

🚨 POR QUE, e a objecao nao e' de percepcao. O `veredito.yml` mora na raiz do
projeto revisado e e' COMMITADO -- conferido em 19/08: `bancada/veredito.yml`
aparece no `git ls-files` com `senha:` em cinco linhas. Somando a isso tres
fatos do pipeline, todos conferidos no mesmo dia:

  - o advogado le o repositorio sob revisao por worktree;
  - `read_file` nao bloqueia arquivo nenhum, e nao ha redacao em lugar nenhum
    de `veredito/*.py`;
  - o parecer e' POSTADO como comentario no PR.

Uma acusacao de "credencial em codigo" -- exatamente o que as lentes `padroes` e
`vazamento` procuram -- leva o advogado a ler o `veredito.yml` e poder citar a
senha num comentario publico.

⚠️ Trocar o VOCABULARIO nao resolve nada disso: scanner de segredo dispara pela
forma do valor, nao pelo nome do campo. E se o rename fizesse o scanner calar,
seria pior -- driblaria o controle mantendo a pratica.

🚨 A TRAVA CENTRAL deste arquivo e' a de `avisos()` contar as contas RESOLVIDAS
e nao as DECLARADAS. Sem ela, `senha_em` INTRODUZ um buraco: variavel esquecida
faz a rodada rodar com menos contas do que o projeto declarou, `len >= 3`
continua verde porque conta a linha do arquivo, e o login falha longe da causa.
E' o mesmo formato dos 94 arbitros "preenchidos" -- medir a existencia da linha
em vez da existencia do fato.
"""
import pytest

from veredito import projeto


def _conta(nome, **kw):
    return {"nome": nome, "email": f"{nome}@t.dev", **kw}


def _projeto(*contas, contexto="docs/REGRAS.md"):
    return {"contas": list(contas), "contexto": contexto}


# ------------------------------------------------------------- resolucao

def test_senha_em_resolve_pela_variavel_de_ambiente():
    d = _projeto(_conta("ana", senha_em="VER_ANA"))
    u = projeto.usuarios(d, {"VER_ANA": "s3nha-de-teste"})
    assert u == {"ana": ("ana@t.dev", "s3nha-de-teste")}


def test_senha_literal_continua_funcionando():
    """Compatibilidade: os dois `veredito.yml` que existem usam `senha:`.

    Quebrar isso transformaria uma melhoria de seguranca numa migracao forcada.
    """
    d = _projeto(_conta("ana", senha="literal"))
    assert projeto.usuarios(d, {}) == {"ana": ("ana@t.dev", "literal")}


def test_variavel_ausente_NAO_vira_senha_vazia(monkeypatch):
    """🚨 Senha vazia faria o `_token` POSTAR credencial vazia no login do
    cliente. A conta tem que SAIR, nunca entrar degradada."""
    d = _projeto(_conta("ana", senha_em="NAO_DEFINIDA"))
    u = projeto.usuarios(d, {})
    assert u == {}
    assert "ana" not in u


def test_variavel_vazia_conta_como_ausente():
    """`VAR=` no ambiente e' variavel sem valor, nao senha vazia."""
    assert projeto.usuarios(_projeto(_conta("ana", senha_em="V")), {"V": ""}) == {}


def test_resolve_contas_devolve_o_que_faltou_junto():
    d = _projeto(_conta("ana", senha_em="TEM"), _conta("bia", senha_em="NAO_TEM"))
    resolvidas, faltando = projeto.resolve_contas(d, {"TEM": "x"})
    assert list(resolvidas) == ["ana"]
    assert len(faltando) == 1 and "NAO_TEM" in faltando[0]


# --------------------------------------------------- arquivo torto LEVANTA

def test_senha_e_senha_em_juntas_levantam(tmp_path):
    """Duas fontes para o mesmo valor divergem em silencio -- custou 4
    tentativas com a chave da API, em 14/08."""
    d = _projeto(_conta("ana", senha="x", senha_em="VER_ANA"))
    with pytest.raises(projeto.ProjetoInvalido, match="senha_em"):
        projeto._valida(d, tmp_path / "veredito.yml")


def test_conta_sem_senha_e_sem_senha_em_levanta(tmp_path):
    with pytest.raises(projeto.ProjetoInvalido, match="sem `senha`"):
        projeto._valida(_projeto(_conta("ana")), tmp_path / "veredito.yml")


def test_conta_sem_email_continua_levantando(tmp_path):
    d = {"contas": [{"nome": "ana", "senha_em": "V"}]}
    with pytest.raises(projeto.ProjetoInvalido, match="email"):
        projeto._valida(d, tmp_path / "veredito.yml")


# ------------------------------------ 🚨 a guarda que o senha_em PODE furar

def test_avisos_conta_as_RESOLVIDAS_e_nao_as_declaradas():
    """🚨 A trava central. Quatro contas no arquivo, duas variaveis esquecidas:
    o aviso de "menos de tres" TEM que disparar.

    Contar `d["contas"]` deixaria isto verde com duas contas utilizaveis.
    """
    d = _projeto(
        _conta("ana", senha_em="TEM_A"),
        _conta("bia", senha_em="TEM_B"),
        _conta("cid", senha_em="ESQUECIDA_1"),
        _conta("davi", senha_em="ESQUECIDA_2", possui=0),
    )
    fora = projeto.avisos(d, ambiente={"TEM_A": "1", "TEM_B": "2"})
    assert any("pelo menos tres" in a for a in fora), fora
    assert any("2 conta(s) utilizavel" in a for a in fora), fora


def test_avisos_nomeia_a_variavel_que_falta():
    d = _projeto(_conta("ana", senha_em="VER_SENHA_ANA"))
    fora = projeto.avisos(d, ambiente={})
    assert any("VER_SENHA_ANA" in a for a in fora), fora


def test_aviso_NUNCA_vaza_o_valor_da_senha():
    """A mensagem nomeia a variavel; o valor nao aparece em lugar nenhum."""
    segredo = "ESTA-STRING-NAO-PODE-VAZAR"
    d = _projeto(
        _conta("ana", senha_em="TEM"),
        _conta("bia", senha_em="NAO_TEM"),
    )
    fora = projeto.avisos(d, ambiente={"TEM": segredo})
    assert fora, "o aviso de conta faltando tinha que sair"
    for a in fora:
        assert segredo not in a, a


def test_controle_negativo_ignora_conta_que_nao_resolveu():
    """🚨 Controle negativo em que nao da' para logar nao e' controle negativo.

    Apontar um sem senha faria a rodada acreditar que tem a peca que sustenta a
    CRITICA de vazamento -- e ela nao existiria.
    """
    d = _projeto(
        _conta("ana", senha_em="TEM"),
        _conta("vazia", senha_em="ESQUECIDA", possui=0),
    )
    assert projeto.controle_negativo(d, {"TEM": "x"}) is None
    assert projeto.controle_negativo(d, {"TEM": "x", "ESQUECIDA": "y"}) == "vazia"


def test_tudo_resolvido_nao_alarma():
    """A guarda tem que conseguir ficar QUIETA -- licao 0 do "como procurar"."""
    d = _projeto(
        _conta("ana", senha_em="A"),
        _conta("bia", senha_em="B"),
        _conta("cid", senha_em="C", possui=0),
    )
    fora = projeto.avisos(d, ambiente={"A": "1", "B": "2", "C": "3"})
    assert fora == [], fora


# --------------------------------------------- a promessa do produto, medida

def test_yml_com_senha_em_nao_tem_nada_com_forma_de_senha(tmp_path):
    """A alegacao inteira do conserto, mecanizada: o arquivo commitado nao
    carrega valor de credencial nenhum."""
    yml = tmp_path / "veredito.yml"
    yml.write_text(
        "versao: 1\n"
        "contas:\n"
        "  - nome: ana\n"
        "    email: ana@t.dev\n"
        "    senha_em: VEREDITO_SENHA_ANA\n"
        "    possui: 2\n", encoding="utf-8")
    d = projeto.carrega(yml)          # tem que passar na validacao
    assert d["contas"][0]["senha_em"] == "VEREDITO_SENHA_ANA"
    texto = yml.read_text(encoding="utf-8")
    assert "senha:" not in texto
    assert projeto.usuarios(d, {"VEREDITO_SENHA_ANA": "vinda-do-ambiente"}) == {
        "ana": ("ana@t.dev", "vinda-do-ambiente")}
