<!-- tag: hack2l -->
<!-- dono: Mariano (ferramentas.py e juiz.py sao dele pela tabela do CONTRATO) -->

# 🚨 Prova por `http_request` não vira evidência no parecer

Achado às 11h35 mapeando a cobertura contra o `docs/REVIEW_TASK.md`. Cruza a
fronteira de dono, então vira arquivo em vez de código dos dois lados.

## O que o desafio aceita como evidência

`REVIEW_TASK.md`, seção *What to hand back*, verbatim — **três** vias:

> "the evidence that proves it is real, **a failing test the agent wrote and
> ran**, **a reproduction against the running app**, or **the trace, log, or
> database state** that shows the wrong behavior."

| via | temos ferramenta? | vira evidência no parecer? |
|---|---|---|
| teste que falha | ✅ `prova_diferencial` | ✅ |
| **reprodução contra o app rodando** | ✅ `http_request` | ❌ **não** |
| trace / log / estado do banco | ❌ (`query_db` e `read_trace` cortados) | ❌ |

## O buraco

`_http_request` devolve um dict e **não grava artefato**. Só
`prova_diferencial` grava `artefatos/prova_*.json`. E `_bloco` no `juiz.py` só
emite evidência quando existe artefato com `estado == "PROVADO"`:

```python
if artefato and artefato.get("estado") == "PROVADO":
    linhas.append(f"EVIDENCIA: {...} passa em {base} e falha em {head} ...")
else:
    linhas.append(f"EVIDENCIA: nao fechou. {motivo}")
```

**Consequência:** o advogado dispara a requisição, vê o vazamento com os
próprios olhos, declara PROVADO — e o parecer imprime **"EVIDENCIA: nao
fechou"**.

## Por que isso é grave hoje, e não em teoria

O PR adiciona **três endpoints novos**. Prova diferencial não funciona neles:
não existem no commit base, então o teste dá 404 no base e passa no head — o
inverso do padrão "passa antes, falha depois". Por isso os `provado_se` dos
promotores roteiam achado de endpoint novo para `http_request` (está escrito em
`promotores/00_LEIA-ME.md`).

Ou seja: **a maior parte dos achados específicos deste PR chega ao parecer sem
linha de evidência**, mesmo quando o advogado provou de verdade.

## E tem um segundo efeito, na direção contrária

Na Regra 0:

```python
if artefato is not None:
    ...
    v["prova_ponta_a_ponta"] = bool(veredicto.get("prova_ponta_a_ponta")) and (
        artefato.get("estado") == "PROVADO"
    )
```

O bloco inteiro é pulado quando `artefato is None`. Então numa prova só por
`http_request` — sem artefato — **a auto-declaração do advogado passa sem
conferência**, que é exatamente o que a Regra 0 existe para impedir.

O resultado combinado é incoerente: o parecer diz *"não fechou"* enquanto a
severidade pode ficar ALTA com base na palavra do modelo. E o CONTRATO diz o
oposto — *"só `http_request` sustenta alta"*. A ferramenta que deveria ser a
única a sustentar severidade alta é a única que não consegue registrar nada.

## Conserto proposto (3 pontos, tudo em arquivo do Mariano)

**1. `_http_request` grava artefato.** Mesmo formato dos outros:

```json
{
  "id": "acusacao_03",
  "tipo": "http",
  "metodo": "GET",
  "caminho": "/shared/2",
  "como_usuario": "carol",
  "status": 200,
  "corpo": "...(truncado)...",
  "momento": "2026-08-08T11:40:00"
}
```

**2. `_bloco` emite evidência a partir dele** quando não há prova diferencial:

```
EVIDENCIA: GET /shared/2 como carol -> HTTP 200 com o corpo do documento.
           Artefato: artefatos/http_acusacao_03.json
```

**3. `prova_ponta_a_ponta` sai do artefato, não do modelo.** Existe artefato
`tipo: "http"` com status registrado → é ponta a ponta. Não existe → não é,
independente do que o advogado declarou. Fecha o furo da Regra 0.

## Duas coisas menores achadas no mesmo mapeamento

**Vocabulário de categoria.** O desafio nomeia cinco: `security`,
`correctness`, `performance`, `convention or pattern`, `PRD divergence`. Nós
emitimos `injection`, `vazamento_de_contexto`, `correcao`, `padroes`,
`performance`, `prd`. Um jurado lendo o parecer vê rótulo que não é o dele.
Um dicionário no `_bloco` resolve — e mantém a granularidade interna.

**Langfuse: a contradição entre os docs está resolvida, a favor de instrumentar.**
`starter-kit/README.md`, verbatim:

> "Submitting a trace link is the cleanest way to prove your multi-agent flow
> actually ran."

O `PLANO.md` põe Langfuse como **primeiro item da lista de corte**; o
`CLAUDE.md` manda instrumentar. Os organizadores escreveram a resposta. Link de
trace é material de submissão, não enfeite.

## Não verificado, e não vou inventar

O `CLAUDE.md` cita *"3 das 6 exigências do desafio"*. **Essa lista de 6 não
existe em lugar nenhum do repo** — procurei em `README.md`, `docs/` e
`starter-kit/`. Veio do briefing ou da página do evento. Alguém precisa abrir a
fonte e conferir; reconstruir de memória num parecer cuja tese é "não afirmamos
sem prova" seria o erro mais caro do dia.

**Verificado e correto:** as 8 convenções do `REFERENCE_GUIDE.md` batem
verbatim com as C1–C8 de `promotores/padroes.md`.
