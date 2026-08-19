<!-- tag: hack2l -->

# Próximos passos — atualizado em 19/08/2026

Quadro geral e fila completa. **Esta é a fila viva** — o `ESTADO.md` é do dia do
hackathon e virou histórico; o `HANDOFF_12AGO.md` também.

> ⚠️ **Existe uma cópia deste quadro no vault** (`Onde retomar.md`). Em 15/08 as
> duas divergiram **nos dois sentidos** — cada uma mais atual que a outra num
> ponto diferente. Se você editar uma, propague. É a regra do "um arquivo só,
> sem cópia" valendo para documento, e ela já custou quatro tentativas com a
> chave da API.

---

> 🎯 **A sessão de 16–17/08 tem handoff próprio: `HANDOFF_17AGO.md`.**
> A entrada "revise este PR" existe, a licença saiu, e a decisão sobre a R3
> **foi tomada e medida em 17/08 à tarde**: "ferramenta não declarada" deixou de
> ser "execução falhou". No mesmo PR de terceiro, com as mesmas 5 acusações, o
> parecer foi de **0 descartados / 5 inconclusivos** para **4 / 1** — e o
> inconclusivo que sobrou é a R3b segurando um veredito sem nenhuma leitura,
> como deve. Comece por lá.
>
> ⚠️ **A fila abaixo ainda diz que PR de terceiro sai 100% inconclusivo em
> alguns pontos.** Não saía por causa de uma coisa só, e o texto é anterior à
> medição.

> 🎯 **A sessão de 18–19/08 tem handoff próprio: `HANDOFF_18AGO.md`. Comece por
> lá — é o mais recente.** O parecer virou comentário de PR e foi publicado de
> verdade; a fusão de achados existe e é **provada por exit code**; os quatro
> PRs da bancada foram refeitos pela porta da frente (4 de 4 com o gabarito).
>
> **Próximo passo:** repo de demonstração público — é o que converte, e o único
> jeito de mostrar isto sem dar acesso à bancada privada.

## Onde o produto está

**O motor está medido nos dois sentidos.** Ele condena com artefato quando há o
que condenar, e absolve com motivo quando não há:

| condição | resultado | custo |
|---|---|---|
| PR com defeito plantado | 10 de 10 provados | US$1,38 |
| PR sem defeito | 8 de 8 refutados | US$1,23 |
| PRs de terceiro (10 reais) | 68% refutados | US$0,071/alegação |

### 🆕 19/08 — os quatro PRs da bancada, pela porta da frente

Refeito com a Action e o pipeline de hoje. **4 de 4 bateram com o gabarito:**

| ramo | defeito | esperado | veio |
|---|---|---|---|
| `pr/tarefa-por-link` | CWE-639 | PROVADO | **PROVADO** (via Action, comentado no PR) |
| `pr/filtro-de-projetos` | CWE-89 | PROVADO | **PROVADO:3** |
| `pr/reconvite-de-membro` | CWE-367 | PROVADO | **PROVADO:4, REFUTADO:1** |
| **`pr/contagem-de-tarefas`** | **nenhum** | REFUTADO | **REFUTADO:5** ← zero falso positivo |

O PR limpo é o que mais importa: 5 suspeitas levantadas, 5 derrubadas. Falso
positivo na Action seria pior que qualquer defeito não encontrado.

⚠️ **Isto mede o INSTRUMENTO, não a capacidade de achar defeito.** Com n=4 o
segundo não se conclui, e o `roda_bancada.py` imprime esse aviso sozinho.

**O que impede uso real** — sobrou UM:

1. ~~**Não tem onde entregar.**~~ ✅ **Saiu em 18/08, e foi verificado
   publicando de verdade.** Ver abaixo.
2. **Escala quebra.** No `next.js`: 220s por acusação, 6 de 8 inconclusivos.

### 🆕 E o comentário parou de exagerar — 18–19/08

Um defeito visto por três lentes saía como **"3 achados com evidência"**. Era o
único lugar em que este produto inflava acusação, e justamente no texto que o
cliente lê. Agora sai como **1**, com as três provas preservadas no bloco.

| peça | o que faz |
|---|---|
| `veredito/fusao.py` | agrupa por endereço + procedência — **inferência** |
| `veredito/prova_de_fusao.py` | **mede**: reverte um trecho do diff, vê quais testes param de falhar |
| `fusao.json` | o orquestrador grava; o juiz e o comentário só **leem** (pureza intacta) |

Sem Docker ou sem `codigo` declarado, o comentário diz *"indício e não prova"* —
nunca cala a diferença.

🚨 **A prova de fusão NUNCA tinha rodado até 19/08**, e só apareceu ao conferir
os PRs restantes: um `NameError` de import e um `_por_id("prova_{}.json")` (que
faz *glob* — `{}` é literal). O `try/except` degradava honestamente e **por isso
mesmo** escondia que a peça não executava. Ver `HANDOFF_18AGO.md`.

🚫 **Quatro ideias foram MEDIDAS e engavetadas** — não reconstruir sem ler
`MEDICAO_CHAVE_PRE_ADVOGADO.md`: afrouxar a chave do pré-advogado (~metade das
fusões erradas), portão de similaridade por Jaccard (caudas sobrepostas),
re-ranquear a fila (0,12 vaga/rodada — a vaga da duplicata não é recuperável
antes de ser gasta) e `MAX_POR_LOCAL` por proximidade (11 de 27 rodadas mudam,
e a troca perde diversidade de lente).

