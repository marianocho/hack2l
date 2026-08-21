<!-- tag: hack2l -->

# Trilhas até 01/09/2026 — cinco sessões em paralelo

> Escrito em 20/08/2026. **Este arquivo é o contrato entre as sessões**, não a
> fila. A fila viva continua sendo `PROXIMOS_PASSOS.md`, e ela tem **um único
> escritor** — ver o protocolo abaixo. Cada trilha escreve no handoff dela.
>
> 🚫 **Não existe cópia deste arquivo em lugar nenhum.** Se quiser um resumo
> para mandar ao Mariano, gere na hora a partir daqui — duas fontes para a mesma
> informação divergem em silêncio, e isso já custou oito dias no vault.

---

## 🆕 Estado em 20/08, fim do dia — leia antes de pegar uma trilha

**As cinco rodaram no mesmo dia, todas entregaram, todas com US$ 0,00 de API.**
Os cinco ramos estão mergeados no `main` (`4f984e5`) e empurrados; a suíte fechou
**836 verdes** depois do merge, com os quatro arnesses de mutação rodados sobre o
resultado.

| item | estado |
|---|---|
| ranking #4 — repo de demonstração | ✅ `luisfelp07/veredito-demo`, público, 2 PRs, 2 pareceres publicados. **O PR limpo saiu limpo** |
| T1 item 1 — os sete defeitos do parecer | ✅ ⚠️ no código, **não no ar** — só uma execução nova substitui o comentário publicado |
| T3 item 1 — corrida do bind-mount | ✅ rotulada |
| T3 item 5 — escala | ✅ degrada rotulada. Aberto: ler centrado na linha |
| T5 item 1 — a demo | ✅ · T5 item 3 — a régua | pronta para disparar, **US$ 0,00 gastos** |
| T4 — a narrativa | ✅ `NARRATIVA.md` no `main`, e o link do rodapé destravado |
| ranking #2 — a primeira chamada real no Bedrock | 🔶 o **caminho de recusa** rodou e funcionou; o caminho feliz continua sem nunca ter rodado |

🚨 **Dois bloqueios novos, e nenhum é de código nosso:**

1. **O saldo da conta Anthropic esgotou.** `sonda_api()` devolve *"SALDO
   esgotado -- a chave esta ok"*. Barra a não-determinância (T3, ~US$7), a régua
   (T5, ~US$13), a paridade (T2) e o `gh run rerun` que trocaria o parecer da
   vitrine. **Toda trilha que gasta está parada até recarregar.**
2. **Não há credencial AWS nesta máquina** — conferido em quatro lugares. O
   `medir_bedrock.py` está pronto e custa ~US$0,01; é a primeira coisa a rodar
   quando a credencial existir, **antes** de gastar a tarde.

⚠️ E o item que a T2 não podia consertar: `orquestrador.py:253` barra rodada em
crédito puro da AWS com um `if not cfg.ANTHROPIC_API_KEY` incondicional. Está na
fila, na seção de 20/08.

---

## O ranking honesto — onde o SEU tempo (não o dos chats) vale mais

Chat é barato e paralelo; a sua atenção não é. Em ordem de retorno:

