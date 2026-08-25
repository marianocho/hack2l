"""hack2l / Veredito -- detector de `veredito.yml`.

O `veredito.yml` tem ~26 campos. Pedir que o cliente escreva os 26 A MAO antes
de ver valor derruba a conversao -- e a maior parte deles ja esta escrita no
repositorio dele, em `docker-compose.yml` e `Dockerfile`, que sao contratos
legiveis por maquina.

Medido em 19/08, contra os dois `veredito.yml` escritos a mao (que sao
gabarito): 12 campos saem de compose+Dockerfile com **zero erro** nos dois
repositorios, incluindo `codigo.montagens` e `codigo.testes` -- exatamente os
campos que causaram o falso negativo silencioso de 08/08 e regrediram duas
vezes.

🚨 O CONTRATO, E ELE E' A PECA QUE IMPEDE A REGRESSAO

    So' escreve o que DERIVOU. Campo nao derivado fica AUSENTE, nunca chutado.

`projeto.py` trata **ausente** como limite honesto (o pre-voo diz o que se
perdeu) e **torto** como `raise`. Um campo chutado nao levanta -- ele *parece*
declarado. Um gerador que chuta converte a categoria honesta na categoria
perigosa, e o produto inteiro existe para impedir exatamente isso.

Por isso cada valor emitido carrega a PROCEDENCIA (`# de docker-compose.yml:12`)
e cada ausencia carrega o MOTIVO. Ausencia sem motivo se le como "o detector nao
sabe fazer isso"; com motivo se le como "isto nao esta escrito no seu
repositorio", que e' outra conversa.

🚨 OS 2 CAMPOS QUE ELE NUNCA VAI DETECTAR SAO OS QUE SUSTENTAM CRITICA

`contas` e `contexto`. Conferido em `juiz.py`, nao deduzido: a R1 aceita arbitro
com procedencia (⟵ `contexto`) OU prova ponta a ponta (⟵ `contas`, porque
`http_request` autenticado precisa de token), e a R2 rebaixa todo o resto para
MEDIA. **Um gerador perfeito nos outros 24 campos entrega uma rodada onde nada
passa de MEDIA.** Isso e' dito em voz alta na saida do comando -- calar seria
vender onboarding curto e entregar rodada morna.

🚫 O QUE ELE NUNCA EMITE SOZINHO

    `app.preparar`  e' EXECUCAO DE COMANDO ARBITRARIO do repo do cliente, e roda
                    sempre que nos subimos o app. Servico chamado `seed` nao e'
                    promessa de que ele semeia.
    `contexto`      `avisos()` so' confere que o arquivo EXISTE. Apontar o README
                    no lugar do CONTRIBUTING da' procedencia a texto nao
                    normativo, e o arbitro passa a citar opiniao com endereco.
    `contas`        o atalho obvio -- registrar contas pela API -- passa por
                    TODAS as guardas de `avisos()` e produz uma rodada onde
                    vazamento nao pode ser demonstrado porque nao ha o que vazar.
                    O padrao de bug da casa dentro da ferramenta de onboarding.
"""

from __future__ import annotations

import dataclasses
import os
import re
from pathlib import Path

import yaml

# Diretorios que nunca entram na busca por codigo ou por teste. Mesma lista de
# espirito do `ferramentas._IGNORA`: em 20/08 a assimetria entre duas funcoes
# irmas -- uma podava, a outra nao -- terminou afirmando "nao existe" sobre
# arquivo que existe.
_IGNORA = {".git", "node_modules", ".next", "__pycache__", ".venv", "venv",
           "dist", "build", ".mypy_cache", ".pytest_cache", ".tox", "target"}

_NOMES_DE_COMPOSE = ("docker-compose.yml", "docker-compose.yaml",
                     "compose.yml", "compose.yaml")

_NOMES_DE_TESTE = {"tests", "test", "__tests__", "spec"}

# `${VAR}`, `${VAR:-default}`, `${VAR-default}`. Sem default o valor so' existe
# em execucao, e o campo fica AUSENTE -- ver `_resolve`.
_INTERPOLA = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)(?::?-(.*))?\}$")


@dataclasses.dataclass(frozen=True)
class Derivado:
    """Um valor e o lugar do repositorio de onde ele saiu.

    A procedencia nao e' enfeite: ela e' o que permite ao humano conferir o
    campo em cinco segundos, e e' a diferenca entre "o detector leu" e "o
    detector achou que". `regra sem procedencia e' opiniao` vale aqui tambem.
    """

    valor: object
    de: str


