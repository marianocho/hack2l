# HANDOFF — T3 (bugs) — 20/08/2026

> Ramo `t3-bugs`. Trabalho em **worktree separada**, não no checkout compartilhado
> — ver "O ambiente compartilhado" abaixo, que é a parte deste handoff com maior
> chance de custar tempo a outra sessão.

**Docker: NÃO peguei.** Rodei só `py -3.12 -m pytest -q -m "not lento"`. O
recurso está livre para quem precisar. **Custo de API: US$0** — nada aqui tocou
em modelo.

---

## ✅ Feito: a corrida do bind-mount, ROTULADA

Item 1 da T3 / opção 2 da fila (seção D). Commit `c6e01cd`.

**O campo, no artefato da prova diferencial:**

```json
"corrida_do_mount": true,
"corrida_do_mount_detalhe": {
  "lado": "head",
  "alvo": "tests/test_selftest_nao.py",
  "no_disco": "C:\\...\\.worktrees\\head\\app\\api\\tests\\test_selftest_nao.py",
  "exit": 4,
  "detalhe": "corrida do bind-mount no head: o arquivo de teste esta gravado no
    worktree do host (...) e o container nao o enxergou (`file or directory not
    found: ...`, exit 4). O lado base rodou com o MESMO alvo, entao o caminho
    resolve dentro do container. Isto e' a camada de compartilhamento de
    arquivos do Docker no host -- NAO e' defeito do PR nem `veredito.yml`
    errado. A prova nao foi obtida e nada foi refutado; repetir a rodada com
    menos containers concorrentes tende a fechar."
}
```

`corrida_do_mount` **nasce `False` no molde do artefato**, inclusive nas saídas
que voltam cedo (`indisponivel`, recusa do código, canário morto, exceção). Ali
a causa já tem nome, e `False` significa *"não atribuído à corrida"*, nunca
*"não olhei"*. Chave que some é o dedup de novo — esta não some.

### 🚫 O que NÃO mudou, de propósito

- **O veredito.** Exit 4 não produz linha de resumo ⇒ `rodou_<lado>` False ⇒
  `erro` preenchido ⇒ R3 ⇒ INCONCLUSIVO. Continua exatamente assim. A opção 2
  **não evita** o inconclusivo, e a fila já dizia isso.
- **O `erro`.** Continua preenchido — é ele que faz a R3 converter. Só o **texto**
  mudou: de `"pytest nao executou no head (exit 4 veio do docker)"`, que se lê
  como culpa do repositório revisado, para a causa medida, que é nossa. A saída
  crua do container continua anexada: rótulo não substitui evidência.
- **Nenhum arquivo de outra trilha.** `juiz.py`, `comentario.py`, `fusao.py`,
  `config.py` — nada tocado.

### 🚨 O critério que impede o rótulo de mentir

`ERROR: file or directory not found` é **também** a assinatura exata de
`codigo.testes` apontando para fora do que `codigo.montagens` monta — o item 3
das cinco suposições chumbadas que o `pallets/flask` expôs em 17/08. Nesse caso
o arquivo **também** está no worktree do host, e a frase é a mesma palavra por
palavra. Rotular isso como corrida mandaria o operador culpar o Docker Desktop
por um `veredito.yml` torto.

O que separa os dois: **config errada falha nos DOIS lados, sempre; corrida
falha em UM.** Daí o critério ser *"o OUTRO lado rodou com o mesmo alvo"* — se
rodou, o caminho resolve dentro do container, logo a queda é do host.

### A guarda foi vista falhando — e a primeira versão do arnês mentiu

`tests/mutacao_corrida_do_mount.py` (roda à mão, não é coletado):

```bash
py -3.12 tests/mutacao_corrida_do_mount.py
```

| mutação injetada | travas que morreram |
|---|---|
| o ingênuo: rotular o lado que falhou sem exigir que o outro tenha rodado | `test_os_dois_lados_negando_o_alvo_NAO_e_corrida` + `test_o_outro_lado_tambem_mudo_NAO_e_corrida` |
| sem conferir que o arquivo está em disco no host | `test_arquivo_ausente_no_worktree_NAO_e_corrida` + o unitário |
| casando a frase solta em vez do alvo exato | `test_not_found_de_OUTRO_caminho_NAO_e_corrida` + o unitário |
| "rotulou, logo não é erro" (a R3 pararia de converter) | `test_o_rotulo_nao_muda_o_veredito_nem_afrouxa_a_R3` + `test_rotulada_*` |