> ✅ **Saiu em 18/08: o parecer chega ao PR.** Duas rodadas da Action contra
> `luisfelp07/bancada#1`, as duas com `postar=true`:
>
> | | rodada 1 | rodada 2 |
> |---|---|---|
> | o passo disse | `criado:` | `atualizado:` |
> | comentários no PR **depois** | 1 | **1** |
> | id | 5333006742 | **5333006742** — o mesmo |
> | corpo | 5683 car. | 5590 car. — trocado |
>
> As duas metades: **publica** e **não empilha**. A conferência é a API do
> GitHub (`issues/1/comments`), não a linha que o nosso script imprimiu —
> `criado:`/`atualizado:` é autodeclaração do código sob teste, e é a mesma
> distinção da R0.
>
> ⚠️ **`posta()` e `acha_o_nosso()` tinham ZERO teste até 18/08** e o caminho
> nunca tinha executado. Agora são 14 (`tests/test_posta_o_parecer.py`), cinco
> violações injetadas — e **uma delas mostrou que o teste da recusa passava
> pelo motivo errado**: com 403 em tudo, quem levantava era o `raise_for_status`
> do GET dentro de `acha_o_nosso`, e o do POST podia ser apagado com a suíte
> verde. Leitura e escrita agora têm status separados no dublê.

> ✅ **Saiu em 14–15/08:** *"metade só funciona no desafio"*. Contas, layout,
> rota de login, bancos e a precedência do `.env` saíram do código — cinco
> chumbados, todos achados apontando o produto para um segundo projeto.
> **Em 16/08 apareceu o sexto**, e era o pior: `-U kb` chumbado no retrato do
> banco fazia a guarda de efeito colateral dizer "limpo" sem ter olhado.
>
> ✅ **Saiu em 16/08:** *"sem licença"*. Apache-2.0, commit `38a6fd7`.

---

## A fila

### A — Para alguém instalar e rodar

| item | tamanho | nota |
|---|---|---|
| ✅ **Licença** *(16/08)* | | Apache-2.0, `38a6fd7` |
| ✅ **Entrada "revise este PR"** *(17/08)* | | `revisa_pr.py <url>`. Resolve o merge-base pela API, clona raso os dois commits, monta os worktrees. ⚠️ Ver `HANDOFF_17AGO.md`: rodou de verdade e expos a R3 |
| ✅ **Contenção do `http_request`** *(14/08)* | | três partes, provada sob carga. Ver abaixo. ⚠️ Fechou o **banco**, não a rede — ver "o vão que sobrou" |
| ✅ **`veredito.yml`** *(14–15/08)* | | contas, layout, login, bancos, como o app sobe. **Cinco chumbados saíram do código**, todos achados apontando para o segundo projeto |
| 🎯 **Parecer como comentário de PR** | 1–2 dias | com a entrada pronta, é o que falta para a Action. Ver os cinco pontos em "A Action não é só seguir passo a passo" |
| **GitHub Action** | 1–2 dias | ver "Por que Action" abaixo |
| **Repo de demonstração** | 1 dia | PR deliberadamente quebrado, público. É o que converte |
| 🆕 **Detector de `veredito.yml`** | 1 dia | **medido em 19/08: 12 campos saem de compose+Dockerfile com 0 erro.** Encolhe o onboarding de 26 campos para 2 perguntas — mas os 2 que sobram são os que sustentam CRÍTICA. Ver abaixo |

#### 🆕 O detector de `veredito.yml` — medido em 19/08

**A proposta veio de fora** (outra IA, na conversa do dia): em repositório
corporativo a configuração de ambiente é caótica ou mal documentada, e exigir
que o cliente escreva um `veredito.yml` à mão **antes de ver valor** derruba a
conversão. Solução proposta: um gerador/auto-detector.

**Medido antes de decidir, porque os dois `veredito.yml` escritos à mão são
gabarito.** Detector mecânico mais óbvio possível — ~90 linhas, sem LLM, sem
subir o app, custo zero de API, lê só `docker-compose.yml` + `Dockerfile` + a
árvore — comparado campo a campo:

| repo | acertou | **errou** | não detectou |
|---|---|---|---|
| `bancada` | 11 | **0** | 11 |
| `desafio` | 12 | **0** | 12 |

🚨 **Acertou `codigo.montagens` e `codigo.testes` nos dois**, inclusive o caso
divergente do desafio (`app/api/tests` no disco → `tests` dentro do container).
São exatamente os campos que causaram o falso negativo silencioso de 08/08 e
regrediram **duas vezes** (15/08, 17/08). E saem por **derivação** —
`build.context` + `COPY` + `WORKDIR` — que é a troca que o comentário do
`config.py:517` já prescreve: *lista mantida → critério derivado*.

##### A distribuição dos ~26 campos não é uniforme

| classe | nº | como se obtém |
|---|---|---|
| lidos de compose+Dockerfile | 12 | medido, 0 erro |
| nossos, inventados | 5 | `subir`, `espera_s`, `descartavel_*`, `rede_isolada` — não há o que detectar |
| sondagem com o app no ar | 5 | `saude` + os 4 de `auth`, via `/openapi.json`. **Verificável**: o login devolve token ou não |
| rodar a suíte duas vezes | 1 | `banco_de_teste_semeado` |
| **autorais — não detectáveis** | **2** | `contas`, `contexto` |

##### 🚨 Os 2 que sobram são os que fecham as DUAS vias da R1

Conferido no código, não deduzido:

- `juiz.py:109` — `prova_ponta_a_ponta` é um **AND** com
  `artefato_http.alcancou_a_api`. **Prova diferencial não conta como ponta a
  ponta.**
- `juiz.py:265` — a R1 aceita árbitro com procedência (⟵ `contexto`) **ou**
  prova ponta a ponta (⟵ `contas`, porque `http_request` autenticado precisa de
  token).
- `juiz.py:278` — a R2 rebaixa todo o resto para MEDIA.

**Um gerador perfeito nos 24 campos entrega uma rodada onde nada passa de
MEDIA.** O que os 12 campos de `codigo.*` compram é real — escapar do
INCONCLUSIVO da R3/R3b, artefato reproduzível, refutação com motivo — mas não é
a demo que converte.

##### 🚨 A armadilha: auto-registrar contas passa por TODAS as guardas

