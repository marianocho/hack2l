<!-- tag: hack2l -->

# Vídeo — roteiro e lista de tomadas

Janela: **15h00–16h00**, junto com submissão e dois ensaios cronometrados. Apertado.

---

# 🚨 LEIA ANTES DAS 14h15

**Quatro tomadas só existem enquanto a rodada final estiver rodando.** Depois
que ela termina, o terminal rolou, as barras de progresso sumiram e o
paralelismo dos promotores não acontece de novo sem gastar mais 14 min.

**Antes de apertar enter na rodada final:**

- [ ] Gravador de tela **já rodando** (OBS, Xbox Game Bar `Win+G`, ou ScreenToGif)
- [ ] Terminal em fonte grande — **16pt ou mais**. Fonte de trabalho não se lê no vídeo.
- [ ] Janela do terminal em **1920×1080**, não maximizada num ultrawide
- [ ] Notificações desligadas (`Win+A` → Assistente de foco)
- [ ] Nada de `.env`, chave de API ou token visível em nenhuma aba
- [ ] Langfuse já aberto em `http://127.0.0.1:3001`, logado
- [ ] **Grava a rodada inteira** (14,3 min). Corta depois — refilmar custa 14 min que não existem.

⚠️ **A rodada final é a única fonte dos números do pitch.** Se ela for
regravada, os números mudam e o slide precisa mudar junto.

---

## A ordem de captura (não é a ordem do vídeo)

| Quando | O quê | Por quê agora |
|---|---|---|
| **14h15, ao vivo** | Tomadas 1–4 | Só existem durante a execução |
| 14h45, depois da rodada | Tomadas 5–7 | Arquivos estáticos, dá pra refazer |
| 15h00+ | Narração e montagem | |

---

## Lista de tomadas

### 1. Os promotores abrindo em leque — ~20s de execução
**Captura:** terminal, do `python -m veredito.orquestrador --top-n 10` até a
linha de total de acusações.
**O que tem que aparecer:** as 6 linhas de promotor com contagem e `cache`.
**Narração:** *"Seis promotores acusam em paralelo. Isso é volume de propósito — acusar é barato."*

### 2. O advogado chamando ferramenta — 30s de qualquer acusação
**Captura:** o loop do `tool_runner` pedindo `prova_diferencial` / `http_request`.
**O que tem que aparecer:** a ferramenta sendo chamada e o resultado voltando.
**Narração:** *"O advogado não argumenta. Ele executa."*
**É a tomada mais importante do vídeo** — é ela que separa "afirma" de "prova".

### 3. O contador da prova diferencial
**Captura:** a linha que mostra o teste rodando nos dois lados e os exit codes.
**Narração:** *"Mesmo teste, commit base e head. Zero antes, um depois."*

### 4. O relógio total
**Captura:** a linha final com o tempo da rodada.
**Narração:** *"Catorze minutos, um pull request inteiro."*

---

### 5. O artefato — a tomada que prova a tese
**Captura:** `artefatos/prova_<id>.json` aberto, com `exit_base`, `exit_head`,
`estado`, `commit_base`, `commit_head` **visíveis na mesma tela**.
**Narração:** *"Isso não é o modelo dizendo que achou. É o exit code."*

Comando para abrir limpo:
```bash
py -3.12 -m json.tool artefatos/prova_<id>.json
```

### 6. O parecer — as três listas
**Captura:** `saidas/parecer.md` rolando devagar: CONDENADOS → DESCARTADOS →
INCONCLUSIVOS. Parar em cada cabeçalho.
**Narração:** a fala da Tela 3 do [PITCH.md](PITCH.md).
**Não corre.** As duas últimas listas são o diferencial; se passarem voando o
espectador não lê.

### 7. O trace do Langfuse — a prova de que o fluxo multiagente rodou
**Captura:** `http://127.0.0.1:3001`, o trace da rodada final, árvore expandida
mostrando promotores → advogado → juiz.
**Narração:** *"E aqui está o rastro inteiro, com custo e latência por etapa."*

Os organizadores dizem, verbatim: *"Submitting a trace link is the cleanest way
to prove your multi-agent flow actually ran."* **O link vai na submissão**, além
de aparecer no vídeo. Ele fica em `saidas/trace.txt`.

---

## Montagem — a ordem do vídeo

Mesma espinha do pitch, com a demo no meio:

```
0:00  problema (curl)                       — voz sobre slide
0:25  why now + tese                        — voz sobre slide
0:50  o que é                               — voz sobre slide
1:05  TOMADA 1 promotores em leque
1:20  TOMADA 2 advogado chamando ferramenta   ← o momento
1:40  TOMADA 5 o artefato, exit 0 → 1
2:00  TOMADA 6 parecer, três listas
2:25  TOMADA 7 trace
2:40  diferenciação + fecho                 — voz sobre slide
```

Se a duração exigida for diferente de 3 min, o que corta primeiro é a tomada 3
e depois a 4. **A tomada 2 e a 5 não se cortam** — são a tese do produto.

⚠️ **Ninguém verificou a duração e o formato exigidos na submissão.** Antes de
montar, abrir a página do evento e conferir. Montar 3 min e descobrir que pedia
90s às 15h50 é o pior jeito de perder a entrega.

---

## Os números — preencher às 14h45, não antes

Cada um sai de um comando. Nada de estimativa no slide.

| Número | Onde vive | Comando |
|---|---|---|
| Condenados / descartados / inconclusivos | `saidas/parecer.md` | primeira linha do parecer |
| Segundos da rodada | log da rodada | linha final do orquestrador |
| **Custo por PR** | soma do `usage` | ver abaixo |
| Link do trace | `saidas/trace.txt` | `cat saidas/trace.txt` |

**Custo por PR** — Haiku 4.5 `$1/$5` por MTok, Opus 5 `$5/$25`, Sonnet 5
`$3/$15`; cache custa 1,25× pra escrever e 0,1× pra ler. Somar por modelo, não
no agregado: a rodada mistura os três e um total indiferenciado dá número
errado por um fator grande.

**A frase, com o número medido:**
> *"Custo por PR revisado: $X, medido, no log."*

**A frase que NÃO se fala** (está no PITCH.md, repetida aqui porque é no vídeo
que escapa):
> ~~"encontrou N dos M defeitos"~~ — não existe gabarito. A verdade é mais forte:
> *"provou N com artefato reproduzível, descartou M com motivo, marcou K como inconclusivos com a causa."*

---

## Checklist de gravação de voz

- [ ] Ler o [PITCH.md](PITCH.md) em voz alta **duas vezes** antes de gravar
- [ ] Gravar a narração **separada** do vídeo, e casar na montagem — errar uma palavra não custa a tomada inteira
- [ ] Falar 10% mais devagar do que parece natural
- [ ] Uma pausa de meio segundo antes de *"Todo mundo afirma. Nós provamos."*

## Checklist de submissão

- [ ] Vídeo montado e no formato pedido
- [ ] **Link do trace do Langfuse** (`saidas/trace.txt`)
- [ ] Link do repo: `https://github.com/marianocho/hack2l`
- [ ] `saidas/final/` com o parecer e o log da rodada final commitados
      (`saidas/final/` **não** é gitignored, de propósito)
- [ ] Conferir se a submissão pede mais alguma coisa — a lista de exigências
      **não está no repo do desafio**, está na página do evento