@dataclasses.dataclass
class Deteccao:
    raiz: Path
    campos: dict[str, Derivado] = dataclasses.field(default_factory=dict)
    ausentes: dict[str, str] = dataclasses.field(default_factory=dict)
    perguntas: list[str] = dataclasses.field(default_factory=list)
    avisos: list[str] = dataclasses.field(default_factory=list)

    def poe(self, campo: str, valor, de: str) -> None:
        """Registra um campo derivado. Valor None nunca entra."""
        if valor is None:
            return
        self.campos[campo] = Derivado(valor, de)

    def falta(self, campo: str, motivo: str) -> None:
        self.ausentes[campo] = motivo


# --------------------------------------------------------------------------
# leitura crua, com numero de linha
# --------------------------------------------------------------------------

def _arvore(texto: str):
    """O compose como arvore de nos, que carrega `start_mark.line`.

    `yaml.safe_load` devolve dicionario e joga a linha fora. A procedencia
    precisa dela, e procurar a chave por texto no arquivo seria convencao de
    string carregando estrutura -- o item 4 do "como procurar".
    """
    try:
        return yaml.compose(texto)
    except yaml.YAMLError:
        return None


def _no(no, *chaves):
    for chave in chaves:
        if not isinstance(no, yaml.MappingNode):
            return None
        achou = None
        for k, v in no.value:
            if getattr(k, "value", None) == chave:
                achou = v
                break
        if achou is None:
            return None
        no = achou
    return no


def _linha(no) -> int | None:
    return None if no is None else no.start_mark.line + 1


def _resolve(bruto):
    """Resolve `${VAR:-default}`. Sem default, devolve None.

    🚨 Sem default o valor so' existe no ambiente de quem roda, e chutar aqui
    produziria uma URL malformada que so' falha la' na sondagem -- longe da
    causa. Ausente e' a resposta certa.
    """
    if bruto is None:
        return None
    texto = str(bruto).strip()
    m = _INTERPOLA.match(texto)
    if not m:
        return texto if texto else None
    padrao = m.group(2)
    return padrao if padrao else None


# --------------------------------------------------------------------------
# compose
# --------------------------------------------------------------------------

def acha_compose(raiz: Path) -> Path | None:
    for nome in _NOMES_DE_COMPOSE:
        if (raiz / nome).is_file():
            return raiz / nome
    return None


def _fatia_por_dois_pontos(texto: str) -> list[str]:
    """Divide `"${API_PORT:-8000}:8000"` em `['${API_PORT:-8000}', '8000']`.

    🚨 ESTA FUNCAO EXISTE POR UM DEFEITO MEDIDO, na primeira vez que o detector
    rodou contra o `desafio`. Um `split(":")` cru parte DENTRO da interpolacao
    (`${API_PORT:-8000}` tem dois-pontos) e devolve `${API_PORT` como porta. O
    resultado era `http://127.0.0.1:${API_PORT` -- uma URL malformada emitida
    como se tivesse sido derivada.

    E' o padrao de bug da casa: `_resolve` estava certo e sabia recusar
    interpolacao sem default, mas recebia um pedaco que OUTRO passo ja tinha
    picado -- a guarda olhando um valor que alguem trocou antes dela. O campo
    saia PREENCHIDO, que e' pior do que ausente: ausente o pre-voo denuncia,
    preenchido-errado so' falha la' na sondagem, longe da causa.
    """
    fora, atual, profundidade = [], [], 0
    i = 0
    while i < len(texto):
        c = texto[i]
        if c == "$" and texto[i:i + 2] == "${":
            profundidade += 1
            atual.append("${")
            i += 2
            continue
        if c == "}" and profundidade:
            profundidade -= 1
        if c == ":" and not profundidade:
            fora.append("".join(atual))
            atual = []
            i += 1
            continue
        atual.append(c)
        i += 1
    fora.append("".join(atual))
    return fora