O atalho óbvio para `contas` é registrar contas pela API. Mas `possui` é lido em
**um único lugar** — `projeto.py:117`, `if c.get("possui") == 0` — e **nada em
`avisos()` confere que alguma conta possui alguma coisa**.

Três contas recém-registradas, todas vazias:

- passam `len(contas) >= 3` ✅
- passam `controle_negativo is not None` ✅
- e produzem uma rodada onde **vazamento não pode ser demonstrado, porque não há
  o que vazar**

É o padrão de bug do projeto **dentro da ferramenta de onboarding**: a guarda
está condicionada ao mesmo sinal que o gerador fabrica, e fica muda exatamente
onde ele introduz o risco.

⚠️ E o atalho nem é geral: o `desafio` tem `POST /auth/register`; a `bancada`
**não tem**. 1 de 2.

##### ⚠️ A premissa do "caos corporativo" corta ao contrário

O detector funciona porque compose e Dockerfile são **contratos legíveis por
máquina**. Repositório sem compose funcional não dá nada a ele — e é o mesmo
repositório onde um humano também não escreveria o yml. **Acelera o caso fácil;
não converte o difícil.** Isso é diferente de "aumenta conversão de SaaS".

##### ⚠️ E o zero-erro não exercitou os ramos onde o protótipo JÁ está errado

`n=2`, os dois Python/FastAPI/compose, e **os dois são single-stage com um único
diretório de teste**. Os dois bugs latentes do protótipo — WORKDIR do estágio
`builder` vazando num multi-stage, e `sorted(candidatos)[0]` quando há mais de um
diretório de teste — **nunca dispararam**. É a lição 5 do *"como procurar"*
valendo contra a nossa própria medição: o que só existe num caso não é testado
pelo caso que existe.

##### O plano — quatro fases, e a ordem É a defesa

| fase | o que | tamanho |
|---|---|---|
| **0** | **O contrato: só escreve o que derivou.** Campo não derivado fica AUSENTE, nunca chutado. Cada campo emitido carrega a procedência em comentário (`# de docker-compose.yml:12`) | 2h |
| **1** | Detector estático (compose + Dockerfile + árvore) → os 12 campos | 3h |
| **2** | Os 5 nossos, derivados de nome (`<banco.nome>_veredito`, `_veredito_app`, `veredito_isolada`) | 30min |
| **3** | Sondagem com o app no ar: `saude` por lista de candidatos, `auth` por `/openapi.json` — emitidos como **proposta não verificada**, confirmados no pré-voo pelo login de verdade | 2h |
| **4** | O pedido humano **reduzido**: *"três logins, e um deles não pode ser dono de nada"* + o caminho do `contexto`. Não é mais um arquivo de 26 campos; são 2 perguntas | 1h |

🚨 **A fase 0 não é preâmbulo, é a fase que impede a regressão.** O `projeto.py`
trata **ausente** como limite honesto (o pré-voo diz o que perdeu) e **torto**
como `raise`. Um campo chutado não levanta — ele *parece* declarado. Um gerador
que chuta converte a categoria honesta na categoria perigosa, e o produto inteiro
existe para impedir exatamente isso.

##### 🚨 O mapa de bugs — o que este detector pode gerar

| # | bug | por que fica mudo | trava |
|---|---|---|---|
| 1 | **Chuta em vez de deixar ausente** | campo chutado não levanta, *parece* declarado | `test_detector_nu`: repo vazio → yml vazio. Irmão do `test_projeto_nu` |
| 2 | **O `or <valor do vizinho>` volta pela porta do detector** | os 14 fallbacks que 17/08 removeu voltariam **gerados** em vez de chumbados — e o `test_projeto_nu` testa o *config*, não o detector | fixture sintético em `tmp_path`, que não é nem o desafio nem a bancada |
| 3 | 🚨 **`preparar` auto-emitido** | é **execução de comando arbitrário do repo do cliente**, e `preparar` roda sempre que nós subimos. Serviço chamado `seed` não é promessa de que ele semeia | **nunca auto-emitir.** Fica ausente com aviso: *"achei o serviço `seed`, confirme"* |
| 4 | **`montagens` errado → falso negativo silencioso** | pytest roda o código **assado na imagem**, os dois lados dão igual, e a prova diferencial absolve. É o canário de 08/08 | 🎯 **canário mecânico**: gravar sentinela no worktree e conferir que aparece dentro do container. Vale sozinho, mesmo sem detector |
| 5 | **Heurística de nome de serviço** (`api`/`backend`/`server`/`app`) | é lista mantida — o mecanismo do bug. `core`, `gateway`, `rest` não casam; e com dois serviços expondo porta, escolhe o errado | derivar do **diff**: a API é o serviço cujo `build.context` contém o código que o PR toca. Ambiguidade → ausente + pergunta |
| 6 | **Multi-stage: WORKDIR do `builder` vaza** | nenhum dos dois repos é multi-stage — o teste que temos não alcança | só considerar do **último `FROM`** em diante |
| 7 | **`${API_PORT}` sem default** | vira literal na URL, e a URL malformada só falha na sondagem | sem default e sem `.env` → ausente |
| 8 | **Mais de um diretório de teste** | `sorted()[0]` escolhe em ordem alfabética e ninguém confere | >1 candidato → ausente + lista para o humano |
| 9 | **Sobrescrever um `veredito.yml` ajustado à mão** | o ajuste some sem sinal | escrever em `veredito.yml.detectado` + imprimir o diff. **Nunca sobrescrever** |
| 10 | **`app.api` errado + `.env` persistente** | 15/08 de novo, agora com **três** fontes (env, yml gerado, yml humano) | `ensombrado_pelo_env` já cobre duas; falta o caso *gerado ≠ humano* |
| 11 | **`contexto` apontando para o arquivo errado** | `avisos()` só confere que o arquivo **existe**. README no lugar do CONTRIBUTING dá procedência a texto não-normativo | **nunca auto-detectar `contexto`.** Fica humano |

