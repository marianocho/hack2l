"""Travas do detector de `veredito.yml`.

🚨 TUDO AQUI RODA CONTRA FIXTURE SINTETICO, e isso nao e' preferencia de estilo.

A licao 5 do "como procurar": o que so' existe num caso nao e' testado pelo caso
que existe. Se a trava rodasse contra o `desafio`, "leu do compose" e "caiu num
padrao chumbado" produziriam o MESMO valor -- e os 14 fallbacks que 17/08 removeu
poderiam voltar pela porta do detector sem nenhum teste ficar vermelho.

Por isso os fixtures usam valores que nao existem em repositorio nenhum desta
maquina: porta 9911, banco `loja`, WORKDIR `/opt/servico`, servico `gateway`.
Qualquer vazamento de valor de vizinho aparece como divergencia, nao como acerto.

Nao bate na API, nao sobe container, nao le os repositorios reais.
"""

from pathlib import Path

import pytest
import yaml

from veredito import detector


def _repo(raiz: Path, compose: str, dockerfile: str = "", onde_df: str = "servico",
          dirs: tuple[str, ...] = ("servico/codigo", "servico/tests")) -> Path:
    (raiz / "docker-compose.yml").write_text(compose, encoding="utf-8")
    for d in dirs:
        (raiz / d).mkdir(parents=True, exist_ok=True)
        (raiz / d / "__init__.py").write_text("", encoding="utf-8")
    if dockerfile:
        pasta = raiz / onde_df
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    return raiz


_COMPOSE = """\
services:
  banco:
    image: postgres:16
    environment:
      POSTGRES_USER: lojista
      POSTGRES_PASSWORD: senha-do-compose
      POSTGRES_DB: loja
    ports:
      - "5499:5432"

  gateway:
    build: ./servico
    ports:
      - "9911:8000"

  carrega:
    build: ./servico
    command: ["python", "-m", "servico.carrega"]
"""

_DOCKERFILE = """\
FROM python:3.12-slim
WORKDIR /opt/servico
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY codigo ./codigo
COPY tests ./tests
CMD ["uvicorn", "servico.main:app"]
"""


@pytest.fixture
def completo(tmp_path):
    return _repo(tmp_path, _COMPOSE, _DOCKERFILE)


# --------------------------------------------------------------------------
# o que ele deriva
# --------------------------------------------------------------------------

def test_deriva_o_banco_do_compose(completo):
    d = detector.detecta(completo)
    assert d.campos["banco.servico"].valor == "banco"
    assert d.campos["banco.usuario"].valor == "lojista"
    assert d.campos["banco.nome"].valor == "loja"


def test_a_api_sai_da_porta_do_HOST_e_usa_127_e_nao_localhost(completo):
    d = detector.detecta(completo)
    # 🚨 Medido: `localhost` resolve ::1 primeiro, o caminho IPv6 aceita a
    # conexao e nunca responde -- 0/8 contra 8/8, e o sintoma e' ReadTimeout,
    # que se le como app lento.
    assert d.campos["app.api"].valor == "http://127.0.0.1:9911"
    assert "localhost" not in d.campos["app.api"].valor


def test_as_montagens_saem_do_COPY_com_o_WORKDIR_do_ultimo_estagio(completo):
    d = detector.detecta(completo)
    assert d.campos["codigo.trabalho"].valor == "/opt/servico"
    assert d.campos["codigo.montagens"].valor == [
        ["servico/codigo", "/opt/servico/codigo"],
        ["servico/tests", "/opt/servico/tests"],
    ]


def test_testes_no_repo_e_testes_sao_campos_DIFERENTES(completo):
    """O caminho no disco e o caminho dentro do container podem divergir.

    E' o caso que os dois gabaritos exibem: um monta `app/api/tests` em
    `/code/tests` (o pytest ve `tests`), o outro monta a arvore toda (o pytest
    ve `app/tests`). Um campo so' nao consegue dizer as duas coisas.
    """
    d = detector.detecta(completo)
    assert d.campos["codigo.testes_no_repo"].valor == "servico/tests"
    assert d.campos["codigo.testes"].valor == "tests"


