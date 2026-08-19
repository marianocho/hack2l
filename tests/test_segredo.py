"""Segredo do projeto revisado: o que nao entra, e o que nao sai.

🚨 O BURACO, conferido em 19/08: `read_file` e `grep` sem restricao de caminho
nenhuma, zero redacao no pipeline inteiro, e o parecer postado como comentario
no PR. A lente `padroes` procura "credencial em codigo" -- ou seja, ela LEVA o
advogado ate' o `.env` do cliente.

⚠️ AS DUAS FRENTES SAO NECESSARIAS. Entrada sozinha nao basta: o diff do PR
entra no prompt inteiro, e credencial commitada NAQUELE diff passa por fora do
`read_file`. Saida sozinha nao basta: o segredo ja teria ido para a API.

🚨 E AS DUAS TEM QUE CONSEGUIR FICAR QUIETAS (licao 0). Bloqueio largo faz o
advogado bater em recusa o tempo todo; redacao larga destroi a evidencia que o
parecer existe para entregar -- inclusive o conserto sugerido, que muitas vezes
e' literalmente "troque por ${VAR}". Metade das travas aqui e' de silencio.

DOIS DEFEITOS MEUS que so' apareceram no smoke test, nao na leitura:

  `lstrip("./")` removia QUALQUER um daqueles caracteres, entao `.env` virava
  `env` e a guarda ficava muda no arquivo mais obvio de todos;

  `\\b(password)` nao casa em `DB_PASSWORD`, porque `_` e' caractere de palavra
  -- e `DB_PASSWORD=` e' a forma mais comum que existe.
"""
import pytest

from veredito import config as cfg
from veredito import ferramentas as f
from veredito import segredo


# ------------------------------------------------- ENTRADA: o que bloqueia

@pytest.mark.parametrize("caminho,esperado", [
    (".env", "dotenv"),
    (".env.local", "dotenv"),
    ("./.env", "dotenv"),                       # o `lstrip` comia o ponto
    ("app/.env.production", "dotenv"),
    ("config/id_rsa", "chave SSH"),
    ("keys/id_ed25519", "chave SSH"),
    ("certs/server.pem", "chave/certificado"),
    ("android/app.jks", "chave/certificado"),
    ("infra/prod.tfvars", "variaveis do terraform"),
    ("src/credentials.json", "credencial"),
    ("k8s/secrets.yaml", "arquivo de segredos"),
    (".ssh/config", "diretorio de credencial"),
    ("home/.aws/credentials", "diretorio de credencial"),
    (".npmrc", "credencial de ferramenta"),
])
def test_caminho_sensivel_e_pego(caminho, esperado):
    assert segredo.caminho_sensivel(caminho) == esperado


@pytest.mark.parametrize("caminho", [
    ".env.example", ".env.sample", ".env.template", "docs/example.env",
    "app/main.py", "README.md", "veredito.yml", "package.json",
    "tests/test_auth.py", "src/keyboard.py", "docs/credentials-guide.md",
])
def test_a_guarda_fica_QUIETA_no_arquivo_normal(caminho):
    """🚨 Licao 0. `.env.example` e' documentacao de quais variaveis o projeto
    quer -- frequentemente o arquivo que o revisor MAIS precisa. Bloquea-lo
    seria a guarda disparando onde nao tem nada a proteger."""
    assert segredo.caminho_sensivel(caminho) is None


def test_projeto_ACRESCENTA_e_nunca_substitui():
    """O projeto pode somar padroes; nao pode desligar os universais.

    Deixar um projeto desligar isto seria dar a ele o direito de mandar o
    proprio `.env` para a API do modelo por engano de uma linha.
    """
    assert segredo.caminho_sensivel("app/cofre.txt", [r"cofre"]) is not None
    assert segredo.caminho_sensivel(".env", [r"cofre"]) == "dotenv"


def test_regex_extra_invalida_nao_derruba_a_leitura():
    assert segredo.caminho_sensivel("app/main.py", ["[invalida"]) is None


