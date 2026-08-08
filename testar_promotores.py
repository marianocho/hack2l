"""Fumaca dos promotores: cada .md devolve um array JSON valido no esquema?

NAO usa o diff do PR. Usa um diff FICTICIO, para nao contaminar quem roda isto
e para provar que o prompt funciona em qualquer PR (a regua do doc).
"""
import os, sys, json, pathlib, concurrent.futures as cf
from dotenv import load_dotenv
import anthropic

RAIZ = pathlib.Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")
cli = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODELO = os.environ["MODEL_PROMOTOR"]

DIFF_FALSO = """
--- a/app/api/app/routers/convites.py
+++ b/app/api/app/routers/convites.py
@@ -0,0 +1,18 @@
+import os
+from fastapi import APIRouter, Depends
+router = APIRouter()
+
+@router.post("/pedidos/{pedido_id}/convite")
+def convidar(pedido_id: int, email: str, db=Depends(get_db)):
+    limite = os.getenv("LIMITE_CONVITES", "10")
+    pedido = db.execute(f"select * from pedidos where id = {pedido_id}").first()
+    destinatario = db.query(User).filter(User.email == email).first()
+    db.add(Convite(pedido_id=pedido_id, user_id=destinatario.id))
+    db.commit()
+    return {"pedido_id": pedido_id, "user_id": destinatario.id}
+
+@router.get("/convidados-comigo")
+def convidados(db=Depends(get_db)):
+    todos = db.query(Convite).all()
+    return [{"pedido": c.pedido_id} for c in todos]
"""

CHAVES = {"id", "categoria", "local", "hipotese", "arbitro", "provado_se", "confianca"}
CONF = {"alta", "media", "baixa"}


def roda(caminho):
    lente = caminho.read_text(encoding="utf-8")
    msg = f"<diff>\n{DIFF_FALSO}\n</diff>\n\n{lente}"
    r = cli.messages.create(model=MODELO, max_tokens=4000,
                            messages=[{"role": "user", "content": msg}])
    if r.stop_reason == "refusal" or not r.content:
        return caminho.name, None, f"stop_reason={r.stop_reason}", r.usage
    return caminho.name, r.content[0].text, None, r.usage


def valida(nome, texto):
    t = texto.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1].rsplit("```", 1)[0]
    dados = json.loads(t)
    assert isinstance(dados, list), "nao e' um array"
    assert dados, "array vazio"
    for a in dados:
        faltando = CHAVES - set(a)
        assert not faltando, f"faltam chaves {faltando}"
        assert a["confianca"] in CONF, f"confianca invalida: {a['confianca']}"
        assert len(a["hipotese"].splitlines()) == 1, "hipotese com mais de uma linha"
    return dados


arquivos = sorted(p for p in (RAIZ / "promotores").glob("*.md") if not p.name.startswith("00_"))
print(f"{len(arquivos)} promotores, modelo {MODELO}, diff FICTICIO\n")

falhas, tot_in, tot_out = 0, 0, 0
with cf.ThreadPoolExecutor(max_workers=6) as ex:
    for nome, texto, erro, usage in ex.map(roda, arquivos):
        tot_in += usage.input_tokens
        tot_out += usage.output_tokens
        if erro:
            print(f"  FALHA {nome:26} {erro}"); falhas += 1; continue
        try:
            dados = valida(nome, texto)
        except Exception as e:
            print(f"  FALHA {nome:26} {type(e).__name__}: {e}")
            print(f"        cru: {texto[:180]!r}"); falhas += 1; continue
        cats = {a["categoria"] for a in dados}
        arbs = [a["arbitro"] for a in dados if a["arbitro"]]
        print(f"  OK    {nome:26} {len(dados):2} acusacoes | cat={cats.pop()} | arbitros={len(arbs)}")

print(f"\ntokens: {tot_in} entrada, {tot_out} saida")
print("6/6" if not falhas else f"{len(arquivos)-falhas}/{len(arquivos)} -- {falhas} falha(s)")
sys.exit(1 if falhas else 0)
