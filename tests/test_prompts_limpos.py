"""As lentes nao podem carregar o desafio para dentro de outro repositorio.

Este arquivo existe porque o defeito de 08/08 estava NO PROMPT, e nada testava
prompt. Os seis .md chumbavam `AC1`-`AC5`, `R1`-`R4`, `C1`-`C8` e o app do
desafio, entao 94 de 94 arbitros em 10 PRs de Flask, Django, Gin, Next.js e
Requests citavam os criterios de aceite da Vindler. Ver
`ACHADO_ARBITRO_CHUMBADO.md`.

O conserto e' um texto, e texto regride sozinho: alguem cola um exemplo do
desafio num prompt para "deixar mais concreto" e a contaminacao volta sem que
nenhum teste caia. Estes testes leem exatamente o que vai para o modelo --
`promotores.lentes()` -- e nao o que achamos que esta la.

Nao bate na API.
"""
import ast
import pathlib
import re

import pytest

from veredito import arbitro as arb
from veredito import config as cfg
from veredito import promotores

LENTES = promotores.lentes()
NOMES = [n for n, _ in LENTES]

# Identificadores do app do desafio. Nomes-persona genericos (alice, bob, carol)
# NAO entram: sao a convencao universal para explicar isolamento, nao
# vocabulario do Hack2L.
MARCAS_DO_DESAFIO = (
    "shared-with-me", "hack2l.dev", "shares.py", "REVIEW_TASK", "REFERENCE_GUIDE",
    "pr/document-sharing", "text-embedding-3-small",
)


def _corpo(texto: str) -> str:
    """Sem a linha `<!-- tag: hack2l -->`, que e' marcador do nosso repo."""
    return "\n".join(l for l in texto.splitlines() if not l.strip().startswith("<!--"))


# ------------------------------------------- vocabulario de projeto, DERIVADO
#
# 🚨 A lacuna que isto fecha, exposta duas vezes em 16-17/08 -- pelo Claude que
# escrevia os prompts, no mesmo dia, depois de ter escrito o aviso.
#
# `MARCAS_DO_DESAFIO` acima e' lista MANTIDA A MAO. Ela pega `shares.py` e
# `hack2l.dev` porque alguem digitou. Nao pegava `adiciona_membro`,
# `project_id` nem `POST /projects/{id}/members` -- nomes reais da BANCADA que
# entraram numa lente que revisa qualquer repositorio do mundo.
#
# E nao adianta acrescentar os nomes da bancada na lista: o projeto seguinte
# traz nomes novos e ninguem vai lembrar. Lista de proibidos e' PREDICAO, e
# predicao ja perdeu duas vezes aqui.
#
# O criterio nao precisa de lista: **nome que aparece em UM projeto e nao no
# outro e' vocabulario daquele projeto; nome que aparece nos dois e' universal.**
# Com desafio e bancada lado a lado, `get_db`, `User`, `/health` e `/login` caem
# fora sozinhos, e `adiciona_membro` e `/shared-with-me` ficam. Projeto novo
# entra na conta sem ninguem editar teste.
_IGNORA_DIR = {".git", "node_modules", "__pycache__", ".venv", ".worktrees"}

# Abaixo disso o nome quase sempre e' fragmento generico (`/`, `User`, `health`)
# e o casamento por substring viraria ruido. Limite conhecido, nao cobertura.
_MIN = 8


def _identificadores(raiz: pathlib.Path) -> set[str]:
    """Nomes de funcao/classe e rotas literais definidos no codigo do projeto."""
    nomes: set[str] = set()
    for py in raiz.rglob("*.py"):
        if any(p in _IGNORA_DIR for p in py.parts):
            continue
        try:
            arvore = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError, ValueError):
            continue
        for n in ast.walk(arvore):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                nomes.add(n.name)
            elif isinstance(n, ast.Constant) and isinstance(n.value, str) \
                    and n.value.startswith("/"):
                nomes.add(n.value)
    return nomes


def _projetos_vizinhos() -> list[pathlib.Path]:
    """Todo repo irmao com `app/` -- desafio, bancada, e o que vier depois."""
    return sorted(p / "app" for p in cfg.RAIZ.parent.iterdir()
                  if p.is_dir() and p.name != cfg.RAIZ.name and (p / "app").is_dir())