**Onde o código vai:** `veredito/detector.py` + CLI `detecta.py` na raiz (irmão do
`revisa_pr.py`); travas em `tests/test_detector.py` e `tests/test_detector_nu.py`.

⚠️ E cada trava precisa ser **vista falhando** com a violação injetada — a do
`ERRO`, em 13/08, passou com o defeito presente.

#### 🚨 A contenção do `http_request` — medido em 14/08

Rodada real de 6 acusações. Banco antes: `users=4, documents=5, **shares=0**`.
Depois: `users=4, documents=5, **shares=3**`.

Nada foi destruído. Mas o advogado **alterou estado do app real** — para provar
a injection no endpoint de compartilhamento, ele chamou
`POST /documents/N/share`, que cria linha. E o `SISTEMA` manda provar *"de forma
que só LÊ, nunca que altera ou apaga estado"*.

**A regra não se sustenta como está escrita:** provar defeito num endpoint de
escrita exige chamar o endpoint de escrita. Não é desobediência do modelo; é
regra impossível de cumprir no caso que mais importa.

**É outra instância do padrão de bug do projeto.** A contenção que funciona —
banco descartável imposto de fora, rede sem saída — foi aplicada ao caminho da
`prova_diferencial`. O `http_request` fala com o app **de verdade**, no banco
`kb` de verdade, e ficou de fora. A guarda existe e está muda exatamente no
caminho que toca dados vivos.

**E só descobrimos por acidente:** o `shares=0 → 3` apareceu porque tiramos
retrato do banco à mão antes da rodada. Nada no sistema teria avisado.

O conserto tem três partes, e a ordem importa:

1. **Tornar a regra verdadeira** (30 min). Trocar *"nunca altere estado"* por
   *"nunca apague nem modifique estado pré-existente; criar estado novo pela API
   documentada é permitido quando o defeito está num caminho de escrita"*. Regra
   que o desenho viola por construção ensina o modelo que as regras são
   aproximadas — e as outras regras do `SISTEMA` são as que impedem ele de
   apagar banco.
2. **Impor a fronteira de fora** (meio dia). Retrato do banco antes da rodada e
   restauração depois, ou app apontado para banco descartável durante a rodada.
   É literalmente o conserto de 11/08 estendido ao caminho que faltou —
   **contenção, não predição**.
3. **Medir sempre** (1 hora). Gravar o delta de estado como artefato da rodada,
   e o parecer dizer quantas linhas a prova criou. Hoje isso é invisível; foi
   preciso um humano desconfiar.

⚠️ Enquanto 2 não existir, a linha de base documentada (`demo=3, alice=1, bob=1,
carol=0, shares=0`) **desloca a cada rodada**, e comparação entre rodadas fica
suja sem ninguém perceber.

### B — Memória e custo

| item | tamanho | nota |
|---|---|---|
| ✅ **Parar de sobrescrever** *(13/08)* | 30 min | `saidas/rodadas/<data>T<hora>-<commit>/` + ponteiro `ULTIMA` |
| ✅ **Cache — virou prefixo compartilhado** *(14/08)* | | o desenho original **não economizaria**: memoizar `read_file` corta 0,15s de disco e US$0. Cada acusação é conversa separada, o conteúdo entra no contexto igual. Os arquivos do PR passaram a entrar no bloco **cacheado** junto com o diff |
| **Fusão por artefato no juiz** | 1 dia | duas acusações com o mesmo artefato **são** o mesmo defeito — fato, não palpite |
| **Biblioteca de andaimes por repo** | 1–2 dias | corta voltas do laço, que é onde mora o custo |
| ❌ **Mostrar veredito passado ao advogado** | — | **nunca.** Precedente não é evidência, e código muda |

**O que o prefixo compartilhado rendeu, medido em rodada real de 6 acusações
(`saidas/rodadas/20260814T1451-1dd2e5c`):**

| | com o bloco | rodada 1440 (6 acusações) |
|---|---|---|
| chamadas de `read_file` | **0**, com 11 arquivos entregues | — |
| tokens novos | 10.530 | 32.360 |
| tokens de saída | 6.452 | 12.871 |
| lidos do cache | 295.752 | 242.002 |
| tempo | 213,9s | 329,6s |

⚠️ **O "3× menos entrada" exagera.** Leitura de cache custa ~10%, não zero.
Entrada efetiva: ~40.100 contra ~56.600 → **1,41× menos**, não 3×. Saída 1,99×,
tempo 1,54×. E a comparação **não é controlada** — outras acusações, outro dia.

O que é evidência limpa é o **zero**: 11 arquivos no bloco, nenhuma chamada de
`read_file` na rodada inteira. Isso não depende de comparação, está no
`chamadas.json`, e é a alegação central — o advogado deixou de gastar volta
pedindo arquivo.

### C — Evidência que falta

| item | custo | o que responde |
|---|---|---|
| **PR de terceiro com IA** | US$0,05 | a lente de injection ficou vazia nos 10 PRs porque nenhum tem modelo. Silêncio correto ou lente quebrada? |
| ✅ **`$PARAM` nas regras do semgrep** *(14/08)* | 3 linhas | a mensagem agora nomeia a variável e a rota. Visível no parecer: *"o parametro **email** … na rota **share_document**"* |
| **Taxa de aceitação** | depende do bot | de cada achado postado, qual fração o autor conserta. É a métrica que prova a tese |
| 🎯 **A bancada com gabarito — 4 PRs** | meio dia + ~US$2 | **destrava a métrica que nunca tivemos.** Ver abaixo |

---

## 🎯 A bancada com gabarito — proposta de 14/08

**O buraco que ela fecha.** Hoje sabemos que o verificador refuta ruído (68% em
repo de terceiro, 8/8 num PR sem defeito). Não sabemos se os promotores **acham
defeito real fora do desafio** — e não dá para saber, porque nos 10 PRs reais
não havia gabarito. Conversão de 10–20% ali pode ser lente ruim ou PR sem
defeito, e as duas hipóteses explicam o mesmo número.

