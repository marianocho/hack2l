"""A ULTIMA MILHA: publicar o parecer, e nao empilhar.

Ate 18/08 este caminho nunca tinha executado. Os 12 testes de
`test_comentario_de_pr.py` cobrem MONTAR o comentario e CORTAR no teto; o que
faltava era `posta()` e `acha_o_nosso()` -- POST, achar o anterior pela marca
invisivel, PATCH em vez de empilhar.

E' a parte que transforma isto em produto, e era a unica sem trava. Rodar a
Action de verdade para descobrir que a publicacao esta torta custa dinheiro e
quatro minutos de CI; descobrir aqui custa milissegundos.

## Por que a marca, e nao o autor

Numa Action o autor e' `github-actions[bot]`; na maquina de alguem e' a conta
dessa pessoa. A MESMA rodada tem que se reconhecer nos dois casos, entao a
busca e' pelo corpo. Se ela fosse pelo autor, a rodada da CI nao acharia o
comentario que a rodada local deixou -- e apareceriam dois pareceres.

## O contrato que fecha o circulo

`posta` publica um corpo que `acha_o_nosso` consegue achar depois. As duas
metades sao testadas JUNTAS (`test_o_circulo_fecha`): cada uma sozinha pode
estar certa e o par errado -- e' esse par que decide entre "um comentario que
se atualiza" e "doze comentarios num PR de tres dias".
"""
import pytest
import requests

import posta_parecer as pp
from veredito import comentario


class _Resposta:
    def __init__(self, corpo, status=200):
        self._corpo, self.status_code = corpo, status

    def json(self):
        return self._corpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class _GitHubFalso:
    """Os comentarios de um PR, e as chamadas que chegaram ate eles.

    Confere a FORMA das URLs: listar e criar sao `/issues/<numero>/comments`,
    mas editar e' `/issues/comments/<id>` -- sem o numero do PR. Trocar uma
    pela outra so' da 404 contra a API de verdade.

    🚨 `status_leitura` e `status_escrita` sao SEPARADOS de proposito. A
    primeira versao deste dublê tinha um status so', e o teste da recusa passava
    pelo motivo errado: com 403 em tudo, quem levantava era o `raise_for_status`
    do GET dentro de `acha_o_nosso`, e o do POST podia ser apagado que o teste
    seguia verde. Confirmado injetando -- 12 passaram com a guarda removida.
    E' o "teste que acusa a coisa errada" do CLAUDE.md, dentro do teste escrito
    para a ultima milha.
    """

    def __init__(self, comentarios=(), status_leitura=200, status_escrita=200):
        self.comentarios = [dict(c) for c in comentarios]
        self.status_leitura, self.status_escrita = status_leitura, status_escrita
        self.chamadas: list[tuple[str, str]] = []
        self._proximo_id = 900

    def get(self, url, headers=None, params=None, timeout=None):
        self.chamadas.append(("GET", url))
        assert url.endswith("/comments"), url
        por_pagina = (params or {}).get("per_page", 30)
        pagina = (params or {}).get("page", 1)
        inicio = (pagina - 1) * por_pagina
        return _Resposta(self.comentarios[inicio:inicio + por_pagina],
                         self.status_leitura)

    def post(self, url, headers=None, json=None, timeout=None):
        self.chamadas.append(("POST", url))
        assert "/issues/comments/" not in url, (
            "criar e' no PR (/issues/<numero>/comments), nao na rota de editar")
        self._proximo_id += 1
        novo = {"id": self._proximo_id, "body": json["body"],
                "html_url": f"https://github.com/d/r/pull/1#c{self._proximo_id}"}
        self.comentarios.append(novo)
        return _Resposta(novo, self.status_escrita)

    def patch(self, url, headers=None, json=None, timeout=None):
        self.chamadas.append(("PATCH", url))
        assert "/issues/comments/" in url, (
            "editar e' /issues/comments/<id>, sem o numero do PR")
        ident = int(url.rsplit("/", 1)[1])
        for c in self.comentarios:
            if c["id"] == ident:
                c["body"] = json["body"]
                return _Resposta(c, self.status_escrita)
        raise AssertionError(f"PATCH em comentario que nao existe: {ident}")

    @property
    def metodos(self):
        return [m for m, _ in self.chamadas]