# --------------------------------- ENTRADA: recusa CONTEUDO, confirma FATO

def test_read_file_recusa_conteudo_mas_confirma_existencia(tmp_path, monkeypatch):
    """🚨 A divisao que impede a guarda de destruir a acusacao legitima.

    Para provar "o PR commitou um segredo", o fato e' a PRESENCA do arquivo. O
    valor la' dentro nao acrescenta prova nenhuma -- e e' justo o que nao pode
    viajar para a API nem para o comentario do PR.
    """
    wt = tmp_path / "head"
    wt.mkdir()
    (wt / ".env").write_text("API_KEY=sk-segredo-de-verdade-123\nDEBUG=1\n",
                             encoding="utf-8")
    monkeypatch.setattr(f, "_worktree_de", lambda lado: wt)
    monkeypatch.setattr(cfg, "CAMINHOS_SENSIVEIS", [])

    saida = f._read_file(".env")

    assert "sk-segredo-de-verdade-123" not in saida, "VAZOU o conteudo"
    assert "RECUSADO" in saida
    assert "EXISTE" in saida
    assert "dotenv" in saida


def test_recusa_NAO_conta_como_falha_de_ferramenta(tmp_path, monkeypatch):
    """🚨 A R3 converteria em INCONCLUSIVO um veredicto que se sustenta.

    A chamada nao falhou (nada quebrou) e a ferramenta nao e' inexistente (ela
    leu o arquivo). Ela devolveu um fato verdadeiro. Marcar falha aqui e' o erro
    exato que 17/08 comprou.
    """
    wt = tmp_path / "head"
    wt.mkdir()
    (wt / ".env").write_text("X=1\n", encoding="utf-8")
    monkeypatch.setattr(f, "_worktree_de", lambda lado: wt)
    monkeypatch.setattr(cfg, "CAMINHOS_SENSIVEIS", [])

    f._abre_chamada() if hasattr(f, "_abre_chamada") else None
    f._FALHA_DA_CHAMADA = None
    f._read_file(".env")
    assert f._FALHA_DA_CHAMADA is None, "recusa deliberada virou falha"


def test_read_file_normal_continua_entregando(tmp_path, monkeypatch):
    wt = tmp_path / "head"
    wt.mkdir()
    (wt / "main.py").write_text("def soma(a, b):\n    return a + b\n", encoding="utf-8")
    monkeypatch.setattr(f, "_worktree_de", lambda lado: wt)
    monkeypatch.setattr(cfg, "CAMINHOS_SENSIVEIS", [])
    assert "def soma" in f._read_file("main.py")


# ------------------------------------- ENTRADA: pulado NAO pode ser MUDO

def test_grep_nao_varre_o_env_MAS_DIZ_que_nao_varreu(tmp_path, monkeypatch):
    """🚨 Omissao muda vira absolvicao falsa fabricada pela propria guarda.

    Sumir com o arquivo faria o advogado ler "nenhum resultado" como "nao ha
    credencial neste repositorio" -- que e' justamente a conclusao que o arquivo
    pulado poderia contradizer.
    """
    wt = tmp_path / "head"
    wt.mkdir()
    (wt / ".env").write_text("SENHA=abc123XYZ\n", encoding="utf-8")
    (wt / "app.py").write_text("# nada aqui\n", encoding="utf-8")
    monkeypatch.setattr(f, "_worktree_de", lambda lado: wt)
    monkeypatch.setattr(cfg, "CAMINHOS_SENSIVEIS", [])

    saida = f._grep("SENHA")

    assert "abc123XYZ" not in saida, "VAZOU pela linha do grep"
    assert "NAO VARRIDO" in saida, "pulou em silencio"
    assert ".env" in saida