def _porta_publicada(servico: dict):
    """A porta do HOST, do primeiro mapeamento que resolver."""
    for p in servico.get("ports") or []:
        if isinstance(p, dict):                      # sintaxe longa
            valor = _resolve(p.get("published"))
            if valor:
                return valor
            continue
        pedaco = _fatia_por_dois_pontos(str(p))
        if len(pedaco) < 2:                          # "8000" sozinho: aleatoria
            continue
        # Com IP publicado ("127.0.0.1:8100:8000") a porta do host e' a do meio.
        valor = _resolve(pedaco[-2])
        if valor:
            return valor
    return None


def _contexto_de_build(servico: dict) -> str | None:
    build = servico.get("build")
    if isinstance(build, str):
        return build
    if isinstance(build, dict):
        return build.get("context")
    return None


def _dockerfile_de(servico: dict) -> str:
    build = servico.get("build")
    if isinstance(build, dict) and build.get("dockerfile"):
        return str(build["dockerfile"])
    return "Dockerfile"


def _servico_do_banco(servicos: dict) -> str | None:
    """O servico de banco, por FATO e nao por nome.

    Casa por `POSTGRES_*` no ambiente ou por imagem de postgres. Nao ha lista de
    nomes: `db`, `postgres`, `database` e `pg` sao todos plausiveis, e lista
    mantida e' o mecanismo do bug -- ver o comentario do `config.py:517`.
    """
    for nome, s in servicos.items():
        if not isinstance(s, dict):
            continue
        env = s.get("environment") or {}
        if isinstance(env, dict) and any(str(k).startswith("POSTGRES_") for k in env):
            return nome
        if "postgres" in str(s.get("image", "")).lower():
            return nome
    return None


def _candidatos_a_api(raiz: Path, servicos: dict, banco: str | None) -> list[str]:
    """Servicos que constroem imagem propria E DECLARAM porta.

    🚫 Sem heuristica de nome (`api`/`backend`/`server`). `core`, `gateway` e
    `rest` nao casariam, e com dois servicos expondo porta a lista escolheria o
    errado calada.

    🚨 DECLARAM, nao "publicam porta que eu consegui resolver". A primeira versao
    exigia `_porta_publicada(s)`, e com isso um servico com `${PORTA}` sem
    default sumia da lista inteira -- a saida virava *"nenhum servico constroi
    imagem propria e publica porta"*, que e' FALSO e manda o operador procurar um
    servico que esta ali, na frente dele. Guarda que acusa a causa errada manda
    consertar a coisa errada; a causa verdadeira (`sem default`) so' aparece se o
    servico continuar sendo candidato.
    """
    return [nome for nome, s in servicos.items()
            if isinstance(s, dict) and nome != banco
            and _contexto_de_build(s) and s.get("ports")]


def _tem_teste_dentro(raiz: Path, contexto: str) -> bool:
    return bool(_dirs_de_teste(raiz, contexto))


# --------------------------------------------------------------------------
# Dockerfile
# --------------------------------------------------------------------------

def le_dockerfile(texto: str) -> dict:
    """`WORKDIR` e os `COPY` do ULTIMO estagio.

    🚨 So' do ultimo `FROM` em diante. Num multi-stage, o `WORKDIR` do estagio
    `builder` vaza para dentro do resultado se voce ler o arquivo inteiro -- e
    nenhum dos dois repositorios da medicao e' multi-stage, entao o zero-erro
    de 19/08 nunca exercitou este ramo. A lição 5 do "como procurar" valendo
    contra a nossa propria medicao.
    """
    linhas = texto.splitlines()
    inicio = 0
    for i, linha in enumerate(linhas):
        if re.match(r"^\s*FROM\s", linha, re.IGNORECASE):
            inicio = i
    workdir, workdir_em = None, None
    copias: list[tuple[str, str, int]] = []
    for i in range(inicio, len(linhas)):
        crua = linhas[i]
        # Continuação de linha nao e' tratada: um COPY quebrado em duas linhas
        # simplesmente nao e' visto, e nao ver e' ausente -- que e' o desfecho
        # seguro. Ver o contrato no topo do modulo.
        m = re.match(r"^\s*WORKDIR\s+(\S+)", crua, re.IGNORECASE)
        if m:
            workdir, workdir_em = m.group(1), i + 1
            continue
        m = re.match(r"^\s*COPY\s+(.*)$", crua, re.IGNORECASE)
        if not m:
            continue
        resto = m.group(1).strip()
        if resto.startswith("--from"):
            # Artefato de outro estagio: nao existe no repositorio do cliente,
            # entao nao ha o que montar por cima.
            continue
        partes = [p for p in resto.split() if not p.startswith("--")]
        if len(partes) < 2:
            continue
        *origens, destino = partes
        for origem in origens:
            copias.append((origem, destino, i + 1))
    return {"workdir": workdir, "workdir_em": workdir_em, "copias": copias}