Um repositório **nosso**, pequeno, rodável, com defeitos plantados que a gente
conhece, transforma isso em número. E é o mesmo ativo do "repo de demonstração"
da seção A — uma coisa serve às duas.

### 🚨 A armadilha, e ela é a mesma do árbitro

**Quem planta o defeito e escreve a lente é a mesma pessoa.** O risco é plantar
exatamente o que as seis lentes já procuram, medir 100%, e ter medido o próprio
reflexo. Foi o que os 94 árbitros fizeram: mediam contaminação e pareciam rigor.

O `desafio` valeu justamente porque **o Carlos plantou, não nós**.

Quatro defesas, e nenhuma é opcional:

1. **Taxonomia externa.** Os defeitos saem de OWASP/CWE ou de CVE real, não de
   "o que a nossa lente pega". A lista de defeitos é escrita **antes** de olhar
   os prompts.
2. **Um planta, o outro não olha.** Entre Luis e Mariano, quem plantou não roda
   a medição.
3. **Defeitos fora do alcance, de propósito.** Race condition, por exemplo — a
   rodada de 14/08 já produziu um INCONCLUSIVO honesto justamente aí. Sem eles,
   a bancada mede um mundo onde tudo é provável e a taxa de inconclusivo parece
   defeito nosso.
4. **PRs limpos como controle negativo.** Já provamos que isso importa: 8/8
   refutados num PR sem defeito é metade do valor do produto.

### 🚨 O gabarito NÃO PODE morar no repositório da bancada

Os promotores leem o repo. O advogado tem `read_file` e `grep`. Um arquivo
`GABARITO.md` na árvore é resposta chumbada servida na bandeja — e o pior é que
a rodada pareceria excelente.

O gabarito fica **fora**: outro repositório, ou um arquivo que o harness de
medição lê e o agente nunca alcança. Vale um teste mecânico que falhe se a
palavra do gabarito aparecer na árvore sob revisão.

### 📍 Estado em 15/08 — a bancada existe, e já se pagou antes de medir

**Pronta:** app de projetos/tarefas rodando, `main` conferido limpo com 11
asserções de isolamento, os **quatro PRs plantados e verificados exploráveis**,
gabarito escrito em `bancada_gabarito.yml` (fora da bancada, de propósito).

### ✅ MEDIDA em 15/08 — 3 de 4, e o quarto foi gabarito meu errado

| PR | esperado | veio | |
|---|---|---|---|
| IDOR (CWE-639) | PROVADO | PROVADO:3 | ✅ |
| SQLi (CWE-89) | PROVADO | PROVADO:2, INCONCLUSIVO:1 | ✅ |
| race (CWE-367) | INCONCLUSIVO | PROVADO:4, REFUTADO:4 | ❌ *(ver abaixo)* |
| limpo | REFUTADO | REFUTADO:3 | ✅ |

**Os quatro desfechos são diferentes entre si** — o critério de instrumento
calibrado. E os quatro juntos custaram **145 mil tokens de entrada**, menos que
**uma** das rodadas quebradas.

**No PR limpo: 3 refutados, zero condenações.** Pegou inclusive uma premissa
alucinada do promotor (*"`ONLY_FULL_GROUP_BY` é do MySQL e não se aplica"*).

#### 🚨 O produto corrigiu o meu gabarito

Escrevi INCONCLUSIVO para o race partindo de *"é impossível provar sem
concorrência"*. **A premissa era falsa.** Ele provou a **precondição** — que a
garantia de unicidade sumiu — com teste que passa no base e falha no head, e
declarou a limitação no motivo: *"não houve prova pela API porque chamadas
sequenciais não expõem a janela de corrida"*.

É *"escreva o teste sobre a INVARIANTE, não sobre o endpoint"* aplicado a
concorrência. A R2 rebaixou para MÉDIA sozinha, por não ser ponta a ponta.

⚠️ E o PR 3 tinha **dois** defeitos: eu plantei um segundo sem querer
(`convidado_por` fora do contrato de resposta) ao alargar a janela do race. O
Veredito achou os dois. O gabarito diz "um defeito por PR" e fui eu que quebrei.

#### O que a medição ensinou sobre seleção

Com `--top-n 3` o defeito do race **não foi julgado**: 8 das 24 acusações o
nomearam, nenhuma entrou. Com `--top-n 8`, entrou e foi provado.

Três hipóteses testadas por contrafactual sobre os dados reais, **duas
erradas**:

| hipótese | medido |
|---|---|
| consenso no ranking resolve | **zero efeito**, 3 de 3 PRs |
| soltar `MAX_POR_LOCAL`/cota resolve | **zero efeito** |
| expansão por área cega resolve | ✅ alcança o defeito com **1** extra |

O consenso ficou como **sinal auditável** (discrimina defeito de ruído em 4 de
4: o PR limpo tem 14 acusações brutas, mais que o do IDOR, e nenhum aglomerado
passa de 2 lentes) — não como entrada de seleção, que a medição não sustenta.

#### 🚨 O que as duas rodadas compraram: cinco suposições do desafio chumbadas

Nenhuma era encontrável por dentro. **Os 382 testes rodam todos contra o
desafio**, então tudo que é específico dele é invisível para eles.

| # | estava fixo no código | fora do desafio |
|---|---|---|
| 1 | rota `/auth/login`, campos `password`/`access_token` | login 404 — **nenhuma** prova ponta a ponta |
| 2 | teste gravado em `app/api/tests` | `FileNotFoundError` **depois** de o advogado escrever o teste |
| 3 | alvo do pytest `tests/` | `file or directory not found` |
| 4 | `.env` vencendo o `veredito.yml` | revisaria um projeto **conversando com o app do outro**, e o pré-voo diria `health -> 200` |
| 5 | `kb:kb@db` no banco descartável | suíte inteira com `password authentication failed` |

