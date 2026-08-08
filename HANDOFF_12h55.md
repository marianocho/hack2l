<!-- tag: hack2l -->

# HANDOFF — 08/08, 12h55 (máquina do Mariano)

Sessão anterior acabou por janela de contexto. **Leia `ESTADO.md` e `README.md`
primeiro**; este arquivo é só o delta das 12h15–12h55 e o que ficou pendente.

Relógio: **rodada final começa 14h15, congela 15h.** A rodada leva 14,3 min
medidos (não 36), então há folga — mas ela roda **na máquina do Luis**.

---

## 1. A rodada cronometrada foi feita. Era o item nº 1 de risco do ESTADO.

`python -m veredito.orquestrador --top-n 10`, 12h15, **856,4 s = 14,3 min**.

| | |
|---|---|
| promotores (6, paralelo) | 55 acusações brutas em ~20 s |
| ao advogado | 10 (cota por categoria) |
| resultado | **5 condenados, 1 descartado, 4 inconclusivos** |
| custo | 149.918 entrada / 30.192 saída / **560.985 de cache** |
| cache 1ª acusação | 55.011 — o prefixo está estável, disciplina nº 4 conferida |

O parecer está em `saidas/parecer.md` e os artefatos em `artefatos/`. **O log
bruto não foi commitado** (`logs/` entrou no `.gitignore`); se for preciso, ele
está em `logs/rodada_cronometrada_1215.log` só nesta máquina.

### Os 4 inconclusivos NÃO eram falta de prova — eram encanamento

Isso é o achado central da sessão. Dois bugs, os dois já corrigidos e no GitHub.

---

## 2. Bug 1 — CORRIGIDO (commit `94be34b`)

**O parse engolia veredito por causa de chave em prosa.**

`_parse_veredicto` usava `re.search(r"\{.*\}", DOTALL)` — ganancioso, casa do
**primeiro** `{` até o **último**. O advogado escreve prosa antes do JSON, e na
rodada a prosa citava `` `SELECT ... email = '{email}'` `` e a rota
`` `/documents/{id}/share` ``. O span começou em `{email}`, o `json.loads`
quebrou, e caiu no fallback.

O fallback existe justamente para uma acusação provada não sumir por erro de
formato — e era ele que sumia com ela. **`correcao_01` e `performance_01` viraram
INCONCLUSIVO com artefato PROVADO no disco.** Ou seja: o LLM sobrescreveu o exit
code pela via mais boba possível, que é exatamente o que a arquitetura promete
impedir.

Agora é `raw_decode` a partir de cada `{`, do fim para o começo; o último objeto
válido com `veredito` ganha. `tests/test_advogado.py`, 8 testes, com a saída real
da rodada como regressão.

⚠️ **Recuperação pendente e barata:** a `saida_crua` das duas acusações está
preservada em `saidas/veredictos.json`. Dá para reparsar com o parser corrigido e
re-rodar só o juiz — **sem re-executar o advogado (~130 s por acusação)**. Script
pronto, testado só até a escrita:
`%TEMP%\claude\...\scratchpad\reparse_hack2l.py` (não sobreviveu ao repo — está
descrito no fim deste arquivo, seção 7).

---

## 3. Bug 2 — CORRIGIDO (commit `c81be61`)

**"recusa do classificador" não aciona nada.** 2 das 10 acusações morreram assim
(`injection_01`, `padroes_01`) — uma delas na categoria carro-chefe.

Verificado **no `anthropic` 0.120.2 instalado, lendo o código, não de memória:**

- `tool_runner` **aceita** `fallbacks` — está na assinatura em
  `resources/beta/messages/messages.py`, nas duas sobrecargas (stream e não).
  (Procurar em `lib/tools/` engana: o `tool_runner` não mora lá.)
- `BetaFallbacksParam = Union[Iterable[BetaFallbackParam], Literal["default"]]`
  → o escalar `"default"` é válido.