def _junta_no_container(workdir: str | None, destino: str) -> str | None:
    destino = destino.rstrip("/") or "/"
    if destino.startswith("/"):
        return destino
    if not workdir:
        return None
    limpo = destino[2:] if destino.startswith("./") else destino
    if limpo == ".":
        return workdir
    return f"{workdir.rstrip('/')}/{limpo}"


# --------------------------------------------------------------------------
# arvore
# --------------------------------------------------------------------------

def _dirs_de_teste(raiz: Path, contexto: str, teto: int = 3) -> list[Path]:
    """Diretorios de teste dentro do contexto de build, podados."""
    base = (raiz / contexto.lstrip("./")).resolve()
    if not base.is_dir():
        return []
    achados: list[Path] = []
    base_partes = len(base.parts)
    for atual, dirs, _arquivos in _anda(base):
        dirs[:] = [d for d in dirs if d not in _IGNORA and not d.startswith(".")]
        if len(Path(atual).parts) - base_partes > teto:
            dirs[:] = []
            continue
        for d in list(dirs):
            if d.lower() in _NOMES_DE_TESTE:
                achados.append(Path(atual) / d)
    return sorted(achados)


def _anda(base: Path):
    return os.walk(base)


def _rel(raiz: Path, alvo: Path) -> str:
    return alvo.resolve().relative_to(raiz.resolve()).as_posix()


# --------------------------------------------------------------------------
# o detector
# --------------------------------------------------------------------------

def detecta(raiz: Path) -> Deteccao:
    """Le o repositorio e devolve o que ele DECLARA sobre si mesmo."""
    raiz = Path(raiz)
    det = Deteccao(raiz=raiz)

    compose = acha_compose(raiz)
    if compose is None:
        # 🚨 Repositorio sem compose nao da' nada ao detector -- e e' o mesmo
        # repositorio onde um humano tambem nao escreveria o yml. Ele acelera o
        # caso facil; nao converte o dificil. Dizer isso e' mais honesto do que
        # emitir um esqueleto vazio que parece progresso.
        det.falta("app.compose",
                  "nao achei docker-compose.yml nem compose.yaml na raiz: sem ele "
                  "nao ha o que derivar, e o Veredito roda so' com leitura e grep")
        _o_que_e_sempre_humano(det)
        return det

    texto = compose.read_text(encoding="utf-8-sig", errors="replace")
    arvore = _arvore(texto)
    # ⚠️ O `try` do `_arvore` sozinho nao bastava, e a assimetria era exatamente
    # o item 9 do "como procurar": duas funcoes irmas lendo O MESMO arquivo, so'
    # uma protegida. Com compose torto o `safe_load` subia `ParserError` cru pelo
    # CLI -- traceback de biblioteca no lugar de "o seu compose nao esta valido",
    # no comando cujo publico e' quem ainda nao conhece a ferramenta.
    try:
        dado = yaml.safe_load(texto) or {}
    except yaml.YAMLError as e:
        # A mensagem sai para uma variavel de proposito: assim esta chamada e a
        # do ramo "nao achei compose" nao ficam com a linha IDENTICA. Duas linhas
        # iguais fazem o arnes de mutacao casar as duas e abortar, e a saida
        # ("a marca casou 2 linhas") se le como arnes quebrado.
        motivo = (f"{compose.name} existe mas nao e' YAML valido "
                  f"({e.__class__.__name__}): corrija o arquivo e rode de novo "
                  "-- nao derivei nada dele")
        det.falta("app.compose", motivo)
        det.campos.pop("app.compose", None)
        _o_que_e_sempre_humano(det)
        return det
    if not isinstance(dado, dict):
        dado = {}
    servicos = dado.get("services") or {}
    if not isinstance(servicos, dict):
        servicos = {}
    nome_do_compose = compose.name
    det.poe("app.compose", nome_do_compose, f"{nome_do_compose} existe na raiz")

    banco = _servico_do_banco(servicos)
    _do_banco(det, servicos, banco, arvore, nome_do_compose)

    candidatos = _candidatos_a_api(raiz, servicos, banco)
    api = _escolhe_api(det, raiz, servicos, candidatos)
    if api:
        _do_app(det, raiz, servicos, api, arvore, nome_do_compose)
        _do_codigo(det, raiz, servicos, api, nome_do_compose)
        _da_web(det, servicos, api, candidatos, arvore, nome_do_compose)

    _o_que_e_nosso(det)
    _o_que_precisa_do_app_no_ar(det)
    _o_que_e_sempre_humano(det)
    _preparar_nunca(det, servicos)
    return det