def test_todo_campo_derivado_carrega_procedencia(completo):
    d = detector.detecta(completo)
    sem = [c for c, v in d.campos.items() if not v.de.strip()]
    assert not sem, f"campo sem procedencia: {sem}"


def test_toda_ausencia_carrega_motivo(completo):
    d = detector.detecta(completo)
    mudas = [c for c, motivo in d.ausentes.items() if not motivo.strip()]
    assert not mudas, (
        "ausencia sem motivo se le como 'o detector nao sabe fazer isso', e nao "
        f"como 'isto nao esta no seu repositorio': {mudas}")


# --------------------------------------------------------------------------
# 🚫 o que ele NUNCA emite -- as tres portas por onde o onboarding viraria risco
# --------------------------------------------------------------------------

def test_preparar_NUNCA_e_auto_emitido_mesmo_com_servico_que_roda_e_sai(completo):
    """`preparar` e' execucao de comando do repo do cliente, e roda toda vez.

    O fixture tem um servico `carrega` com `command` e sem porta -- a cara de um
    semeador. Parecer nao e' ser, e a diferenca entre os dois e' o banco de
    alguem.
    """
    d = detector.detecta(completo)
    assert "app.preparar" not in d.campos
    assert "app.preparar" in d.ausentes
    assert any("carrega" in a for a in d.avisos), (
        "achou o servico e nao perguntou: ficar calado aqui devolve o operador "
        "para a escrita manual sem ele saber que havia algo a declarar")


def test_contas_NUNCA_e_auto_emitido(completo):
    """O atalho obvio passa por TODAS as guardas de `avisos()`.

    Registrar tres contas pela API satisfaz `len(contas) >= 3` e
    `controle_negativo is not None`, e produz uma rodada onde vazamento nao pode
    ser demonstrado porque nao ha o que vazar. E' o padrao de bug da casa dentro
    da ferramenta de onboarding.
    """
    d = detector.detecta(completo)
    assert "contas" not in d.campos
    assert "SO' VOCE SABE" in d.ausentes["contas"]


def test_contexto_NUNCA_e_auto_detectado_mesmo_havendo_candidato(tmp_path):
    """`avisos()` so' confere que o arquivo EXISTE.

    Apontar o README no lugar do documento normativo da' procedencia a texto que
    nao promete nada -- e o arbitro passa a citar opiniao com endereco, que e'
    a forma mais convincente de estar errado.
    """
    r = _repo(tmp_path, _COMPOSE, _DOCKERFILE)
    (r / "docs").mkdir()
    (r / "docs" / "REGRAS.md").write_text("# regras\n", encoding="utf-8")
    (r / "README.md").write_text("# leia\n", encoding="utf-8")
    d = detector.detecta(r)
    assert "contexto" not in d.campos


def test_as_duas_perguntas_saem_sempre_e_dizem_o_que_esta_em_jogo(completo):
    d = detector.detecta(completo)
    assert len(d.perguntas) == 2
    junto = " ".join(d.perguntas)
    assert "NAO pode ser dono de nada" in junto
    assert "senha_em" in junto


# --------------------------------------------------------------------------
# os ramos que o zero-erro de 19/08 NUNCA exercitou (n=2, os dois parecidos)
# --------------------------------------------------------------------------

def test_multi_stage_o_WORKDIR_do_builder_NAO_vaza(tmp_path):
    """So' do ultimo `FROM` em diante.

    Nenhum dos dois repositorios da medicao e' multi-stage, entao este ramo
    nunca disparou -- e o protótipo de 19/08 estava errado nele.
    """
    # ⚠️ O `COPY` do builder usa destino ABSOLUTO de proposito. Com destino
    # relativo ele resolveria contra o WORKDIR final e viraria uma montagem
    # duplicada e plausivel -- e a trava passaria verde com o defeito presente,
    # que e' o modo de falha que este projeto ja pagou quatro vezes. Absoluto,
    # o vazamento aparece.
    df = ("FROM python:3.12 AS builder\n"
          "WORKDIR /construcao\n"
          "COPY codigo /construcao/codigo\n"
          "RUN pip wheel .\n"
          "\n"
          "FROM python:3.12-slim\n"
          "WORKDIR /opt/servico\n"
          "COPY codigo ./codigo\n"
          "COPY tests ./tests\n")
    d = detector.detecta(_repo(tmp_path, _COMPOSE, df))
    assert d.campos["codigo.trabalho"].valor == "/opt/servico"
    assert d.campos["codigo.montagens"].valor == [
        ["servico/codigo", "/opt/servico/codigo"],
        ["servico/tests", "/opt/servico/tests"],
    ], "o COPY do estagio `builder` entrou nas montagens"


