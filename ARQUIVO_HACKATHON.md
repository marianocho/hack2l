<!-- tag: hack2l -->

# Arquivo — o que era do dia 08/08

Extraído do `CLAUDE.md` em **11/08/2026**. É tudo que só fazia sentido **durante
o hackathon**: cronograma, checklist de preparo, parâmetros da rodada que
congelou às 15h, e o roteiro do pitch de 3 minutos.

**Nada aqui foi apagado — foi movido.** O `CLAUDE.md` é carregado a cada sessão
nova, então regra de relógio de um dia que já passou custa contexto em toda
conversa daqui pra frente. Mas é história do projeto e prova de como as decisões
foram tomadas, então mora no repositório, versionado.

O que continua no `CLAUDE.md`: arquitetura, regra central, esquema, regras do
juiz, API da Anthropic, modelos, ambiente, princípios, e o mapa do app alvo.

---

## ESTADO ATUAL (08/08, manhã) — o checklist de preparo

```
C:\hack_agents\Hack2L\        ← abrir o Claude Code aqui
├── CLAUDE.md                 ← este arquivo
├── desafio\                  ✅ clonado, git intocado
└── veredito\                 ⬜ falta: git init nosso
```

**Feito:** repo clonado, `.env` criado do `.env.example`, `docker compose up
--build` disparado, `langfuse==2.57.0` instalado.

**Falta:**

```bash
cd C:\hack_agents\Hack2L && mkdir veredito && cd veredito && git init && git commit --allow-empty -m "inicio do Veredito - Hack2L"
```

O commit vazio carimba a hora de início antes de existir uma linha de código.

**Por que dois repos:** o nosso histórico é a prova de integridade e precisa ser
só nosso; e a prova diferencial (slot 2) faz checkout do commit base **no repo
deles** — misturar vira confusão na hora errada.

> *Na prática o nosso repo virou `hack2l/`, não `veredito/`.*

### 🚨 A branch do PR já está no remote

`origin/pr/document-sharing` já existe, e o `git clone` já baixou os objetos —
o conteúdo está no disco. Mas o `docs/REVIEW_TASK.md` deles diz: *"nada sobre a
mudança está disponível antes disso, deliberadamente. Todo time recebe no mesmo
momento."*

**Não abrir antes do briefing.** Não é regra formal, é contaminação: depois de
ver o defeito não se desvê, e cada decisão sobre o agente fica torta. Depois das
9h, `git fetch && git checkout pr/document-sharing`.

## Regras de integridade que eram do dia

**Todo o código nasce em 08/08.** Podem pedir histórico de commits. Antes do dia
vale pesquisa, arquitetura e preparo de ambiente — não código.

**`git init` às 9h05, commit a cada 20–30 min.** O histórico é a prova.

**Restrições do dia:** 5h de construção, congela às 15h, time de 2 (talvez 3),
pitch de 3 minutos.

---

## 📏 LINHA DE BASE — medida em 08/08 09h46, na `main`, ANTES do briefing

O stack subiu no commit base `f491ae1` e o isolamento foi medido **sem ninguém
ter visto o PR**. Esta é a metade "passa antes" da prova diferencial, com
número, e não pode ser acusada de ter sido feita sabendo a resposta.

| Usuário | Documentos visíveis via `GET /documents` |
|---|---|
| `demo` | **3** |
| `alice` | **1** |
| `bob` | **1** |
| `carol` | **0** |

Rotas da API na base (do `openapi.json`): `POST /auth/login`,
`POST /auth/register`, `POST /chat`, `GET|POST /documents`,
`GET|DELETE /documents/{doc_id}`, `GET /health`.
**`/shares` NÃO existe** — ela chega com o PR.

> *Estes números seguem válidos e hoje moram em `contexto/hack2l.md`, com
> procedência. Ficam aqui como registro de que foram medidos antes do briefing.*

⚠️ **O código é assado na imagem** (sem volume montando o fonte). Trocar de
branch exige `docker compose up -d --build api`.

## A decisão das 10h sobre a chave da OpenAI