Mais o `BadRequestError` do bloco `fallback`, que derrubava o **fechamento
forçado** — justamente a rede que impede o teto de voltas de custar a perícia.

⚠️ O item 4 é a instância mais perigosa: **o pré-voo passava verde**. `read_file`
e `grep` funcionam em qualquer layout, e `http_request` só testava `/health`,
que responde sem autenticação. Duas sondas novas (**login** e **destino do
teste**) teriam abortado no primeiro segundo em vez de gastar US$2.

> **A bancada funcionou como instrumento de diagnóstico antes de funcionar como
> régua.** Foi a resposta empírica para "vão aparecer bugs novos?", perguntada
> em 14/08: apareceram cinco, e só apontando o produto para um segundo projeto.

#### 🎯 O que falta, e é o topo da fila

✅ **O parecer confessa o escopo** *(15/08)*. Abre com *"25 suspeitas
levantadas, 8 testadas dentro do orçamento da rodada (TOP_N=8)"*, e a seção
`LEVANTADAS E NÃO TESTADAS` lista cada uma com posição na fila e motivo.
`escopo.json` é gravado **antes** do laço caro; as contagens viraram *"das
examinadas"*, então o cabeçalho parou de implicar completude mesmo sem escopo em
disco (rodadas anteriores reconstroem a contagem pelas brutas e **dizem** o que
não dá para reconstruir).

> ⚠️ E o dado real corrigiu a redação: a 9ª e a 10ª da fila **ganharam** vaga de
> cota e o teto chegou antes, mas o motivo saía *"vaga da cota"* dentro da lista
> de não-testadas — o campo descrevia a posição e era lido como a exclusão.

✅ **O critério da bancada conta os dois defeitos do PR 3** *(15/08)*. E o
conserto era maior do que "contar dois": o critério era `bateu = existe algum
PROVADO`, que é verdade também quando o PROVADO fala de outra coisa. **As
`pistas` existiam e só eram consultadas no ramo do fracasso** — a guarda ficava
muda exatamente no falso ACERTO. É o padrão de bug do projeto **dentro da régua
que deveria medi-lo**.

Agora cada defeito plantado exige um veredito com o desfecho esperado *sobre uma
acusação que fala dele*; defeito sem `pistas` **levanta** em vez de pontuar
generoso; e o casamento é contra os campos semânticos, não contra `str(a)` — ali
dentro vão `"id": "injection_01"` e `"categoria": "injection"`, e a pista mediria
de qual promotor a acusação veio.

**Reaplicado offline às quatro rodadas de 15/08: 4 de 4**, com o PR 3 confirmando
os dois defeitos separadamente. ⚠️ Não é medição nova — são as mesmas rodadas
repontuadas pelo critério novo, sem gastar.

As pistas foram **validadas contra as acusações reais** das quatro rodadas, e o
PR limpo dá **zero em todas as quatro** — o controle negativo que importa. (A
pista `race` solta casava dentro de *"trace"*; levou borda de palavra.)

**Rodar de novo com a expansão ligada** (~US$1) para ver se ela alcança o race
sem precisar de `--top-n 8`. O contrafactual diz que sim; falta o dado real.
**É o topo da fila agora.**

### 🩺 Versão reduzida: QUATRO PRs primeiro

**Não construir a bancada completa antes de saber se o instrumento mede.** É a
mesma disciplina do princípio nº 2 — pipeline inteiro rodando cedo, mesmo burro,
antes de refinar peça. Vale para a bancada também.

Bancada de 10 PRs custa 2–3 dias e US$4–13 por varredura, e você só descobre no
fim se ela mede o que devia. Quatro PRs custam meio dia e ~US$2, e respondem a
mesma pergunta de instrumento.

| PR | o que carrega | o que ele mede |
|---|---|---|
| 1 | defeito **ao alcance** (ex.: injection num caminho de escrita) | o motor prova o que dá para provar? |
| 2 | defeito **ao alcance**, de outra categoria | uma lente diferente acorda, ou só a de injection funciona? |
| 3 | defeito **fora do alcance** (race condition / check-then-act) | ele responde INCONCLUSIVO com causa, ou inventa prova? |
| 4 | **nenhum defeito** | ele refuta com motivo, ou condena por condenar? |

**Os quatro desfechos esperados são diferentes entre si** — provado, provado,
inconclusivo, refutado. Se os quatro derem a mesma coisa, o instrumento está
quebrado, e isso aparece por ~US$2 em vez de US$13.

O PR 3 é o menos intuitivo e o mais valioso: a rodada de 14/08 já produziu um
INCONCLUSIVO exemplar em concorrência — *"as ferramentas disponíveis são
sequenciais, não há artefato determinístico possível"*. Esse comportamento é
ativo, não falha, e sem um PR assim a bancada não consegue medi-lo.

**Só depois de os quatro se comportarem** vale construir os outros seis.

### Como seria

| passo | nota |
|---|---|
| 1. `veredito.yml` | **pré-requisito duro.** Hoje `config.py:155` chumba os quatro usuários; sem isso a bancada só funciona se ela imitar o desafio, e aí não prova generalização nenhuma |
| 2. app mínimo rodável | API + banco + suíte. Rodável é obrigatório: sem app no ar só se mede o promotor, e o diferencial é a prova por execução. **E fácil de mexer** — bancada em que dá trabalho acrescentar um PR não é usada, e isso é requisito, não conforto |
| 3. os 4 PRs acima | um defeito por PR: com dois, fica ambíguo qual condenação corresponde a qual, e a conta de recall vira palpite |
| 4. rodar e contar | recall, precisão, e a **distribuição dos inconclusivos com causa** — as três, nunca só a primeira |
| 5. *(depois)* mais 6 PRs | só se os quatro primeiros se comportarem |

### O que ela permite dizer, e que hoje é proibido