def _vocabulario_de_projeto() -> set[str]:
    vizinhos = _projetos_vizinhos()
    if len(vizinhos) < 2:
        # 🚫 Nunca devolver conjunto vazio aqui: vazio faria a assercao passar
        # por ausencia de dado, que e' a guarda muda que este projeto ja pagou
        # tres vezes. Quem chama SKIPA com a causa.
        raise LookupError(
            f"preciso de 2+ projetos irmaos para contrastar, achei {len(vizinhos)}: "
            f"{[str(v.parent.name) for v in vizinhos]}")
    conjuntos = [_identificadores(v) for v in vizinhos]
    universal = set.intersection(*conjuntos)
    especifico = set.union(*conjuntos) - universal
    return {n for n in especifico if len(n) >= _MIN}


def _cita(nome: str, texto: str) -> bool:
    """Casamento com FRONTEIRA, nunca substring nua.

    ⚠️ A primeira versao deste detector procurava substring, e acusou `Document`
    dentro da palavra portuguesa **Documentos** em dois prompts. Teste que acusa
    a coisa errada nao vale mais que teste que nao acusa nada -- e' a mesma
    familia do `kb` casando dentro de `kb_veredito_app` e do `override=True`
    casando no comentario que explicava por que ele estava desligado.
    """
    return re.search(rf"(?<![0-9A-Za-zÀ-ÿ_]){re.escape(nome)}(?![0-9A-Za-zÀ-ÿ_])",
                     texto) is not None


@pytest.mark.parametrize("nome,texto", LENTES, ids=NOMES)
def test_nenhuma_lente_cita_vocabulario_de_UM_projeto(nome, texto):
    """A lente nao pode nomear rota, funcao ou modelo de um alvo especifico.

    Foi assim que 93 acusacoes citaram os criterios da Vindler em repositorios
    de Flask, Django e Gin. O texto era do desafio; o defeito e' de forma, e a
    forma se repete com qualquer projeto -- inclusive com a nossa bancada, que
    e' onde ela reapareceu.
    """
    try:
        proibidos = _vocabulario_de_projeto()
    except LookupError as e:
        pytest.skip(str(e))
    corpo = _corpo(texto)
    presentes = sorted(n for n in proibidos if _cita(n, corpo))
    assert not presentes, (
        f"{nome}.md cita vocabulario de um projeto especifico: {presentes}. "
        "Troque por descricao generica -- 'o endpoint alterado', 'a restricao "
        "de unicidade' -- senao a lente leva este alvo para dentro de todo "
        "repositorio que ela revisar.")


def test_o_detector_pega_a_violacao_injetada():
    """A guarda vista FALHANDO -- senao ela passa por nao achar nada.

    Usa um nome real de projeto vizinho em vez de inventado: o teste acima so'
    vale se o conjunto derivado estiver de fato populado, e um nome fabricado
    passaria mesmo com o conjunto vazio.
    """
    try:
        proibidos = _vocabulario_de_projeto()
    except LookupError as e:
        pytest.skip(str(e))
    assert proibidos, "conjunto derivado vazio: o detector nao detectaria nada"
    alvo = sorted(proibidos)[0]
    texto = f"## Como escrever\n\nEx.: chamar `{alvo}` e conferir a resposta.\n"
    assert [n for n in proibidos if _cita(n, texto)], (
        f"o detector nao pegou `{alvo}` num texto que o cita")


def test_as_seis_lentes_continuam_sendo_carregadas():
    """Se o loader parar de achar um .md, a lente some em silencio e nenhum
    outro teste aqui reclama -- todos passariam com zero arquivos."""
    assert len(LENTES) == 6, NOMES
    assert set(NOMES) == {"prd", "injection", "vazamento_contexto", "correcao",
                          "padroes", "performance"}


