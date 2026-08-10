<!-- tag: hack2l -->

# promotores/ — o contrato de integração (Luis → Mariano)

Seis prompts de promotor, texto puro. **O código lê esta pasta; não importa nada
daqui.** Integração = commit. Cada `.md` é um prompt **completo e autônomo**.

## 🚨 Reescritos em 10/08 — o PRD saiu daqui

A versão original destes prompts trazia o PRD, os critérios de aceite e as 8
convenções **colados dentro da lente**. Parecia certo: era material do lado limpo
do muro de contaminação, e nenhum deles cita achado do diff.

Estava errado por outro motivo. Medido em 08/08 à noite, em 10 PRs reais de
Flask, Django, httpx, Gin, Next.js e Requests: **94 acusações com árbitro
preenchido, 94 citando os critérios de aceite do desafio da Vindler** — em
repositórios que não têm nada a ver com ele. A lente de PRD nunca ficava vazia
porque sempre tinha critério para conferir: os critérios estavam dentro dela.
Não lia o repositório, **recitava o desafio**.

E os rótulos `AC1`–`AC5`, `R1`–`R4`, `C1`–`C8` **nunca existiram nem no desafio**
— `grep AC1 docs/` no repo deles não acha nada. Nós inventamos a numeração ao
escrever estes prompts, e depois mandamos o modelo citá-la *verbatim*.

Detalhe em `../ACHADO_ARBITRO_CHUMBADO.md`.

**O que mudou:**

| | antes | agora |
|---|---|---|
| PRD, critérios, convenções | colados na lente | `contexto/hack2l.md`, carregado em tempo de execução |
| `arbitro` | sigla de lista fixa (`"AC2"`) | `{"regra": "...", "onde": "arquivo:linha"}` ou `null` |
| lente sem contexto | recitava o desafio | acusa igual, com `arbitro: null` |

A régua se mantém, e agora de verdade: troca o PR, os prompts continuam válidos,
porque descrevem **classes de defeito** — e o que é específico de um repositório
entra por fora.

## Os arquivos

| Arquivo | `categoria` que emite | bucket (p/ a cota do juiz) |
|---|---|---|
| `prd.md` | `prd` | prd |
| `injection.md` | `injection` | seguranca_ia |
| `vazamento_contexto.md` | `vazamento_de_contexto` | seguranca_ia |
| `correcao.md` | `correcao` | correcao |
| `padroes.md` | `padroes` | padroes |
| `performance.md` | `performance` | performance |

Segurança de IA foi **dividida em dois** promotores (injection + vazamento) — é
o degrau 2 da escada de conserto do doc, e é onde investimos. Os dois caem no
bucket `seguranca_ia`.

## Como montar a mensagem de cada promotor

```
[ diff do PR + código em volta ]      <- prefixo grande, IGUAL nos 6
[ contexto do repositório ]           <- opcional, também IGUAL nos 6
[ conteúdo do arquivo .md ]           <- a lente, específica de cada um
```

**Ordem importa para o cache.** Ponha o diff **antes** da lente. O prefixo é
idêntico nas 6 chamadas → o Opus/Haiku cacheia o diff uma vez e relê a ~10% nas
outras cinco. Conferir `cache_read_input_tokens > 0` na 1ª rodada; se vier zero,
tem algo variando no prefixo (timestamp/ordem de dict).

O contexto entra **no prefixo, não na lente** — ele é o mesmo para os seis, então
cacheia igual. Dentro da lente ele voltaria a viajar para dentro de todo diff do
mundo, que é o defeito que acabamos de consertar.

Cada `.md` já traz o esquema de saída e o exemplo de formato. O modelo responde
**um array JSON** e nada mais. Mantenha o `try/except` no parse com fallback pra
saída crua — está no CONTRATO, e é o que impede a acusação de morrer por formato.

## Esquema que os promotores emitem

```json
{ "id": "...", "categoria": "...", "local": "arquivo:linha",
  "hipotese": "uma linha",
  "arbitro": {"regra": "...", "onde": "arquivo:linha"},
  "provado_se": "uma linha", "confianca": "alta|media|baixa" }
```

**`id` é prefixado por categoria** (`prd_01`, `injection_01`, …) para não colidir
entre os 6 promotores rodando em paralelo. Se você preferir `acusacao_NN` global,
renumere no merge — a única exigência da fronteira é que sejam únicos.

