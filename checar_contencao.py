"""A contencao do `http_request` esta funcionando? Confere em segundos, de graca.

    py -3.12 checar_contencao.py

Zero chamada de modelo -- nosso ou da OpenAI. Nenhuma rota de chat e' tocada, de
proposito: ela gastaria credito de verdade do app alvo.

POR QUE ESTE SCRIPT EXISTE

A contencao poe o app para trabalhar numa COPIA do banco durante a rodada, e ela
tem um modo de falha caro e silencioso: se o reapontamento nao pegar, a rodada
corre no banco de VERDADE achando que esta protegida. Os testes automaticos
cobrem a logica com dublê; so' este script exercita container, banco e app de
verdade.

E' o mesmo papel do `checar_paridade.py`: responder "esta maquina consegue?"
antes de a rodada custar dinheiro.

O QUE ELE PROVA, e o exit code diz

  0  o app funciona normal na copia, as escritas caem la, o banco real fica
     com delta ZERO, e a api volta ao banco original no fim
  1  qualquer uma dessas quatro falhou -- e ai NAO rode com a contencao ligada
     ate' entender, porque contencao que falha calada e' pior que nenhuma
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# A contencao e' o objeto do teste: ligada aqui, explicitamente, sem depender do
# .env da maquina. Nao vaza para fora deste processo.
os.environ["APP_EM_BANCO_DESCARTAVEL"] = "1"

sys.path.insert(0, str(Path(__file__).resolve().parent))

from veredito import config as cfg          # noqa: E402
from veredito import contencao_app as ca    # noqa: E402
from veredito import ferramentas as f       # noqa: E402

# Leitura, escrita, quatro usuarios e a rota sem autenticacao. carol nao possui
# nada -- e' o controle negativo do seed, e um 200 dela em documento alheio seria
# vazamento, nao sucesso.
CHAMADAS = [
    ("GET",  "/health",                                   "", ""),
    ("GET",  "/documents",                                "", ""),
    ("GET",  "/documents",                                "", "demo"),
    ("GET",  "/documents",                                "", "alice"),
    ("GET",  "/documents",                                "", "carol"),
    ("GET",  "/documents/1",                              "", "demo"),
    ("POST", "/documents/1/share?email=alice@hack2l.dev", "", "demo"),
    ("GET",  "/shared-with-me",                           "", "alice"),
    ("GET",  "/shared-with-me",                           "", "demo"),
    ("POST", "/documents/4/share?email=bob@hack2l.dev",   "", "alice"),
    ("GET",  "/shared-with-me",                           "", "bob"),
    ("GET",  "/documents/1",                              "", "carol"),
]


def main() -> int:
    problemas: list[str] = []

    antes = ca.retrato_do_banco()
    if not antes.get("tabelas"):
        print(f"[!] nao consegui ler o banco {cfg.BANCO_APP_ORIGEM}: "
              f"{antes.get('erro', 'sem tabelas')}")
        print("    o app esta no ar? `docker compose up -d` no desafio.")
        return 1
    print(f"banco real ANTES: {antes['tabelas']}\n")

    with tempfile.TemporaryDirectory() as tmp:
        with ca.app_em_banco_descartavel(Path(tmp)):
            em_uso = ca.banco_em_uso_pela_api()
            print(f"api conectada em: {em_uso}")
            if em_uso != cfg.BANCO_APP:
                problemas.append(f"a api ficou em '{em_uso}', nao na copia")

            # Login NOVO dentro da contencao: exercita o caminho de autenticacao
            # contra a copia, em vez de reaproveitar token de antes.
            f._TOKENS.clear()
            print("tokens limpos -- os logins acontecem contra a copia\n")

            falhas = 0
            for metodo, caminho, corpo, usuario in CHAMADAS:
                r = f._http_request(metodo, caminho, corpo, usuario)
                ok = r["erro"] is None
                falhas += 0 if ok else 1
                print(f"  {'ok ' if ok else 'ERRO'} {metodo:5} {caminho:42} "
                      f"como {usuario or '(anonimo)':6} -> "
                      f"{r['status'] if r['status'] is not None else r['erro'][:40]}")
            if falhas:
                problemas.append(f"{falhas} chamada(s) nao alcancaram o app na copia")

            na_copia = ca.retrato_do_banco(cfg.BANCO_APP)["tabelas"].get("shares")
            no_real = ca.retrato_do_banco()["tabelas"].get("shares")
            print(f"\nshares na copia: {na_copia}   no banco real: {no_real}")
            if na_copia is None or no_real is None:
                problemas.append("nao consegui contar shares nos dois bancos")
            elif na_copia <= no_real:
                # As escritas tem que ter ido para ALGUM lugar, e o lugar e' a
                # copia. Copia igual ao real significa que nada foi escrito ali.
                problemas.append(
                    f"a copia nao recebeu as escritas ({na_copia} vs {no_real})")

    voltou = ca.banco_em_uso_pela_api()
    print(f"\napi conectada em: {voltou}")
    if voltou != cfg.BANCO_APP_ORIGEM:
        problemas.append(f"a api NAO voltou ao banco original (esta em '{voltou}')")

    d = ca.delta_do_banco(antes, ca.retrato_do_banco())
    print(f"delta no banco real: criadas={d['criadas']} removidas={d['removidas']}")
    if not d["limpo"]:
        problemas.append(f"o banco real MUDOU apesar da contencao: {d}")

    print()
    if problemas:
        print("CONTENCAO COM PROBLEMA:")
        for p in problemas:
            print(f"  - {p}")
        return 1
    print("CONTENCAO OK: o app funciona na copia e o banco real ficou intacto.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