Quatro mutações, quatro conjuntos exatos. **12 travas, todas verdes.**

🚨 **Duas coisas só apareceram rodando a mutação, e as duas são do padrão de bug:**

1. **A primeira rodada do arnês MENTIU.** Três mutações tinham indentação
   errada, o módulo mutado não compilava, o pytest reportava `ERROR` (não
   `FAILED`), e o arnês lia isso como *"nenhuma trava pega"* — ou seja, **acusava
   as travas de fracas por um defeito dele**. É a variação de 19/08 (`replace`
   que vira no-op) com outra cara. O arnês agora casa **linha inteira** — a
   substring `art["erro"] = (` casava duas indentações diferentes — e **levanta**
   se o mutado não compilar.
2. **Uma das minhas duas condições era DECORAÇÃO.** A versão original tinha
   `len(suspeitos) != 1` *e* `o outro lado rodou`. Com dois lados suspeitos,
   nenhum "outro" produziu resumo, então o segundo filtro já esvaziava a lista:
   **não existia violação que deixasse a primeira vermelha sozinha.** Guarda que
   não pode ser vista falhando não é guarda. Virou um critério só.

---

## ✅ Feito: a escala, ROTULADA (item 5 / item E da fila)

Commit `3a368bd`. Medido no `next.js`: ~220s por acusação contra ~30s nos
outros, **6 de 8 inconclusivos** — *"quando a fatia não cabe, ele não degrada
para 'não sei' com elegância: gasta 220s e aí diz não sei"*.

### O quarto sinal: `parcial`

Entra ao lado de `ok` / `erro` / `indisponivel` no registro de cada chamada, e é
**ortogonal aos três**: a chamada deu certo e a ferramenta existe — ela olhou um
pedaço.

```python
ferramentas.leitura_parcial_da_acusacao("correcao_01")
# ['read_file: app/main.py tem 4200 linhas e nao coube: o corte deixou o FIM ...',
#  'grep: /session/ parou no teto de 200 resultados: ha mais ocorrencias ...']
```

🚫 **`parcial` NUNCA vira `erro`.** Marcar assim faria a R3 converter em
INCONCLUSIVO **toda refutação obtida em repositório grande** — é o erro de 17/08
(`indisponivel` contado como erro no `pallets/flask`) reentrando pela porta do
**tamanho** do repo. `test_parcial_NUNCA_vira_erro` é a trava dessa ponta.

Três fatias passam a ser ditas: arquivo cortado no `CORTE_SAIDA`, grep parado no
teto de achados, arquivo pulado por convenção de segredo.

### 🚨 E o achado que não era o item da fila

O resgate por sufixo do `_resolve_caminho` era **ilimitado e não podava nada**.
`rglob` anda a árvore inteira por dentro — `node_modules`, `.next`, `.git` — a
cada `read_file` que erra a raiz, **que é o caso comum** (29 acusações disseram
`app/routers/shares.py` e 20 disseram `app/api/app/routers/shares.py` para o
mesmo arquivo). O `_grep` sempre honrou `_IGNORA`; este caminho não, e a
assimetria não tinha motivo.

**O pior não era o tempo, era a mentira no fim dele.** Sem alvo, o `read_file`
respondia *"não existe em head"*. Num repositório grande isso é **falso** — o
arquivo pode muito bem estar lá, nós só paramos de procurar. O advogado que lê
"não existe" refuta a acusação em cima disso, e absolvição falsa é o desfecho
que este produto existe para impedir. Agora quem desiste **diz que desistiu**,
com frase diferente da de ausência.

E a poda não é só tempo: com uma cópia vendorizada casando o **mesmo sufixo**, o
resgate ficava ambíguo (`len(casam) != 1`) e devolvia `None` — um arquivo que
**existe** passava a "não existir" porque alguém vendorizou uma cópia.

**Medido** (resgate por chamada, árvore sintética com `node_modules`):

