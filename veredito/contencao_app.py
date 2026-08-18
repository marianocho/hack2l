"""hack2l / Veredito -- a contencao do `http_request`.

O app inteiro aponta para uma COPIA descartavel do banco durante a rodada. O
banco original e' apenas LIDO; nenhuma escrita da rodada o alcanca.

POR QUE ISTO EXISTE

Medido em 14/08, rodada real de 6 acusacoes: `shares` saiu de 0 para 3. Provar
a injection na rota de compartilhamento exige chamar `POST /documents/N/share`,
que cria linha. Nada foi destruido, mas a linha de base documentada deslocou --
e nada no sistema avisou. So' apareceu porque um humano tirou retrato do banco
antes de rodar.

A contencao de 11/08 (banco descartavel, rede sem saida) cobria a
`prova_diferencial`. O `http_request` fala com o app de verdade e ficou de fora.
Este modulo fecha esse vao, com o mesmo principio: CONTENCAO, NAO PREDICAO --
a fronteira e' imposta de fora, nao pedida ao modelo no prompt.

🚫 O CAMINHO PROIBIDO, e por que esta escrito aqui

`CREATE DATABASE ... TEMPLATE kb` foi testado com o app conectado e DERRUBOU o
servidor Postgres inteiro ("another server process exited abnormally", banco em
recuperacao). Nao usar. `pg_dump` com o app rodando e' seguro e rapido (0,6s
para 171KB neste app) e e' o caminho daqui.
"""

from __future__ import annotations

import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

from . import config as cfg

# O override do compose. A `DATABASE_URL` da api e' CHUMBADA no
# docker-compose.yml do desafio (sem `${...}`), entao variavel de ambiente nao
# sobrescreve. Um segundo `-f` sobrepoe so' este campo e nao toca no repo deles.
_OVERRIDE = """\
services:
  api:
    environment:
      DATABASE_URL: postgresql+psycopg://kb:kb@db:5432/{banco}
"""


class ContencaoFalhou(RuntimeError):
    """A contencao foi pedida e nao subiu.

    ⚠️ Levantar e' deliberado. Seguir a rodada sem contencao, depois de ela ter
    sido pedida, e' o padrao de bug do projeto na pior forma: a guarda existe,
    fica muda, e quem pediu acha que esta protegido.
    """


def _compose(*args: str, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-f", str(cfg.COMPOSE),
         "--project-directory", str(cfg.RAIZ_DO_PROJETO), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )


def _compose_com_override(override: Path, *args: str,
                          timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-f", str(cfg.COMPOSE), "-f", str(override),
         "--project-directory", str(cfg.RAIZ_DO_PROJETO), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )


def _psql(banco: str, sql: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """🚨 Usuario e servico vem do `veredito.yml`, nunca chumbados.

    Ate' 16/08 isto era `-U kb` e `db` fixos -- as credenciais do desafio. Na
    bancada, que usa `bancada`, TODO retrato do banco falhava com
    `role "kb" does not exist`, e o `delta_do_banco` lia dois dicionarios vazios
    e concluia "limpo". Seis rodadas seguidas disseram que nao tocaram em nada
    sem terem conseguido olhar uma vez.

    E' o sexto chumbado da mesma familia dos cinco que o `veredito.yml` tirou em
    14-15/08 -- e o mais perigoso deles, porque os outros faziam a rodada
    FALHAR, e este fazia ela dizer que estava tudo bem.

    ⚠️ 17/08: consertar o VALOR nao bastava, porque o fallback continuava sendo
    `kb`. Agora `usuario` e `nome` nao tem padrao, e a pergunta vem antes --
    `psql -U "" -d ""` nao e' uma pergunta, e' um erro com cara de resposta.
    """
    if not cfg.TEM_BANCO:
        return subprocess.CompletedProcess(
            args=["psql"], returncode=1, stdout="",
            stderr=("o projeto revisado nao declara `banco` (nome, usuario, "
                    "servico) no veredito.yml"))
    return _compose("exec", "-T", cfg.BANCO_SERVICO,
                    "psql", "-U", cfg.BANCO_USUARIO, "-d", banco,
                    "-v", "ON_ERROR_STOP=1", "-t", "-A", "-c", sql,
                    timeout=timeout)


def confere_nomes() -> None:
    """A copia nao pode ser o proprio banco do app.

    Uma variavel de ambiente trocada faria a rodada escrever no banco real
    ACHANDO que esta contida -- pior do que nao ter contencao, porque some o
    unico sinal de que ha risco.
    """
    if cfg.BANCO_APP.strip() == cfg.BANCO_APP_ORIGEM.strip():
        raise ContencaoFalhou(
            f"BANCO_APP e BANCO_APP_ORIGEM sao o mesmo banco ({cfg.BANCO_APP}): "
            "a 'copia' seria o proprio alvo")
    if not cfg.BANCO_APP.strip():
        raise ContencaoFalhou("BANCO_APP vazio")


def copia_o_banco(destino: Path | None = None) -> None:
    """Duplica o banco do app. O ORIGINAL so' e' lido.

    pg_dump -> banco novo. Se qualquer passo falhar, o estrago fica no banco
    descartavel, que existe para isso.
    """
    confere_nomes()
    dump = "/tmp/veredito_contencao.sql"

    r = _compose("exec", "-T", cfg.BANCO_SERVICO, "pg_dump", "-U", cfg.BANCO_USUARIO,
                 "-d", cfg.BANCO_APP_ORIGEM, "-f", dump, timeout=600)
    if r.returncode != 0:
        raise ContencaoFalhou(f"pg_dump falhou: {r.stderr.strip()[:300]}")

    # DROP+CREATE no DESCARTAVEL. Nunca na origem -- e o nome ja foi conferido.
    r = _psql("postgres", f'DROP DATABASE IF EXISTS "{cfg.BANCO_APP}"')
    if r.returncode != 0:
        raise ContencaoFalhou(f"nao consegui limpar {cfg.BANCO_APP}: "
                              f"{r.stderr.strip()[:300]}")
    r = _psql("postgres", f'CREATE DATABASE "{cfg.BANCO_APP}"')
    if r.returncode != 0:
        raise ContencaoFalhou(f"nao consegui criar {cfg.BANCO_APP}: "
                              f"{r.stderr.strip()[:300]}")

    r = _compose("exec", "-T", cfg.BANCO_SERVICO, "sh", "-c",
                 f"psql -U {cfg.BANCO_USUARIO} -d {cfg.BANCO_APP} "
                 f"-v ON_ERROR_STOP=1 -f {dump}",
                 timeout=600)
    if r.returncode != 0:
        raise ContencaoFalhou(f"restore falhou: {r.stderr.strip()[:300]}")

    if destino:   # o dump tambem e' evidencia da rodada
        d = _compose("exec", "-T", "db", "cat", dump, timeout=600)
        if d.returncode == 0:
            destino.write_text(d.stdout, encoding="utf-8")


def retrato_do_banco(banco: str | None = None) -> dict:
    """Quantas linhas cada tabela tem AGORA. Nunca levanta.

    Sempre no banco de ORIGEM por padrao, mesmo com a contencao ligada: a
    pergunta e' "a rodada mexeu no dado do cliente?", e com a contencao no ar a
    resposta tem que ser zero. Medir o descartavel responderia outra pergunta.

    ⚠️ O QUE ISTO NAO PEGA, e esta dito aqui para nao virar metrica que mede a
    coisa errada: contagem detecta linha CRIADA e linha APAGADA, nao linha
    MODIFICADA no lugar. Um UPDATE que troca o dono de um documento sem mudar a
    contagem passa batido. Pegar isso exigiria checksum por tabela, que num
    banco de cliente pode ser caro -- fica registrado como limite conhecido, e
    nao como cobertura que nao existe.
    """
    banco = banco or cfg.BANCO_APP_ORIGEM
    r = _psql(banco, "select tablename from pg_tables where schemaname='public' "
                     "order by tablename")
    if r.returncode != 0:
        return {"erro": (r.stderr or "").strip()[:200], "tabelas": {}}
    tabelas = [t.strip() for t in (r.stdout or "").splitlines() if t.strip()]
    if not tabelas:
        return {"banco": banco, "tabelas": {}}

    sql = " union all ".join(
        f"select '{t}', count(*) from \"{t}\"" for t in tabelas)
    r = _psql(banco, sql, timeout=300)
    if r.returncode != 0:
        return {"banco": banco, "erro": (r.stderr or "").strip()[:200], "tabelas": {}}

    contagem = {}
    for linha in (r.stdout or "").splitlines():
        if "|" in linha:
            nome, _, n = linha.partition("|")
            try:
                contagem[nome.strip()] = int(n.strip())
            except ValueError:
                pass
    return {"banco": banco, "tabelas": contagem}


def delta_do_banco(antes: dict, depois: dict) -> dict:
    """O que a rodada mudou, separando o que CRIOU do que REMOVEU.

    A separacao e' o ponto: criar linha e' aceitavel (provar defeito em endpoint
    de escrita exige), remover nao e' nunca. Somar os dois num numero so'
    esconderia exatamente o caso grave.
    """
    # 🚨 RETRATO QUE FALHOU NAO E' RETRATO VAZIO.
    #
    # Este bloco e' o conserto de 16/08, e o defeito era exemplar: a comparacao
    # lia so' `tabelas`, entao dois retratos que ERRARAM viravam {} contra {},
    # nenhuma diferenca, e `limpo: True`. Seis rodadas da bancada afirmaram nao
    # ter tocado no banco sem terem conseguido conectar nele uma vez -- o
    # `erro` estava gravado nos dois retratos, e ninguem olhava.
    #
    # E' o padrao de bug da casa na guarda que existe justamente porque o
    # `shares 0->3` de 14/08 "so' apareceu porque tiramos retrato a mao". Ela
    # voltou a nao avisar, e da forma mais cara: dizendo que estava tudo bem.
    #
    # Mesma doutrina do terceiro estado -- ausencia de observacao nunca e'
    # absolvicao. Aqui `medido: False` e' o INCONCLUSIVO do efeito no banco.
    erros = [e for e in (antes.get("erro"), depois.get("erro")) if e]
    if erros:
        return {
            "banco": depois.get("banco") or antes.get("banco"),
            "medido": False,
            "criadas": {},
            "removidas": {},
            # Nunca True aqui. "Nao consegui olhar" nao pode ler como "olhei e
            # estava limpo" -- e' a diferenca entre REFUTADO e INCONCLUSIVO.
            "limpo": False,
            "houve_remocao": False,
            "causa": " | ".join(erros)[:400],
            "nao_detecta": "TUDO -- o retrato do banco falhou, nada foi medido",
        }

    a, d = antes.get("tabelas", {}), depois.get("tabelas", {})
    criadas, removidas = {}, {}
    for t in sorted(set(a) | set(d)):
        antes_n, depois_n = a.get(t, 0), d.get(t, 0)
        if depois_n > antes_n:
            criadas[t] = depois_n - antes_n
        elif depois_n < antes_n:
            removidas[t] = antes_n - depois_n
    return {
        "banco": depois.get("banco") or antes.get("banco"),
        "medido": True,
        "criadas": criadas,
        "removidas": removidas,
        "limpo": not criadas and not removidas,
        # 🚨 Remocao e' a unica que nunca deveria acontecer. Fica com nome
        # proprio para o juiz e o operador nao precisarem interpretar.
        "houve_remocao": bool(removidas),
        "nao_detecta": "linha modificada no lugar (UPDATE sem mudar contagem)",
    }


def _api_no_ar(tentativas: int = 30) -> bool:
    import requests
    for _ in range(tentativas):
        try:
            r = requests.get(f"{cfg.APP_API_URL}/health", timeout=3)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def banco_em_uso_pela_api() -> str | None:
    """Em qual banco a api esta conectada AGORA, perguntando ao Postgres.

    🚨 A conferencia e' o ponto, e a licao e' de 11/08: `docker network connect`
    subia "com sucesso" e ficava quebrado, entao `_garante_rede_isolada` passou
    a devolver o resultado da CONFERENCIA, nao o do comando. Aqui e' igual --
    se o override nao pegar, a api segue no banco real e a rodada correria solta
    achando que esta contida.
    """
    r = _psql("postgres",
              "select datname from pg_stat_activity "
              "where application_name <> 'psql' and datname is not null "
              "group by datname order by count(*) desc limit 1")
    if r.returncode != 0:
        return None
    return (r.stdout or "").strip() or None


def aponta_api_para(banco: str, override: Path) -> None:
    """⚠️ RECRIAR O CONTAINER RELE O AMBIENTE INTEIRO, nao so' a DATABASE_URL.

    Medido em 14/08, e custou meia hora de diagnostico: o `.env` do repositorio
    alvo tinha sido editado depois de o app subir, com uma chave errada no
    OPENAI_API_KEY. O app rodava bem porque containers so' releem `.env` quando
    sao recriados. A contencao recriou -- e a edicao pendente entrou em vigor no
    meio da rodada.

    Ou seja: a contencao pode ATIVAR mudanca de configuracao que estava parada,
    e o sintoma aparece depois, longe da causa. Nao ha o que consertar aqui (e'
    como o compose funciona), mas quem for depurar "o app quebrou durante a
    rodada" tem que olhar o `.env` do alvo antes de olhar a contencao.
    """
    override.parent.mkdir(parents=True, exist_ok=True)
    override.write_text(_OVERRIDE.format(banco=banco), encoding="utf-8")
    r = _compose_com_override(override, "up", "-d", "--force-recreate", "api",
                              timeout=300)
    if r.returncode != 0:
        raise ContencaoFalhou(f"nao consegui subir a api em {banco}: "
                              f"{r.stderr.strip()[:300]}")
    if not _api_no_ar():
        raise ContencaoFalhou(f"a api nao respondeu /health apontada para {banco}")


def devolve_api_ao_original() -> bool:
    """Sem o override, o compose volta a valer o que esta no arquivo deles."""
    r = _compose("up", "-d", "--force-recreate", "api", timeout=300)
    return r.returncode == 0 and _api_no_ar()


@contextmanager
def app_em_banco_descartavel(pasta_da_rodada: Path | None = None):
    """Roda o bloco com o app apontado para uma copia descartavel do banco.

    Desligada devolve no-op: a rodada corre como sempre correu.
    """
    if not cfg.APP_EM_BANCO_DESCARTAVEL:
        yield None
        return

    override = (pasta_da_rodada or cfg.RODADA) / "compose.contencao.yml"
    dump = (pasta_da_rodada or cfg.RODADA) / "banco_antes.sql"
    print(f"contencao: copiando {cfg.BANCO_APP_ORIGEM} -> {cfg.BANCO_APP}", flush=True)
    copia_o_banco(dump if dump.parent.is_dir() else None)

    aponta_api_para(cfg.BANCO_APP, override)
    em_uso = banco_em_uso_pela_api()
    if em_uso != cfg.BANCO_APP:
        # Nao seguir: contencao pedida e nao confirmada e' o pior dos mundos.
        devolve_api_ao_original()
        raise ContencaoFalhou(
            f"a api deveria estar em {cfg.BANCO_APP} e o banco diz '{em_uso}'. "
            "Rodada abortada em vez de correr sem contencao.")
    print(f"contencao: api confirmada em {cfg.BANCO_APP}", flush=True)

    try:
        yield cfg.BANCO_APP
    finally:
        # SEMPRE devolve, inclusive se a rodada explodir no meio. Deixar o app
        # do usuario apontado para um banco temporario seria um estrago nosso.
        if devolve_api_ao_original():
            print(f"contencao: api devolvida a {cfg.BANCO_APP_ORIGEM}", flush=True)
        else:
            print(f"  [!] NAO consegui devolver a api a {cfg.BANCO_APP_ORIGEM} -- "
                  f"rode: docker compose up -d --force-recreate api", flush=True)