def test_COPY_from_de_outro_estagio_NAO_vira_montagem(tmp_path):
    """Artefato de estagio nao existe no repositorio: nao ha o que montar."""
    df = ("FROM python:3.12 AS builder\n"
          "WORKDIR /construcao\n"
          "\n"
          "FROM python:3.12-slim\n"
          "WORKDIR /opt/servico\n"
          "COPY --from=builder /construcao/codigo ./codigo\n"
          "COPY tests ./tests\n")
    d = detector.detecta(_repo(tmp_path, _COMPOSE, df))
    assert d.campos["codigo.montagens"].valor == [["servico/tests",
                                                   "/opt/servico/tests"]]


def test_mais_de_um_diretorio_de_teste_fica_AUSENTE_com_a_lista(tmp_path):
    """🚫 `sorted(candidatos)[0]` escolheria em ordem alfabetica, calado."""
    r = _repo(tmp_path, _COMPOSE, _DOCKERFILE,
              dirs=("servico/codigo", "servico/tests", "servico/spec"))
    d = detector.detecta(r)
    assert "codigo.testes" not in d.campos
    motivo = d.ausentes["codigo.testes"]
    assert "servico/spec" in motivo and "servico/tests" in motivo, (
        "ausente sem a lista devolve o operador para a busca manual")


def test_porta_interpolada_SEM_default_fica_ausente(tmp_path):
    compose = _COMPOSE.replace('"9911:8000"', '"${PORTA_DO_GATEWAY}:8000"')
    d = detector.detecta(_repo(tmp_path, compose, _DOCKERFILE))
    assert "app.api" not in d.campos
    assert "default" in d.ausentes["app.api"]


def test_porta_interpolada_COM_default_usa_o_default(tmp_path):
    """🚨 A regressao que a primeira execucao real pegou.

    `split(":")` cru parte DENTRO de `${PORTA:-9911}` e devolve `${PORTA` como
    porta do host: a URL sai `http://127.0.0.1:${PORTA`, preenchida e
    malformada. Preenchido-errado e' PIOR que ausente -- ausente o pre-voo
    denuncia; este so' falha na sondagem, longe da causa.
    """
    compose = _COMPOSE.replace('"9911:8000"', '"${PORTA_DO_GATEWAY:-9911}:8000"')
    d = detector.detecta(_repo(tmp_path, compose, _DOCKERFILE))
    assert d.campos["app.api"].valor == "http://127.0.0.1:9911"


def test_senha_do_banco_interpolada_sem_default_fica_ausente(tmp_path):
    compose = _COMPOSE.replace("POSTGRES_PASSWORD: senha-do-compose",
                               "POSTGRES_PASSWORD: ${SENHA_DO_BANCO}")
    d = detector.detecta(_repo(tmp_path, compose, _DOCKERFILE))
    assert "banco.senha" not in d.campos
    assert "banco.usuario" in d.campos, "um campo sem default nao derruba os irmaos"


# --------------------------------------------------------------------------
# a escolha do servico -- sem lista de nomes
# --------------------------------------------------------------------------

def test_o_servico_da_aplicacao_NAO_sai_de_lista_de_nomes(completo):
    """O fixture chama o servico de `gateway`.

    `api`/`backend`/`server`/`app` e' lista mantida -- o mecanismo do bug. Se o
    detector dependesse dela, `gateway`, `core` e `rest` nao casariam e o campo
    sairia ausente num repositorio perfeitamente legivel.
    """
    d = detector.detecta(completo)
    assert d.campos["app.api"].valor == "http://127.0.0.1:9911"