def _escolhe_api(det: Deteccao, raiz: Path, servicos: dict,
                 candidatos: list[str]) -> str | None:
    if not candidatos:
        det.falta("app.api", "nenhum servico do compose constroi imagem propria e "
                             "publica porta: nao da' para dizer qual e' a aplicacao")
        return None
    if len(candidatos) == 1:
        return candidatos[0]
    # Desempate por FATO: a aplicacao que nos interessa e' aquela cuja suite de
    # testes existe -- e' dela que sai a prova diferencial.
    com_teste = [c for c in candidatos
                 if _tem_teste_dentro(raiz, _contexto_de_build(servicos[c]) or ".")]
    if len(com_teste) == 1:
        return com_teste[0]
    det.falta("app.api",
              f"mais de um servico publica porta ({', '.join(sorted(candidatos))}) "
              "e o desempate por diretorio de teste nao resolveu: diga qual e' a "
              "aplicacao sob revisao")
    return None


def _do_app(det, raiz, servicos, api, arvore, compose_nome):
    porta = _porta_publicada(servicos[api])
    linha = _linha(_no(arvore, "services", api, "ports"))
    if porta:
        # 🚨 127.0.0.1, nunca `localhost`. Medido: `localhost` resolve ::1
        # primeiro, o caminho IPv6 aceita a conexao e nunca responde -- 0/8
        # contra 8/8. Nao da' ConnectionRefused, da' ReadTimeout, que se le como
        # app lento e nao como app inalcancavel.
        det.poe("app.api", f"http://127.0.0.1:{porta}", f"{compose_nome}:{linha}")
    else:
        det.falta("app.api",
                  f"o servico `{api}` nao publica porta com valor fixo (provavelmente "
                  "`${VAR}` sem default): sem a porta nao da' para montar a URL")


def _da_web(det, servicos, api, candidatos, arvore, compose_nome):
    outros = [c for c in candidatos if c != api]
    if len(outros) != 1:
        det.falta("app.web", "opcional: nao ha exatamente um outro servico com porta "
                             "publicada para chamar de front")
        return
    porta = _porta_publicada(servicos[outros[0]])
    linha = _linha(_no(arvore, "services", outros[0], "ports"))
    det.poe("app.web", f"http://127.0.0.1:{porta}", f"{compose_nome}:{linha}")


def _do_banco(det, servicos, banco, arvore, compose_nome):
    if not banco:
        det.falta("banco.servico", "nenhum servico com `POSTGRES_*` nem imagem de "
                                   "postgres: o delta de estado por rodada nao vai "
                                   "conseguir tirar retrato")
        return
    linha = _linha(_no(arvore, "services", banco))
    det.poe("banco.servico", banco, f"{compose_nome}:{linha}")
    env = servicos[banco].get("environment") or {}
    if not isinstance(env, dict):
        return
    for campo, chave in (("usuario", "POSTGRES_USER"),
                         ("senha", "POSTGRES_PASSWORD"),
                         ("nome", "POSTGRES_DB")):
        valor = _resolve(env.get(chave))
        onde = _linha(_no(arvore, "services", banco, "environment", chave))
        if valor:
            det.poe(f"banco.{campo}", valor, f"{compose_nome}:{onde}")
        else:
            det.falta(f"banco.{campo}",
                      f"`{chave}` nao tem valor fixo no compose (sem default): so' "
                      "existe no ambiente de quem sobe")