def test_grep_sem_pulados_nao_ganha_rodape(tmp_path, monkeypatch):
    """A guarda fica quieta quando nao ha o que dizer."""
    wt = tmp_path / "head"
    wt.mkdir()
    (wt / "app.py").write_text("TOKEN = 1\n", encoding="utf-8")
    monkeypatch.setattr(f, "_worktree_de", lambda lado: wt)
    monkeypatch.setattr(cfg, "CAMINHOS_SENSIVEIS", [])
    assert "NAO VARRIDO" not in f._grep("TOKEN")


# -------------------------------------------------- SAIDA: o que mascara

@pytest.mark.parametrize("texto,marca", [
    ("vazou sk-ant-api03-AbCdEf0123456789XYZab", "chave-anthropic"),
    ("AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE", "chave-aws"),
    ("token ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5", "token-github"),
    ("bot xoxb-1234567890-abcdefghij", "token-slack"),
    ("DB_PASSWORD=Tr0ub4dor3xKz9", "valor"),
    ("client_secret=\"a1b2c3d4e5f6g7h8\"", "valor"),
])
def test_credencial_de_verdade_e_mascarada(texto, marca):
    saida, n = segredo.redige(texto)
    assert n >= 1
    assert marca in saida


def test_bloco_pem_inteiro_some():
    pem = ("-----BEGIN RSA PRIVATE KEY-----\n"
           "MIIEowIBAAKCAQEAx7Vq9\nlinhas\n"
           "-----END RSA PRIVATE KEY-----")
    saida, n = segredo.redige(f"achei isto:\n{pem}\nfim")
    assert n == 1
    assert "MIIEowIBAAKCAQEAx7Vq9" not in saida


@pytest.mark.parametrize("texto", [
    "CONSERTO: troque por `senha_em: VEREDITO_SENHA_ANA`",
    "o `campo_senha: senha` do veredito.yml esta certo",
    "api_key: ${OPENAI_API_KEY}",
    "password = \"changeme\"",
    "SECRET_KEY = os.environ['SECRET_KEY']",
    "client_secret=<seu-valor-aqui>",
    "**provado** = ha artefato reproduzivel (um teste que passa no base)",
    "- **injection** em `app/routers/shares.py:41`",
])
def test_a_redacao_fica_QUIETA_no_parecer_normal(texto):
    """🚨 Licao 0 do lado da saida.

    Redacao larga demais mutila a evidencia que o produto existe para entregar
    -- e o alvo mais provavel e' justamente o CONSERTO SUGERIDO, que costuma ser
    "troque o literal por uma variavel".
    """
    saida, n = segredo.redige(texto)
    assert n == 0, saida
    assert saida == texto


def test_parecer_inteiro_sem_segredo_sai_intacto():
    parecer = (
        "<!-- veredito:parecer -->\n\n## Veredito\n\n"
        "**1 achado(s) com evidencia.** Outras 4 suspeita(s) foram descartadas.\n\n"
        "- **injection** em `app/routers/shares.py:41`\n"
        "  CONSERTO: use parametro ligado em vez de f-string.\n"
        "- **config** em `veredito.yml:53`\n"
        "  CONSERTO: troque `senha:` por `senha_em: VEREDITO_SENHA_ANA`.\n")
    saida, n = segredo.redige(parecer)
    assert n == 0
    assert saida == parecer


# ---------------------------------------------------------- a fiacao final

def test_o_comentario_redige_e_DIZ_quantas(monkeypatch):
    """A contagem e' dita: redacao muda nao da' para auditar, e "0" informa
    tanto quanto "3"."""
    from veredito import comentario
    org = {"condenados": [], "descartados": [], "inconclusivos": []}
    monkeypatch.setattr(comentario.segredo, "redige",
                        lambda t: (t + "\nsk-REDIGIDO", 2))
    corpo = comentario.monta(org, {}, {})
    assert "2 trecho(s)" in corpo
    assert "mascarados" in corpo


def test_comentario_sem_segredo_nao_ganha_aviso():
    from veredito import comentario
    org = {"condenados": [], "descartados": [], "inconclusivos": []}
    corpo = comentario.monta(org, {}, {})
    assert "mascarados" not in corpo