- `cyber` **é** categoria coberta. A docstring do próprio SDK diz: *"Benign
  cybersecurity work can also trigger this category."*
- O pareamento header↔forma está certo: `"default"` exige
  `server-side-fallback-2026-07-01` (a forma de array exigiria `-2026-06-01`;
  cruzar os dois dá 400). É o que `advogado.py` já passa.

**Então a recusa que chega ao parecer significa uma de duas coisas**, e nós
jogávamos fora justamente o campo que distingue:

| sinal | significado | ação |
|---|---|---|
| `stop_details.recommended_model` preenchido | o fallback **não foi tentado** (rate limit / sobrecarga) | retry direto no modelo sugerido |
| `fallback_message` em `usage.iterations` | o fallback rodou e **também** recusou | cadeia inteira negou |
| nenhum dos dois | indeterminado | admitir que não sabe |

`advogado._diagnostico_da_recusa` grava os três casos. 4 testes.

---

## 4. Cosmético — FEITO (no `94be34b`)

`ferramentas.normaliza_local` + `juiz._local`: o `local` da acusação ia cru para
o parecer. Nesta rodada, **24, 20 e 7 acusações citaram o mesmo arquivo com três
raízes diferentes** (`app/api/app/routers/shares.py`, `app/routers/shares.py`,
`routers/shares.py`). Caminho que não abre no palco custa mais que as linhas.
Não cria worktree e nunca levanta. 3 testes.

---

## 5. ✅ FEITO às 13h20 (commit `b66c66f`) — era o furo da Regra 0

**Os 3 pontos foram implementados, mais o dicionário de categorias.** 90 testes
rápidos passando; validado ponta a ponta contra o app do PR (carol →
`GET /shared/2` gravou artefato e virou linha de evidência).

O que mudou, em uma linha cada:

1. `_http_request` grava `artefatos/http_<id>.json` a cada chamada.
2. `juiz` carrega `http_*.json` por id; `_bloco` ganhou o ramo de evidência por
   API e imprime `E TAMBÉM:` quando as duas provas fecham.
3. **R0b saiu de dentro do `if artefato is not None`** e virou AND: o modelo
   alega, o artefato corrobora. Sem chamada registrada é falso.
4. Categorias saem no vocabulário do desafio (`security`, `correctness`,
   `performance`, `convention or pattern`, `PRD divergence`).

⚠️ **Decisão de honestidade que vale conhecer antes de mexer:**
`alcancou_a_api` significa *"a chamada completou"*, **inclusive um 404** — não
"o defeito foi alcançado". O 404 conta de propósito: prova de negação indevida
(403/404 onde deveria haver dado) é achado legítimo, e exigir 2xx tornaria essa
classe indemonstrável. **Há teste travando isso**
(`test_404_conta_como_ter_alcancado_a_api_e_isso_e_deliberado`) para ninguém
"consertar" achando que é bug.

<details>
<summary>Especificação original (mantida para referência)</summary>

**Não comecei a codar. Está tudo especificado em
`ACHADO_PROVA_POR_API_NAO_VIRA_EVIDENCIA.md` (achado do Luis, 11h35, arquivos
meus).** Eu verifiquei e **confirmei no código** — não é teoria:

**(a)** `_http_request` não grava artefato; só `prova_diferencial` grava.

**(b)** `juiz._bloco` só emite evidência se existe artefato com
`estado == "PROVADO"`, senão imprime `EVIDENCIA: nao fechou`. **A prova disso
está no parecer que acabei de gerar:** o achado de `padroes` imprime
`EVIDENCIA: nao fechou.` seguido de uma explicação técnica real e correta.

**(c)** O pior: em `juiz.aplica_regras`, todo o bloco da R0 está dentro de
`if artefato is not None:`, **inclusive** o aterramento de
`prova_ponta_a_ponta`. Numa prova só por `http_request` não há artefato → o
bloco é pulado → **a auto-declaração do advogado passa sem conferência**, que é
o oposto exato do que a R0 existe para fazer. Combinado com a R2, a palavra do
modelo pode sustentar severidade ALTA sozinha.