| # | onde | por que |
|---|---|---|
| 1 | **Taxa de aceitação** | de cada achado postado, qual fração o autor conserta. A própria fila chama isso de *"a métrica que prova a tese"*, e hoje ela tem **zero medições**. Tudo que temos é gabarito nosso, em repositório nosso |
| 2 | **A primeira chamada real no Bedrock** | o `motor.py` está **exatamente** onde o `posta_parecer.py` estava em 18/08: coberto de teste com dublê, **nunca executado**. Naquele dia a primeira execução real quebrou em quatro lugares. Não há motivo para esta ser diferente |
| 3 | **O bloco ```suggestion no comentário** | é a alavanca de conversão mais barata que existe, e é ela que **produz** o número do item 1 — "Commit suggestion" é um clique registrável |
| 4 | ✅ **Repo de demonstração público** *(feito em 20/08)* | sem ele nada disto era mostrável: a bancada é privada, e o 404 do GitHub **mente** ("not found" se lê como "não existe"). `luisfelp07/veredito-demo` |

### E duas coisas para NÃO fazer

🚫 **Não mova a CI para a AWS.** O argumento central do produto é que o código do
cliente **não sai da casa dele** — é o que o comentário no topo do workflow diz,
e é o que vende para quem mais precisa. Runner na nossa infra destrói esse
argumento e ainda passa a custar dinheiro. O crédito da AWS deve comprar **uma
coisa só: inferência via Bedrock**. Action continua no GitHub, de graça em repo
público.

🚫 **Não construa a síntese em linguagem natural do juiz** (`MODEL_JUIZ`, item
aberto em D). O juiz ser determinístico — milissegundos, sem rede, com teste — é
argumento de venda. Enfiar um modelo ali troca a única peça auditável do
pipeline por opinião.

---

## Onde eu discordo de você: o parecer

**Você está meio certo.** O comentário publicado no `bancada#1` tem **5.590
caracteres** — isso não é grande; o CodeRabbit posta muito mais. O problema não é
tamanho: é que **os primeiros vinte segundos de leitura entregam software
quebrado**. Os sete defeitos, todos verificáveis no comentário que está no ar:

| # | o que o autor vê | por que dói |
|---|---|---|
| 1 | *"1 achado(s) com evidencia"* — **sem acento no nosso texto, com acento no texto do modelo**, na mesma tela | a restrição do `print()` em console cp1252 vazou para a superfície que o cliente lê, onde ela não vale. Padrão de bug da casa: regra aplicada onde não é o caso |
| 2 | `achado(s)`, `suspeita(s)` | plural de formulário. Custa uma função de quatro linhas |
| 3 | `[ALTA] [alta]` | severidade e confiança renderizadas como duas etiquetas quase idênticas. Lê como bug |
| 4 | `O QUE:` `ARBITRO:` `EVIDENCIA:` em caixa alta | formato de terminal despejado dentro de markdown. Nenhum título, nenhum negrito estrutural |
| 5 | `app/main.py:103-106` | **não é link.** O autor tem a linha exata e precisa procurar à mão. Permalink do GitHub é uma f-string |
| 6 | `Artefato: artefatos/prova_correcao_01.json` | **caminho morto.** O autor não tem esse arquivo. E o workflow **já** sobe `saidas/rodadas/` com `upload-artifact` — a URL existe e não é usada |
| 7 | oito itens em "levantadas e não testadas", **todos no mesmo `app/main.py:97-108`** | a fusão de 18/08 foi aplicada aos **condenados** e não à fila. O cabeçalho diz "1 achado" e logo abaixo o autor lê oito suspeitas sobre as mesmas linhas. É a inflação de acusação que a fusão existe para matar, sobrevivendo do outro lado da mesma tela |

### O que NÃO encurtar

🚨 **As listas de descartados e inconclusivos ficam.** São a peça que nenhum
concorrente entrega, e já estão colapsadas em `<details>`. Encurtar ali é jogar
fora o diferencial para resolver um problema que não é de tamanho.

### "Assim do jeito que tá é melhor aos devs?" — não

Dev não quer mais prosa nem menos prosa. Dev quer **o achado na linha do diff**,
**o conserto como bloco clicável** e **a evidência a um clique**. Hoje o produto
tem os três e não entrega nenhum: o achado está num comentário solto, o conserto
é frase, e a evidência é um caminho de arquivo local.

O que o dev valoriza e o leigo não é exatamente o **artefato** — e é justo ele
que hoje está morto no texto.

---

## As cinco trilhas

### T1 — O parecer que o autor lê *(a trilha de UI)*

**Entrega:** o comentário de PR reescrito como markdown de verdade, e o
onboarding do cliente.

1. ✅ *(feito em 20/08)* Os sete defeitos da tabela acima, nesta ordem:
   1, 2, 3 → 5, 6 → 4 → 7. ⚠️ **No código, não no ar** — o comentário publicado
   só muda com uma execução nova, e elas estão paradas por saldo.