URL = "https://github.com/dono/repo/pull/7"
CAB = {"Authorization": "Bearer x"}


@pytest.fixture
def gh(monkeypatch):
    def _monta(comentarios=(), status_leitura=200, status_escrita=200):
        falso = _GitHubFalso(comentarios, status_leitura, status_escrita)
        monkeypatch.setattr(pp, "requests", falso)
        return falso
    return _monta


def _com(ident, corpo, autor="alguem"):
    return {"id": ident, "body": corpo, "user": {"login": autor},
            "html_url": f"https://github.com/d/r/pull/7#c{ident}"}


# ------------------------------------------- achar o nosso

def test_acha_pela_marca_e_nao_pelo_autor(gh):
    """Numa Action o autor e' o bot; na maquina de alguem e' a pessoa."""
    gh([_com(1, "otimo PR", autor="humano"),
        _com(2, comentario.MARCA + "\n## Veredito", autor="github-actions[bot]")])
    assert pp.acha_o_nosso("dono", "repo", 7, CAB) == 2


def test_acha_o_nosso_deixado_por_OUTRO_autor(gh):
    """A rodada local deixou o comentario; a da CI tem que reconhece-lo.

    Sem isto o mesmo PR ganharia um parecer do bot e outro da pessoa.
    """
    gh([_com(5, comentario.MARCA + "\nparecer", autor="luisfelp07")])
    assert pp.acha_o_nosso("dono", "repo", 7, CAB) == 5


def test_sem_a_marca_e_None_e_nao_o_primeiro_que_aparecer(gh):
    """Comentario de terceiro nunca pode ser confundido com o nosso -- um PATCH
    ali reescreveria o texto de outra pessoa."""
    gh([_com(1, "LGTM"), _com(2, "## Veredito sem marca")])
    assert pp.acha_o_nosso("dono", "repo", 7, CAB) is None


def test_pagina_ate_achar(gh):
    """PR movimentado tem mais de 100 comentarios, e o nosso envelhece para o
    fim da lista. Parar na primeira pagina faria o bot empilhar EXATAMENTE nos
    PRs mais longos -- onde empilhar mais incomoda."""
    muitos = [_com(i, f"comentario {i}") for i in range(100)]
    muitos.append(_com(777, comentario.MARCA + "\nparecer"))
    falso = gh(muitos)
    assert pp.acha_o_nosso("dono", "repo", 7, CAB) == 777
    assert falso.metodos == ["GET", "GET"], "a segunda pagina nao foi pedida"


def test_lista_vazia_nao_quebra(gh):
    gh([])
    assert pp.acha_o_nosso("dono", "repo", 7, CAB) is None


# ------------------------------------------- publicar

def test_sem_comentario_anterior_CRIA(gh):
    falso = gh()
    saida = pp.posta(URL, comentario.MARCA + "\nprimeiro parecer", CAB)
    assert falso.metodos == ["GET", "POST"]
    assert saida.startswith("criado:")
    assert len(falso.comentarios) == 1


def test_com_comentario_anterior_ATUALIZA_e_nao_empilha(gh):
    falso = gh([_com(42, comentario.MARCA + "\nparecer velho")])
    saida = pp.posta(URL, comentario.MARCA + "\nparecer novo", CAB)
    assert "POST" not in falso.metodos, "empilhou um segundo comentario no PR"
    assert falso.metodos == ["GET", "PATCH"]
    assert saida.startswith("atualizado:")
    assert len(falso.comentarios) == 1, "o PR ficou com dois pareceres"
    assert "parecer novo" in falso.comentarios[0]["body"]


