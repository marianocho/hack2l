"""Nenhum valor do PROJETO REVISADO pode ter padrao no nosso codigo.

🚨 POR QUE ESTE ARQUIVO EXISTE, e por que ele nao e' mais uma lista a mao.

Em 17/08 medi o `config.py`: **14 de 14** fallbacks com literal string usavam um
valor que o `desafio.yml` declara. Nove deles a bancada declara DIFERENTE --
ou seja, nove valores do desafio morando no nosso codigo como padrao universal.

Nao foi descuido. A linha `X = _projeto.get("x") or <valor do desafio>` e'
CICATRIZ DE MIGRACAO: o codigo nasceu contra o desafio e o `veredito.yml` foi
enxertado em 14/08. O `or` era a ponte que manteve tudo funcionando durante a
troca, e virou divida no segundo em que ela acabou.

🚨 E os 506 testes nao pegavam NENHUM. Todos rodam contra o desafio, e ali "leu
do yml" e "caiu no padrao" produzem o MESMO valor -- a suite e' cega para esta
classe por construcao. Foi assim que 14 fallbacks atravessaram 506 asseroes.

O `CLAUDE.md` dizia "foi preciso apontar para um SEGUNDO projeto". A versao
afiada e' o contrario: quem pega esta classe e' a AUSENCIA de projeto, e ela e'
de graca -- sem repo, sem container, sem API. E' o outro arquivo,
`test_projeto_nu.py`.

⚠️ E a forma do conserto importa: em 15/08 `app/api/tests` foi MEXIDO -- trocaram
o valor e deixaram o `or`. Mordeu de novo em 17/08, no Flask. Consertar o valor
trata o sintoma; o mecanismo e' o fallback existir.

## O criterio, derivado

Nada de blocklist. O oraculo sao os proprios descritores dos dois projetos
irmaos: **valor que o desafio declara e a bancada declara DIFERENTE nao pode
aparecer como literal no config**. Padrao novo do desafio falha sozinho, sem
ninguem lembrar de atualizar nada. Mesmo truque de `test_prompts_limpos`, na
peca onde ele morde de verdade.

Valor que os dois declaram IGUAL (`db`, `/health`, `email`, `docker-compose.yml`)
e' convencao, e continua podendo ser padrao.
"""
import ast
import pathlib

import pytest
import yaml

from veredito import config as cfg

RAIZ = pathlib.Path(__file__).resolve().parents[1]
FONTE_CONFIG = RAIZ / "veredito" / "config.py"

# Valores que sao NOSSOS, nao do projeto revisado: nomes de banco descartavel e
# da rede isolada. Aparecem no `desafio.yml` porque ele os documenta, nao porque
# sejam dele. O fallback aqui e' SEGURANCA -- `descartavel_testes` vazio faria
# `url_do_banco_descartavel()` montar uma URL quebrada, e a suite do cliente
# poderia acabar rodando no banco REAL, que e' o incidente de 11/08.
NOSSOS = {"kb_veredito", "kb_veredito_app", "veredito_isolada"}


def _folhas(caminho: pathlib.Path) -> dict[str, str]:
    """{caminho.da.chave: valor} de todo texto declarado no yml."""
    dado = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    plano: dict[str, str] = {}

    def anda(no, chave: str) -> None:
        if isinstance(no, dict):
            for k, v in no.items():
                anda(v, f"{chave}.{k}" if chave else str(k))
        elif isinstance(no, str) and no.strip():
            plano[chave] = no.strip()

    anda(dado, "")
    return plano


def _fallbacks() -> list[tuple[int, str, str]]:
    """(linha, expressao, literal) de todo `... or "literal"` no config."""
    fora = []
    for no in ast.walk(ast.parse(FONTE_CONFIG.read_text(encoding="utf-8"))):
        if isinstance(no, ast.BoolOp) and isinstance(no.op, ast.Or):
            for v in no.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str) and v.value.strip():
                    fora.append((no.lineno, ast.unparse(no), v.value))
    return fora


@pytest.fixture(scope="module")
def irmaos():
    desafio = _folhas(RAIZ / "projetos" / "desafio.yml")
    bancada_yml = RAIZ.parent / "bancada" / "veredito.yml"
    if not bancada_yml.is_file():
        pytest.skip("a bancada nao esta ao lado; o contraste precisa dos dois")
    return desafio, _folhas(bancada_yml)


# ------------------------------------------- a trava

def test_nenhum_valor_do_desafio_e_padrao_no_config(irmaos):
    """A trava derivada. O oraculo sao os dois ymls, nunca uma lista aqui."""
    desafio, bancada = irmaos
    sujos = []
    for linha, expr, literal in _fallbacks():
        if literal in NOSSOS:
            continue
        chaves = [k for k, v in desafio.items() if v == literal]
        difere = [k for k in chaves if k in bancada and bancada[k] != desafio[k]]
        if difere:
            k = difere[0]
            sujos.append(f"config.py:{linha}  {expr[:70]}\n"
                         f"      desafio {k}={desafio[k]!r}  bancada={bancada[k]!r}")
    assert not sujos, (
        "valor do projeto revisado como padrao no nosso codigo:\n"
        + "\n".join(sujos)
        + "\n\nPadrao que aponta para um projeto especifico e' PIOR que padrao "
          "nenhum: as sondas ficam verdes e a rodada segue contra o alvo errado."
    )


def test_a_trava_enxerga_o_que_ela_deve_enxergar(irmaos):
    """🚫 O controle, e sem ele a trava acima passaria vazia para sempre.

    Uma trava que nao encontra nada porque procura errado le exatamente igual a
    uma trava satisfeita. Aqui ela e' obrigada a demonstrar que reconhece um
    valor contaminado -- `/auth/login`, o caso real que quebrou a bancada.
    """
    desafio, bancada = irmaos
    assert desafio.get("auth.rota") == "/auth/login"
    assert bancada.get("auth.rota") == "/login", (
        "o contraste perdeu o par que ele existe para comparar")


def test_os_nossos_estao_declarados_por_um_motivo():
    """A excecao e' pequena, fechada e justificada -- nao uma valvula de escape.

    Se ela crescer, alguem esta usando `NOSSOS` para calar a trava em vez de
    tirar o chumbado.
    """
    assert len(NOSSOS) <= 3, (
        "a lista de excecao cresceu -- ela e' para valor NOSSO, nao para "
        "silenciar padrao do projeto revisado")


# ------------------------------------------- e o que os TEM_* prometem

@pytest.mark.parametrize("bandeira", ["TEM_APP", "TEM_PROVA_DIFERENCIAL",
                                      "TEM_AUTH", "TEM_BANCO", "ALCANCA_BANCO"])
def test_as_bandeiras_sao_derivadas_nunca_declaradas(bandeira):
    """Nenhuma pode vir de variavel de ambiente nem do yml.

    Declarar duas vezes e' convidar as duas a divergirem -- e' o motivo de o
    controle negativo ser deduzido de `possui: 0`. Aqui e' pior: uma bandeira
    ligada a mao reabriria exatamente o caminho que ela fecha.
    """
    fonte = FONTE_CONFIG.read_text(encoding="utf-8")
    atrib = next(n for n in ast.walk(ast.parse(fonte))
                 if isinstance(n, ast.Assign)
                 and any(getattr(t, "id", "") == bandeira for t in n.targets))
    texto = ast.unparse(atrib.value)
    assert "_s(" not in texto and "_b(" not in texto, (
        f"{bandeira} aceita ser declarada, e deveria ser so' derivada")
    assert hasattr(cfg, bandeira)