2. **Bloco ` ```suggestion `** para o `CONSERTO SUGERIDO` quando o conserto é
   local e cabe em poucas linhas. Quando não cabe, texto — 🚫 nunca
   `suggestion` inventado, que quebra o build de quem clicar.
3. **Decidir MEDINDO:** comentário único (hoje) vs. review com comentários
   inline nas linhas. Inline converte mais e empilha se feito errado. Não
   decidir por gosto — postar dos dois jeitos no repo de demonstração e olhar.
4. **`veredito init`** — o detector de `veredito.yml` medido em 19/08 (12 dos 26
   campos saem de `compose`+`Dockerfile`, zero erro). Encolhe o onboarding para
   duas perguntas. 🚨 Os dois campos que sobram são justamente os que sustentam
   CRÍTICA: diga isso em voz alta na saída do comando, não silencie.

⚠️ Regra da trilha: **acento, plural e link são texto; nada aqui pode mudar o
que o pipeline decide.** Item que exija mudar regra do juiz vira PEDIDO para a
T3 — ver protocolo.

---

### T2 — AWS: da fiação ao primeiro parecer faturado no Bedrock

**Entrega:** uma rodada real, completa, paga com crédito da AWS, com o parecer
comparado lado a lado contra a API direta.

1. **Executar de verdade.** O `motor.py` nunca falou com a AWS. Rodar
   `VEREDITO_MOTOR=bedrock` contra o PR da bancada e ver o que quebra. Esperar
   que quebre.
2. 🚨 **`SEM_NO_BEDROCK` foi conferido na matriz de disponibilidade, não
   medido.** O comentário do próprio código diz isso com todas as letras —
   *"conferido contra a matriz... não de memória"* — o que é ler doc, e o
   `CLAUDE.md` inteiro é sobre a diferença. Mandar os dois parâmetros de
   propósito e registrar o 400 (ou a ausência dele) é meia hora, e transforma
   uma leitura em medição.
3. **Paridade de parecer.** Mesmo PR, mesmo commit, três motores, três pareceres
   no disco, `diff`. A pergunta é: *perder `task_budget` e `fallback_de_recusa`
   muda o VEREDITO, ou só o custo?* Ninguém sabe, e é o que decide se dá para
   rodar o produto inteiro em crédito.
4. **Habilitação de modelo no Bedrock** é por conta e por região, e o erro é um
   404 que se lê como "modelo não existe" — mesma classe de mentira do 404 do
   repo privado. Conferir antes de gastar a tarde.
5. **Custo:** crédito de Activate vale em Bedrock; a API direta da Anthropic não
   consome crédito AWS. Isso, e não elegância, é o motivo do motor existir.

⚠️ Só a T2 mexe em `config.py`. Todo mundo pede.

---

### T3 — Os bugs de hoje e os que a migração vai acordar

**Entrega:** o pipeline parando de produzir inconclusivo por culpa nossa, e a
não-determinância medida em vez de anedótica.

1. ✅ *(feito em 20/08, `c6e01cd`)* **A corrida do bind-mount** (diagnosticada
   em 19/08). Foi feita a
   **opção 2 da fila — rotular**: `ERROR: file or directory not found` com o
   arquivo presente no worktree vira `corrida_do_mount: true` no artefato.
   🚫 Não retry cego — esconderia o caso em que o arquivo realmente não foi
   gravado, que é defeito de verdade.
   ⚠️ A T3 produz **o campo**; quem desenha no parecer é a T1. Quem produz o
   dado não é quem o desenha.
2. **A lente `performance` emitindo achado de segurança com rótulo errado**, e
   **não determinístico** (aconteceu na rodada 1, não na 2). A fusão esconde o
   sintoma no cabeçalho e não resolve.
3. **Medir a não-determinância.** Mesmo PR, mesmo commit, cinco rodadas. Quanto
   o parecer varia? Bot que diz coisas diferentes sobre o mesmo commit perde a
   confiança do time em uma semana — e hoje sabemos que o trio condenado muda,
   sem saber quanto.
4. **A chave rígida do `promotores.deduplica`** — item aberto, já medido em
   `MEDICAO_CHAVE_PRE_ADVOGADO.md`. 🚫 **Não reconstruir sem ler aquele
   arquivo**: quatro ideias plausíveis já foram medidas e engavetadas.
5. ✅ *(feito em 20/08, `3a368bd`)* **Escala** (item E da fila): repositório
   grande derrubava a leitura, 220s por
   acusação no next.js. Não precisa resolver; precisa **falhar rotulado** em vez
   de morrer no timeout.

---

### T4 — A narrativa em português de gente

**Entrega:** um documento que um CTO, um investidor ou o pessoal do Activate
leem inteiro sem abrir código, mais o texto do site alinhado a ele.

Conteúdo: o que o produto faz · os melhores achados, com o do `bancada#1` por
extenso · os doze bugs de 18/08 e o que cada um ensinou · o árbitro chumbado (94
acusações citando critérios inventados) contado como a história de rigor que ela
é · o terceiro estado, explicado sem jargão.

