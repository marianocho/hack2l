<!-- tag: hack2l -->

# HANDOFF T2 — AWS/Bedrock — 20/08/2026

> Ramo `t2-aws`, worktree em `C:\hack_agents\Hack2L\.worktrees-trilhas\t2-aws`.
> Commit: `2a523cf`.
>
> **Docker: não peguei.** Nada nesta sessão subiu container. Rodei sempre
> `pytest -q -m "not lento"`.
>
> **Dinheiro: US$ 0,00.** Nenhuma chamada de API foi feita — nem à Anthropic,
> nem à AWS. Tudo que está medido abaixo saiu de introspecção do SDK e de
> captura no transporte, em milissegundos.

---

## O veredito do item 2, na forma que este projeto exige

> **`SEM_NO_BEDROCK` continua LIDA, não medida. O instrumento existe, está
> validado e é grátis; falta a credencial.**

Não há credencial AWS nesta máquina — conferido em quatro lugares: nenhuma
variável `AWS_*`, nenhum `~/.aws` (nem `credentials` nem `config`), nenhum `aws`
no PATH, nenhum cache de SSO. `boto3` está instalado (1.43.74), o que não ajuda
sem credencial.

Dizer "medido" aqui seria exatamente o erro que o produto existe para impedir.
O que eu **posso** afirmar está abaixo, e é mais do que eu esperava.

---

## O que FOI medido — offline, sem credencial, sem custo

### 1. O SDK não filtra nada. O 400 seria do servidor.

`anthropic 0.120.2`, lido no pacote instalado:

- `lib/bedrock/_beta_messages.Messages.create` **é o mesmo objeto-função** que
  `resources.beta.messages.Messages.create` — a primeira parte. Conferido com
  `is`, não por leitura.
- `_prepare_options` do Bedrock legado só move `model` para a URL, põe
  `anthropic_version` e recusa Batch/count_tokens. Não toca em `output_config`
  nem em `fallbacks`.
- `_prepare_request` do Mantle **só assina SigV4**. Zero filtragem de corpo.

**Consequência:** `SEM_NO_BEDROCK` é uma afirmação sobre o **servidor**, não
sobre o SDK. Sem `ajusta_chamada`, os dois parâmetros chegam ao Bedrock
verbatim — a máscara é a única coisa entre o produto e o fio.

### 2. 🚨 O cliente legado do Bedrock **não tem `tool_runner`**

Medido construindo os dois clientes de verdade:

| cliente | `create` | `tool_runner` |
|---|---|---|
| `AnthropicBedrockMantle` (padrão) | sim | **sim** |
| `AnthropicBedrock` (`VEREDITO_BEDROCK_LEGADO=1`) | sim | **NÃO** |

O `MantleBeta.messages` devolve a classe de primeira parte; o `Beta.messages` do
legado devolve `lib/bedrock/_beta_messages.Messages`, que define `create` e nada
mais.

**Por que isso é grave, e não um detalhe de compatibilidade:** o `tool_runner`
**é** o advogado. Com a escotilha ligada, cada acusação morreria com
`AttributeError` dentro do `try` de `julga` — que converte qualquer exceção em
INCONCLUSIVO. A rodada terminaria com a categoria carro-chefe vazia e o parecer
parecendo rigoroso. É o desfecho que o terceiro estado existe para impedir,
chegando pela porta da infraestrutura.

E o docstring de `_fab_bedrock` tratava o legado como alternativa equivalente
("nem toda conta tem o Mantle habilitado"), o que convida a ligar a escotilha
justamente quando o Mantle falta.

**Consertado**, dentro do desenho que o módulo já tinha:

- `CAPACIDADES` — toda capacidade que *algum* motor pode perder, separada de
  `SEM_NO_BEDROCK` (que é só o que o Bedrock recusa **por parâmetro**).
  `tool_runner` não é parâmetro e não tem beta; enfiá-lo na constante faria todo
  Bedrock declarar uma perda que o caminho padrão não tem — guarda morrendo de
  excesso.
- o pré-voo **reprova**, não avisa: perder `task_budget` degrada e o operador
  decide; perder `tool_runner` cancela. Alarme que só informa, num caso que não
  tem como dar certo, ensina a seguir em frente.
- `_legado_pedido()` — a escotilha lida em **um** lugar. Lida em dois, o motor
  prometeria `tool_runner` e construiria o cliente que não tem: é a "chave em
  dois lugares" que já custou quatro tentativas neste projeto.