@pytest.mark.parametrize("nome,texto", LENTES)
def test_nenhuma_lente_cita_o_vocabulario_chumbado(nome, texto):
    """AC1-AC5, R1-R4, C1-C8, INV-*: os rotulos que viajavam junto.

    E nenhum deles existia sequer no repo do desafio -- `grep AC1 docs/` nao
    acha nada la. Nos inventamos a numeracao e depois mandamos o modelo citar
    "verbatim" um vocabulario que nao esta escrito em lugar nenhum.
    """
    achados = arb.cita_vocabulario_chumbado(_corpo(texto))
    assert not achados, f"{nome}.md voltou a citar {achados}"


@pytest.mark.parametrize("nome,texto", LENTES)
def test_nenhuma_lente_chumba_o_app_do_desafio(nome, texto):
    """O PRD saiu, mas o app tambem tem que sair: uma lente que anuncia
    "o app tem um endpoint /chat que faz RAG" nao esta lendo o repositorio a
    frente dela, esta recitando o desafio -- e e' a mesma doenca."""
    corpo = _corpo(texto).lower()
    presentes = [m for m in MARCAS_DO_DESAFIO if m.lower() in corpo]
    assert not presentes, f"{nome}.md chumba o app do desafio: {presentes}"


@pytest.mark.parametrize("nome,texto", LENTES)
def test_toda_lente_ensina_o_arbitro_com_procedencia(nome, texto):
    """O contrato tem que estar nas seis, nao em cinco: a lente que esquecer
    volta a emitir sigla solta, e a sigla solta passa pelo parse."""
    assert "procedência" in texto or "procedencia" in texto, nome
    assert '"onde"' in texto, f"{nome}.md nao mostra o campo onde"
    assert '"regra"' in texto, f"{nome}.md nao mostra o campo regra"


@pytest.mark.parametrize("nome,texto", LENTES)
def test_toda_lente_autoriza_null_explicitamente(nome, texto):
    """Sem isto o modelo preenche o campo de qualquer jeito -- foi exatamente
    o que ele fez por 209 acusacoes. `null` precisa ser dito como resposta
    CERTA, nao como falha em achar algo."""
    assert "`null`" in texto, nome


@pytest.mark.parametrize("nome,texto", LENTES)
def test_toda_lente_continua_pedindo_cobertura(nome, texto):
    """Regressao na direcao oposta: desacoplar o arbitro nao pode ter virado
    um pedido de seletividade. O promotor filtrar e' o produto inteiro ao
    contrario -- quem filtra e' o advogado, que tem ferramenta."""
    assert "Cobertura, não seletividade" in texto, nome


# ------------------------------------------------------- o contexto, do lado certo

def test_o_contexto_do_desafio_existe_e_traz_procedencia():
    """O material do desafio nao foi apagado, foi MOVIDO: sai da lente, entra
    como contexto do repositorio sob revisao, com arquivo e linha."""
    ctx = cfg.contexto_do_repo()
    assert ctx, "contexto/hack2l.md sumiu -- os promotores perdem o arbitro no desafio"
    assert "docs/REVIEW_TASK.md:" in ctx
    assert "docs/REFERENCE_GUIDE.md:" in ctx


def test_o_contexto_nao_reintroduz_a_numeracao_inventada():
    """Mover o PRD para o contexto nao vale se ele chegar rotulado como AC2:
    o modelo cita o rotulo de novo e a procedencia volta a ser decorativa."""
    achados = arb.cita_vocabulario_chumbado(cfg.contexto_do_repo() or "")
    assert not achados, f"contexto/hack2l.md traz numeracao inventada: {achados}"


def test_contexto_ausente_nao_quebra_e_nao_inventa_bloco_vazio(tmp_path, monkeypatch):
    """Repositorio que nao documenta nada roda sem contexto -- que e' o caso da
    esmagadora maioria dos PRs do mundo, e o caso que a regua exercita."""
    monkeypatch.setattr(cfg, "CONTEXTO", tmp_path / "nao_existe.md")
    assert cfg.contexto_do_repo() is None
    (tmp_path / "vazio.md").write_text("   \n\n", encoding="utf-8")
    monkeypatch.setattr(cfg, "CONTEXTO", tmp_path / "vazio.md")
    assert cfg.contexto_do_repo() is None


