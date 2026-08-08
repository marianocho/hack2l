"""Duas perguntas de uma vez, com uma chamada real de modelo:

  1. O prompt caching esta valendo? (disciplina no 4 do doc)
     Os 6 promotores compartilham o mesmo prefixo -- o diff. Se o cache nao
     pegar, cada promotor paga o diff inteiro e o TOP_N da rodada final cai.

  2. O tracing.geracao registra usage e cache de verdade?

Usa um prefixo SINTETICO, nao o diff do PR: o que esta sob teste e' o
mecanismo, e assim quem roda isto nao se contamina.
"""
import os
import sys

import anthropic
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from veredito import tracing  # noqa: E402

MODELO = os.environ["MODEL_PROMOTOR"]
cli = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Prefixo grande e ESTAVEL -- e' o papel que o diff faz na rodada real.
# Sem timestamp, sem uuid, sem ordem de dict variando: qualquer um desses
# invalida o cache e o sintoma e' cache_read == 0.
BLOCO = "\n".join(
    f"linha {i:04d}: def funcao_{i}(a, b): return a + b  # modulo sintetico "
    f"de teste, sem relacao com o PR sob revisao"
    for i in range(400)
)
PREFIXO = f"<codigo>\n{BLOCO}\n</codigo>"

PERGUNTAS = [
    "Quantos argumentos a funcao_0007 recebe? Responda so o numero.",
    "Qual operacao a funcao_0100 faz? Responda em tres palavras.",
]


def chamada(pergunta, etapa, nome):
    r = cli.messages.create(
        model=MODELO,
        max_tokens=64,
        messages=[{
            "role": "user",
            "content": [
                # cache_control no bloco estavel; a pergunta fica FORA dele
                {"type": "text", "text": PREFIXO,
                 "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": pergunta},
            ],
        }],
    )
    etapa.geracao(nome, MODELO, pergunta, r)
    return r


with tracing.rodada("verificacao_cache", origem="verificar_cache_e_trace.py") as rod:
    print(f"trace: {rod.url or '<Langfuse fora -- a rodada segue sem link>'}\n")
    with rod.etapa("cache") as e:
        resultados = [chamada(p, e, f"chamada_{i+1}") for i, p in enumerate(PERGUNTAS)]

print(f"{'':12} {'input':>8} {'cache_w':>8} {'cache_r':>8} {'output':>8}")
for i, r in enumerate(resultados, 1):
    u = r.usage
    print(f"  chamada {i}  {u.input_tokens:8} "
          f"{getattr(u,'cache_creation_input_tokens',0) or 0:8} "
          f"{getattr(u,'cache_read_input_tokens',0) or 0:8} "
          f"{u.output_tokens:8}")

leu = getattr(resultados[-1].usage, "cache_read_input_tokens", 0) or 0
escreveu = getattr(resultados[0].usage, "cache_creation_input_tokens", 0) or 0

print()
if leu > 0:
    print(f"OK -- CACHE VALENDO. A 2a chamada releu {leu} tokens a ~10% do preco.")
    print("     Na rodada real o diff sera' esse bloco: 6 promotores pagam 1x.")
    sys.exit(0)
if escreveu > 0:
    print(f"PARCIAL -- escreveu {escreveu} no cache mas nao releu.")
    print("     Prefixo instavel entre chamadas, ou TTL curto demais.")
    sys.exit(1)
print("CACHE NAO PEGOU -- nem escreveu. Bloco menor que o minimo do modelo,")
print("     ou cache_control ausente. Na rodada real isso multiplica o custo")
print("     do diff por 6 e derruba o TOP_N.")
sys.exit(2)