def _do_codigo(det, raiz, servicos, api, compose_nome):
    """`codigo.*` -- os campos que decidem se a prova diferencial vale.

    🚨 Sao estes que causaram o falso negativo silencioso de 08/08 e regrediram
    duas vezes (15/08, 17/08). Montagem errada => o pytest importa o codigo
    assado na imagem, os dois lados dao o mesmo exit code, e `_classifica` le
    isso como "nao falhou no head" => REFUTADO. Absolvicao falsa e muda.

    ⚠️ O canario das montagens (19/08) confere isso em execucao, e e' por isso
    que este detector pode existir sem aumentar aquele risco: ele propoe, e o
    canario reprova antes de a rodada valer.
    """
    contexto = _contexto_de_build(servicos[api]) or "."
    df = raiz / contexto.lstrip("./") / _dockerfile_de(servicos[api])
    if not df.is_file():
        det.falta("codigo.montagens",
                  f"nao achei {df.name} em {contexto}: sem ele nao da' para saber "
                  "para onde o codigo vai dentro do container")
        return
    lido = le_dockerfile(df.read_text(encoding="utf-8-sig", errors="replace"))
    df_rel = _rel(raiz, df)
    if not lido["workdir"]:
        det.falta("codigo.trabalho",
                  f"{df_rel} nao tem WORKDIR no ultimo estagio: sem ele os destinos "
                  "relativos dos COPY nao resolvem")
    else:
        det.poe("codigo.trabalho", lido["workdir"], f"{df_rel}:{lido['workdir_em']}")

    montagens, procedencias = [], []
    ctx = contexto.lstrip("./").rstrip("/")
    for origem, destino, linha in lido["copias"]:
        limpa = origem.lstrip("./")
        no_disco = (raiz / ctx / limpa) if ctx else (raiz / limpa)
        if not no_disco.is_dir():
            continue                       # arquivo solto nao e' montagem
        no_container = _junta_no_container(lido["workdir"], destino)
        if not no_container:
            continue
        caminho = _rel(raiz, no_disco)
        montagens.append([caminho, no_container])
        procedencias.append(f"{df_rel}:{linha}")
    if montagens:
        det.poe("codigo.montagens", montagens, ", ".join(procedencias))
    else:
        det.falta("codigo.montagens",
                  f"nenhum COPY de {df_rel} aponta para um diretorio deste "
                  "repositorio: nao ha o que montar por cima da imagem")

    _dos_testes(det, raiz, contexto, montagens, lido["workdir"])


def _dos_testes(det, raiz, contexto, montagens, workdir):
    dirs = _dirs_de_teste(raiz, contexto)
    if not dirs:
        det.falta("codigo.testes", f"nao achei diretorio de teste em {contexto}")
        det.falta("codigo.testes_no_repo", "idem")
        return
    if len(dirs) > 1:
        # 🚫 `sorted(candidatos)[0]` escolheria em ordem alfabetica e ninguem
        # conferiria. Escolha calada entre dois e' pior do que pergunta.
        lista = ", ".join(_rel(raiz, d) for d in dirs)
        det.falta("codigo.testes",
                  f"mais de um diretorio de teste ({lista}): escolha o da suite que "
                  "deve rodar na prova diferencial")
        det.falta("codigo.testes_no_repo", "idem")
        return
    no_repo = _rel(raiz, dirs[0])
    det.poe("codigo.testes_no_repo", no_repo, f"diretorio {no_repo} existe")

    # O caminho DENTRO do container: passa pela montagem que cobre este
    # diretorio. ⚠️ Os dois gabaritos divergem exatamente aqui -- um monta
    # `app/api/tests` em `/code/tests` (o pytest ve `tests`), o outro monta a
    # arvore inteira (o pytest ve `app/tests`). E' o caso que ensina por que
    # `testes` e `testes_no_repo` sao dois campos e nao um.
    for disco, container in montagens:
        if no_repo == disco or no_repo.startswith(disco.rstrip("/") + "/"):
            resto = no_repo[len(disco):].lstrip("/")
            pleno = f"{container.rstrip('/')}/{resto}" if resto else container
            if workdir and pleno.startswith(workdir.rstrip("/") + "/"):
                det.poe("codigo.testes", pleno[len(workdir.rstrip("/")) + 1:],
                        f"{no_repo} -> {pleno}, relativo a {workdir}")
                return
    det.falta("codigo.testes",
              f"{no_repo} existe no disco mas nenhuma montagem o leva para dentro do "
              "container: confira se a suite chega la'")