## O campo `arbitro` — não há mais vocabulário

Não existe lista de rótulos válidos, e é esse o conserto. O árbitro é uma **regra
escrita no repositório sob revisão**, citada com o arquivo e a linha onde está.
Sem conseguir apontar onde, é `null` — a resposta honesta, e a mais comum fora de
um repositório que documente os próprios critérios.

`veredito/arbitro.py` normaliza o campo na fronteira (aceita o objeto novo, a
string das rodadas antigas, e lixo) e é quem responde a pergunta que as regras do
juiz fazem: `tem_procedencia()`, não "o campo está preenchido".

**A regra R1 do juiz mudou junto**, e em duas direções:

- **mais estrita** — árbitro sem `onde` não sustenta CRÍTICA. "AC2" não diz onde
  a regra mora, e a essa altura sabemos que na maioria das vezes ela não morava
  em lugar nenhum.
- **mais larga** — **prova ponta a ponta com artefato** virou uma segunda via
  para CRÍTICA, independente de árbitro. Sem isso, desacoplar o árbitro tornaria
  SUSPEITA todo achado provado em todo repositório que não documenta os próprios
  critérios, ou seja, quase todos.

O furo que a segunda via fecha está no parecer premiado: o **mesmo** SQL
injection saiu como `padroes_01` (árbitro `"C2"`) → CRÍTICA e como `correcao_01`
(árbitro `null`) → SUSPEITA, tendo os dois prova diferencial e artefato HTTP. A
severidade seguiu o acaso de uma lente ter recitado um rótulo chumbado.

## ⚠️ Dois pontos de integração que preciso te passar

**1. `prova_diferencial` não serve para bug em endpoint NOVO.** Os endpoints de
share (`/documents/{id}/share`, `/shared-with-me`, `/shared/{id}`) **não existem
no commit base** — um teste que os chama dá 404 no base (falha) e funciona no
head. Isso é o **inverso** do padrão "passa no base, falha no head". Então:

- Regressão em comportamento **que já existia** (isolamento de `/documents`,
  `/chat`, a linha de base) → `prova_diferencial`. É aqui que ela brilha, e a
  linha de base (`demo=3, alice=1, bob=1, carol=0`) é um diferencial de uma linha.
- Bug **em endpoint novo** → teste que **falha no head** expressando o certo, ou
  `http_request` mostrando o errado. **Não** diferencial.

Os `provado_se` dos promotores já vêm roteados por essa distinção. O advogado
precisa saber escolher a ferramenta na mesma lógica — senão vira INCONCLUSIVO à
toa.

**2. A cota do juiz não tem vaga de `performance`.** A tabela da rodada final é
seguranca_ia(3) · prd(2) · correcao(2) · padroes(2) · curinga(1) = 10. Como
adicionei a 5ª categoria que o enunciado nomeia, ou você dá 1 vaga a performance
(total 11), ou ela disputa só o curinga. Recomendo `performance: 1`. É uma linha
no orquestrador — decide junto com o `TOP_N` das 12h, com a medição.

## Contaminação — e a lição de 09/08

Estes prompts não citam nenhum arquivo nem linha do diff, e continuam não
citando. **Mas essa nunca foi a única forma de contaminar.**

O muro que construímos era contra chumbar *o achado*. O que passou por baixo dele
foi chumbar *o repositório*: PRD, critérios, convenções, nomes de endpoint e até
o mapa do app viajaram dentro da lente para dentro de Flask, Django e Gin. Nada
disso era resposta do PR — e mesmo assim tornou a métrica de árbitro inútil e a
lente de PRD incapaz de ver qualquer outro projeto.

A regra que sobra, e que vale para o próximo prompt que alguém escrever aqui:

> **Se a frase só faz sentido no desafio, ela não é lente — é contexto.** Vai
> para `contexto/`, entra em tempo de execução, e some sozinha quando o
> repositório é outro.

`tests/test_prompts_limpos.py` verifica isso mecanicamente nos seis arquivos:
vocabulário chumbado, marcas do app do desafio, e o contrato do árbitro presente
em todas as lentes. Prompt regride em silêncio; asserção não.
