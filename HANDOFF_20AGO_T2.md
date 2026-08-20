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