def _o_que_e_nosso(det: Deteccao) -> None:
    """Os 5 campos que sao NOSSOS -- nao ha o que detectar neles.

    ⚠️ Nao sao deteccao, e a saida diz isso com outra palavra (`convencao do
    Veredito`). Misturar as duas procedencias faria "o detector leu no seu
    repositorio" cobrir um valor que nos inventamos.
    """
    nome = det.campos.get("banco.nome")
    if nome:
        base = str(nome.valor)
        det.poe("banco.descartavel_testes", f"{base}_veredito", "convencao do Veredito")
        det.poe("banco.descartavel_app", f"{base}_veredito_app", "convencao do Veredito")
    else:
        det.falta("banco.descartavel_testes",
                  "depende de `banco.nome`, que nao foi derivado")
        det.falta("banco.descartavel_app",
                  "depende de `banco.nome`, que nao foi derivado")
    det.poe("app.subir", True, "convencao do Veredito")
    det.poe("app.espera_s", 120, "convencao do Veredito")
    det.poe("rede_isolada", "veredito_isolada", "convencao do Veredito")


def _o_que_precisa_do_app_no_ar(det: Deteccao) -> None:
    det.falta("app.saude",
              "precisa do app no ar: e' a rota que responde 200 quando ele esta "
              "pronto, e so' da' para saber tentando")
    for campo in ("auth.rota", "auth.campo_usuario", "auth.campo_senha",
                  "auth.campo_token"):
        det.falta(campo,
                  "precisa do app no ar: sai de `/openapi.json` e so' vale depois de "
                  "um login de verdade devolver token")
    det.falta("codigo.banco_de_teste_semeado",
              "so' se descobre rodando a suite duas vezes: se ela depende dos dados "
              "do seed ou cria o que precisa")


def _o_que_e_sempre_humano(det: Deteccao) -> None:
    """🚨 Os dois campos que fecham as DUAS vias da R1."""
    det.falta("contas",
              "SO' VOCE SABE, e nenhum atalho serve -- ver a pergunta 1 abaixo")
    det.falta("contexto",
              "SO' VOCE SABE: `avisos()` so' confere que o arquivo existe, entao "
              "apontar o README daria procedencia a texto nao normativo")
    det.perguntas.append(
        "1. TRES logins do seu app, e um deles NAO pode ser dono de nada.\n"
        "   A conta vazia e' o controle negativo: qualquer dado de outro usuario que "
        "apareca para ela e' vazamento, sem precisar interpretar.\n"
        "   NUNCA registre tres contas novas so' para preencher: tres contas vazias "
        "passam por todas as guardas e produzem uma rodada onde vazamento nao pode "
        "ser demonstrado, porque nao ha o que vazar.\n"
        "   NUNCA ponha a senha no arquivo: use `senha_em: NOME_DA_VARIAVEL`.")
    det.perguntas.append(
        "2. O ARQUIVO em que este repositorio escreve as regras que ele promete "
        "cumprir (`docs/REGRAS.md`, `CONTRIBUTING.md`, o PRD...).\n"
        "   E' dele que sai o arbitro com procedencia. Sem ele o arbitro sai `null`, "
        "que e' a resposta honesta -- e nada sustenta CRITICA por regra.")


def _preparar_nunca(det: Deteccao, servicos: dict) -> None:
    """🚫 `preparar` nunca sai daqui sozinho. Ele so' PERGUNTA.

    E' execucao de comando arbitrario do repositorio do cliente, e roda toda vez
    que nos levantamos o app. Servico com `command` e sem porta se parece com um
    semeador -- parecer nao e' ser, e a diferenca entre os dois e' o banco de
    alguem.
    """
    efemeros = [n for n, s in servicos.items()
                if isinstance(s, dict) and s.get("command") and not s.get("ports")]
    det.falta("app.preparar",
              "nunca auto-emitido: e' execucao de comando do SEU repositorio, e roda "
              "toda vez que o Veredito sobe o app")
    if efemeros:
        det.avisos.append(
            f"achei servico(s) que rodam e saem: {', '.join(sorted(efemeros))}. "
            "Se algum deles prepara o banco, declare em `app.preparar` -- eu nao "
            "emito isso sozinho.")


# --------------------------------------------------------------------------
# saida
# --------------------------------------------------------------------------

_ORDEM = ("versao", "app", "codigo", "auth", "banco", "contas", "contexto",
          "rede_isolada")


