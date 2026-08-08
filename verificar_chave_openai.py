"""Depois de por a OPENAI_API_KEY no .env do desafio: o LLM alvo acordou?

Roda as tres coisas que mudam:
  1. o modelo le a pergunta (sondas divergem)
  2. a recuperacao melhora (pergunta em pt-BR acha o doc certo em ingles)
  3. a regra R4 desarma

Nao toca no diff do PR nem em endpoint de share.
"""
import sys

from veredito import llm_alvo, config as cfg
from veredito.ferramentas import _token, http_request
from veredito.juiz import aplica_regras

print("=== 1. o LLM alvo esta vivo? ===")
est, detalhe = llm_alvo.estado(forcar=True)
print(f"  estado: {est.upper()}")
print(f"  {detalhe}\n")

print("=== 2. a recuperacao ficou semantica? ===")
tok = _token("demo")
casos = [
    ("Qual e a politica de viagem da empresa?", "Company travel policy"),
    ("O que fazer quando acontece um incidente?", "Incident response runbook"),
]
import requests, json
acertos = 0
for pergunta, esperado in casos:
    r = requests.post(f"{cfg.APP_API_URL}/chat", json={"question": pergunta},
                      headers={"Authorization": f"Bearer {tok}"},
                      timeout=cfg.TIMEOUT_HTTP_S)
    d = r.json()
    cites = d.get("citations") or []
    topo = cites[0].get("document_title") if cites else "<nenhuma>"
    bateu = topo == esperado
    acertos += bateu
    print(f"  {'OK  ' if bateu else 'MISS'} {pergunta}")
    print(f"       1a citacao: {topo!r} (esperado {esperado!r})")
    print(f"       resposta:   {(d.get('answer') or '')[:110]!r}")
print(f"  -> {acertos}/{len(casos)} no topo\n")

print("=== 3. a regra R4 desarma? ===")
llm_alvo.registra()
acu = {"id": "injection_01", "categoria": "injection", "arbitro": "INV-INSTRUCAO-NAO-E-DADO"}
ref = {"veredito": "REFUTADO", "severidade": "BAIXA", "motivo": "o app nao obedeceu"}
v = aplica_regras(ref, acu, None)
disparou = any("R4" in r for r in v.get("regras_aplicadas", []))
print(f"  veredito de um injection REFUTADO: {v['veredito']}")
print(f"  R4 disparou: {disparou}")

if est == llm_alvo.VIVO and not disparou:
    print("\nOK -- modelo vivo, R4 em silencio. Injection agora e' provavel/refutavel de verdade.")
    sys.exit(0)
if est == llm_alvo.DUBLE and disparou:
    print("\nAINDA DUBLE -- a chave nao chegou no container. Faltou reiniciar o api?")
    sys.exit(1)
print(f"\nESTADO INESPERADO: llm={est}, R4={disparou}")
sys.exit(2)
