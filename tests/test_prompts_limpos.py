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
