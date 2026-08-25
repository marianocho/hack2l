"""O DETECTOR NU: apontado para um repositorio que nao declara nada.

Irmao do `test_projeto_nu.py`, e pelo mesmo motivo -- ali a licao e':

    A bancada acha bug por ser um segundo EXEMPLO.
    Quem acha ESTA classe e' a AUSENCIA de exemplo, e ela e' de graca.

Aplicada ao detector, a ausencia de exemplo e' ainda mais afiada, porque no
estado nu **nao existe valor certo para ele cair**. Qualquer campo preenchido
aqui e' chute, por construcao -- nao ha o que interpretar.

🚨 E chute e' pior do que ausencia, nao melhor. `projeto.py` trata AUSENTE como
limite honesto (o pre-voo diz o que se perdeu) e TORTO como `raise`. Campo
chutado nao levanta: ele *parece* declarado, e converte a categoria honesta na
categoria perigosa. Um gerador que chuta seria a maquina de fabricar rodadas que
parecem boas e nao sao -- que e' exatamente o que este produto existe para
impedir.

⚠️ A segunda trava daqui e' a que fecha a porta dos 14 fallbacks removidos em
17/08: eles nao podem voltar GERADOS. `test_projeto_nu` testa o *config*; este
testa o *detector*, e sao dois lugares diferentes por onde o mesmo valor do
vizinho entra.

Nao bate na API, nao sobe container, nao le repositorio real nenhum.
"""

from pathlib import Path

import pytest

from veredito import detector

# Valores que existem nos repositorios VIZINHOS desta maquina. Nenhum deles pode
# aparecer num repositorio nu -- se aparecer, veio de fallback, nao de leitura.
_DO_VIZINHO = ("app/api/app", "/code", "kb", "kb_veredito", "8000", "8100",
               "bancada", "app/api/tests", "hack2l", "demo@hack2l.dev",
               "docs/REGRAS.md", "/srv")


@pytest.fixture
def nu(tmp_path):
    """Um diretorio. Sem compose, sem Dockerfile, sem nada."""
    return tmp_path


def test_repo_nu_nao_deriva_campo_nenhum(nu):
    d = detector.detecta(nu)
    assert d.campos == {}, (
        "campo derivado de um repositorio vazio e' chute por construcao -- nao "
        f"havia o que ler: {d.campos}")


def test_repo_nu_produz_yaml_sem_nenhum_campo(nu):
    texto = detector.para_yaml(detector.detecta(nu))
    corpo = [l for l in texto.splitlines()
             if l.strip() and not l.strip().startswith("#") and l.strip() != "versao: 1"]
    assert corpo == [], f"o yml do repo nu tem conteudo: {corpo}"


def test_nenhum_valor_de_repositorio_VIZINHO_aparece_no_repo_nu(nu):
    """🚨 A trava que impede o `or <valor do desafio>` de voltar GERADO.

    17/08 removeu 14 fallbacks com literal no `config.py`. Um detector que
    chutasse os mesmos valores reintroduziria a divida inteira -- agora por um
    caminho que o `test_projeto_nu` nao alcanca, porque ele mede o config.
    """
    texto = detector.para_yaml(detector.detecta(nu))
    vazou = [v for v in _DO_VIZINHO if v in texto]
    assert not vazou, (
        f"valor de repositorio vizinho num repositorio VAZIO: {vazou}. Nao ha de "
        "onde isso ter sido lido -- e' fallback chumbado com outra roupa")


def test_repo_nu_explica_a_causa_em_vez_de_ficar_mudo(nu):
    d = detector.detecta(nu)
    motivo = d.ausentes.get("app.compose", "")
    assert "compose" in motivo, (
        "ausencia sem causa se le como 'a ferramenta nao funcionou'; com causa se "
        "le como 'o seu repositorio nao tem um contrato de maquina para eu ler'")


def test_repo_nu_ainda_faz_as_duas_perguntas(nu):
    """🚨 As duas perguntas NAO dependem de ter detectado alguma coisa.

    Elas sao sobre `contas` e `contexto` -- os dois campos que fecham as duas
    vias da R1. Um repositorio sem compose e' exatamente aquele em que o operador
    mais precisa saber o que ainda falta; calar ali porque "nao detectei nada"
    seria a guarda condicionada ao sinal errado.
    """
    d = detector.detecta(nu)
    assert len(d.perguntas) == 2


def test_compose_vazio_tambem_nao_inventa(tmp_path):
    """Arquivo existe e nao declara servico: nao ha o que derivar."""
    (tmp_path / "docker-compose.yml").write_text("services:\n", encoding="utf-8")
    d = detector.detecta(tmp_path)
    derivados = {c: v.valor for c, v in d.campos.items()
                 if v.de != "convencao do Veredito" and c != "app.compose"}
    assert derivados == {}, f"inventou a partir de um compose vazio: {derivados}"


def test_compose_quebrado_nao_derruba_o_comando(tmp_path):
    """YAML torto e' engano do operador -- mas o detector le, nao valida.

    Ele nao levanta: quem levanta em arquivo torto e' o `projeto.carrega`, na
    hora da rodada. Aqui o desfecho certo e' nao derivar nada.
    """
    (tmp_path / "docker-compose.yml").write_text(
        "services:\n  api:\n   - isto: [nao\n", encoding="utf-8")
    d = detector.detecta(tmp_path)
    assert isinstance(d.campos, dict)


def test_o_repo_nu_nao_escreve_arquivo_nenhum(nu):
    detector.detecta(nu)
    assert list(nu.iterdir()) == []