🚨 **Toda cifra tem que vir de arquivo em `saidas/` ou de rodada medida.** Este
projeto já comemorou uma métrica que media contaminação, e documento de
marketing é onde essa classe de erro nasce. Número sem procedência não entra —
**regra sem procedência é opinião** vale para o nosso texto também.

🚫 **A T4 não abre `veredito/` para escrever.** Leitura à vontade, escrita
nenhuma.

---

### T5 — Vitrine e régua *(a trilha que eu acrescentei)*

**Entrega:** o repo de demonstração público, e o primeiro número sobre o mundo
real.

1. ✅ *(feito em 20/08)* **O repo de demonstração** — `luisfelp07/veredito-demo`.
   Público,
   pequeno, com `veredito.yml` na raiz e o workflow. 🚨 **O PR limpo é o que mais
   importa** — a bancada acabou de mostrar por quê: `pr/contagem-de-tarefas`
   levantou cinco suspeitas e derrubou as cinco. Falso positivo é pior que
   defeito não achado: o autor que recebe acusação falsa desinstala e não volta.
   🚫 O gabarito **não mora lá dentro** — os promotores leem o repo.
2. **O canário de egresso** vai junto: a contenção de rede é a única camada sem
   validação empírica em direção nenhuma, e o lugar de demonstrá-la é repo
   nosso e público. 🚫 Não detectando `smtplib` nem mantendo lista de API
   perigosa — isso é predição, e predição já perdeu duas vezes.
3. **A régua contra o mundo real:** rodar o Veredito em ~10 PRs **já mergeados**
   de repositórios públicos — metade com correção de bug conhecida (o PR que
   conserta é o gabarito, invertido), metade rotina. Contar: quantos condenados,
   quantos descartados com motivo, quantos inconclusivos e por quê. A ~US$1,40
   por PR isso custa **~US$15** e produz o único número que hoje não temos: como
   o produto se comporta em código que não é nosso.
   ⚠️ Pontuar **pelo parecer**, nunca por `veredictos.json` — em 18/08 a régua
   teria comemorado 1 de 1 com o parecer dando o defeito por inexistente.

---

## O protocolo — como cinco sessões não se atropelam

### 1. Um dono por arquivo. Sem exceção.