| arquivos | antes (`rglob`) | agora (`os.walk` podado) |
|---|---|---|
| 2.001 | 0,025s | ~0s |
| 10.001 | 0,116s | ~0s |
| 40.001 | 0,501s | ~0s |

⚠️ **Isto não é "220s → 0s", e não vou dizer que é.** O que foi medido é o
resgate, numa árvore sintética. Os 220s do `next.js` incluem latência de modelo
e muito mais; o `next.js` real é bem maior que 40 mil arquivos com
`node_modules` instalado, então extrapolar é plausível e **não foi medido**.

### A guarda foi vista falhando

```bash
py -3.12 tests/mutacao_leitura_parcial.py
```

6 mutações, cada uma matando exatamente o conjunto que alega prender; 13 travas.
**Duas lições novas do arnês, as duas registradas dentro dele:**

1. Mutação que troca o **nome** de uma função levanta `NameError`: as travas
   certas ficam vermelhas **pela causa errada**, e o arnês daria OK. É o defeito
   de 19/08 outra vez. O `ast.parse` não pega — nome indefinido só explode em
   execução. O arnês agora levanta ao ver `NameError`/`ImportError`/etc., e a
   mutação usa `False and f(...)`, que curto-circuita sem quebrar o módulo.
2. **Minha previsão estava errada** numa das seis: eu disse que remover
   `_marca_parcial` do corte mataria uma trava, e mata **três** — as outras duas
   montam o cenário delas com um arquivo cortado. O arnês reprovou a previsão, e
   é exatamente para isso que se prevê antes.

⚠️ **Uma coisa que eu NÃO provei, e não vou alegar:** o `_PARCIAL_DA_CHAMADA.clear()`
dentro do `_fecha_chamada` é redundante — o `_abre_chamada` já limpa, e nenhuma
violação o deixa vermelho sozinho. Mantive por simetria com os dois irmãos
(`_FALHA_*`, `_INDISPONIVEL_*`, que limpam nas duas pontas pelo motivo
documentado lá), mas pela régua da casa ele é decoração até alguém achar o caso
que o exercita.

---

## 📋 PEDIDOS

### Para a T1 — desenhar o campo (é o encontro previsto no protocolo)

`corrida_do_mount` / `corrida_do_mount_detalhe` estão no artefato e prontos. O
dado existe; **quem desenha é você**. Duas coisas que valem no parecer:

1. O inconclusivo dessa causa **não é do PR** — hoje ele entra na lista de
   inconclusivos indistinguível de um limite do código revisado. Vale uma marca
   visual separando *"não conseguimos medir, e a culpa é da nossa bancada"* de
   *"medimos e não deu para concluir"*.
2. `detalhe` já vem redigido para leitura humana e termina dizendo o que fazer
   (repetir com menos containers). Se preferir redigir do seu lado, use os
   campos estruturados (`lado`, `alvo`, `no_disco`, `exit`) — são fato, não
   paráfrase.

⚠️ Nada disso muda regra do juiz. Se você precisar que mude, volta para mim.

**E o segundo campo, da escala:** `ferramentas.leitura_parcial_da_acusacao(id)`
devolve a lista do que aquela acusação **não conseguiu olhar**. Mesma tese do
`corrida_do_mount`: um INCONCLUSIVO por teto nosso não é um INCONCLUSIVO sobre o
PR do autor, e hoje o parecer não distingue os dois. Sugestão (sua a decisão):
uma linha na lista de inconclusivos dizendo *"a perícia trabalhou sobre uma
visão parcial do repositório"* com os itens.

⚠️ Lista vazia significa *"leu inteiro tudo que pediu"*, **não** *"leu tudo que
existe"* — o advogado pode simplesmente não ter pedido, e isso não aparece aqui.
Não renderize como cobertura.

### Para a T2 (dona do `config.py`)

`_teto_da_varredura()` mora em `ferramentas.py` com `VEREDITO_TETO_VARREDURA` e
padrão 20000, lido **em execução**. Deveria estar no `config.py` junto com
`CORTE_SAIDA` e os `TIMEOUT_*` — não pus lá para não colidir com você. Mova
quando estiver com o arquivo na mão; a função é o único ponto de leitura.

