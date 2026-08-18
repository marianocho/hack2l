<!-- tag: hack2l -->

# Handoff — 18/08/2026

> **Leia primeiro:** `CLAUDE.md` (produto) e `../CLAUDE.md` (máquina) carregam
> sozinhos. `PROXIMOS_PASSOS.md` é a fila viva. Este arquivo é o **delta** da
> sessão de 17–18/08 e diz exatamente onde retomar.
>
> O handoff anterior (`HANDOFF_17AGO.md`) continua válido como registro da
> decisão sobre a R3. As duas partes dele foram feitas.

## Estado verificado

**570 testes verdes** (`py -3.12 -m pytest -q`, ~80s, com Docker e o app do
desafio de pé). Sem Docker, use `-m "not lento"` — 6 testes são deselecionados.

`main == origin/main` em `ed74143`.

⚠️ **A bancada tem 1 commit local não enviado** (o bump dos actions):

```bash
cd ../bancada && git push origin main
```

## 🎯 O QUE A SESSÃO ENTREGOU: a saída existe, e a Action roda

Os dois bloqueadores da fila eram *"não tem onde entregar"* e *"escala quebra"*.
**O primeiro caiu.** O parecer vira comentário de PR (`veredito/comentario.py`,
`posta_parecer.py`), e o pipeline inteiro roda na CI de ponta a ponta.

**Medido, três rodadas do mesmo PR da bancada** (`luisfelp07/bancada#1`, IDOR
plantado, CWE-639):

| | 1ª | 2ª | 3ª |
|---|---|---|---|
| | auth quebrada | rodou cega | **completa** |
| morreu em | 30s | — | — |
| descritor | — | não achado | ✅ do worktree do base |
| ferramentas no pré-voo | — | 2 | ✅ **7** |
| achados | — | 0 (3 inconclusivos) | ✅ **3 com evidência, ALTA** |

E o achado da 3ª tem as **duas vias da R1**:

```
EVIDÊNCIA: test_isolamento_tarefa.py passa em f3bdd65 e falha em 61cc0a7 (0 -> 1)
E TAMBÉM:  GET /tasks/1 como davi -> HTTP 200        (davi = controle negativo)
ÁRBITRO:   "Ler uma tarefa exige poder ver o projeto..."
           (docs/REGRAS.md:Acesso e isolamento)
```

Prova diferencial **mais** ponta a ponta **mais** regra do repositório deles
citada com procedência. É o defeito do gabarito, com o conserto exato.

## 🚨 O QUE NÃO ESTÁ VERIFICADO — leia antes de dizer que funciona

**O código que POSTA o comentário nunca executou.** As três rodadas usaram
`postar=false`. `posta()` e `acha_o_nosso()` em `posta_parecer.py` não têm um
único teste — os 12 de `test_comentario_de_pr.py` cobrem montar e cortar, não
publicar.

Ou seja: está provado da entrada até **montar** o comentário. A última milha —
POST, achar o comentário anterior pela marca invisível, PATCH em vez de
empilhar — é código que nunca rodou. É justamente o que transforma isto em
produto.

**É o passo 1 de "onde retomar".**

## Os doze bugs, e o que cada um ensinou

Todos com trava, e **cada trava foi vista falhando** com a violação injetada.

| bug | a lição |
|---|---|
| `app/api/tests` chumbado | ferramenta que o projeto não declara **recusa dizendo**, em vez de falhar |
| R3 confundindo "não declarada" com "quebrou" | terceiro desfecho: `ok` / `erro` / `indisponivel` |
| alarme do banco disparando sempre | **guarda pode morrer de excesso** — a variação nova do padrão |
| 7 fallbacks do desafio no `config.py` | `or <valor do desafio>` é cicatriz de migração |
| caminho reescrito na hora de formatar | caminho normalizado é **fato da rodada**, carimbado |
| descritor lido do clone sem árvore | o clone é `git init`+`fetch`: só os worktrees têm arquivos |
| `--project-directory` no clone | oito chamadas; "sete de oito" ninguém percebe lendo |
| raiz única para descritor e app | **duas raízes**: config vem do base, código sob revisão vem do head |
| `Bearer` no git fetch | git sobre HTTPS quer `Basic`; `Bearer` só vale na API |
| worktrees nascendo tarde demais | *ambiente primeiro* inclui os worktrees |
| R0 tratando recusa como discordância | artefato que nunca rodou não derruba veredito |
| actions em Node 20 | era runtime de terceiro, não nosso |

### 🚨 As três que mais valem

**1. A R0 dava atestado de limpeza a uma vulnerabilidade real.** No primeiro run
completo, o advogado achou o IDOR e disse PROVADO nas três acusações. O parecer
saiu *"Nenhum achado sustentado por evidência — 3 inconclusivas"*. A R0 leu
`artefato.estado == INCONCLUSIVO` e derrubou — mas aquele artefato era uma
**recusa**, não um exit code discordando.

E a incoerência fechava o círculo: o texto da recusa diz *"Prove por leitura
(read_file/grep)"*. **O advogado obedeceu, provou por leitura, e o juiz o
derrubou por ter obedecido.** É a mesma distinção que a R3 aprendeu na véspera,
uma regra acima, e que não foi propagada na hora.

**2. A régua teria comemorado.** Os vereditos do advogado **batiam com o
gabarito**. Quem pontuasse a bancada lendo `veredictos.json` leria *"PROVADO,
acertou"* e marcaria 1 de 1 — enquanto o parecer, a única coisa que o cliente
vê, dava o defeito por inexistente.