Isso morde neste PR especificamente: **o PR adiciona 3 endpoints novos**, e prova
diferencial não funciona neles (404 no base = o inverso do padrão). Os
`provado_se` dos promotores roteiam esses achados para `http_request`.

### Conserto, 3 pontos (desenho já fechado, é só escrever)

1. **`_http_request` grava artefato** `artefatos/http_<id_acusacao>.json`.
   Acumular as chamadas da acusação numa lista de módulo, resetada em
   `define_acusacao` (mesmo padrão do `_AVISOS`), e gravar a cada chamada — não
   no fim — para que rodada que morre no meio não perca a evidência. Forma:
   ```json
   {"id": "...", "tipo": "http",
    "chamadas": [{"metodo":"GET","caminho":"/shared/2","como":"carol",
                  "status":200,"corpo":"...truncado...","erro":null}],
    "alcancado": true}
   ```
   `alcancado` = existe ao menos uma chamada com `status` e sem `erro`.

2. **`juiz.carrega_do_disco` também carrega `http_*.json`** num dict por id, e
   `organiza`/`aplica_regras`/`_bloco` recebem esse dict.

3. **`prova_ponta_a_ponta` sai do artefato, e o cálculo sai de dentro do
   `if artefato is not None`.** Regra nova, uma linha, sempre executada:
   ```python
   v["prova_ponta_a_ponta"] = bool(veredicto.get("prova_ponta_a_ponta")) and bool(
       (artefato_http or {}).get("alcancado")
   )
   ```
   AND deliberado: o modelo alega, o artefato corrobora. Sem artefato http →
   falso, independente do que ele declarou. Fecha o furo.

4. **`_bloco` ganha 3 ramos** em vez de 2: diferencial PROVADO → linha atual;
   senão http `alcancado` → `EVIDENCIA: GET /shared/2 como carol -> HTTP 200.
   Artefato: artefatos/http_<id>.json`; senão → `nao fechou`. Citar a última
   chamada com status e sem erro (regra determinística).

⚠️ Testes: `tests/test_juiz.py` tem 4 lugares que chamam `juiz.organiza(...)` /
`formata_parecer(...)` com a assinatura antiga — atualizar junto.

</details>

### Segundo item do mesmo achado — FEITO junto

**Vocabulário de categoria.** O desafio nomeia `security`, `correctness`,
`performance`, `convention or pattern`, `PRD divergence`. Nós emitimos
`injection`, `vazamento_de_contexto`, `correcao`, `padroes`, `performance`,
`prd`. Um dicionário de tradução no `_bloco` resolve e mantém a granularidade
interna. Jurado lendo rótulo que não é o dele é atrito à toa.

---

## 6. Ambiente desta máquina — MUDOU às 12h50

**Decisão do usuário:** rebuildar a stack no PR, porque com o app servindo `main`
o `http_request` nunca prova alcance no código do PR e a R2 trava tudo em MEDIA.

```
git -C ..\hack2l-challenge checkout pr/document-sharing
docker compose -f ...\docker-compose.yml --project-directory ... up -d --build api web
```

✅ **FEITO E VERIFICADO às 12h58, nas quatro vias:**

| checagem | resultado |
|---|---|
| branch do repo do desafio | `pr/document-sharing` @ `1dd2e5c` |
| `wc -l /code/app/routers/shares.py` no container | **96 linhas** (o `+96` do diff) |
| `/openapi.json` | serve `/documents/{doc_id}/share`, `/shared-with-me`, `/shared/{doc_id}` — os três só existem no PR |
| tabela `shares` em `kb` | **criada** (o `create_all` do startup fez sozinho) |

`documents` continua lá, então **o seed e os embeddings sobreviveram** — não
precisa re-semear.