def test_dois_servicos_com_porta_desempatam_pelo_diretorio_de_teste(tmp_path):
    compose = _COMPOSE + """
  painel:
    build: ./painel
    ports:
      - "9922:3000"
"""
    r = _repo(tmp_path, compose, _DOCKERFILE,
              dirs=("servico/codigo", "servico/tests", "painel/src"))
    (r / "painel" / "Dockerfile").write_text("FROM node:22\nWORKDIR /app\n",
                                             encoding="utf-8")
    d = detector.detecta(r)
    assert d.campos["app.api"].valor == "http://127.0.0.1:9911"
    assert d.campos["app.web"].valor == "http://127.0.0.1:9922"


def test_ambiguidade_real_fica_AUSENTE_em_vez_de_escolher(tmp_path):
    """Dois candidatos, os dois com teste: escolher calado seria pior."""
    compose = _COMPOSE + """
  painel:
    build: ./painel
    ports:
      - "9922:3000"
"""
    r = _repo(tmp_path, compose, _DOCKERFILE,
              dirs=("servico/codigo", "servico/tests", "painel/src", "painel/tests"))
    (r / "painel" / "Dockerfile").write_text("FROM node:22\nWORKDIR /app\n",
                                             encoding="utf-8")
    d = detector.detecta(r)
    assert "app.api" not in d.campos
    assert "gateway" in d.ausentes["app.api"] and "painel" in d.ausentes["app.api"]


# --------------------------------------------------------------------------
# o arquivo escrito
# --------------------------------------------------------------------------

def test_o_yaml_emitido_e_valido_e_o_projeto_o_aceita(completo):
    from veredito import projeto
    saida = completo / "veredito.yml.detectado"
    saida.write_text(detector.para_yaml(detector.detecta(completo)), encoding="utf-8")
    dado = projeto.carrega(saida)
    assert dado["banco"]["nome"] == "loja"
    assert dado["codigo"]["montagens"][0] == ["servico/codigo", "/opt/servico/codigo"]


def test_cada_campo_do_yaml_vem_com_a_procedencia_ao_lado(completo):
    texto = detector.para_yaml(detector.detecta(completo))
    # ⚠️ Sem pre-filtrar comentario: a primeira versao desta trava jogava fora
    # as linhas que comecam com `#` na coluna 0 -- que sao justamente as
    # procedencias dos campos de primeiro nivel. Ela acusava `rede_isolada` de
    # nao ter procedencia depois de ter apagado a procedencia dele.
    linhas = [l for l in texto.splitlines() if l.strip()]
    for i, linha in enumerate(linhas):
        if linha.strip().startswith("#") or ":" not in linha:
            continue
        chave = linha.split(":")[0].strip()
        if chave in ("versao", "app", "codigo", "banco", "auth"):
            continue
        assert linhas[i - 1].strip().startswith("# de "), (
            f"campo `{chave}` sem procedencia acima dele: conferir o valor deixa "
            "de custar cinco segundos e passa a custar uma busca")


def test_o_destino_NUNCA_e_o_veredito_yml(tmp_path):
    """Sobrescrever apagaria `contas` e `contexto` -- os dois que sustentam CRITICA."""
    assert detector.destino(tmp_path).name != "veredito.yml"
    assert detector.destino(tmp_path).name == "veredito.yml.detectado"


def test_detecta_nao_escreve_nada_sozinho(completo):
    antes = {p.name for p in completo.iterdir()}
    detector.detecta(completo)
    assert {p.name for p in completo.iterdir()} == antes


# --------------------------------------------------------------------------
# divergencia entre o gerado e o humano -- o par que faltava
# --------------------------------------------------------------------------

def test_divergencia_aponta_o_campo_em_que_os_dois_discordam(completo):
    d = detector.detecta(completo)
    humano = yaml.safe_load("""
app:
  api: http://127.0.0.1:8000
banco:
  nome: loja
""")
    briga = detector.divergencias(d, humano)
    assert [c for c, _, _ in briga] == ["app.api"]


def test_campo_que_o_humano_nao_declarou_NAO_e_divergencia(completo):
    d = detector.detecta(completo)
    assert detector.divergencias(d, {}) == []


def test_convencao_nossa_nunca_conta_como_divergencia(completo):
    """Nome que nos escolhemos: divergir e' escolha do operador, nao erro."""
    d = detector.detecta(completo)
    humano = {"banco": {"descartavel_testes": "loja_para_teste", "nome": "loja"},
              "rede_isolada": "outra_rede"}
    assert detector.divergencias(d, humano) == []
