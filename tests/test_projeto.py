"""O `veredito.yml` -- o projeto sob revisão descrito por ele mesmo.

Até 14/08 as quatro contas de teste estavam chumbadas em `config.py`. Isso fazia
a prova ponta a ponta -- única via que sustenta CRÍTICA junto com o árbitro --
funcionar só no repositório do desafio. Apontar o Veredito para outro projeto
rendia leitura e grep, e mais nada.

O que estes testes travam não é "o yaml carrega". É o comportamento quando ele
está AUSENTE, INCOMPLETO ou ERRADO -- porque é aí que o produto ou degrada com
honestidade, ou mente em silêncio.
"""

from pathlib import Path

import pytest

from veredito import projeto


def _escreve(tmp_path: Path, texto: str) -> Path:
    p = tmp_path / "veredito.yml"
    p.write_text(texto, encoding="utf-8")
    return p


COMPLETO = """
versao: 1
app:
  api: http://127.0.0.1:9000
contas:
  - {nome: dono,   email: d@x.dev, senha: s1, possui: 2}
  - {nome: outro,  email: o@x.dev, senha: s2, possui: 1}
  - {nome: ninguem, email: n@x.dev, senha: s3, possui: 0}
contexto: docs/REGRAS.md
"""


# --------------------------------------------------- ausencia e' legitima

def test_sem_arquivo_devolve_vazio_e_nao_levanta():
    """🚨 Projeto que não descreve suas contas continua sendo revisável -- com
    leitura e grep. Levantar aqui transformaria "este repo não tem veredito.yml"
    em "o Veredito não roda neste repo", que são coisas muito diferentes."""
    assert projeto.carrega(None) == {}


def test_arquivo_vazio_devolve_vazio(tmp_path):
    assert projeto.carrega(_escreve(tmp_path, "")) == {}


def test_avisa_o_que_o_projeto_perde_sem_contas():
    """E avisa ANTES de gastar. Sem isso a rodada sai toda em MÉDIA e parece o
    produto não funcionando, quando é o projeto que não se descreveu."""
    avisos = projeto.avisos({})
    assert any("prova ponta a ponta" in a for a in avisos)
    assert any("MEDIA" in a for a in avisos)


# ------------------------------- 🚨 as tres contas, e a que nao tem nada

def test_menos_de_tres_contas_e_denunciado():
    """Carlos Dutra, 06/08, verbatim: "anything involving one user's access to
    another user's data needs at least three accounts to test properly"."""
    d = {"contas": [{"nome": "a", "email": "a@x", "senha": "s"},
                    {"nome": "b", "email": "b@x", "senha": "s"}]}
    assert any("tres" in a for a in projeto.avisos(d))


def test_sem_controle_negativo_e_denunciado():
    """A conta que não possui nada é a mais valiosa da lista e a que ninguém
    lembra de criar. Foi ela que provou a CRÍTICA de 14/08: carol obteve 200 num
    documento compartilhado entre alice e bob."""
    d = {"contas": [{"nome": "a", "email": "a@x", "senha": "s", "possui": 1},
                    {"nome": "b", "email": "b@x", "senha": "s", "possui": 2},
                    {"nome": "c", "email": "c@x", "senha": "s", "possui": 3}]}
    assert projeto.controle_negativo(d) is None
    assert any("controle negativo" in a for a in projeto.avisos(d))


def test_controle_negativo_sai_do_possui_zero(tmp_path):
    d = projeto.carrega(_escreve(tmp_path, COMPLETO))
    assert projeto.controle_negativo(d) == "ninguem"


def test_projeto_completo_nao_gera_aviso_nenhum(tmp_path):
    """Silêncio quando está tudo certo. Aviso que aparece sempre treina o
    operador a pular a seção, e aí ele não serve quando importa."""
    d = projeto.carrega(_escreve(tmp_path, COMPLETO))
    regras = tmp_path / "docs" / "REGRAS.md"
    regras.parent.mkdir()
    regras.write_text("as regras\n", encoding="utf-8")
    assert projeto.avisos(d, regras) == []


# ------------------------------------ arquivo escrito errado LEVANTA

def test_yaml_quebrado_levanta(tmp_path):
    """Ausência degrada; arquivo ERRADO não. Escrever errado é engano do
    operador, e seguir com metade do arquivo produziria uma rodada que parece
    boa e não é."""
    with pytest.raises(projeto.ProjetoInvalido):
        projeto.carrega(_escreve(tmp_path, "contas: [{nome: a\n  isto: nao fecha"))


def test_raiz_que_nao_e_mapa_levanta(tmp_path):
    with pytest.raises(projeto.ProjetoInvalido, match="mapa"):
        projeto.carrega(_escreve(tmp_path, "- so\n- uma\n- lista\n"))


def test_conta_sem_senha_levanta(tmp_path):
    """Conta incompleta é pior que conta ausente: o login falha no meio da
    rodada, vira INCONCLUSIVO de infraestrutura, e parece defeito do app."""
    with pytest.raises(projeto.ProjetoInvalido, match="senha"):
        projeto.carrega(_escreve(tmp_path, "contas:\n  - {nome: a, email: a@x}\n"))