O app alvo chama `gpt-4o-mini` e `text-embedding-3-small`. **Nossa chave da
Anthropic não substitui isso** — é o código deles.

Sem `OPENAI_API_KEY` o app sobe com embeddings offline e **resposta enlatada**.
Continua testável: API, auth, lógica do PR, `pytest`, e vazamento de contexto.
Degrada em dois pontos: não dá pra mostrar "o modelo obedeceu a injeção", e
embeddings offline tornam a similaridade quase aleatória.

**Decisão:** manda uma pergunta no chat como `demo`, abre o trace. Se a
recuperação vier aleatória, US$5 de OpenAI é seguro barato.

> *Virou a regra R4 do juiz e o módulo `llm_alvo.py`: LLM alvo dublê + REFUTADO
> = INCONCLUSIVO, nunca absolvição. Ver `ACHADO_APP_SEM_MODELO.md`.*

---

## PARÂMETROS — decididos 08/08

| Parâmetro | Dev | Rodada final |
|---|---|---|
| `TOP_N` acusações ao advogado | **2** | **fórmula abaixo** |
| Timeout por acusação | 3 min | 3 min |
| Teto de voltas do loop | 10 | 10 |
| `task_budget` por acusação | 30.000 | 30.000 |
| `max_tokens` do advogado | 64.000 | 64.000 |
| `effort` | `high` | `high` |

### O orçamento é TEMPO, não token

Contando de trás pra frente: a rodada final tem que estar **gravada** às 15h, o
vídeo e a submissão comem 15h–16h, logo **a rodada começa 14h15**. Janela real:
**45 minutos.**

```
TOP_N final = 40 min ÷ (segundos medidos por acusação)
```

Os 40 e não 45 são margem pra uma acusação estourar o timeout.

### `effort` e `TOP_N` disputam o mesmo relógio

Não são botões independentes: `effort` mais alto = mais tempo por acusação =
menos acusações cabem nos 45 min.

⚠️ **Se não couber, corte o `effort` antes de cortar o `TOP_N`.** O que vende é
o parecer ter achado provado + suspeita rotulada + lista de descartados, e isso
vem de **cobertura**.

### 🎯 Cota por categoria

Ordenar as `TOP_N` puramente por confiança faz uma categoria comer todas as
vagas. Repartição da rodada final:

| Categoria | Vagas |
|---|---|
| Segurança de IA | 3 |
| PRD | 2 |
| Correção | 2 |
| Padrões do repo | 2 |
| Curinga (maior confiança, qualquer categoria) | 1 |

> *Virou `promotores.COTAS`, com `performance: 1` acrescentado.*

### As 3 medições das 11h30

Quando a primeira acusação fechar ponta a ponta, anotar do `usage`:

1. **Segundos por acusação** → define o `TOP_N`
2. **Voltas do loop** → confirma se o teto de 10 está certo
3. **Custo em dólar** → é o "custo por PR" do pitch

---

## ORDEM DE CONSTRUÇÃO E CRONOGRAMA

O caminho crítico é o **loop do advogado**. Prompt de promotor são 20 minutos a
qualquer hora do dia; sem o loop não existe demo.

| Hora | O quê |
|---|---|
| 08h30 | Check-in, bateria cheia |
| 09h00 | Briefing. **Um clona e sobe o app, o outro ouve** |
| 09h05 | **Os comandos do topo deste arquivo** — clone, `git init`, commit vazio |
| 10h00–10h20 | App no ar + ler PRD e critérios de aceite (em paralelo) |
| 10h20–10h40 | **Travar:** esquema da acusação, formato do parecer, tabela de parâmetros |
| 10h40–12h00 | **Slot 1** — `run_tests` + loop do advogado ponta a ponta |
| 12h00–12h40 | **Slot 2** — prova diferencial |
| 12h40–13h00 | **Slot 3** — os 4 promotores |
| 13h00–13h40 | Pizza. **Ações 1 e 4 do pitch aqui** (não codar) |
| 14h00–14h15 | Mentoria com Carlos Dutra |
| 14h15–14h45 | **Slot 4** — juiz + 3 regras determinísticas + formato |
| 14h45–15h00 | Endurecer. **Duas rodadas limpas.** |
| **15h00** | **CONGELA.** Rodada final já **gravada** |
| 15h00–16h00 | Vídeo + submissão + ensaiar cronometrado 2x |
| 16h00 | Demo Day — 3 minutos |