### 3. O padrão de bug apareceu dentro da guarda escrita contra ele — de novo

A primeira versão da conferência procurava as betas em `corpo["anthropic_beta"]`.
**No Mantle a beta viaja só no cabeçalho `anthropic-beta` e nunca chega ao
corpo.** A lista vinha vazia nas cinco células, a exigência passava por
**vacuidade**, e a sonda declarava "máscara perfeita" sem nunca ter olhado para
uma beta. Verde, muda, e do lado errado.

No Bedrock legado é o contrário — `_prepare_options` copia cabeçalho → corpo. Por
isso `_betas_no_fio` olha os dois: a resposta certa depende de qual cliente foi
construído, e a sonda não pode depender disso.

Registrado com número, não com prosa:

```bash
py -3.12 scripts/mutacao_medir_bedrock.py --vacuidade
```

> a beta REALMENTE sai na chamada mascarada? True `['server-side-fallback-2026-07-01']`
> onde ela sai: cabeçalho=`'server-side-fallback-2026-07-01'` corpo=`None`
> predicado ANTIGO (só o corpo): **PASSOU VERDE**
> conferência de HOJE (cabeçalho + corpo): **ACUSOU**

⚠️ O modo `--vacuidade` **reproduz o predicado antigo sobre o dado capturado**,
em vez de re-encenar a versão antiga por mutação do fonte. Reverter só a
extração deixaria de pé as exigências positivas, que são parte do conserto, e o
resultado mediria a mistura das duas versões.

---

## O instrumento: `medir_bedrock.py`

**Cinco células, não uma chamada.** Mandar os dois parâmetros juntos e ver um 400
não diz qual dos dois foi recusado — e não adianta mais que a matriz que já foi
lida.

| célula | o que isola |
|---|---|
| `controle` | a chamada mínima passa neste motor? |
| `task_budget` | ele sozinho, com a beta dele |
| `fallback` | ele sozinho, com a beta dele |
| `ambos` | o que o advogado mandaria **sem** máscara |
| `mascarado` | o que `ajusta_chamada` deixa passar — a chamada de **hoje** |

O par `ambos`+`mascarado` é o que responde à pergunta que importa — não "existe
400?", mas **"a máscara é carga ou peso morto?"**:

| ambos | mascarado | leitura |
|---|---|---|
| RECUSADO | ACEITO | `SEM_NO_BEDROCK` certa, e a máscara é carga |
| ACEITO | ACEITO | 🚨 **constante errada para mais** — o produto joga fora `fallbacks` de graça |
| RECUSADO | RECUSADO | 🚨 a máscara não cobre o que devia |

Três decisões de desenho que vale a pena não desfazer:

- **o `model` já vai traduzido em TODAS as células**, inclusive nas cruas. Se o
  controle fosse com o id sem prefixo e o `mascarado` com o prefixado, a
  diferença medida seria a do prefixo — e o 404 resultante se leria como recusa.
- **sem controle verde, toda célula vira INCONCLUSIVO**, inclusive as que
  voltaram 400. Modelo não habilitado, região errada ou credencial sem permissão
  produzem erro nas cinco. E a guarda consegue ficar quieta: com o controle
  passando, não mexe em linha nenhuma.
- **403/404/429 nunca são veredito sobre parâmetro.** Habilitação de modelo no
  Bedrock é por conta e por região, e o erro é um 404 que se lê como "o modelo
  não existe" — mesma classe de mentira do 404 do repositório privado. É o item
  4 da T2, e já está tratado na classificação.

### Travas vistas falhando

| arnês | resultado |
|---|---|
| `scripts/mutacao_medir_bedrock.py` | **5/5** mutações mataram exatamente a conferência que alegam matar |
| mutação das guardas do legado | **3/3**, idem |

A especificidade é o ponto, não a contagem: a mutação do pré-voo mata **uma só**
trava, e é a que fala do pré-voo.

---

## Como continuar — o item 2 fecha em minutos com credencial

```bash
py -3.12 medir_bedrock.py --offline          # sem credencial, sem rede, sem custo
py -3.12 medir_bedrock.py --motor bedrock    # ~US$0,01, cinco chamadas mínimas
```

Antes de gastar a tarde, o item 4 da trilha: habilitação de modelo é por conta e
por região. Se o `controle` voltar 404, é isso — e a sonda já diz com essas
palavras, em vez de deixar parecer recusa de parâmetro.

