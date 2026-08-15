"""hack2l / Veredito -- o orquestrador. Promotores -> advogado -> juiz.

Cada etapa grava em disco antes da proxima comecar. Nao e' zelo: ajustar o juiz
pela trigesima vez nao pode re-executar o advogado, e se a rodada morrer no meio
o que ja foi provado continua provado.

    python -m veredito.orquestrador --manual   # uma acusacao escrita a mao
    python -m veredito.orquestrador            # roda os 6 promotores

Cada rodada tem a SUA pasta, em saidas/rodadas/<data>T<hora>-<commit>/, e
saidas/rodadas/ULTIMA aponta para a mais recente. Rodada nao apaga rodada; o
juiz avulso acha a ultima sozinho.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import (advogado, config as cfg, contencao_app, ferramentas, fontes,
               juiz, llm_alvo, projeto, promotores, subida, tracing)


def _carimbo_da_rodada() -> str:
    """`<data>T<hora>-<commit head>`. Ordena sozinho e diz o que foi revisado.

    O commit e' o do HEAD do PR: duas rodadas sobre o mesmo codigo ficam lado a
    lado e comparaveis, e rodada de outro commit nunca se confunde com elas.

    ⚠️ Carimbo NUNCA derruba rodada. Se o git nao responder, o horario sozinho
    ja separa as pastas -- que e' o objetivo. Perder o sufixo custa legibilidade;
    levantar aqui custaria a rodada inteira, e o pre-voo logo abaixo e' quem tem
    a tarefa de reclamar de git quebrado.
    """
    agora = time.strftime("%Y%m%dT%H%M")
    try:
        return f"{agora}-{ferramentas.commit_head()[:7]}"
    except Exception:
        return agora

# Acusacao de bancada para o slot 1: exercita o pipeline inteiro sem depender de
# ninguem ter lido o diff. Vem da INVARIANTE do desafio (o seed com carol sem
# nada existe para testar isolamento), nao de um achado -- por isso sobrevive a
# troca de PR, e por isso nao e' resposta chumbada.
ACUSACAO_DE_BANCADA = {
    "id": "bancada_isolamento",
    "categoria": "vazamento_de_contexto",
    "local": "app/api/app/routers/",
    "hipotese": "um usuario consegue alcancar documento que nao e' dele",
    # Arbitro com procedencia, no formato de 10/08: a regra E onde ela esta
    # escrita no repo do desafio. "INV-ISOLAMENTO", que estava aqui antes, era
    # rotulo que nos inventamos -- `grep INV-ISOLAMENTO` no repo deles nao acha
    # nada, e era exatamente esse habito que contaminou os 10 PRs reais.
    "arbitro": {
        "regra": "quem nao e' dono nem destinatario nao pode ler o documento",
        "onde": "docs/REVIEW_TASK.md:43",
    },
    "provado_se": "carol, que nao possui nada, alcanca dado de outro usuario",
    "confianca": "media",
}


def _carrega_acusacoes(manual: bool, reusar: bool, diff: str,
                       com_scanner: bool = True,
                       anterior: Path | None = None) -> list[dict]:
    if manual:
        return [ACUSACAO_DE_BANCADA]
    # --reusar le da rodada ANTERIOR: a desta acabou de ser criada e esta vazia.
    caminho = (anterior or cfg.RODADA) / "acusacoes_brutas.json"
    if reusar and caminho.is_file():
        # Afinar o advogado nao pode custar outra rodada de promotores.
        print(f"reusando {caminho.name} (--reusar)")
        try:
            brutas = [a for a in json.loads(caminho.read_text(encoding="utf-8"))
                      if isinstance(a, dict)]
            # 🚨 Grava a propria copia, e nao so' consome a da anterior.
            #
            # Medido em 14/08: a rodada que morreu na chave de API tinha reusado,
            # entao nao gravou nada -- e a rodada SEGUINTE, tambem com --reusar,
            # olhou so' para ela, nao achou lista, e rodou os promotores de novo
            # em silencio. Uma rodada falha no meio quebrava a corrente.
            #
            # E o motivo maior: pasta de rodada tem que ser autossuficiente. Sem
            # isto, quem abre a pasta de uma rodada reusada nao consegue saber
            # de que acusacoes ela partiu sem adivinhar de quem ela herdou.
            (cfg.RODADA / "acusacoes_brutas.json").write_text(
                json.dumps(brutas, indent=2, ensure_ascii=False), encoding="utf-8")
            return brutas
        except (OSError, json.JSONDecodeError) as e:
            print(f"  ilegivel ({e}), rodando os promotores", file=sys.stderr)
    # O contexto do repo entra aqui, em tempo de execucao, e nao chumbado nas
    # lentes. Ausente = os promotores acusam igual e o arbitro sai `null`.
    brutas = promotores.acusa(diff, cfg.contexto_do_repo())

    # Scanner gratis EM PARALELO, nao em serie -- os promotores nao sabem que
    # ele existe. Ver o cabecalho de fontes.py: mostrar o achado do scanner ao
    # promotor ancora a lente e destroi o sinal de `_corroborado`.
    if com_scanner:
        print("\nfontes externas (scanner gratis, em paralelo):")
        do_scanner = fontes.acusa(diff)
        if do_scanner:
            novas = fontes.cruza(brutas, do_scanner)
            corrob = sum(1 for a in brutas if a.get("_corroborado_externo"))
            print(f"  {corrob} acusacao(oes) corroborada(s) por ferramenta "
                  f"independente | {len(novas)} achado(s) que ninguem viu")
            brutas += novas

    # A lista bruta COMPLETA, com todas as fontes. `promotores.acusa` gravava a
    # dele por dentro, entao o arquivo nunca teve o que veio de fora -- e
    # "imprima a lista bruta" e' a primeira coisa que este projeto manda fazer
    # quando algo passa batido.
    (cfg.RODADA / "acusacoes_brutas.json").write_text(
        json.dumps(brutas, indent=2, ensure_ascii=False), encoding="utf-8")
    return brutas


def _registra_efeito_no_banco(antes: dict) -> dict:
    """O que a rodada deixou no banco do app. Grava, e diz em voz alta.

    ⚠️ NUNCA derruba a rodada. Os veredictos ja estao provados e gravados; um
    erro de medicao nao pode custar o parecer. Mas tambem nao pode passar
    calado: silencio aqui e' exatamente o estado anterior, em que a linha de
    base deslocava e ninguem via.
    """
    try:
        depois = contencao_app.retrato_do_banco()
        d = contencao_app.delta_do_banco(antes, depois)
        (cfg.RODADA / "efeito_no_banco.json").write_text(
            json.dumps({"antes": antes, "depois": depois, "delta": d},
                       indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"  [!] nao consegui medir o efeito no banco: {type(e).__name__}: {e}")
        return {}

    if d["limpo"]:
        print(f"\nefeito no banco {d['banco']}: NENHUM"
              + (" (contencao ligada)" if cfg.APP_EM_BANCO_DESCARTAVEL else ""))
        return d

    if d["houve_remocao"]:
        # A unica que nunca deveria acontecer -- em voz alta, e sem emoji: os
        # cinco prints com emoji do projeto estavam todos em caminho de alarme
        # e cada um matava o processo em vez de avisar.
        print(f"\n  [!!] A RODADA REMOVEU LINHAS de {d['banco']}: {d['removidas']}")
        print("       Criar linha para provar defeito em endpoint de escrita e'"
              " esperado; REMOVER nunca e'.")
    if d["criadas"]:
        print(f"\nefeito no banco {d['banco']}: criou {d['criadas']}")
        if not cfg.APP_EM_BANCO_DESCARTAVEL:
            print("       A linha de base deslocou. `APP_EM_BANCO_DESCARTAVEL=1`"
                  " roda em copia e deixa o banco intacto.")
    print(f"       (nao detecta: {d['nao_detecta']})")
    return d


def roda(manual: bool = False, top_n: int | None = None, reusar: bool = False,
         com_scanner: bool = True) -> dict:
    # O app de pe envolve a rodada INTEIRA -- o pre-voo ja sonda `http_request`,
    # entao levantar depois dele seria abortar por uma coisa que a gente mesmo
    # ia consertar duas linhas adiante.
    with subida.app_no_ar() as estado_do_app:
        return _roda(manual, top_n, reusar, com_scanner, estado_do_app)


def _roda(manual: bool, top_n: int | None, reusar: bool, com_scanner: bool,
          estado_do_app: dict) -> dict:
    cfg.prepara_pastas()
    if not cfg.ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY ausente no .env -- nada roda sem ela.")

    # A rodada anterior, ANTES de abrir a nova -- na importacao cfg ja apontava
    # para ela. E' de onde --reusar le.
    anterior = cfg.RODADA

    # Abre a pasta desta rodada antes de QUALQUER escrita: o pre-voo grava
    # artefato de selftest e avisos.json, e llm_alvo.registra grava
    # ambiente.json. Abrir depois deles espalharia a rodada por duas pastas.
    pasta = cfg.nova_rodada(_carimbo_da_rodada())
    cfg.prepara_pastas()
    print(f"rodada em {pasta.relative_to(cfg.RAIZ)}\n")

    inicio = time.time()

    # PRE-VOO. Segundos, uma vez, antes de gastar ~US$0,07 por acusacao numa
    # rodada condenada. Em 10/08 a worktree estava corrompida e o advogado
    # devolveu PROVADO com TODAS as chamadas falhando -- infraestrutura podre
    # virando veredito positivo. A R3b do juiz pega depois; isto pega antes.
    # Antes de tudo: alguem esta valendo em vez do .env? Nao e' fatal (rodar com
    # `APP_EM_BANCO_DESCARTAVEL=1` na linha de comando e' legitimo e cai aqui),
    # mas quando e' a chave da API isso custa horas -- trocar o .env nao muda
    # nada e o erro continua identico.
    # O que ESTE projeto nao vai conseguir provar, dito antes de gastar.
    # Descobrir no fim que faltava conta e' pagar US$1,30 para aprender uma coisa
    # que o veredito.yml ja sabia.
    print(f"projeto: {cfg.PROJETO_YML or '(sem veredito.yml -- usando os padroes)'}")
    if estado_do_app.get("subimos"):
        print(f"  app: subimos nesta rodada"
              + (f", preparacao: {estado_do_app['preparacao']}"
                 if estado_do_app.get("preparacao") else "")
              + " -- sera' derrubado no fim")
    elif estado_do_app.get("pedido"):
        print("  app: ja estava no ar, nao tocamos (nao derrubamos o que nao subimos)")
    for aviso in projeto.avisos(cfg.PROJETO, cfg.CONTEXTO):
        print(f"  [!] {aviso}")

    ensombradas = cfg.variaveis_ensombradas()
    if ensombradas:
        print(f"  [!] o .env NAO esta valendo para: {', '.join(ensombradas)}")
        print("      uma variavel de ambiente ja definida vence o .env "
              "(load_dotenv nao sobrescreve). Se nao foi de proposito, apague a "
              "do sistema -- veja o README.")

    # A API primeiro: e' a unica coisa do pre-voo que CUSTA, e por isso a
    # primeira que tem que responder. Ate' 14/08 ela era a unica que nao era
    # conferida -- e foi exatamente ela que caiu.
    api_ok, api_detalhe = advogado.sonda_api()
    print(f"  {'ok ' if api_ok else 'FALHOU'} {'api anthropic':16} {api_detalhe[:90]}")
    if not api_ok:
        raise SystemExit(
            f"pre-voo falhou na API da Anthropic: {api_detalhe}\n"
            "A rodada nao comeca: sem modelo nao ha promotor nem advogado, e "
            "seguir produziria uma lista de INCONCLUSIVOs de autenticacao que "
            "nao diz nada sobre o codigo."
        )

    sonda = ferramentas.autoteste()
    for nome, res in sonda["ferramentas"].items():
        print(f"  {'ok ' if res['ok'] else 'FALHOU'} {nome:16} {res['detalhe'][:90]}")
    if not sonda["ok"]:
        raise SystemExit(
            "pre-voo falhou nas ferramentas essenciais "
            f"({', '.join(ferramentas.ESSENCIAIS)}). A rodada nao comeca: sem "
            "leitura nao ha observacao, e veredito sem observacao e' opiniao.\n"
            "Worktree parcial e' a causa comum -- apague os diretorios em "
            "WORKTREES e rode `git worktree prune` no repo do desafio."
        )
    if not sonda["ferramentas"].get("http_request", {}).get("ok"):
        print("  [!] app fora do ar: sem prova ponta a ponta, nada passa de MEDIA (R2)")

    # Mede o LLM alvo UMA vez e grava. O juiz roda depois, possivelmente em
    # outro processo, e a decisao dele nao pode depender de sondar o app de novo.
    estado, detalhe = llm_alvo.registra()
    print(f"LLM do app alvo: {estado} -- {detalhe[:90]}")

    diff = advogado.diff_do_pr()  # prefixo cacheado; NUNCA imprimir
    print(f"diff do PR carregado: {len(diff)} caracteres (nao exibido de proposito)")

    # UMA vez por rodada, nao por acusacao: e' o prefixo que as N acusacoes
    # compartilham, e montar de novo daria o mesmo texto gastando N leituras.
    contexto_arquivos = advogado.contexto_dos_arquivos(diff)
    print(f"arquivos do PR no bloco cacheado: {len(contexto_arquivos)} caracteres\n")

    brutas = _carrega_acusacoes(manual, reusar, diff, com_scanner, anterior)
    if not brutas:
        return {}
    teto = top_n if top_n is not None else cfg.TOP_N
    # Por COTA de categoria, nao pelas N primeiras -- ver promotores.seleciona.
    acusacoes = brutas if manual else promotores.seleciona(brutas, teto)
    print(f"\n{len(acusacoes)} de {len(brutas)} acusacoes vao ao advogado "
          f"({cfg.MODEL_ADVOGADO})\n")

    # Trace da rodada. Os organizadores dizem, verbatim: "Submitting a trace
    # link is the cleanest way to prove your multi-agent flow actually ran."
    #
    # tracing.rodada NUNCA derruba a rodada -- 4 dos 13 testes do modulo
    # existem so para provar isso (cliente que explode na criacao, span que
    # explode no end). Langfuse fora = no-op silencioso, o parecer sai igual.
    rod_cm = tracing.rodada("veredito", top_n=teto, brutas=len(brutas),
                            ao_advogado=len(acusacoes))
    rod = rod_cm.__enter__()
    if rod.url:
        print(f"trace desta rodada: {rod.url}\n", flush=True)

    veredictos: list[dict] = []

    # Retrato ANTES, sempre -- inclusive com a contencao ligada, e sobretudo com
    # ela desligada, que e' o padrao. Foi por falta disto que o deslocamento de
    # 14/08 (shares 0 -> 3) so' apareceu porque um humano desconfiou e anotou o
    # estado a mao. Medicao nao pode depender de alguem lembrar.
    antes_do_banco = contencao_app.retrato_do_banco()

    # A contencao envolve SO' o laco do advogado: e' ele que tem http_request
    # apontado para o app. O juiz nao toca no app, entao fica de fora e a api
    # ja volta ao banco original antes da sentenca.
    with contencao_app.app_em_banco_descartavel(pasta):
        for i, a in enumerate(acusacoes, 1):
            print(f"[{i}/{len(acusacoes)}] {a.get('id')} -- {a.get('categoria')}", flush=True)
            with rod.etapa(f"advogado/{a.get('id')}",
                           entrada={"categoria": a.get("categoria"),
                                    "arbitro": a.get("arbitro"),
                                    "local": a.get("local")}) as et:
                v = advogado.julga(a, diff, contexto_arquivos)
                et.evento("veredito", veredito=v.get("veredito"), voltas=v.get("voltas"),
                          severidade=v.get("severidade"), cache_read=v.get("cache_read"))
            veredictos.append(v)

            # Grava a cada acusacao, nao no fim: rodada que morre no meio nao
            # perde o que ja foi provado.
            (cfg.RODADA / "veredictos.json").write_text(
                json.dumps(veredictos, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            (cfg.RODADA / "acusacoes.json").write_text(
                json.dumps(acusacoes, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            print(
                f"    -> {v['veredito']} em {v['segundos']}s, {v['voltas']} voltas | "
                f"entrada {v['tokens_entrada']} saida {v['tokens_saida']} "
                f"cache_read {v['cache_read']}"
            )
            if v.get("motivo"):
                print(f"       {v['motivo'][:150]}")
            # Disciplina no 4: conferir o cache na 1a rodada. Zero aqui e' sinal
            # de timestamp, UUID ou ordem de dicionario variando no prefixo.
            if i == 1 and v["cache_read"] == 0:
                print("    [!] cache_read zero na 1a acusacao -- algo varia no prefixo",
                      flush=True)

    _registra_efeito_no_banco(antes_do_banco)

    with rod.etapa("juiz") as et:
        texto = juiz.sentencia()
        et.evento("parecer", caracteres=len(texto))
    rod_cm.__exit__(None, None, None)   # fecha o trace e faz flush
    if rod.url:
        print(f"\ntrace: {rod.url}  (tambem em {(cfg.RODADA / 'trace.txt').relative_to(cfg.RAIZ)})")

    total = {
        "acusacoes": len(veredictos),
        "segundos": round(time.time() - inicio, 1),
        "tokens_entrada": sum(v["tokens_entrada"] for v in veredictos),
        "tokens_saida": sum(v["tokens_saida"] for v in veredictos),
        "cache_read": sum(v["cache_read"] for v in veredictos),
    }
    print(f"\n{'=' * 70}\n{texto}\n{'=' * 70}")
    print(
        f"custo da rodada: {total['tokens_entrada']} entrada / "
        f"{total['tokens_saida']} saida / {total['cache_read']} de cache, "
        f"em {total['segundos']}s"
    )
    (cfg.RODADA / "custo.json").write_text(
        json.dumps(total, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return total


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--manual", action="store_true",
                   help="usa a acusacao de bancada em vez de rodar os promotores")
    p.add_argument("--top-n", type=int, default=None)
    p.add_argument("--reusar", action="store_true",
                   help="reusa acusacoes_brutas.json da ULTIMA rodada, sem chamar os promotores")
    p.add_argument("--sem-scanner", action="store_true",
                   help="so os promotores, sem as fontes externas gratuitas")
    args = p.parse_args()
    roda(manual=args.manual, top_n=args.top_n, reusar=args.reusar,
         com_scanner=not args.sem_scanner)