| arquivo / área | dono | quem mais vai querer |
|---|---|---|
| `veredito/comentario.py` | **T1** | — |
| `veredito/juiz.py` — **render** (`bloco_*`, `_secao_*`, `organiza`) | **T1** | T3 |
| `veredito/juiz.py` — **regras** (`aplica_regras`, R0–R4) | **T3** | T1 |
| `veredito/fusao.py`, `veredito/prova_de_fusao.py` | **T1** | T3 |
| `posta_parecer.py`, `revisa_pr.py` | **T1** | T2 |
| `veredito/motor.py`, `veredito/advogado.py`, `veredito/config.py` | **T2** | todos |
| `.github/workflows/` | **T2** | T5 |
| `veredito/ferramentas.py`, `veredito/promotores.py`, `promotores/*.md` | **T3** | T2 |
| `site/`, arquivos `.md` novos de narrativa | **T4** | — |
| repo de demonstração (repositório novo) | **T5** | — |
| `tests/test_<novo>.py` | quem criou | — |
| **`PROXIMOS_PASSOS.md`, os dois `CLAUDE.md`** | 🚨 **só a sessão principal** | todos |

**Precisou de arquivo que não é seu? Não edite.** Escreva na seção `## PEDIDOS`
do seu `HANDOFF_20AGO_T<n>.md`, com o arquivo, a linha e o que precisa. O dono
lê, faz, e responde no handoff dele.

### 2. Quando o encontro é inevitável: **comportamento vai antes de texto**

Quem muda **o que o pipeline produz** vai primeiro. Quem **desenha** rebasa
depois. Motivo: renderização se adapta barato a um campo novo; lógica reescrita
depois de o texto estar pronto quebra o texto e o teste dele.

Aplicado ao caso concreto que já existe: a T3 produz `corrida_do_mount` no
artefato e para. A T1 desenha. As duas trilhas tocam o mesmo parecer, e nenhuma
toca o mesmo arquivo.

### 3. Ramo por trilha — e **worktree** por trilha, que é o que faltava aqui

```bash
py -3.12 scripts/worktree_de_trilha.py t1-parecer
```

`t1-parecer`, `t2-aws`, `t3-bugs`, `t4-narrativa`, `t5-vitrine`.
`git pull --rebase origin main` antes de qualquer commit; merge para `main` no
fim de cada bloco de trabalho. ⚠️ Acumular três dias de ramo transforma conflito
de arquivo em conflito de arquitetura.

🆕 **Primeira emenda ao protocolo (20/08).** A versão original mandava
`git checkout -b tN origin/main` e **assumia, sem dizer, um checkout por
sessão** — que não é o que existe. O que aconteceu no primeiro dia: a T2 viu
`veredito/juiz.py` modificado e um `superficie.py` novo que não eram dela, e dois
comandos depois os arquivos sumiram e o `HEAD` estava em outro ramo. Era a T1
trabalhando no mesmo diretório. **A tabela de propriedade por arquivo não protege
disso, porque a colisão é do checkout, um nível abaixo.**

⚠️ E enquanto o diretório era compartilhado, **`git status` e a suíte não eram
evidência sobre o próprio trabalho.** Conferir contra o hash do blob, não contra
a árvore.

🚫 **Não use `git worktree add` cru** — o `.env` está no `.gitignore` e não vai
junto, e `CHALLENGE_REPO=../desafio` é relativo. A worktree nasce caindo em todos
os padrões do código, e o erro **se anuncia como defeito do produto**
(`RuntimeError: ref nao encontrada no repo do desafio: main`). Custou seis
vermelhos a três sessões, cada uma diagnosticando do zero. O script resolve os
dois, e deriva a raiz do git em vez de supor o layout.

🚫 **Não use `git stash` enquanto o repo for compartilhado.** A pilha é do
**repositório**, não da worktree: um `pop` segundos depois trouxe o stash de
outra trilha, porque os índices `stash@{n}` mudam sob você. Para conferir uma
linha de base, use uma worktree descartável. Se precisar mesmo do stash, resolva
por SHA (`git stash list --format='%H %gs'`), **nunca por índice**.

🆕 **Segunda emenda: o vault espelha `main`, nunca um ramo de trilha.** Rodar
`sync_vault.py --sincronizar` de dentro de uma worktree publica o estado do ramo
como se fosse canônico. ⚠️ E a sincronia é repo → vault e só detecta
*diferente*, nunca *qual é mais novo*: se o vault estiver **à frente** — e já
esteve, com 176 linhas que não existiam em commit nenhum — sincronizar
**destrói** a versão nova. Confira o sentido antes de escrever.