Grava em `saidas/bedrock/<carimbo>-<motor>.json`. ⚠️ `saidas/` está no
`.gitignore`, então a saída de hoje não foi commitada — ela se refaz de graça em
milissegundos.

**Ordem sugerida:** item 2 (fechar a leitura) → item 1 (rodar de verdade e ver o
que quebra) → item 3 (paridade de parecer). O item 3 é o que decide se dá para
rodar o produto inteiro em crédito, e depende do 1.

---

## PEDIDOS

### 1 → main / T3: **seis testes já vermelhos no merge `04fb1d7`**

Conferido que **não** são meus: mesmos seis com os meus arquivos removidos da
árvore.

```
tests/test_advogado.py::test_sonda_distingue_chave_de_saldo
tests/test_advogado.py::test_sonda_gasta_um_token_so
tests/test_contencao_app.py::test_a_copia_nunca_escreve_no_banco_de_origem
tests/test_efeito_nao_medido.py::test_psql_usa_as_credenciais_do_projeto_e_nao_as_do_desafio
tests/test_ferramentas.py::test_base_e_o_pai_do_pr_nao_a_ponta_da_main
tests/test_fusao_provada_no_parecer.py::test_o_caminho_FELIZ_chega_ao_fim_sem_erro_de_encanamento
```