def test_o_circulo_fecha(gh):
    """A rodada 2 tem que achar o que a rodada 1 publicou.

    E' o teste que as duas Actions de verdade custam 8 minutos para dar: as
    duas metades certas em SEPARADO ainda deixam doze comentarios no PR se o
    corpo publicado nao carregar a marca.
    """
    falso = gh()
    corpo = comentario.monta({"condenados": [], "descartados": [],
                              "inconclusivos": []}, {}, {})
    assert pp.posta(URL, corpo, CAB).startswith("criado:")
    assert pp.posta(URL, corpo, CAB).startswith("atualizado:")
    assert len(falso.comentarios) == 1, (
        "o corpo publicado nao carrega a marca que a rodada seguinte procura")


def test_recusa_no_CRIAR_sobe_e_nao_vira_sucesso(gh):
    """403 sem `pull-requests: write` e' o erro mais provavel numa Action nova.
    Engolir vira "postado" num PR que continua sem parecer.

    ⚠️ A leitura vai 200 DE PROPOSITO: com 403 tambem no GET, quem levantava
    era `acha_o_nosso`, e esta guarda podia ser removida sem ninguem ver.
    """
    gh(status_escrita=403)
    with pytest.raises(requests.HTTPError):
        pp.posta(URL, comentario.MARCA + "\nx", CAB)


def test_recusa_no_ATUALIZAR_sobe_e_nao_vira_sucesso(gh):
    """O outro ramo. Um comentario apagado a mao no PR deixa a marca achavel no
    cache e o PATCH devolve 404: silenciar aqui diria "atualizado" para sempre,
    num PR que nunca mais recebeu parecer."""
    gh([_com(42, comentario.MARCA + "\nvelho")], status_escrita=404)
    with pytest.raises(requests.HTTPError):
        pp.posta(URL, comentario.MARCA + "\nnovo", CAB)


def test_recusa_no_LISTAR_sobe(gh):
    """E a leitura tambem: token sem escopo devolve 403 no GET, e seguir para o
    POST criaria um segundo comentario por nao ter conseguido ver o primeiro."""
    gh(status_leitura=403)
    with pytest.raises(requests.HTTPError):
        pp.posta(URL, comentario.MARCA + "\nx", CAB)


def test_url_do_pr_vira_dono_repo_numero(gh):
    """O numero do PR sai da URL: publicar no PR errado e' pior que nao
    publicar."""
    falso = gh()
    pp.posta("https://github.com/luisfelp07/bancada/pull/1",
             comentario.MARCA + "\nx", CAB)
    criado = [u for m, u in falso.chamadas if m == "POST"][0]
    assert criado.endswith("/repos/luisfelp07/bancada/issues/1/comments"), criado


# ------------------------------------------- o dry-run

def test_sem_postar_nao_toca_na_rede(gh, monkeypatch, capsys):
    """DRY-RUN E' O PADRAO. Se o caminho sem `--postar` chamasse a API, a
    conferencia "olha como vai ficar" publicaria."""
    falso = gh()
    monkeypatch.setattr(pp.comentario, "do_disco", lambda meta=None: "corpo qualquer")
    monkeypatch.setattr("sys.argv", ["posta_parecer.py", URL])
    assert pp.main() == 0
    assert falso.chamadas == [], "o dry-run falou com o GitHub"
    assert "DRY-RUN" in capsys.readouterr().out


def test_sem_token_nao_tenta_e_diz_por_que(gh, monkeypatch, capsys):
    """Sem token o GitHub responde 404, que se le como "o PR nao existe" e
    manda procurar no lugar errado -- a mesma mentira do repo privado."""
    falso = gh()
    monkeypatch.setattr(pp.comentario, "do_disco", lambda meta=None: "corpo")
    monkeypatch.setattr(pp.entrada, "_cabecalhos", dict)
    monkeypatch.setattr("sys.argv", ["posta_parecer.py", URL, "--postar"])
    assert pp.main() == 2
    assert falso.chamadas == []
    assert "GH_TOKEN" in capsys.readouterr().err
