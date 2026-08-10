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

---

# O conserto, aplicado e medido em 10/08

Os três itens acima foram implementados. O que segue é medição, não intenção.

## O que mudou no código

| | antes | agora |
|---|---|---|
| PRD, critérios, convenções | colados nos 6 prompts | `contexto/hack2l.md`, carregado em tempo de execução |
| `arbitro` | sigla de lista fixa (`"AC2"`) | `{"regra": "...", "onde": "arquivo:linha"}` ou `null` |
| quem valida o árbitro | ninguém — bastava o campo estar preenchido | `veredito/arbitro.py`, `tem_procedencia()` |
| R1 do juiz | CRÍTICA sem árbitro → SUSPEITA | duas vias: árbitro **com procedência** **ou** prova ponta a ponta |
| regressão de prompt | invisível | `tests/test_prompts_limpos.py` |

Os rótulos `AC1`–`AC5`, `R1`–`R4`, `C1`–`C8` **não existiam nem no repositório do
desafio** — `grep AC1 docs/` lá não acha nada. Nós inventamos a numeração ao
escrever os prompts e depois mandamos o modelo citá-la *verbatim*. Isso torna o
achado pior do que parecia: não era critério de outro projeto sendo reciclado,
era **vocabulário que não existe em lugar nenhum**.

## A régua, mesmos 10 PRs, depois do conserto

```
                              08/08        10/08
acusacoes                      209          144
com arbitro                     94            3
citando vocabulario do Hack2L   93            0      ← o número que importa
taxa de arbitro                45%           2%
concentracao media              —           76%
```

**Zero de 144.** A lente de `prd`, que nunca ficava vazia porque carregava os
critérios dentro de si, agora arbitra contra a **descrição do próprio PR** —
`psf/requests#7576` produziu *"a descrição do PR diz 'não é acessível com link
relativo dentro da pasta .github', mas a mudança…"*. Isso é a lente lendo o
repositório à frente dela.

## O controle positivo — o conserto emudeceu o agente?

Cair de 45% para 2% é o resultado certo **se** o mecanismo ainda funcionar onde
há material. Rodado contra o PR do próprio desafio, que documenta as próprias
regras (não precisa de Docker, só do diff do git):

```
45 acusacoes, as 6 lentes disparando
arbitro COM procedencia          29/45  (64%)
arbitro com vocabulario inventado    0
injection                            3   (0 nos 10 PRs sem modelo)
```

E a procedência é **conferível**, que era o ponto. Conferidas uma a uma no repo
do desafio:

| citado | o que está lá |
|---|---|
| `docs/REFERENCE_GUIDE.md:70` | *"Persistence goes through the ORM models; there is no raw SQL"* |
| `docs/REVIEW_TASK.md:39` | *"Only the owner may share a document"* |
| `docs/REVIEW_TASK.md:43` | *"A user may read a document that has been shared with them"* |
| `docs/REVIEW_TASK.md:45` | *"`GET /shared-with-me` returns the documents other users have shared"* |

4 de 4 caem exatamente na regra que alegam. **A taxa de árbitro deixou de medir
o prompt e passou a medir o repositório** — 2% onde ninguém documenta nada, 64%
onde o repositório documenta as próprias regras.

## A segunda via para CRÍTICA, e o furo que ela fecha

O item 3 previa que R1 rebaixaria quase tudo. Previu certo, e o conserto está no
próprio parecer premiado: o **mesmo SQL injection** saiu duas vezes na rodada
final do Hack2L.

```
padroes_01    arbitro "C2"    -> CRITICA
correcao_01   arbitro null    -> SUSPEITA
```

Os dois com prova diferencial (passa no base, falha no head) **e** artefato HTTP.
A severidade não seguiu a força da prova: seguiu o acaso de uma lente ter
recitado um rótulo chumbado que a outra não recitou — rótulo que, agora sabemos,
nós mesmos inventamos.

Recomputando a rodada final gravada com a R1 nova:

```
correcao_01    SUSPEITA -> CRITICA      prova diferencial + artefato http
injection_01   SUSPEITA -> CRITICA      idem
injection_03   CRITICA  -> CRITICA
padroes_01     CRITICA  -> CRITICA
correcao_03    BAIXA    -> BAIXA        sem prova ponta a ponta
injection_02   BAIXA    -> BAIXA        idem
```

**Nada subiu sem artefato.** A via de prova só vale aterrada na R0b — se valesse
a autodeclaração do advogado, teríamos trocado um rótulo reciclado por um LLM
dizendo "provei", que é pior porque parece evidência.

## ⚠️ Três ressalvas honestas

1. **Duas variáveis mudaram na mesma rodada.** Tirei também o piso *"se saíram
   menos de ~5 acusações, você foi conservador demais"*, que fabricava volume —
   é o que produzia 17 acusações num diff de uma linha. Então a queda de 209 →
   144 tem **duas** causas, e não é medição limpa do desacoplamento sozinho. A
   contagem de contaminação (93 → 0) não é afetada por isso.

2. **`injection` ficou cega nos 10 PRs.** Nenhum deles tem modelo, e a lente
   agora diz explicitamente que sem modelo a resposta certa é silêncio. O
   controle positivo mostra que ela dispara (3) onde há `/chat` com RAG. Mas
   isso **não** fecha o buraco 3 do handoff — não temos um PR de terceiro *com*
   LLM na régua, e sem isso "0 em todos" e "quebrada" são indistinguíveis pelo
   número. Falta um PR de repositório com IA no `prs.txt`.

3. **Perdi um arquivo da linha de base.** Rodei `--refazer` no
   `psf/requests#7576` antes de fazer backup, e `saidas/` é gitignored. As 11
   acusações originais sobrevivem em `psf_requests_7576_advogado.json` (id,
   categoria, confiança, hipótese, veredito); o que se perdeu foi o campo
   `arbitro` de cada uma. Os outros 9 estão em `saidas/generaliza_antes_10ago/`.

## Reproduzir

```bash
py -3.12 generaliza.py --lote prs.txt --refazer                          # ~$0,50
py -3.12 generaliza.py --resumo                                          # de graça
py -3.12 -m pytest tests/test_arbitro.py tests/test_prompts_limpos.py -q # de graça
py -3.12 controle_negativo.py https://github.com/psf/requests/pull/7576  # ~$0,61
```