> *"Provou 4 dos 5 defeitos plantados, com artefato reproduzível."*

Isso hoje é alegação sobre gabarito que não temos — está listado nos 🚫 do
`CLAUDE.md`. Com a bancada, passa a ser verdade conferível. É a frase que muda
uma conversa de investidor.

⚠️ Com quatro PRs o n é pequeno demais para essa frase. A versão reduzida prova
que **o instrumento funciona**, não que o produto acha defeito. As duas coisas
são diferentes, e confundi-las seria o erro dos 45% de árbitro outra vez.

### ⚠️ Custo

Cada rodada completa custa US$0,40–1,30. **Quatro PRs ≈ US$2 por varredura**;
dez, US$4–13. Toda mudança de prompt pede varredura nova, então isso vira o
maior item de custo recorrente do projeto — e é o preço de parar de andar às
cegas.

### 🚫 E a regra que a bancada compra

**Nunca calibrar prompt na bancada inteira.** Ajustar as lentes até a bancada
dar 100% é decorar a prova. Separar um conjunto de PRs que só é rodado no fim,
e nunca olhado durante o ajuste.

---

## 📍 16/08 — o dia da troca de máquina, e o que ela expôs

A máquina nova funcionou como **segundo ambiente**: o mesmo papel que a bancada
faz para o produto, ela fez para a toolchain. Nada disso era encontrável na
máquina antiga.

### Achados de produto (os que valem)

**🚨 O `provado_se` decide o veredito.** `ACHADO_PROVADO_SE_DECIDE_O_VEREDITO.md`.
O mesmo defeito, a mesma regra citada com procedência, as mesmas ferramentas —
e o veredito virou conforme o experimento que o *promotor* prescreveu. Quem
mandou `grep` produziu REFUTADO; quem mandou `chamar` produziu PROVADO com
prova diferencial. `padroes.md` mandava ler em 57% das acusações; as outras
cinco lentes, em 0–8%.

Consertado e **medido em A/B** (2% → 41% de execução, consistente nos três
diffs). A classe que causou a absolvição falsa — forma da resposta — foi de 11%
para 82%.

**🚨 O retrato do banco dizia "limpo" sem ter olhado.** Seis rodadas gravaram
`"limpo": true` com o psql falhando nos dois lados. `-U kb` chumbado contra a
bancada, que usa `bancada`; `delta_do_banco` lia só `tabelas` e ignorava `erro`.
O console imprimia a **mesma frase do sucesso**. Consertado: `medido: False` +
causa, e levanta se a contenção estava ligada.

**🚨 Os scanners falhavam calados.** `bandit` ausente virava `[]` e o log dizia
"0 achado(s)" — idêntico a "rodou e não achou". Agora levantam, e o pré-voo os
expõe. ⚠️ E eles **funcionam**: 13 corroborações do bandit, 20 do semgrep nas
rodadas gravadas — mas quase todas contra o desafio; na bancada dão ~0, o que é
esperado e não é sintoma.

### Ferramenta nova

**`experimento_prompt.py`** — A/B de prompt de promotor. Mesmo diff, mesmo
modelo, N repetições, só o prompt mudando. Haiku, centavos, um minuto.

🚨 **Ele existe porque a varredura da bancada NÃO distingue melhora de
variância.** A varredura pareceu confirmar o conserto do `padroes` e não
confirmava: as outras cinco lentes, que ninguém tocou, tinham se movido junto.
Com 2–4 acusações por PR, "melhorou" e "variou" têm a mesma cara — e a varredura
custa ~US$2 para não responder.

### A bancada

✅ **Está no GitHub** (`luisfelp07/bancada`, privado). O 404 dele mente: privado
sem acesso responde "not found", que se lê como "não existe".

✅ **Tags `medicao-15ago/*`** preservam os SHAs medidos, que estavam soltos e a
um `git gc` de sumir. Correspondência no `LEIA.md` da pasta de evidência.

✅ **O controle negativo voltou a ser negativo.** Ele condenava com razão: o PR
"limpo" adicionava agregação sobre FK sem índice, com prova diferencial e
`EXPLAIN` mostrando `Seq Scan`. Foi a **terceira vez que o produto corrigiu o
gabarito**. `index=True` em `Task.project_id`, e a rodada de verificação deu
`REFUTADO:4`, zero condenações.

⚠️ **Placar retroativo:** as medições anteriores a 16/08 foram feitas com o
controle negativo cego. O que se afirma com segurança é sobre as rodadas de hoje
em diante.

✅ **A expansão foi validada.** Com `--top-n 3` ela alcança o defeito do race,
que antes exigia `--top-n 8`. E é também ela que alcançou o achado do PR limpo —
o mecanismo compra cobertura, e cobertura encontra o que o gabarito não previa.

### 🚨 O vão que sobrou, e é decisão tomada

O `contencao_app.py` de 14/08 fechou o `http_request` **pelo lado do banco**. A
rede não. Não há função de rede naquele módulo.

A análise de 10/08 (no vault, `conversas/2026-08-10`) tratou disso a fundo — a
tabela de irreversibilidade (email, cobrança, webhook, SMS), o diagnóstico
(*"o denominador comum é a rede"*) e a decisão: rede interna **só no base**,
porque a CI do cliente já roda o head. O limite ficou escrito em
`config.py:208`.

⚠️ **Mas aquela análise é sobre a SUÍTE.** O argumento da assimetria não
transfere para o `http_request`: a CI do cliente roda a suíte dele todo dia;
ela nunca dá `POST /convite` com o payload do advogado.

**Decidido em 16/08: fica assim.** Nenhum dos dois apps revisados manda e-mail,
e a contenção do app está desligada por padrão. Quando for atacar, o gancho é o
`aponta_api_para`, que já recria o container — e o lugar de *demonstrar* é o
repo de demonstração, com um **canário de egresso** (endpoint que tenta sair
para um coletor nosso), não um envio de e-mail de verdade.

