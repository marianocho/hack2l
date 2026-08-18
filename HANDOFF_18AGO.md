<!-- tag: hack2l -->

# Handoff — 18/08/2026

> **Leia primeiro:** `CLAUDE.md` (produto) e `../CLAUDE.md` (máquina) carregam
> sozinhos. `PROXIMOS_PASSOS.md` é a fila viva. Este arquivo é o **delta** da
> sessão de 17–18/08 e diz exatamente onde retomar.
>
> O handoff anterior (`HANDOFF_17AGO.md`) continua válido como registro da
> decisão sobre a R3. As duas partes dele foram feitas.

## Estado verificado

**600 testes verdes** (`py -3.12 -m pytest -q`, ~95s, com Docker e o app do
desafio de pé). Sem Docker, use `-m "not lento"` — 6 testes são deselecionados.

`main == origin/main` nos dois repos. ✅ O commit local da bancada (o bump dos
actions, `3105b95`) foi enviado em 18/08 à tarde.

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

## ✅ A ÚLTIMA MILHA FECHOU — 18/08, à tarde

*(Esta seção dizia "o código que POSTA nunca executou". Executou.)*

Duas rodadas da Action contra `luisfelp07/bancada#1`, as duas com
`postar=true`:

| | rodada 1 | rodada 2 |
|---|---|---|
| o passo disse | `criado:` | `atualizado:` |
| comentários no PR **depois** | 1 | **1** |
| id | 5333006742 | **5333006742** — o mesmo |
| corpo | 5683 car. | 5590 car. — trocado |
| duração | 3m07s | 3m13s |

**Publica e não empilha**, as duas metades. E a conferência foi a API
(`gh api repos/luisfelp07/bancada/issues/1/comments`), **não** a linha que o
nosso próprio script imprimiu: `criado:`/`atualizado:` é autodeclaração do
código sob teste. Mesma distinção da R0 — quem decide é o fato externo.

### E a última milha ganhou trava antes de rodar

14 testes em `tests/test_posta_o_parecer.py`, cinco violações injetadas, cada
`raise_for_status` removido individualmente derrubando **exatamente um** teste.

🚨 **A quarta injeção cobrou o preço de sempre.** O teste da recusa afirmava que
um 403 no POST sobe em vez de virar "postado". Apaguei o `raise_for_status()`
do POST e a suíte ficou **verde, 12 de 12**: o dublê de GitHub tinha um status
só, então com 403 em tudo quem levantava era o `raise_for_status` do **GET**
dentro de `acha_o_nosso`. O teste observava a exceção certa vindo do lugar
errado.

> **Teste que acusa a coisa errada não vale mais que teste que não acusa nada.**
> O `CLAUDE.md` já dizia. Escrevi o teste, confiei nele, e a injeção desmentiu —
> dentro do teste escrito justamente para a peça sem trava.

`status_leitura` e `status_escrita` são separados agora, e são três testes:
recusa no LISTAR, no CRIAR e no ATUALIZAR.

Suíte: **577 verdes** (eram 563) — e **600** depois da fusão, abaixo.

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

~~**1. Postar de verdade**~~ ✅ **FEITO** — ver a seção acima. As duas rodadas,
`criado:` e `atualizado:`, um comentário só no PR.

~~**2. Atualizar a fila**~~ ✅ `PROXIMOS_PASSOS.md` registra que o bloqueador
"não tem onde entregar" caiu, e sobrou um.
⚠️ **A cópia no vault (`Onde retomar.md`) diverge** e não é alcançável daqui.

~~**1. Fundir por CONSERTO**~~ ✅ **FEITO em 18/08** — `veredito/fusao.py`.
As duas rodadas de 18/08 saíam com *"3 achados com evidência"* para **um**
defeito; agora saem com **1**, e as três provas continuam no bloco.

**A leitura literal de "fundir por conserto" repetiria o bug.** Os três
consertos da rodada 1 dizem a mesma coisa em três redações — casar essa string
falha exatamente como a chave do árbitro falhava. Os dois **fatos** embaixo das
redações são: mesmo arquivo em linhas vizinhas, e mesma **procedência**.

> **Procedência é fato do repositório; a paráfrase da regra e do conserto é
> opinião do modelo. A chave se constrói do fato.**

Mora **depois** do laço caro, de propósito: fundir antes do advogado
economizaria dinheiro (3 vagas → 1), mas ali uma fusão errada custa uma
*verificação*. Na apresentação, fundir errado não esconde prova nenhuma.
⚠️ A chave de `promotores.deduplica` **continua rígida** e é um item em aberto —
medí-la é o que economizaria API de verdade.

Reusa `_faixa` / `TOLERANCIA_LINHAS` / `LARGURA_MAX_PARA_CORROBORAR` de
`fontes.py`, já calibrados contra este mesmo fenômeno.

⚠️ **Ainda em aberto, medido em duas amostras:** a lente `performance` produziu
um achado de **segurança** com rótulo errado na rodada 1 e **não** na rodada 2.
Conteúdo certo, categoria absurda, e **não determinístico**. A fusão esconde o
sintoma no cabeçalho (o grupo assume o rótulo da lente líder) mas não resolve.

⚠️ **A composição ainda muda entre rodadas:** mesmo PR, mesmo commit, mesmas 12
suspeitas, trio condenado diferente. A fusão faz as duas rodadas convergirem no
mesmo *achado*, mas as acusações que chegam ao advogado seguem variando.

**2. Os outros três PRs da bancada** *(~US$1,50)* — a medição de 15/08 refeita
pela porta da frente. **O PR limpo é o que mais importa:** se ele condenar
alguma coisa, há falso positivo na Action, e isso é pior que tudo que foi
consertado hoje.

**3. Repo de demonstração público** *(1 dia)* — é o que converte, e o único
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