### 4. 🚨 O Docker é recurso de UMA sessão por vez

Está **medido** que a corrida do bind-mount piora com mais containers disputando
a camada de compartilhamento de arquivos do Docker Desktop. Cinco sessões
rodando `pytest` com Docker ao mesmo tempo produzem inconclusivos espúrios que
ninguém vai conseguir reproduzir depois.

- Uma sessão de cada vez roda a suíte completa. **Anuncie no seu handoff quando
  pegar o Docker, e quando soltar.**
- As outras quatro rodam `py -3.12 -m pytest -q -m "not lento"` — seis testes
  são deselecionados.
- Antes de qualquer boot:
  `powershell -ExecutionPolicy Bypass -File hack2l\scripts\docker-up.ps1`

### 5. Dinheiro

Toda rodada que gasta API vai para o handoff da trilha **com o custo em
dólares**. Ordem de grandeza conhecida: US$1,38 por PR completo, US$0,071 por
acusação verificada. A T5 é a que mais gasta (~US$15 no total); T1 e T4
trabalham quase inteiras com `comentario.do_disco()` e o juiz lendo do disco,
**sem tocar em API**.

### 6. Toda guarda nova precisa ser vista falhando

Vale para as cinco trilhas, e não é formalidade: em 19/08 duas travas passaram
**verdes com o defeito presente**. A pergunta não é "passou?", é *"o que eu
quebro para ver este teste ficar vermelho, e é exatamente o defeito que ele
alega pegar?"*

---

## Os prompts de abertura

Um chat novo por trilha, em `C:\hack_agents\Hack2L`. Cole:

### T1
```
Leia hack2l/TRILHAS_ATE_01SET.md e assuma a trilha T1 (o parecer que o autor
le). Trabalhe so' nos arquivos da T1 na tabela de propriedade; o que precisar de
outra trilha vai para a secao PEDIDOS do seu handoff.
Ramo: t1-parecer. Handoff: hack2l/HANDOFF_20AGO_T1.md.
Comece pelo comentario real que esta no ar:
gh api repos/luisfelp07/bancada/issues/1/comments --jq '.[].body'
```

### T2
```
Leia hack2l/TRILHAS_ATE_01SET.md e assuma a trilha T2 (AWS/Bedrock). Trabalhe
so' nos arquivos da T2; o resto vai para PEDIDOS no seu handoff.
Ramo: t2-aws. Handoff: hack2l/HANDOFF_20AGO_T2.md.
Comece pelo item 2: SEM_NO_BEDROCK foi lido na matriz de disponibilidade e
nunca medido. Meca.
```

### T3
```
Leia hack2l/TRILHAS_ATE_01SET.md e assuma a trilha T3 (bugs). Trabalhe so' nos
arquivos da T3; o resto vai para PEDIDOS no seu handoff.
Ramo: t3-bugs. Handoff: hack2l/HANDOFF_20AGO_T3.md.
Comece pela corrida do bind-mount (PROXIMOS_PASSOS.md, secao D), opcao 2 --
rotular. Voce produz o campo no artefato e para; a T1 desenha.
```

### T4
```
Leia hack2l/TRILHAS_ATE_01SET.md e assuma a trilha T4 (narrativa nao tecnica).
Voce NAO escreve em veredito/ -- leitura a vontade, escrita nenhuma.
Ramo: t4-narrativa. Handoff: hack2l/HANDOFF_20AGO_T4.md.
Toda cifra precisa vir de arquivo em saidas/ ou de rodada medida. Numero sem
procedencia nao entra.
```

### T5
```
Leia hack2l/TRILHAS_ATE_01SET.md e assuma a trilha T5 (vitrine e regua).
Ramo: t5-vitrine. Handoff: hack2l/HANDOFF_20AGO_T5.md.
Comece pelo repo de demonstracao publico, e comece pelo PR LIMPO -- falso
positivo e' pior que defeito nao achado. O gabarito nao mora dentro dele.
```