> **Régua olhando o lugar errado reporta sucesso com o instrumento quebrado.**
> É o padrão dos 45% de árbitro, dentro da própria medição. Pontue sempre pelo
> **parecer**, nunca por `veredictos.json`.

**3. O corte pela raiz.** Medido: **14 de 14** fallbacks com literal string no
`config.py` usavam um valor que o `desafio.yml` declara; nove a bancada declara
diferente. Duas travas novas, nenhuma é lista mantida à mão:

- `tests/test_config_sem_desafio.py` — contraste entre projetos irmãos. O
  oráculo são os dois `veredito.yml`.
- `tests/test_projeto_nu.py` — o config **carregado de verdade** sem
  `veredito.yml`, em subprocesso.

> **A bancada acha essa classe por ser um segundo EXEMPLO, a ~US$2 por
> varredura. O projeto nu acha por ser a AUSÊNCIA de exemplo, em
> milissegundos.**

## Armadilhas que morderam nesta sessão

- 🚨 **Verificar o estado que você supõe, e não o que o código produz.** A
  checagem da separação base/head passou porque os worktrees foram criados **à
  mão** antes do teste. Em produção eles não existiam ainda, e o bug passou.
- 🚨 **Injeção de violação que não roda é verde falso.** Um script de shell
  morreu com `SyntaxError` e os testes "passaram" sem violação nenhuma. Ler o
  exit code do injetor, sempre.
- **Teste cujo valor esperado é igual ao valor errado não discrimina.** O teste
  do carimbo punha `local == local_normalizado` e passava com o carimbo
  ignorado.
- **Guarda que respeita o limite calando o aviso.** A primeira `corta` cabia no
  teto do GitHub omitindo o aviso de truncamento — cumpria metade do contrato.
- **O Docker Desktop caiu 3× na sessão.** É o bug de socket do `../CLAUDE.md`;
  `scripts/docker-up.ps1` resolve em ~15s. Os containers do desafio caem junto
  e precisam de `docker compose up -d` de novo.
- **Emoji em `print()` derruba o console cp1252.** Mordeu de novo. Convenção: `[!]`.

## 📍 Onde retomar — em ordem

**1. Postar de verdade, uma vez** *(15 min, ~US$0,50)* ← **comece aqui**

```bash
cd ../bancada && git push origin main          # o bump dos actions
gh workflow run Veredito --repo luisfelp07/bancada \
  -f pr=https://github.com/luisfelp07/bancada/pull/1 -f top_n=3 -f postar=true
```

Depois **dispare de novo**. Se aparecer um segundo comentário em vez de o
primeiro ser atualizado, a marca invisível (`<!-- veredito:parecer -->`) não
está funcionando. Duas rodadas provam as duas metades: publicar e não empilhar.

**2. Atualizar a fila** *(30 min)* — `PROXIMOS_PASSOS.md` foi atualizado no
essencial, mas vale reler: partes dele são anteriores a esta sessão.
⚠️ **A cópia no vault (`Onde retomar.md`) diverge** e não é alcançável daqui.

**3. Fundir por CONSERTO, não por artefato** *(1 dia)* — os "3 achados" da
rodada 3 são **1 defeito** visto por três lentes, todos em `app/main.py:103-104`
com o mesmo conserto. A fusão que está na fila é por artefato, e a rodada
provou que não basta: são três arquivos de teste diferentes provando a mesma
invariante. Sem isso, todo PR com defeito real gera comentário que exagera 3×.

⚠️ Relacionado: a lente `performance` produziu um achado de **segurança** com
rótulo errado (`[ALTA] performance — "muda modelo de segurança sem compensação
em cache ou índice"`). Conteúdo certo, categoria absurda.

**4. Os outros três PRs da bancada** *(~US$1,50)* — a medição de 15/08 refeita
pela porta da frente. **O PR limpo é o que mais importa:** se ele condenar
alguma coisa, há falso positivo na Action, e isso é pior que tudo que foi
consertado hoje.

**5. Repo de demonstração público** *(1 dia)* — é o que converte, e o único
jeito de mostrar isto sem dar acesso à bancada privada.

## Mapa rápido do que é novo no código

```
veredito/comentario.py     monta o comentário de PR (marca, <details>, corte, legenda)
posta_parecer.py           CLI: dry-run por padrão, --postar comenta de verdade
veredito/config.py         RAIZ_DO_DESCRITOR (base) | RAIZ_DO_APP (head)
                           TEM_APP TEM_AUTH TEM_BANCO TEM_PROVA_DIFERENCIAL ALCANCA_BANCO
veredito/ferramentas.py    _marca_indisponivel, monta_os_dois, carimba_local
veredito/juiz.py           R0 ignora artefato indisponível; R3 lê só `erro`
veredito/entrada.py        Basic (não Bearer) no git fetch
.github/workflows/         hack2l: PR de terceiro (leitura+grep)
../bancada/.github/        bancada: caso completo, app de pé
```

> ⚠️ **O comentário do PR é para o AUTOR, que nunca ouviu falar do produto.**
> Isso desenhou o texto: uma linha de resumo, e a legenda das três palavras
> antes de usá-las — com `descartado` explicado como *"não é um problema no seu
> PR"*. Medido do jeito mais direto: o dono do projeto, olhando um parecer com
> "4 descartados", perguntou se aquilo era boa notícia.
