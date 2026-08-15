<!-- tag: hack2l -->

# A primeira medição com gabarito — 15/08/2026

**O que isto prova:** o Veredito acha, prova e **refuta** num repositório que ele
nunca tinha visto, com domínio diferente do desafio e defeitos plantados por
taxonomia externa (CWE).

É a pergunta que o projeto nunca tinha conseguido responder — *"os promotores
acham defeito real fora do desafio?"* — porque nenhum repositório de terceiro
tem gabarito.

## O placar

| PR | defeito | esperado | veio | |
|---|---|---|---|---|
| `pr/tarefa-por-link` | CWE-639 IDOR | PROVADO | **PROVADO:3** | ✅ |
| `pr/filtro-de-projetos` | CWE-89 SQLi | PROVADO | **PROVADO:2**, INCONCLUSIVO:1 | ✅ |
| `pr/reconvite-de-membro` | CWE-367 TOCTOU | INCONCLUSIVO | PROVADO:2, REFUTADO:1 | ❌ |
| `pr/contagem-de-tarefas` | **nenhum** | REFUTADO | **REFUTADO:3** | ✅ |

**Os quatro desfechos são diferentes entre si** — o critério de instrumento
calibrado. Custo somado: **145.190 tokens de entrada**, menos que *uma* das
rodadas quebradas de 14/08.

## As duas pontas, medidas fora de casa

**Achou e provou.** No IDOR, prova diferencial (passa em `93f69d1`, falha em
`c17d211`) **e** `GET /tasks/1 como davi -> HTTP 200` contra o app rodando —
causalidade e alcance. O árbitro citou `docs/REGRAS.md`, regra que o promotor
encontrou sozinho, sem nada chumbado na lente.

**Refutou sem inventar.** No PR limpo, três acusações e **zero condenações**.
Uma refutação pegou premissa alucinada do promotor — *"a premissa de
`sql_mode ONLY_FULL_GROUP_BY` é do MySQL e não se aplica"*. Outra mostrou que o
`ValueError` acusado exigiria mudança de schema que o PR não faz.

## ❌ Por que o PR 3 não bateu — e os três erros são do gabarito, não do produto

**1. Eu plantei dois defeitos nele.** Ao alargar a janela do race, acrescentei
`convidado_por` na resposta — que viola o contrato de saída das próprias
`REGRAS.md`. O Veredito **achou e provou** esse, com teste diferencial e
árbitro. Ele estava certo; a regra "um defeito por PR" fui eu que quebrei.

**2. `--top-n 3` era estreito demais.** 🚨 **Oito das 24 acusações brutas
nomearam o race**, uma com precisão — *"entre a checagem de limite e o INSERT
não há lock; dois requests simultâneos podem ambos passar"*. **Nenhuma entrou no
TOP_N.**

Pela escada do `CLAUDE.md`: **falha de RANKING, não de cobertura.** A cobertura
generalizou — cinco lentes diferentes viram um defeito de concorrência num repo
novo. O que faltou foi vaga.

**3. O runner contava errado**, tratando "não foi julgado" igual a "o veredito
divergiu". Corrigido: agora ele distingue e diz qual dos dois foi.

## O que continua sem resposta

**Se ele responde INCONCLUSIVO num defeito fora do alcance.** O race nunca
chegou ao advogado, então a pergunta central do PR 3 segue aberta. Precisa de
`--top-n 8`, e o gabarito agora registra esse mínimo.

⚠️ **n=4 prova que o instrumento mede, não que o produto acha defeito.**
Confundir as duas seria o erro dos 45% de árbitro outra vez.

## Reproduzir

```bash
py -3.12 roda_bancada.py --top-n 3            # os quatro
py -3.12 roda_bancada.py --top-n 8 --so pr/reconvite-de-membro
```

O runner troca de ramo, reconstrói as imagens, semeia, espera a rota de saúde e
devolve a bancada ao `main` no fim.