### Para a sessão principal (dona de `PROXIMOS_PASSOS.md` e dos dois `CLAUDE.md`)

1. **Seção D, "A corrida do bind-mount":** a opção 2 está feita. A opção 1
   (conferir visibilidade antes de rodar, +1 container por prova) **continua
   aberta e não recomendada por enquanto** — o rótulo custa zero no caminho
   quente e a falha já é para o lado seguro.
2. **Item E, "Escala":** deixou de ser só "não sabemos ainda". A leitura agora
   degrada rotulada, e o resgate ilimitado do `_resolve_caminho` — que ninguém
   tinha olhado — era metade do problema. O que **continua aberto** é ler
   centrado na linha da acusação: hoje `_corta` fica com o **fim** do arquivo, e
   a acusação quase sempre aponta para o começo. Isso é conserto, não rótulo, e
   é o próximo passo óbvio dali.
3. **Padrão de bug, quatro linhas novas** — as duas do bloco da corrida mais:
   - **o resgate por sufixo que mentia no fim:** `_grep` honrava `_IGNORA` e
     `_resolve_caminho` não. A mesma pergunta feita a duas funções irmãs recebia
     tratamento diferente, e a que não podava terminava afirmando *"não existe"*
     sobre um arquivo que existe. É o primo do "meio-nu não é nu": **duas portas
     para o mesmo repositório, com regras diferentes.**
   - **a mutação que mata a trava certa pela causa errada:** trocar o nome de
     uma função dá `NameError`; as travas ficam vermelhas e o arnês diz OK. O
     `ast.parse` não alcança. Terceira variação de *"mutação que não mede o que
     alega"* em dois dias.
4. **`test_sync_vault.py::test_o_vault_desta_maquina_esta_em_dia` ficou vermelho
   durante a sessão** — o espelho diverge em `PROXIMOS_PASSOS.md`. Não é meu (só
   toquei `veredito/ferramentas.py`) e **não sincronizei de propósito**: minha
   cópia do arquivo é a de `04fb1d7` e sincronizar a partir daqui sobrescreveria
   o que você escreveu. É seu, e é a trava funcionando.

### Para quem for mexer em `veredito/advogado.py` (T2)

`_formata_prova` passou a emitir, quando há corrida:

```
CORRIDA DO BIND-MOUNT (infraestrutura do host, nao o PR): ...
O teste nao tem defeito: NAO o reescreva por causa disto.
```

É texto **para o modelo**, não para o parecer — sem ele o advogado lê
`file or directory not found`, conclui que errou o teste, e gasta voltas do loop
reescrevendo um teste que está certo.

---

## ⚠️ Achados sobre o ambiente compartilhado — leiam antes de trabalhar

### 1. Os cinco chats compartilham UM checkout, e isso já mordeu

Abri a sessão com o repo em `t2-aws` (a T2 tinha trocado o ramo do checkout
compartilhado). **`git checkout -b t3-bugs` teria arrancado a árvore debaixo da
T2 no meio do trabalho dela.** Por isso a T3 trabalha numa worktree:

```
C:\hack_agents\Hack2L\.worktrees-trilhas\t3-bugs
```

Nome distinto de propósito: `.worktrees` e `.worktrees-bancada` são do harness
(`WORKTREES_DIR`, e o `roda_bancada.py`), e levam `git worktree prune`.

**Sugestão para as outras trilhas: façam o mesmo.** `git worktree add` é barato e
o protocolo do `TRILHAS_ATE_01SET.md` ("ramo por trilha") assume implicitamente
um checkout por sessão, que não é o que existe.

### 2. 🚨 `git stash` é do REPOSITÓRIO, não da worktree — e eu paguei por isso

Dei `git stash push` para conferir a linha de base, e o `git stash pop` de
segundos depois **trouxe o stash da T1** (`t1: superficie + juiz em campos`),
porque ela empilhou o dela no meio. A pilha é global; os índices `stash@{n}`
mudam sob você.

Nada foi perdido — a entrada da T1 foi restaurada por SHA com `git stash store`,
e o trabalho dela está intacto. Mas o modo de falha é silencioso e a recuperação
depende de o SHA ainda estar na tela.