def test_contas_com_nome_repetido_levanta(tmp_path):
    """`usuarios()` é um dict por nome: a segunda calaria a primeira, e uma
    conta declarada simplesmente não existiria."""
    with pytest.raises(projeto.ProjetoInvalido, match="mesmo `nome`"):
        projeto.carrega(_escreve(tmp_path,
                                 "contas:\n"
                                 "  - {nome: a, email: 1@x, senha: s}\n"
                                 "  - {nome: a, email: 2@x, senha: s}\n"))


def test_contas_vazio_levanta(tmp_path):
    """`contas: []` é diferente de não ter a chave -- alguém escreveu e errou."""
    with pytest.raises(projeto.ProjetoInvalido, match="nao vazia"):
        projeto.carrega(_escreve(tmp_path, "contas: []\n"))


# ------------------------- 🚨 contexto declarado e apontando para o nada

def test_contexto_inexistente_e_denunciado(tmp_path):
    """"Não declarei contexto" e "declarei e digitei errado" são coisas
    diferentes, e só a segunda é bug. Tratadas iguais, um caminho errado sai
    como árbitro `null` -- que parece o repositório não documentar nada."""
    d = projeto.carrega(_escreve(tmp_path, COMPLETO))
    avisos = projeto.avisos(d, tmp_path / "nao" / "existe.md")
    assert any("nao existe" in a and "engano" in a for a in avisos)


def test_env_que_sobrepoe_o_projeto_e_denunciado():
    """🚨 O caso que quase invalidou a primeira medição da bancada (15/08).

    O `.env` do Veredito tinha `APP_API_URL=...:8000` do desafio; a bancada
    declara `:8100`. A rodada revisaria o código da bancada **conversando com o
    app do desafio** — e o pré-voo diria `health -> 200`, porque o outro app
    responde. Medição inteira inválida, sem um único sinal.
    """
    d = {"app": {"api": "http://127.0.0.1:8100"}}
    conflitos = projeto.ensombrado_pelo_env(d, {"APP_API_URL": "http://127.0.0.1:8000"})
    assert len(conflitos) == 1 and "8100" in conflitos[0] and "8000" in conflitos[0]


def test_env_igual_ao_projeto_nao_denuncia():
    """Barra final não é divergência. Aviso à toa treina o operador a ignorar."""
    d = {"app": {"api": "http://127.0.0.1:8100/"}}
    assert projeto.ensombrado_pelo_env(d, {"APP_API_URL": "http://127.0.0.1:8100"}) == []


def test_env_para_chave_que_o_projeto_nao_declara_nao_denuncia():
    """Projeto que não declara a URL aceita a do ambiente — é o padrão dele."""
    assert projeto.ensombrado_pelo_env({"app": {}}, {"APP_API_URL": "http://x"}) == []


def test_denuncia_tambem_os_bancos():
    """Banco sobreposto é pior que URL: a suíte rodaria e daria DROP no banco
    de outro projeto."""
    d = {"banco": {"nome": "bancada", "descartavel_testes": "bancada_test"}}
    c = projeto.ensombrado_pelo_env(d, {"BANCO_DESCARTAVEL": "kb_veredito"})
    assert len(c) == 1 and "BANCO_DESCARTAVEL" in c[0]


def test_contexto_ausente_no_yml_nao_denuncia_caminho(tmp_path):
    """Sem a chave, não há caminho errado -- há projeto sem docs, que é comum e
    honesto. O aviso aqui é outro (árbitro sai null)."""
    d = projeto.carrega(_escreve(tmp_path, "contas:\n  - {nome: a, email: a@x, senha: s, possui: 0}\n"))
    assert not any("nao existe" in a for a in projeto.avisos(d, None))
    assert any("arbitro" in a for a in projeto.avisos(d, None))


# ------------------------------------------------ onde o arquivo e' achado

def test_prefere_o_yml_do_proprio_projeto(tmp_path):
    """O lugar certo é a raiz do projeto revisado, junto do código que ele
    descreve. É assim que a Action vai achar."""
    (tmp_path / "veredito.yml").write_text("versao: 1\n", encoding="utf-8")
    assert projeto.caminho(tmp_path) == tmp_path / "veredito.yml"


def test_explicito_vence_tudo(tmp_path):
    outro = tmp_path / "outro.yml"
    outro.write_text("versao: 1\n", encoding="utf-8")
    (tmp_path / "veredito.yml").write_text("versao: 1\n", encoding="utf-8")
    assert projeto.caminho(tmp_path, str(outro)) == outro


def test_explicito_que_nao_existe_nao_cai_no_padrao(tmp_path):
    """Se o operador apontou um arquivo, ele quis AQUELE. Cair no padrão em
    silêncio faria a rodada usar outra configuração sem avisar."""
    (tmp_path / "veredito.yml").write_text("versao: 1\n", encoding="utf-8")
    assert projeto.caminho(tmp_path, str(tmp_path / "nao-existe.yml")) is None


def test_sem_nada_devolve_none(tmp_path):
    assert projeto.caminho(tmp_path) is None


# ------------------------------------------------ o formato que o codigo usa

def test_usuarios_sai_no_formato_que_ferramentas_consome(tmp_path):
    d = projeto.carrega(_escreve(tmp_path, COMPLETO))
    u = projeto.usuarios(d)
    assert u["dono"] == ("d@x.dev", "s1")
    assert set(u) == {"dono", "outro", "ninguem"}