Duas amostras parecem **ambientais**, não lógicas — `RuntimeError: ref nao
encontrada no repo do desafio: main` (estado do checkout do `desafio\`) e as duas
sondas do advogado, que querem chave/rede. Não investiguei além: não é arquivo
meu. ⚠️ Mas suíte que já nasce com seis vermelhos ensina a ignorar vermelho, que
é como a próxima regressão de verdade passa.

### 2 → dono de `tests/test_saida_no_console.py`: a guarda não olha `scripts/`

O glob é `RAIZ.glob("*.py")` + `veredito/*.py`. **`scripts/` fica de fora** — e
`scripts/` é onde moram os arnesses, que rodam justamente em caminho de
diagnóstico. Bati nisso ao vivo: um `print` com 🚨 em
`scripts/mutacao_medir_bedrock.py` estourou `UnicodeEncodeError` no console
cp1252, matando a saída **na hora em que ela ia dizer que o registro não
fechou** — o mesmo alarme-que-derruba-o-programa de 11/08, no diretório que a
trava não varre. Já corrigi os meus dois arquivos; a **glob** continua curta.

### 3 → sessão principal (única que escreve `CLAUDE.md`): duas linhas novas

- **padrão de bug** — "a beta que viaja no cabeçalho": guarda conferindo o campo
  errado de dois possíveis, passando por vacuidade. Quarta vez que o padrão
  aparece dentro da guarda escrita contra o padrão.
- **seção do MOTOR** — o legado do Bedrock não tem `tool_runner`, e a escotilha
  `VEREDITO_BEDROCK_LEGADO` **não** é uma alternativa equivalente. Hoje o texto
  do `CLAUDE.md` diz que os clientes de Bedrock/AWS "expõem
  `beta.messages.tool_runner` igual" — verdade para o Mantle e para o `aws`,
  **falso para o legado**.

### 4 → T1: nada de mim ainda

Não toquei em `posta_parecer.py` nem em `revisa_pr.py`. Quando o item 3
(paridade) rodar, vou querer comparar dois pareceres no disco — se isso pedir
campo novo no parecer, viro pedido antes de escrever.

---

## Sobre o protocolo — o que aconteceu com o diretório compartilhado

Comecei em `C:\hack_agents\Hack2L\hack2l` e, no meio da sessão, `git status`
mostrou `veredito/juiz.py` e `tests/test_juiz.py` modificados e um
`veredito/superficie.py` novo — **nada disso meu**. Dois comandos depois os
arquivos tinham sumido e o `HEAD` estava em outro ramo: a T1 trabalhando no mesmo
diretório, e o meu checkout trocado embaixo de mim. Cinco testes vermelhos que eu
atribuí à minha mudança eram edições em curso da T1.

A tabela de propriedade por *arquivo* não protege disso, porque a colisão é do
**checkout**, um nível abaixo. Worktree por trilha resolve, e agora existe para
as cinco.

⚠️ Fica a lição operacional: enquanto o diretório era compartilhado, **`git
status` e a suíte não eram evidência sobre o meu trabalho.** Conferi os dois
achados centrais deste handoff contra o hash do blob (`motor.py` e `advogado.py`
idênticos entre `3be9750` e o merge `04fb1d7`), e não contra o que estava na
árvore.

---

# Item 1 — `VEREDITO_MOTOR=bedrock` rodado de verdade (20/08)

> **Custo: US$ 0,00.** A rodada abortou no pré-voo, antes de qualquer chamada.
> **Docker: não peguei** — rodei com `APP_SUBIR=0`, que basta para chegar ao
> motor e não tira o recurso das outras sessões.

O comando, contra o PR da bancada:

```bash
VEREDITO_MOTOR=bedrock CHALLENGE_REPO=C:/hack_agents/Hack2L/bancada \
  WORKTREES_DIR=C:/hack_agents/Hack2L/.worktrees-bancada \
  BASE_BRANCH=main PR_BRANCH=pr/tarefa-por-link APP_SUBIR=0 \
  py -3.12 -m veredito.orquestrador --top-n 1
```

## O motor NÃO quebrou — e essa é a notícia

A trilha dizia *"esperar que quebre"*, comparando com o `posta_parecer.py`, que
em 18/08 quebrou em quatro lugares na primeira execução real. **Não foi o caso.**
Na primeira vez que o `motor.py` falou com o mundo, ele fez exatamente o que o
desenho promete:

```
pre-voo falhou na API da Anthropic: o motor nao resolveu: RuntimeError:
VEREDITO_MOTOR=bedrock foi pedido e nao ha' credencial AWS utilizavel: a cadeia
de credenciais do boto3 nao resolveu nada.
Cair para a API direta aqui faturaria a rodada na conta errada em silencio.
Configure a credencial, ou peca VEREDITO_MOTOR=anthropic de proposito.
A rodada nao comeca: sem modelo nao ha promotor nem advogado.
```

Os três comportamentos que importavam, todos observados:

1. **forçado levanta** — não caiu calado para a API direta, que faturaria a
   rodada na conta errada e a faria parecer perfeita;
2. o pré-voo **abortou antes de gastar** — zero chamada, zero dólar;
3. a mensagem diz a causa **e a saída**, em vez de "sem credencial AWS".

⚠️ Isto é o caminho de recusa, não o caminho feliz. **O caminho feliz continua
sem nunca ter rodado** — e é lá que o `posta_parecer.py` quebrou em quatro
lugares. Não confunda "a recusa funciona" com "o Bedrock funciona".

## 🚨 O que BLOQUEIA a T2 inteira — e não é a credencial

`veredito/orquestrador.py:253`:

```python
if not cfg.ANTHROPIC_API_KEY:
    raise SystemExit("ANTHROPIC_API_KEY ausente no .env -- nada roda sem ela.")
```

**Incondicional.** Medido:

```bash
ANTHROPIC_API_KEY= VEREDITO_MOTOR=bedrock ... py -3.12 -m veredito.orquestrador
# -> ANTHROPIC_API_KEY ausente no .env -- nada roda sem ela.   (exit 1)
```

Quem roda **inteiramente em crédito da AWS** — que é o motivo do motor existir,
item 5 da trilha — corretamente **não tem** `ANTHROPIC_API_KEY`. E é parado por
uma chave que aquela rodada nunca usaria, com uma mensagem que manda pôr no
`.env` o que a pessoa deliberadamente não tem.

E o `motor.py` **já sabe a regra certa** — `descreve()` faz
`if m.nome == "anthropic" and not cfg.ANTHROPIC_API_KEY`. O orquestrador
contradiz uma regra que o módulo do lado já acertou. É a guarda aplicada onde não
é o caso: a mesma classe do acento vazando para o comentário do PR, na T1.

🚫 **Não editei** — `orquestrador.py` não está na minha tabela. Vai como pedido.

## Duas quebras que o worktree acordou

A mudança de hoje (worktree por trilha) quebra o pipeline, e o erro aponta para
o lugar errado.

**(a) `.env` não vai junto.** Ele está no `.gitignore`, então `git worktree add`
não o leva. Sem ele o produto cai em **todos** os padrões do `config.py` — a
dívida do `or <valor do desafio>` que o `CLAUDE.md` documenta — e não avisa. O
sintoma aparece longe:

```
open C:\...\.worktrees-trilhas\hack2l-challenge\docker-compose.yml:
The system cannot find the path specified.
```

`hack2l-challenge` é o **padrão do código**, um diretório que não existe em
lugar nenhum desta máquina. Lê-se como "falta clonar o repo do desafio".

**(b) e o `.env` copiado não basta**, porque os caminhos dele são **relativos**:
`CHALLENGE_REPO=../desafio` resolve contra a raiz do *worktree*. O erro só troca
de nome, para `.worktrees-trilhas\desafio`.

A suposição "o repo mora ao lado de `desafio/` e `bancada/`" está em três
lugares, e os três quebram em worktree:

| arquivo | linha |
|---|---|
| `veredito/config.py:71` | `DESAFIO = (RAIZ / _s("CHALLENGE_REPO", "../hack2l-challenge"))` |
| `roda_bancada.py:23` | `BANCADA = RAIZ.parent / "bancada"` |
| `roda_bancada.py:56` | `WORKTREES_DIR = RAIZ.parent / ".worktrees-bancada"` |

Contornável por variável de ambiente absoluta (foi o que fiz), mas **cada trilha
vai tropeçar nisto sozinha**, e o erro não diz "você está num worktree".

## O que funcionou, e vale registrar

- a guarda do `.env` sombreado **disparou certo**: *"o .env NAO esta valendo
  para: CHALLENGE_REPO, PR_BRANCH"* — exatamente as duas que eu havia
  sobreposto de propósito. Ela consegue ficar quieta e não ficou à toa.
- o pré-voo alcança o motor com `APP_SUBIR=0`: dá para exercitar a fiação da AWS
  sem Docker e sem tirar o recurso de ninguém.
- as contas da bancada pedem `VEREDITO_SENHA_*` no ambiente (trabalho de 19/08).
  Não estão setadas aqui, e o pré-voo listou as quatro **com o nome da variável
  que falta**. Para a rodada paga valer, elas precisam estar no ambiente — senão
  a prova ponta a ponta fica desligada e a rodada mede menos do que parece.

## Onde o item 1 para

Sem credencial AWS, o caminho feliz é inalcançável. **Ordem para quando ela
existir:**

1. o pedido do `ANTHROPIC_API_KEY` (senão nem começa em crédito puro);
2. `medir_bedrock.py --motor bedrock` — cinco chamadas mínimas, ~US$0,01, fecha
   o item 2 e valida credencial/região/habilitação antes de gastar de verdade;
3. só então o item 1 completo, com Docker e `VEREDITO_SENHA_*` no ambiente.

Fazer (2) antes de (3) é deliberado: se o modelo não estiver habilitado na
conta, o erro é um 404 que se lê como "o modelo não existe" — e custa uma tarde.

---

## PEDIDOS (continuação)

### 5 → sessão principal / T3: `orquestrador.py:253` bloqueia rodada em crédito AWS

Trocar o `if not cfg.ANTHROPIC_API_KEY` incondicional por algo que respeite o
motor. O `motor.descreve()` já tem a regra certa e o pré-voo já aborta com boa
mensagem — a checagem antecipada pode virar motor-aware ou simplesmente sair.
🚨 **Enquanto isso não mudar, os itens 1, 3 e 5 da T2 não rodam em crédito puro.**

### 6 → sessão principal: worktree quebra o pipeline (as três linhas acima)

Sugestão, na ordem de custo: documentar no `CLAUDE.md` que worktree precisa de
`.env` copiado **com caminhos absolutos**; ou derivar a raiz do repositório com
`git rev-parse --path-format=absolute --git-common-dir` em vez de `RAIZ.parent`,
que é o que resolve de verdade e vale para as cinco trilhas.

---

# CI do `veredito-demo` vermelha — diagnóstico (20/08)

Email do GitHub, "all jobs have failed". **Não era o `hack2l`** (0 runs de
Actions — o workflow só dispara em `pull_request` e nenhum foi aberto) **nem a
`bancada`** (últimos runs 18/08, verdes). Era `luisfelp07/veredito-demo`, o repo
público que a T5 criou hoje: dois runs de `pull_request`, PRs #1 e #2.

## A causa, em duas camadas

**Camada 1 — o secret não existia.** `gh secret list -R luisfelp07/veredito-demo`
voltou vazio. `git push` não leva secret; ele é configuração do repositório.

**Camada 2, e é a que custou a ida e volta — o secret existia e estava VAZIO.**
Depois de criado (`06:09:00Z`), a re-rodada (`06:10:44Z`, tentativa 2) falhou no
**mesmo passo com a mesma mensagem**. Descartado tudo o que era estrutural:
não é fork, zero environments, secret no nível do repositório, run iniciado
104 s **depois** da criação.

`gh secret set` lê o valor do **stdin**. Com stdin que não é terminal ele grava
**string vazia sem reclamar** — o secret passa a existir, aparece na lista com
data, e chega vazio no runner.

## O conserto no nosso lado

O guarda dizia *"nao esta nos secrets DESTE repositorio"* para qualquer valor
vazio. Isso é **afirmar uma causa que ele não consegue distinguir** — de dentro
do workflow, "ausente" e "vazio" são indistinguíveis — e mandou o operador
adicionar o que já estava lá.

Guarda que acusa a causa errada manda consertar a coisa errada: **o padrão de
bug da casa aplicado ao TEXTO do alarme.** Agora ele diz as duas causas e dá o
comando que as separa (`gh secret list`).

De quebra, o `-z` antigo **passava** com a chave só de espaço em branco — a
rodada morreria depois, no 401 da API, que se lê como defeito do produto.

Conferido nos quatro casos, com a violação injetada:

| entrada | desfecho |
|---|---|
| vazia | erro, exit 1, com as duas causas |
| só espaço | idem — **o guarda antigo passava aqui** |
| plausível | silêncio, exit 0 — ele consegue ficar quieto |
| com aspas coladas | warning, exit 0 |

🚫 O valor nunca é impresso, e a classificação é grosseira de propósito: o log é
público num repositório de demonstração.

## PEDIDOS (continuação)

### 7 → T5: o secret do `veredito-demo` está vazio, e o PR "limpo" não é limpo

**(a)** Regravar `ANTHROPIC_API_KEY` com valor de verdade — pela web, ou
`gh secret set ANTHROPIC_API_KEY -R luisfelp07/veredito-demo < arquivo`.
🚫 Não fiz: valor de chave de API é do operador, não meu.

**(b)** ~~A PR #1 estaria sem o `index=True`~~ — **RETRATADO. Eu errei, e a PR
#1 é sim a PR limpa.**

O diff dela toca `app/main.py` **e** `app/models.py`, e o que faz em models é
exatamente acrescentar o índice, com comentário explicando o porquê:

```python
-    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
+    # index=True porque a listagem de projetos agrega tarefas por project_id.
+    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
```

🚨 **Como eu errei, porque o formato do erro importa mais que o erro.** Dois
descuidos que se somaram e produziram uma conclusão confiante e falsa:

1. li o diff com `gh pr diff 1 | head -40` — os hunks de `app/models.py` estavam
   **abaixo do corte**, e eu concluí "a PR não toca models.py" a partir de uma
   leitura truncada, sem notar que tinha truncado;
2. depois fui conferir `app/models.py` por `gh api .../contents/app/models.py`,
   que devolve o **default branch** — ou seja, o **base** do PR. O base
   corretamente não tem o índice: é a PR que o adiciona. Li o base como se fosse
   o head.

O segundo é o mesmo erro que o `CLAUDE.md` já documenta em outra roupa: o
descritor se lê **do base**, o código sob revisão é o **head**, e confundir os
dois produz um retrato do lugar errado. Eu confundi, e o sintoma foi
indistinguível de uma medição de verdade — conclusão específica, com número de
linha, e errada.

⚠️ E a lição operacional: **`head -N` num diff é truncamento silencioso.** Não
existe aviso de que havia mais. Para decidir "a PR toca o arquivo X?", a
pergunta certa é `--name-only`, que não tem cauda para cortar.

**Nada a fazer na PR #1.** Ela é a versão pós-16/08 e o parecer da rodada de
13:25 saiu como deveria: *"Nada a apontar neste PR. 4 suspeita(s) levantadas e a
verificação derrubou todas."* — o falso positivo que a T5 mais temia **não
aconteceu**, e é esse o resultado que a vitrine precisa mostrar.

### 8 → T5: sincronizar o workflow

O conserto do guarda está em `.github/workflows/veredito.yml` **do hack2l**. O
`veredito-demo` tem cópia própria — o repo busca a *ferramenta* em
`marianocho/hack2l@main`, não o workflow. Sem copiar, o demo continua com a
mensagem que acusa a causa errada.