🚫 **Enquanto as cinco sessões dividirem o repo: não usem `git stash`.** Para
conferir uma linha de base, use uma worktree descartável:

```bash
git worktree add --detach /c/hack_agents/Hack2L/.worktrees-trilhas/base <commit>
```

E se precisarem mesmo do stash, **nunca por índice** — resolvam por mensagem ou
SHA primeiro (`git stash list --format='%H %gs'`).

### 3. O ramo `main` não tem o trabalho de 19/08

O protocolo manda `git checkout -b t3-bugs origin/main`. **Não dá:**
`origin/main` = `main` = `ec109a5`, que **não contém** `TRILHAS_ATE_01SET.md`,
`veredito/motor.py`, o canário das montagens nem o `senha_em`. O merge do
trabalho de 19/08 está em `04fb1d7`, criado localmente pela T2 e apontado
**pelo ramo `t2-aws`**, não por `main`.

`t3-bugs` saiu de `04fb1d7`. **Alguém precisa decidir se `04fb1d7` vira `main`
de verdade** (e empurrar), senão cada trilha escolhe uma base diferente e o
merge de 01/09 vira conflito de arquitetura — exatamente o que o protocolo diz
para evitar.

### 4. Seis testes já estavam vermelhos ANTES de eu tocar em nada

Conferido: guardei minhas mudanças e rodei a suíte no `04fb1d7` puro — **as
mesmas seis**, idênticas.

```
tests/test_advogado.py::test_sonda_distingue_chave_de_saldo
tests/test_advogado.py::test_sonda_gasta_um_token_so
tests/test_contencao_app.py::test_a_copia_nunca_escreve_no_banco_de_origem
tests/test_efeito_nao_medido.py::test_psql_usa_as_credenciais_do_projeto_e_nao_as_do_desafio
tests/test_ferramentas.py::test_base_e_o_pai_do_pr_nao_a_ponta_da_main
tests/test_fusao_provada_no_parecer.py::test_o_caminho_FELIZ_chega_ao_fim_sem_erro_de_encanamento
```

Com o meu trabalho: **784 passed, 6 failed, 10 skipped, 6 deselected** (eram 772
passed + as 12 travas novas). Não investiguei — não são da T3 e não quis mexer
em arquivo de outra trilha. Mas **suíte que já está vermelha é onde regressão se
esconde**, e são cinco sessões commitando: vale alguém adotar.

---

## Fila da T3 — o que sobra

| # | item | estado |
|---|---|---|
| 1 | corrida do bind-mount, rotular | ✅ `c6e01cd` |
| 5 | escala: falhar **rotulado** em vez de morrer no timeout | ✅ `3a368bd` |
| 2 | lente `performance` emitindo achado de segurança com rótulo errado, não determinístico | aberto |
| 3 | medir a não-determinância (mesmo PR, mesmo commit, 5 rodadas) | aberto — **precisa do Docker e de API**, ~US$7 |
| 4 | chave rígida do `promotores.deduplica` | aberto — 🚫 **ler `MEDICAO_CHAVE_PRE_ADVOGADO.md` antes**, quatro ideias plausíveis já foram medidas e engavetadas |

**Onde eu retomaria:** o **item 3**, e ele destrava o 2. Hoje sabemos que o trio
condenado muda entre rodadas e não sabemos *quanto* — e o item 2 (a lente
`performance` com rótulo errado, que aconteceu na rodada 1 e não na 2) é um caso
particular disso. Medir primeiro evita caçar um sintoma que talvez nem reproduza.

⚠️ É o primeiro item da T3 que **gasta**: 5 rodadas × ~US$1,38 ≈ **US$7**, e
**precisa do Docker exclusivo** — anuncie aqui ao pegar. Se o Docker estiver
ocupado, o item 4 é o único que anda sem ele (é leitura + medição em cima de
`MEDICAO_CHAVE_PRE_ADVOGADO.md`).

⚠️ E uma armadilha para o item 3: **medir a não-determinância com as duas
rodadas disputando o Docker mede a corrida do bind-mount, não o modelo.** Rode
as cinco em série, e use o `corrida_do_mount` que acabou de entrar para
descartar as que forem contaminadas — é literalmente para isso que o campo
serve.
