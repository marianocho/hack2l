"""hack2l / Veredito -- levantar o app do projeto, quando ele nao esta no ar.

Ate' 14/08 o app era responsabilidade de fora: alguem rodava `docker compose up`
antes, e se esquecesse o pre-voo abortava a rodada. Isso funciona na bancada de
quem escreveu o produto e nao funciona em lugar nenhum -- na CI ninguem sobe
nada a mao, e "o app precisa estar no ar" nao e' instrucao, e' o trabalho.

🚨 AS DUAS REGRAS QUE ESTE MODULO OBEDECE

  1. NAO DERRUBA O QUE NAO SUBIU. Se o app ja estava de pe, ele e' do operador
     -- talvez com o navegador aberto nele. Mexer seria estrago nosso, e a
     rodada nao precisa disso.

  2. `preparar` (seed, migration) SO' RODA se nos levantamos os containers.
     Seed costuma RESETAR o banco. Rodar isso num app que ja estava servindo
     apagaria dado que nao e' nosso -- e' a mesma classe de risco que custou o
     banco da aplicacao em 11/08, e a licao foi: contencao, nao predicao.

A consequencia das duas juntas: `subir: true` num app ja no ar e' NO-OP
completo. Isso e' de proposito -- torna a opcao segura de ligar por padrao no
projeto, sem exigir que o operador saiba o estado do ambiente antes de rodar.
"""

from __future__ import annotations

import subprocess
import time
from contextlib import contextmanager

import requests

from . import config as cfg


class SubidaFalhou(RuntimeError):
    """Pedimos o app de pe e ele nao ficou. Levanta em vez de seguir.

    Seguir sem app produz uma rodada inteira em MEDIA -- `http_request` nunca
    alcanca nada, `prova_ponta_a_ponta` fica falsa, a R2 rebaixa tudo -- e o
    sintoma nao parece problema de ambiente, parece o produto nao funcionando.
    """


def _compose(*args: str, timeout: int = 600) -> subprocess.CompletedProcess:
    # Gemeo do helper em contencao_app. Duplicado de proposito: sao dois modulos
    # com ciclos de vida diferentes, e acoplar um ao outro por seis linhas
    # criaria dependencia onde nao ha relacao.
    return subprocess.run(
        ["docker", "compose", "-f", str(cfg.COMPOSE),
         "--project-directory", str(cfg.RAIZ_DO_APP), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )


def no_ar(tentativas: int = 1, intervalo_s: float = 2.0) -> bool:
    """O app responde na rota de saude?

    ⚠️ "Container subiu" NAO e' "app no ar" -- ja custou um `compose up`
    falhando logo depois de eu reportar sucesso (CLAUDE.md). Quem responde e' a
    aplicacao, nao o docker.
    """
    alvo = f"{cfg.APP_API_URL}{cfg.APP_SAUDE}"
    for i in range(tentativas):
        try:
            if requests.get(alvo, timeout=5).status_code == 200:
                return True
        except Exception:
            pass
        if i + 1 < tentativas:
            time.sleep(intervalo_s)
    return False


def _prepara() -> list[str]:
    """Roda os comandos de preparacao (seed, migration). So' apos subirmos."""
    feitos = []
    for passo in cfg.APP_PREPARAR:
        if not isinstance(passo, list) or not passo:
            continue
        # Lista de argumentos, nunca string com shell: `preparar` vem de um
        # arquivo do projeto revisado, e passar isso por shell seria executar
        # texto de terceiro com as nossas permissoes.
        r = _compose(*[str(a) for a in passo])
        feitos.append(" ".join(str(a) for a in passo))
        if r.returncode != 0:
            raise SubidaFalhou(
                f"preparacao falhou em `{feitos[-1]}`: {r.stderr.strip()[:300]}")
    return feitos


@contextmanager
def app_no_ar():
    """Garante o app de pe durante o bloco, se o projeto pediu.

    Devolve um dict com o que aconteceu -- o pre-voo imprime, e a pasta da
    rodada guarda. Rodada que subiu o app e rodada que o encontrou de pe sao
    ambientes diferentes, e daqui a um mes ninguem lembra qual foi qual.
    """
    estado = {"pedido": cfg.APP_SUBIR, "ja_estava": None, "subimos": False,
              "preparacao": []}

    if not cfg.APP_SUBIR:
        estado["ja_estava"] = no_ar()
        yield estado
        return

    estado["ja_estava"] = no_ar()
    if estado["ja_estava"]:
        # NO-OP completo: nao subimos, nao preparamos, nao derrubamos.
        yield estado
        return

    # ⚠️ `--build`, e nao so' `up -d`. O Dockerfile faz COPY do codigo, entao um
    # `up` com imagem existente sobe o codigo do BUILD ANTERIOR -- possivelmente
    # de outro ramo. Em 15/08 isso custou uma rodada inteira: o app respondia
    # como o commit base e o defeito do PR simplesmente nao existia de fora.
    #
    # Custa segundos quando nada mudou (cache de camada) e evita o falso
    # negativo mais caro que este produto tem.
    r = _compose("up", "-d", "--build", timeout=1200)
    if r.returncode != 0:
        raise SubidaFalhou(f"`compose up -d --build` falhou: {r.stderr.strip()[:300]}")
    estado["subimos"] = True

    if not no_ar(tentativas=cfg.APP_ESPERA_S // 2 or 1):
        _derruba()
        raise SubidaFalhou(
            f"o app nao respondeu {cfg.APP_API_URL}{cfg.APP_SAUDE} em "
            f"{cfg.APP_ESPERA_S}s. Containers derrubados -- nao vale deixar meio "
            "ambiente de pe atras de nos.")

    try:
        estado["preparacao"] = _prepara()
    except SubidaFalhou:
        _derruba()
        raise

    try:
        yield estado
    finally:
        # SEMPRE, inclusive se a rodada explodir: subimos, entao limpamos.
        _derruba()


def _derruba() -> None:
    try:
        _compose("down")
    except Exception:
        # Falhar aqui nao pode custar o parecer, que ja esta gravado. Mas nao
        # pode passar calado: container esquecido de pe e' porta aberta.
        print("  [!] nao consegui derrubar o app que subimos -- rode "
              "`docker compose down` no projeto", flush=True)