def para_yaml(det: Deteccao) -> str:
    """O `veredito.yml` parcial, com a procedencia de cada campo ao lado."""
    linhas = [
        "# veredito.yml -- DETECTADO automaticamente, e incompleto de proposito.",
        "#",
        "# Cada campo abaixo traz de onde ele saiu. O que nao deu para derivar NAO",
        "# esta aqui: campo chutado nao levanta erro, ele parece declarado -- e o",
        "# `projeto.py` trata ausente como limite honesto e torto como `raise`.",
        "#",
        "# Rode `py -3.12 detecta.py` de novo para ver a lista do que falta e por que.",
        "",
        "versao: 1",
    ]
    aninhado: dict[str, list[tuple[str, Derivado]]] = {}
    soltos: list[tuple[str, Derivado]] = []
    for campo, d in det.campos.items():
        if "." in campo:
            pai, filho = campo.split(".", 1)
            aninhado.setdefault(pai, []).append((filho, d))
        else:
            soltos.append((campo, d))

    for secao in _ORDEM:
        if secao in aninhado:
            linhas.append("")
            linhas.append(f"{secao}:")
            for filho, d in aninhado[secao]:
                linhas.extend(_campo(filho, d, "  "))
        for campo, d in soltos:
            if campo == secao and campo != "versao":
                linhas.append("")
                linhas.extend(_campo(campo, d, ""))
    return "\n".join(linhas) + "\n"


def _campo(nome: str, d: Derivado, recuo: str) -> list[str]:
    fora = [f"{recuo}# de {d.de}"]
    if isinstance(d.valor, list):
        fora.append(f"{recuo}{nome}:")
        for item in d.valor:
            fora.append(f"{recuo}  - {_escalar(item)}")
    else:
        fora.append(f"{recuo}{nome}: {_escalar(d.valor)}")
    return fora


def _escalar(valor) -> str:
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, list):
        return "[" + ", ".join(_escalar(v) for v in valor) + "]"
    if isinstance(valor, int):
        return str(valor)
    return f'"{valor}"'


def divergencias(det: Deteccao, existente: dict) -> list[tuple[str, object, object]]:
    """(campo, o que o humano escreveu, o que eu derivei) -- so' onde discordam.

    🚨 E' o caso `gerado != humano` do mapa de bugs, e ele e' o terceiro lado de
    um problema que ja custou caro duas vezes. O `ensombrado_pelo_env` cobre
    `.env` contra o yml; o `variaveis_ensombradas` cobre `.env` contra o
    ambiente. Faltava o par novo: o arquivo que uma pessoa escreveu contra o que
    esta escrito no compose.

    ⚠️ Divergir NAO quer dizer que o humano errou. `banco.descartavel_testes` e'
    nome escolhido, e `codigo.testes` pode ter sido ajustado para uma suite que
    o detector nao viu. O que a divergencia significa e' "os dois nao contam a
    mesma historia" -- e um dos dois esta desatualizado.

    🚫 Comparacao textual do arquivo inteiro nao serve: ela acusa comentario,
    ordem de chave e campo ausente como se fossem discordancia, e afoga o unico
    caso que importa em ruido que o leitor aprende a pular. Guarda que alarma
    sempre morre de excesso.
    """
    fora = []
    for campo, d in det.campos.items():
        if d.de == "convencao do Veredito":
            continue                     # nome nosso: divergir e' escolha, nao erro
        atual = existente
        achou = True
        for parte in campo.split("."):
            if not isinstance(atual, dict) or parte not in atual:
                achou = False
                break
            atual = atual[parte]
        if not achou:
            continue                     # o humano nao declarou: nao e' conflito
        if _mesmo(atual, d.valor):
            continue
        fora.append((campo, atual, d.valor))
    return fora


def _mesmo(a, b) -> bool:
    if isinstance(a, list) and isinstance(b, list):
        return [list(x) if isinstance(x, (list, tuple)) else x for x in a] == \
               [list(x) if isinstance(x, (list, tuple)) else x for x in b]
    return str(a).rstrip("/") == str(b).rstrip("/")


def destino(raiz: Path) -> Path:
    """🚫 NUNCA `veredito.yml`.

    Sobrescrever um arquivo ajustado a mao faria o ajuste sumir sem sinal -- e o
    ajuste a mao e' justamente onde moram `contas` e `contexto`, os dois campos
    que sustentam CRITICA.
    """
    return raiz / "veredito.yml.detectado"
