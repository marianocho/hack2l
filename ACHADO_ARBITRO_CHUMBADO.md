<!-- tag: hack2l -->

# O árbitro é do Hack2L, e viaja junto

Medido em **08/08/2026, à noite**, com `generaliza.py` (10 PRs) e
`controle_negativo.py` (11 acusações no advogado).

**É o achado mais importante desde o hackathon**, e a causa é minha: os prompts
dos promotores chumbam os critérios de aceite do desafio, e eles são aplicados
a qualquer repositório do mundo.

---

## O número

Nas 209 acusações dos 10 PRs — Flask, Django, httpx, Gin, Next.js, Requests:

```
acusações com árbitro preenchido        94
árbitro do vocabulário do Hack2L        93   (99%)
árbitro de qualquer outra coisa          1   → "R1 R2 R3 R4 AC1 AC2 AC3 AC4 AC5"
```

A nonagésima quarta é a **lista inteira copiada do prompt**, colada como se
fosse um árbitro só.

**Fora do desafio, a taxa real de árbitro é zero.** Todos os 94 são critérios de
aceite de outro projeto, reciclados.

E a distribuição mostra quais lentes carregam o vício:

| lente | acusações citando vocabulário do Hack2L |
|---|---|
| `prd` | 32 |
| `vazamento_de_contexto` | 30 |
| `injection` | 29 |
| `correcao` | 2 |
| `padroes` | 1 |

---

## Como isso apareceu no controle negativo

`psf/requests#7576` conserta **um link de markdown**. Uma linha. Os promotores
produziram 11 acusações; o advogado julgou as onze com `read_file` e `grep`:

```
REFUTADO       7   64%
INCONCLUSIVO   2   18%
PROVADO        2   18%      US$ 0,61 · 328 s
```

Sete refutados é a boa notícia: **a divisão promotor/advogado funciona.** O
verificador vai olhar e diz que não, com motivo.

Mas dois sobreviveram, e cada um tem uma causa diferente.

### Sobrevivente 1 — erro de raciocínio, com a direção invertida

> *"o caminho `/​.github/AI_POLICY.md` … no render do GitHub vira
> `https://github.com/.github/AI_POLICY.md` (404)"*

**Está errado.** O GitHub resolve caminho absoluto em markdown a partir da raiz
do *repositório*, não do domínio.

E o PR se chama *"Fix link to AI Policy"* — o autor estava **consertando** um
link. O advogado acusou o conserto de ser o defeito, com um mecanismo técnico
falso, e marcou PROVADO.

A R2 travou em BAIXA porque não houve prova ponta a ponta. Foi o único freio.

### Sobrevivente 2 — o PRD do Hack2L, num repositório que não é o Hack2L

Hipótese, textual:

> *"nenhum requisito **R1–R4** ou critério **AC1–AC5** pode ser validado ou
> invalidado por esta mudança"*

`R1`–`R4` e `AC1`–`AC5` são os critérios do desafio da Vindler. O `psf/requests`
não tem nenhum deles. O prompt do promotor de PRD os embute, então a lente
carrega o PRD do desafio pra dentro de qualquer diff.

E o advogado **provou**: confirmou que um PR de documentação do `requests` não
satisfaz critérios de aceite de outro projeto. Verdade trivial, valor zero,
lista de condenados.

---

## O que isso explica

Na tabela dos 10 PRs, a lente de `prd` foi **a única que nunca ficou vazia**:

```
4 · 6 · 4 · 7 · 5 · 4 · 8 · 10 · 2 · 6
```

Claro que nunca fica. Ela sempre tem critério pra conferir, porque os critérios
estão dentro dela. Não estava lendo o repositório — estava recitando o desafio.

**E os 45% de árbitro que eu tinha comemorado como "acima do piso" eram
exatamente isso.** A métrica media a contaminação, não a cobertura.

---

## O conserto

O árbitro não pode ser lista fixa. Ele precisa ser **citação com procedência do
repositório sob revisão**:

1. **Remover `AC1`–`AC5`, `R1`–`R4`, `C1`–`C8` dos seis prompts.** Eles entram
   como *contexto do PR sob revisão*, quando existirem, não como vocabulário
   permanente da lente.

2. **O árbitro vira campo com fonte obrigatória:** não `"AC2"`, e sim
   `{"regra": "...", "onde": "docs/CONTRIBUTING.md:14"}`. Se o promotor não
   consegue apontar onde a regra está escrita **naquele repositório**, o árbitro
   é `null` — que é a resposta honesta.

3. **Consequência a jusante, e é séria:** com árbitro honestamente `null` na
   maioria dos casos, a regra R1 do juiz rebaixa quase tudo para SUSPEITA. **Nada
   consegue ser crítico fora de um repositório que documente seus próprios
   critérios.**

   Isso não é bug da R1 — é a R1 dizendo a verdade. Um achado sem regra
   documentada violada *é* mais fraco. Mas significa que o produto precisa de uma
   segunda via para severidade alta que não dependa de árbitro: provavelmente a
   reprodução ponta a ponta sozinha.

---

## O que fica de pé

Vale separar o que quebrou do que aguentou:

| | |
|---|---|
| Cobertura generaliza | 3 linguagens, nenhuma lente cega |
| Concentração se espalha | 39% no next.js de 13 arquivos |
| O advogado mata ruído | 7 de 11 refutados num PR de documentação |
| Terceiro estado funciona | 2 inconclusivos, com causa registrada |
| **Árbitro não generaliza** | **94 de 94 são do Hack2L** |
| **Precisão não tem piso** | 1 linha → 17 acusações |
| **O custo não escala** | US$ 0,61 para limpar um PR de doc |

---

## Reproduzir

```bash
py -3.12 generaliza.py --lote prs.txt                                    # ~$0,50
py -3.12 controle_negativo.py https://github.com/psf/requests/pull/7576  # ~$0,61
```