🚫 E a restrição de 10/08 vale: *"não detectar `smtplib`, não mapear serviços
conhecidos, não manter lista de APIs perigosas — é predição, e predição já
perdeu duas vezes"*.

### O que 16/08 deixou aberto

| item | custo | o que responde |
|---|---|---|
| **Canário de egresso** | junto com o repo de demo | a única camada de contenção sem validação empírica em qualquer direção |
| ✅ **`CLAUDE.md:407`** *(16/08)* | | dizia "banco descartável, rede sem saída ✅ 14/08" para o `http_request`; só o banco foi |
| ❌ **A lente de `performance`** | *investigada, não é defeito* | ver abaixo |

#### ❌ A lente de `performance` — levantada e derrubada no mesmo dia

Ficou registrado que ela tinha 48 de 78 `provado_se` sem experimento
(`descrição`) e que era "a próxima pedra da mesma calçada". **Investigado: não
é.** Descrição dá 5 PROVADO / 0 REFUTADO / 2 INCONCLUSIVO (n=7); execução dá
2/1/0 (n=3). As duas inconclusivas são infraestrutura, não fraseado.

O erro foi de categoria: `descrição` e `leitura` não são a mesma coisa, mesmo o
classificador chamando as duas de "não-execução". **Leitura desvia** o advogado
para um método que absolve falso; **descrição deixa o método aberto**, e ele
escolhe um bom sozinho. O PROVADO do PR limpo veio de uma descrição sem medida
citada — o advogado inventou a carga e o `EXPLAIN`.

🚫 **Não mexer no `padroes.md`-style aqui.** Seria otimizar a métrica contra o
conteúdo. Detalhe em `ACHADO_PROVADO_SE_DECIDE_O_VEREDITO.md`.

### D — Dívida

- **Versionar o `CLAUDE.md`** — mora fora do repo, sem histórico
- **Juiz sem síntese** — `MODEL_JUIZ` está no config e nunca é consumido; hoje
  ele só é consumido pelo `experimento_adaptador.py`, como revisor externo dublê
- ✅ **Artefatos no `.gitignore`** *(13/08)* — rodada nova grava em
  `saidas/rodadas/<carimbo>/artefatos/`, que já é ignorado. `artefatos/` na raiz
  ficou como legado do que está commitado
- ✅ **`ERRO` como convenção de string** *(13/08)* — era o **caso vivo** do
  padrão de bug. Quem sabe que falhou passou a ser quem falhou: a ferramenta
  registra o desfecho, e a string virou só o que o modelo lê. Três travas
  mecânicas seguram a convenção nova, e as três foram **provadas não-mudas**
  injetando a violação de propósito

### E — Capacidade que falta (não é "fazer", é "não sabemos ainda")

- **Escala**: repositório grande derruba a leitura (220s/acusação no next.js)
- **Concorrência**: race condition e check-then-act são invisíveis — nenhuma
  ferramenta dispara requisições em paralelo
- **Prova diferencial em superfície nova**: 404 no base é o inverso do padrão

---

## Posicionamento — a discussão de 10/08

Levantada depois da conversa com o Carlos. **Nada foi decidido**; é decisão de
sócio, entre você e o Mariano.

### O reenquadramento

Há **um ativo provado** e dois não provados:

| | estado |
|---|---|
| o verificador refuta ruído com motivo | **medido**: 68% em repo de terceiro, 8/8 em PR sem defeito |
| os promotores acham defeito real fora do desafio | **desconhecido** — não existe gabarito |
| a prova por execução em ambiente que não preparamos | parcial: leitura sim, ponta a ponta não |

A metade "achar" é a lotada (Cursor comprou a Graphite acima de ~US$290M;
Greptile já revisou 1 bilhão+ de linhas) e a que **não dá para medir sem
gabarito**. A metade "matar alegação falsa" é a provada, a vazia de concorrente,
e a que tem crise datada — o curl fechou o bug bounty com confirmação abaixo de
5%.

**Daí a hipótese: o produto é o verificador, não o pipeline.** A entrada não
precisa ser um PR — pode ser uma fila de alegações.

### Medido a favor

- prosa de revisor genérico → **90%** vira alegação testável (num PR com defeito)
- os 5 defeitos reais foram recuperados **sem os promotores**
- 26 refutações usaram **só `read_file` e `grep`** — sem app rodando

### Medido contra, e as ressalvas

- **a variável dominante é o repo ter defeito**, não o formato da fonte. Em PR
  de manutenção a conversão cai para 10–20%
- scanner **não** rende mais por dólar (1,09×)
- o "revisor externo" testado era o Sonnet 5 com prompt genérico — stand-in
  fiel, mas **não é o produto do Greptile**
- n pequeno: 10 achados, 1 PR com defeito

### Por que Action e não bot hospedado

O produto precisa **rodar o app do cliente**. Um bot hospedado exigiria clonar o
código e subir o stack de cada cliente na nossa infra — pesadelo de segurança
para dois sócios, e o comprador que mais precisa é justo quem não deixa o código
sair.

A CI dele **já faz** checkout de base e head, já sobe o app, já roda testes.
A Action inverte a restrição em vantagem. E banco descartável, que a contenção
de 11/08 exige, já é o normal numa CI.

---

## As decisões que custaram caro

Sete, e as três que mais importam hoje:

1. **INCONCLUSIVO não é REFUTADO.** Somar os dois é absolvição falsa.
2. **Contenção, não predição.** Adivinhar o que o código do cliente faz perdeu
   duas vezes em 11/08; impor a fronteira de fora funcionou nas duas.
3. **Regra sem procedência é opinião.** Comprou o conserto do árbitro.

E o padrão de bug do projeto, com sete instâncias, está no `CLAUDE.md` com as
quatro perguntas de busca. Se for caçar bug amanhã, comece por ali — não por
regras faltando, mas por **regras que existem e ficam mudas**.
