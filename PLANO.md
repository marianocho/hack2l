<!-- tag: hack2l -->

# Plano de divisão — Mariano e Luis (08/08/2026)

Congela **15h**. Pitch 16h, 3 min. Escrito ~10h, briefing em curso.

## O princípio da divisão

O caminho crítico é **um só e é serial**: `run_tests` → loop do advogado →
prova diferencial → juiz. Não dá pra duas pessoas empurrarem isso ao mesmo
tempo sem uma esperar a outra.

Tudo o resto — promotores, pitch, paridade de máquina — é paralelo e **não pode
virar sobra de fim de tarde**. Os 4 critérios de julgamento têm peso igual e
**3 deles são negócio e apresentação**. Um time que coda até 14h45 e improvisa
o pitch joga fora 3/4 da nota com o protótipo pronto.

## Quem pega o caminho crítico, e por quê

**Mariano.** Não é preferência: a máquina dele está verificada e rodando agora
(stack no ar, `pytest` verde, venv 3.12 com paridade), e a sessão do Claude Code
está com o contexto inteiro carregado. Reconstruir isso na máquina do Luis custa
a hora que não temos.

**Luis** pega a máquina do palco e o pitch. A apresentação roda na máquina dele,
então a paridade dela é bloqueio de demo, não tarefa de limpeza.

## Bloco 0 — juntos, ~20 min, antes de qualquer código

Só três coisas. Elas destravam trabalho independente pelo resto do dia:

1. **Criar o repo no GitHub** e o Luis clonar. Sem isso ele não recebe nada.
2. **Travar o esquema JSON da acusação.** É o contrato entre as duas pessoas —
   ver abaixo.
3. **Travar o formato do parecer.** Princípio nº 1 do doc: sabendo a cara da
   saída, o agente se desenha. E é o slide de resultado do pitch.

## O contrato: o esquema é a API entre vocês

A disciplina nº 2 do doc já manda salvar cada etapa em disco — promotores em
arquivo, advogado em arquivo, juiz lendo do arquivo. **Essa mesma fronteira vira
a fronteira entre as duas pessoas:**

- Luis escreve os promotores como **arquivos de texto** em `promotores/*.md`.
- O código do Mariano **lê a pasta**, não importa nada dele.
- Integração = o Luis dar commit. Não existe reunião de integração, não existe
  conflito de merge, ninguém fica bloqueado.

Se o esquema JSON estiver travado às 10h20, essa interface aguenta o dia inteiro.

## Contaminação: quem lê o quê

| | Pode ler | **Não pode** |
|---|---|---|
| Luis (promotores) | PRD, critérios de aceite, as 8 convenções | **o diff do PR** |
| Mariano (advogado) | o que for preciso pra debugar | — |

O Mariano vai esbarrar em código do PR rodando teste e lendo arquivo — isso é
inevitável e não é problema. O que desqualifica é **chumbar um achado no
prompt**. Quem escreve prompt de promotor fica longe do diff, e a régua se
mantém: troca o PR, o agente continua funcionando.

## Cronograma

| Hora | Mariano — caminho crítico | Luis — máquina do palco + pitch |
|---|---|---|
| agora–10h20 | **JUNTOS:** GitHub, esquema da acusação, formato do parecer | idem |
| 10h20–11h00 | **Slot 1** — `run_tests` + loop do `tool_runner` | **Paridade da máquina:** clone, `.env` com as portas dele, `up`, `pytest` verde |
| 11h00–12h00 | Slot 1 — advogado ponta a ponta, com 1 acusação escrita à mão | Ler PRD + critérios de aceite |
| 12h00–12h40 | **Slot 2** — prova diferencial base↔head | **Slot 3** — os 4 promotores, em `promotores/*.md` |
| 12h40–13h20 | Integrar: advogado lê os promotores do disco | 🔒 **PITCH** — narrativa, slides, números verificados |
| 13h20–14h00 | Endurecer: duas rodadas limpas em dev | 🔒 **PITCH** + ensaio cronometrado |
| 14h00–14h15 | Mentoria com Carlos Dutra — **os dois**, as 2 perguntas do doc | idem |
| **14h15** | 🚨 **DISPARA A RODADA FINAL** (~36 min) | Recebe o parecer, monta o slide de resultado |
| 14h15–14h45 | **Slot 4** — juiz + 3 regras, em paralelo com a rodada | Vídeo |
| 14h45–15h00 | Juiz na saída fresca | Ensaiar 2x cronometrado |
| **15h00** | **CONGELA** | |

🔒 = bloco protegido. Não é onde se corta quando atrasar.

O slot 4 rodar em paralelo com a rodada final só funciona porque o juiz lê de
**arquivo**. É a disciplina nº 2 pagando a conta.

## Decisões com hora marcada

Decisão sem hora marcada vira decisão às 14h45 sob pressão.

- **~11h — a chave da OpenAI.** Mandar uma pergunta no chat como `demo`, abrir o
  trace. Se a recuperação vier aleatória, US$5 é seguro barato. Sem isso, risco
  de falso negativo no teste de canário.
- **10h20, depois de ler o PRD — a ordem muda?** Se ficar claro que o defeito de
  segurança só é alcançável pela API rodando, `http_request` sobe pro slot 1.
- **12h30 — `http_request` entra ou não.** É a decisão mais afiada do dia:
  segurança de IA é onde o doc manda ir fundo, e essa ferramenta cobre 3 das 6
  exigências de uma vez. Mas o doc também a lista como "só se sobrar". **Decidir
  às 12h30 olhando se o slot 2 fechou** — não às 14h45.

## Cortar sem dó, se atrasar

Nesta ordem: Langfuse instrumentando o nosso agente (o `usage` já dá custo e
latência), `query_db`, `read_trace`, Playwright, promotor nº 5 do linter.

**Nunca cortar:** as listas de descartados e inconclusivos. São a peça que
nenhum outro time vai ter, e o README dos organizadores já entregou a
arquitetura promotor/advogado/juiz pra todo mundo.