⚠️ **Consequência para o parecer:** `http_request` agora prova alcance no código
do PR. Mas isso **só vira evidência depois do conserto da seção 5** — hoje a
prova por API ainda imprime `EVIDENCIA: nao fechou`. As duas coisas se pagam
juntas; rebuild sem o conserto não muda o parecer.

⚠️ Esta máquina agora diverge do que o `ESTADO.md` descreve (lá o desafio estava
com git intocado em `main`). Para voltar: `git -C ..\hack2l-challenge checkout
main` + o mesmo `up -d --build`.

`main.py` faz `Base.metadata.create_all` no startup, então a tabela `shares`
aparece sozinha; o volume do banco não é tocado, seed e embeddings sobrevivem.
Se o banco for recriado, **re-semeie** (ver `ESTADO.md` — o seed pula se os
documentos existirem).

⚠️ O `_TESTE_PERIGOSO` #1 continua correto e **não deve ser removido**: teste
diferencial não pode falar com o serviço `api` no ar, porque a imagem serve um
código fixo. O que muda é que `http_request` agora prova **alcance no código do
PR**, que é a frase central do pitch.

Portas desta máquina seguem **8010 / 3010 / 55432 / 3001**, sempre `127.0.0.1`.

---

## 7. Estado do git — sincronizado às 12h52

`main` em `abe6469`, **em sincronia com `origin/main`**, árvore limpa exceto o
que estiver em curso. Commits desta sessão: `94be34b` (parse + normaliza_local),
`c81be61` (diagnóstico de recusa), `abe6469` (merge com o Luis).

Do Luis, já mergeados: `f8bb860` (**Langfuse instrumentado — `veredito/tracing.py`,
13 testes; a questão nº 4 do ESTADO está RESOLVIDA, não precisa decidir**) e
`42cbb58` (promotores, 47 acusações do diff real em 37 s).

**Divisão:** `ferramentas.py`, `juiz.py`, `config.py`, `advogado.py`,
`orquestrador.py`, `promotores.py` → Mariano. `llm_alvo.py`, `tracing.py`,
`promotores/*.md` → Luis.

### Script de reparse (não sobreviveu ao corte; recriar se quiser recuperar as 2)

Ler `saidas/veredictos.json`; para cada entrada com `saida_crua`, chamar
`advogado._parse_veredicto(crua)`; se o resultado não tiver `saida_crua`,
`v.update(novo)`, restaurar `v["id"]`, `v.pop("saida_crua")`. Regravar o JSON e
chamar `juiz.sentencia()`. A R0 continua conferindo contra o artefato, então
nada é promovido sem prova.

---

## 8. Ordem sugerida — atualizada 13h20

~~1. Conferir o rebuild da stack~~ ✅ seção 6
~~2. Conserto da R0 em 3 pontos~~ ✅ seção 5, commit `b66c66f`
~~3. Dicionário de categorias~~ ✅ junto

**O que resta:**

1. **Reparse das 2 acusações** (seção 7) — 2 min, recupera 2 achados sem custo
   de API.
2. **Ver uma CRÍTICA acontecer.** Nunca foi observado: até 13h20 nenhum achado
   passou de MÉDIA porque `prova_ponta_a_ponta` era estruturalmente impossível.
   Agora é possível — falta confirmar numa rodada real que o advogado
   efetivamente faz as duas provas. Rodada `--top-n 3 --reusar` disparada 13h22;
   **conferir `logs/validacao_r0.log`**.
3. **Rodada final 14h15**, na máquina do Luis, `--top-n 10`, Opus 5. Copiar o log
   para `saidas/final/`.

⚠️ **A máquina do Luis precisa do mesmo rebuild no PR** (seção 6), senão a R0b
nunca dispara lá e o parecer do palco volta a travar em MÉDIA — o oposto do
efeito pretendido. É o item de sincronização mais importante entre as duas
máquinas agora.

**Não fazer:** trocar de modelo, `docker system prune -a`, chumbar achado,
afirmar número sem gabarito no pitch.