⚠️ **A rodada final leva ~36 min** (12 acusações × 3 min de timeout).

**Slot 1 usa `run_tests`, não `http_request`,** porque é a única que funciona com
o app fora do ar. Se o Docker deles empacar às 11h, o dia não morre.

### ⚠️ Como `run_tests` tem que ser (medido em 08/08)

**A suíte deles tem 5 testes e TODOS PASSAM.** 8s por chamada.

Logo, `run_tests` **não é "roda a suíte e vê se dá vermelho"** — ela é verde e
continua verde. A prova é um **teste novo, escrito pelo advogado**, que falha
por causa do defeito.

E o código é **assado na imagem** — tem que injetar no container: `docker
compose cp` do host, ou stdin via `exec -T api sh -c 'cat > /tmp/test_x.py'`.

Usar `run --rm` e não `exec`: 2s mais lento, mas isolado.

**Cortar sem dó:** Langfuse instrumentando o nosso agente, `query_db`,
`read_trace`, Playwright, promotor #5 do linter.

**Se o app não subir:** `read_file`, `grep` e `run_tests` funcionam sem ele.

---

## PITCH — o roteiro dos 3 minutos

Critérios com pesos iguais: protótipo · viabilidade como startup · pitch ·
criatividade.

> *Os fatos de mercado verificados desta seção continuam valendo e foram
> mantidos no `CLAUDE.md` em forma compacta, porque reaparecem em toda conversa
> de estratégia. O que ficou aqui é o roteiro do dia.*

### Diferenciação — a frase corrigida

⚠️ **NÃO dizer "nenhuma ferramenta do mercado faz".** É falso e cai em 30
segundos no celular de um jurado.

> "Existe quem escaneie prompt injection no PR — a Promptfoo faz, com análise
> estática de fluxo de dados. **Ninguém executa o ataque para provar que é
> alcançável.** É a diferença entre 'este padrão é arriscado' e 'eu disparei
> este payload pela API e olha o trace'."

### Se perguntarem "isso já existe?"

> "O ICSE deste ano teve um trabalho com enquadramento multiagente parecido. Lá
> os agentes debatem por escrito. Aqui o verificador executa, e o veredito final
> é um exit code."

### Defensibilidade

Não usar "volante de dados" — todo concorrente diz isso em escala maior.

- **A categoria, não o volante.** Nenhum incumbente tem oráculo para "este PR
  quebrou o isolamento de tenant no RAG".
- **O laudo é auditável.** "Merge com laudo" tem comprador (segurança,
  auditoria) que "menos ruído no PR" não tem.

### ⚠️ A metáfora NÃO é o diferencial

O README do starter kit deles diz, textual: *"growing it into a team of
specialist reviewers with a verifier that tries to refute each finding, and a
synthesizer that de-duplicates and ranks, **is the work that wins**."*

Bom: estamos na direção certa, validado pela fonte. Ruim: **todo time que ler
esse README vai construir algo parecido.** O diferencial passa a ser a camada de
baixo — a prova diferencial, o veredito como exit code, e as listas de
descartados e inconclusivos.

### O momento forte do demo

O **mesmo tipo de achado em dois níveis**: um provado e crítico, outro que
cheirou mal e virou suspeita de baixa confiança, mostrando o que foi tentado.

Enquadrar a lista de descartados **em voz alta**, senão soa como confissão de
erro: *"toda ferramenta te enche de alarme falso até você parar de ler; esta te
mostra o que descartou e por quê."*

### Perguntar na mentoria das 14h

- A priorização em segurança de LLM faz sentido?
- O parecer ideal é laudo para humano ou decisão de merge?

> *Respondido em 10/08, na conversa com o Carlos: bot de PR, sem jargão
> jurídico, foco em validação e não em monetização.*
