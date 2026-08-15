<!-- tag: hack2l -->

# Rodada de 14/08, 21h31 — a contenção do `http_request` sob carga real

**O que esta rodada prova:** que o Veredito revisa um PR inteiro **sem tocar no
banco do app**. É a primeira rodada completa com `APP_EM_BANCO_DESCARTAVEL=1`.

```
6 acusações · 161s · 4 provados, 1 descartado, 1 inconclusivo
7338 entrada / 3938 saída / 300520 de cache
```

---

## A contenção, que é o motivo de arquivar esta rodada

Durante os 161 segundos o advogado fez POSTs com payload de injection, leu
documento como `carol` e compartilhou documento entre usuários. Tudo isso caiu
numa **cópia descartável** do banco.

| | antes | depois |
|---|---|---|
| banco real `kb` | `shares=3, documents=5, users=4` | **idêntico** |
| cópia `kb_veredito_app` | — | `shares=4` ← levou a bagunça |

Conferido por duas vias que não dependem uma da outra: a medição automática
(`efeito_no_banco.json`, que diz `limpo: true`) e um `psql` manual antes e
depois. As duas batem.

**Por que isso importa:** em 14/08 de manhã, uma rodada sem contenção deixou
`shares` em 3 quando a linha de base do seed é 0 — e ninguém teria visto, porque
nada media. Um revisor que suja o banco do cliente na primeira rodada não tem
segunda chance.

---

## O parecer, que por acaso é o melhor do dia

**A crítica** é a invariante de isolamento do desafio: `carol`, que não possui
nada e existe como controle negativo, obteve `HTTP 200` em `GET /shared/4` — um
documento compartilhado **entre alice e bob**. Árbitro com procedência
(`docs/REVIEW_TASK.md:43`) e prova ponta a ponta contra o app rodando.

**Duas altas de SQL injection**, corroboradas por bandit *e* semgrep. A linha do
semgrep agora nomeia a variável e a rota — mudança de 14/08 nas regras de taint,
visível no parecer final:

> *"O parametro **email**, controlado pelo cliente na rota **share_document**,
> alcanca db.execute() por um caminho que nao passa por bind params"*

**O descartado foi bem descartado.** O advogado não só refutou: mostrou que a
acusação estava com o rótulo errado — *"o defeito real é o filtro invertido, uma
divergência de PRD, não vazamento nem injection como acusado"*. Mais útil que a
acusação original.

**E o inconclusivo é o melhor exemplo do terceiro estado que temos.** A acusação
era de duplicação sob concorrência. Resposta: a janela só ocorre com duas
transações simultâneas, as ferramentas disponíveis são sequenciais, logo **não
há artefato determinístico possível** — nem confirmado, nem derrubado. Isso
mapeia exatamente na lacuna já documentada na seção E do `PROXIMOS_PASSOS`
(*"race condition e check-then-act são invisíveis"*). Ele não chutou.

---

## ⚠️ O que esta rodada NÃO prova

- **Não é comparação controlada** com a rodada das 14h51. As acusações são
  outras (os promotores rodaram de novo), então os números de custo servem para
  ordem de grandeza, não para medir efeito.
- **A contenção estava ligada**, então esta rodada não diz nada sobre quanto uma
  rodada *sem* contenção suja o banco. Isso quem mede é a de 14h51.
- **`prova_diferencial` só rodou onde já rodava.** A cópia é do app; a suíte do
  repositório continua indo para `kb_veredito`, como desde 11/08.

## Como reproduzir

```bash
py -3.12 checar_contencao.py                 # a contenção funciona nesta máquina? (grátis)
APP_EM_BANCO_DESCARTAVEL=1 py -3.12 -m veredito.orquestrador --top-n 6
```