# ------------------------------------------- prova nao-destrutiva (11/08)

@pytest.mark.parametrize("nome,texto", LENTES, ids=NOMES)
def test_lente_que_prova_SQL_injection_manda_read_only(nome, texto):
    """A rodada de 11/08 recusou 2 de 10 acusacoes: o Haiku gerou `provado_se`
    com `DROP TABLE users`, o classificador cyber recusou, e o advogado teria
    rodado aquilo contra o app REAL, com dados reais.

    So vale para lentes que propoem prova de SQL/banco. A lente de prompt
    injection usa SENTINELA, que e' nao-destrutiva por construcao -- cobrada no
    teste seguinte.
    """
    baixo = texto.lower()
    # SQL **explorável**, nao qualquer mencao a SQL: o promotor de performance
    # fala em "log SQL" para contar queries, e nao propoe payload nenhum.
    if not ("sql" in baixo and "inje" in baixo):
        return
    assert "read-only" in baixo, f"{nome} propoe prova de SQL sem mandar read-only"
    assert "1'='1" in texto, f"{nome} nao da o payload nao-destrutivo como padrao"
    assert "drop" in baixo, f"{nome} nao proibe explicitamente o destrutivo"


def test_a_lente_de_prompt_injection_prova_por_sentinela():
    """Sentinela e' prova de leitura: o modelo emite um texto improvavel se
    obedeceu. Nao altera estado, entao nao ha o que destruir."""
    texto = dict(LENTES)["injection"]
    assert "sentinela" in texto.lower()


def test_o_advogado_proibe_prova_destrutiva():
    """A salvaguarda que vale: mesmo que um promotor peca DROP TABLE, o advogado
    -- que e' quem tem http_request apontado pro banco vivo -- nao executa."""
    from veredito.advogado import SISTEMA
    s = SISTEMA.lower()
    for proibido in ("drop", "delete", "read-only"):
        assert proibido in s, f"o advogado nao menciona '{proibido}'"


def test_a_regra_distingue_criar_de_destruir():
    """Medido em 14/08: a rodada criou 3 linhas em `shares` provando a injection.

    A regra antiga -- "prove SEMPRE de forma que so LE" -- e' impossivel de
    cumprir quando o defeito mora num endpoint de escrita: para provar injecao
    na rota que compartilha documento, tem que chamar a rota que compartilha
    documento. Nao foi desobediencia do modelo; foi regra que o desenho viola
    por construcao.

    Isso importa alem deste caso: regra impossivel no mesmo prompt ensina que
    as regras dali sao aproximadas -- e as outras regras deste prompt sao as que
    impedem o advogado de apagar o banco do cliente.

    A linha correta e' entre CRIAR e DESTRUIR, e o prompt tem que dizer as duas
    metades. So' a proibicao, sem a permissao, e' a regra impossivel de novo.
    """
    from veredito.advogado import SISTEMA
    s = SISTEMA.lower()
    assert "pre-existente" in s or "ja existia" in s, (
        "o prompt nao diz que o proibido e' mexer no que JA EXISTIA -- sem isso "
        "a regra volta a ser 'nunca escreva', que o desenho viola sozinho")
    assert "endpoint documentado" in s or "rota que compartilha" in s, (
        "o prompt nao reconhece que chamar endpoint de escrita e' legitimo "
        "quando o defeito mora nele")


def test_a_permissao_de_criar_nao_afrouxa_o_payload():
    """A permissao vale para a CHAMADA, nunca para o payload injetado.

    Sao coisas diferentes e confundi-las desfaz a salvaguarda de 11/08: chamar
    POST /share e' usar o app como ele foi feito; injetar `'; INSERT` e' fazer o
    banco executar o que voce escreveu. O segundo continua proibido.
    """
    from veredito.advogado import SISTEMA
    s = SISTEMA.lower()
    assert "payload" in s and "read-only" in s, (
        "o prompt nao amarra o read-only ao PAYLOAD especificamente")
    assert "insert" in s, (
        "INSERT saiu da lista de SQL proibido -- escrita via SQL injetado nao e' "
        "a mesma coisa que chamar um endpoint documentado")
