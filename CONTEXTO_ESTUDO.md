<!-- tag: hack2l -->

# Veredito — contexto completo para estudo

Documento autocontido. Escrito para ser lido (ou colado numa IA) por alguém que
não acompanhou a construção. Explica **o que construímos, por que cada decisão
foi tomada, e o que descobrimos medindo** — inclusive os erros, que são a parte
mais instrutiva.

Projeto: **Veredito**, hackathon Hack2L, 08/08/2026. Time de 2. ~5h de
construção. Estado deste documento: 14h00 do dia da construção.

---

# PARTE 1 — O problema

## O desafio

Os organizadores entregam um **pull request** num app real (RAG sobre
documentos: FastAPI + Next.js + Postgres com pgvector). O PR adiciona
compartilhamento de documentos entre usuários.

Três coisas tornam o problema interessante:

1. **O PR tem defeitos plantados E falsos alarmes deliberados.** Código que
   parece errado e está certo, misturado com código que parece certo e está
   errado.
2. **A contagem não é revelada. Não existe gabarito.** Você nunca sabe se achou
   tudo, e não pode calibrar contra uma resposta.
3. **Parte do código sob revisão são instruções em texto para um modelo.** A
   regra não está trancada no código — está num prompt que o modelo pode ou não
   obedecer.

O autor do desafio, Carlos Dutra, deu a régua em voz alta:

> *"Passar um defeito real é mais problemático do que um falso alarme. No falso
> alarme, o importante é ser interpretável... precisão vale tanto quanto
> cobertura."*

## Por que isso não é um problema resolvido

Ferramentas de revisão por IA existem e são boas em *afirmar*. O modo de falha
delas é o mesmo há anos: **enchem o PR de alarme até o revisor parar de ler.**

O número que ancora isso: **o curl fechou o programa de bug bounty no fim de
janeiro de 2026.** A taxa de confirmação, acima de 15% por anos, caiu abaixo de
5% em 2025 com a enxurrada de relatórios gerados por IA. Pagaram US$100 mil por
87 vulnerabilidades antes de desligar o programa. Imprecisão de IA já matou uma
instituição inteira.

---

# PARTE 2 — A tese

> **Nada vira parecer sem prova reproduzível. A severidade acompanha a FORÇA DA
> PROVA, não a gravidade teórica. Nada é descartado em silêncio.**

Três consequências, e cada uma é uma decisão de produto:

**1. O veredito final é um exit code, não opinião de modelo.** Se o modelo diz
"provado" e o artefato diz que não, ganha o artefato. Isso precisa ser *código*,
não intenção — voltaremos a isso na Parte 6, porque foi exatamente aí que
erramos.

**2. Existem três resultados, não dois.** Provado, refutado, e **inconclusivo
com a causa**. Sem o terceiro, toda falha de execução vira absolvição.

**3. O que foi descartado aparece no parecer, com motivo.** É a peça que
transforma "menos ruído" em interpretabilidade: *"toda ferramenta te enche de
alarme falso até você parar de ler; esta te mostra o que descartou e por quê."*

---

# PARTE 3 — A arquitetura

**Promotores acusam → advogado testa → juiz sentencia.** Um orquestrador, três
tipos de chamada, cada um com um modelo de custo diferente.

```
acusações = []
para cada lente em [injection, vazamento, correção, padrões, performance, PRD]:
    acusações += chamada_de_modelo(prompt, diff)      # paralelo, Haiku 4.5

veredictos = []
para cada acusação em acusações[:TOP_N]:
    veredictos.append( advogado(acusação) )           # ← o loop caro, Opus 5

parecer = chamada_de_modelo(prompt_do_juiz, veredictos)   # Sonnet 5
```

*"Haiku para gerar hipóteses, Opus para verificar, Sonnet para sintetizar —
modelo caro só onde a decisão acontece."*

## 3.1 Promotores — o trabalho deles é COBERTURA, não seletividade

Seis lentes em paralelo, cada uma com contexto próprio. Leem o PR e o código em
volta. Queremos **volume**: acusar é barato, e essa lista bruta ninguém vê.

⚠️ **A armadilha:** o prompt do promotor não pode pedir seletividade. Escrever
*"reporte apenas problemas relevantes"* faz o modelo se autocensurar — modelos
seguem filtro de severidade ao pé da letra e você perde recall sem perceber. A
filtragem é trabalho do advogado, que tem ferramenta para decidir.

Medido: **55 acusações brutas em ~20 s.**

## 3.2 Advogado — a única peça que é agente de verdade

Loop: pensa → ferramenta → resultado → decide. **Ele não argumenta, TESTA.**

Vê **uma acusação por vez, isolado**. Duas razões, e a segunda é econômica:

- uma acusação fraca não contamina a próxima;
- o prefixo (o diff do PR) fica idêntico em todas as chamadas, e o cache paga.
  Medido: **~55–65 mil tokens lidos de cache por acusação.**

### A prova diferencial — o coração do produto

O advogado escreve um teste e roda **nos dois lados**: commit base e head do PR.

```
pytest no base  → exit_base
pytest no head  → exit_head
pytest no base  → confirmação (só para candidato a PROVADO)
```

Só é **PROVADO** se **passa antes e falha depois**. Consequências:

- O falso alarme plantado se elimina sozinho: passa nos dois lados.
- A evidência vira *"este teste passa no seu código de hoje e quebra com a sua
  mudança"* — que é uma frase que um humano não precisa confiar em ninguém para
  verificar.
- **A terceira execução** (base de novo, depois do head) mata dois falsos
  positivos: teste não-determinístico, e poluição de estado. O head sempre roda
  depois, então "passou antes, falhou depois" poderia ser a *ordem* e não o
  código.

### O teste é sobre a INVARIANTE, não sobre o endpoint

Uma sutileza que custa caro se ignorada. O PR adiciona **endpoints novos**.
Prova diferencial não funciona neles do jeito ingênuo:

```
ruim:  "GET /shared/1 como carol devolve 200"   → 404 no base → inconclusivo
bom:   "carol não alcança o documento de alice
        por nenhuma rota"                        → passa no base (não havia como
                                                   vazar), falha no head. PROVADO.
```

A invariante quase sempre já vale no commit base — **é por isso que ela é
invariante.** Formule assim e a prova diferencial serve para os dois casos.

### Causalidade e alcance são provas diferentes

| prova | responde | artefato |
|---|---|---|
| teste diferencial | *foi esta mudança que quebrou* | `prova_<id>.json` |
| `http_request` | *dá para fazer isso de fora, agora* | `http_<id>.json` |

São coisas diferentes, e as duas juntas valem mais. Só a segunda sustenta
severidade alta — a primeira é rebaixada automaticamente.

## 3.3 Juiz — a parte que não pode ser opinião

Regras determinísticas, em ordem, todas com teste, todas rodando sem rede:

| regra | o que faz |
|---|---|
| **R0** | o artefato ganha do advogado quando os dois discordam |
| **R0b** | quem decide `prova_ponta_a_ponta` é o artefato HTTP, **sempre** |
| **R4** | REFUTADO em `injection` com LLM alvo dublê → INCONCLUSIVO |
| **R3** | execução falhou → INCONCLUSIVO, nunca absolvido |
| **R1** | CRÍTICA sem árbitro citado → SUSPEITA |
| **R2** | prova que não é ponta a ponta não passa de MÉDIA |

**Por que isso é código e não prosa:** regra escrita em prosa não acontece às
14h30 com 12 achados e vídeo para gravar. Vira código ou não existe. É isso que
impede o alarme crítico errado **mecanicamente**, em vez de por disciplina
humana sob pressão.

Todo rebaixamento sai **impresso no parecer**. Rebaixar sem dizer por que é tão
opaco quanto não rebaixar.

---

# PARTE 4 — O terceiro estado, e por que ele é obrigatório

Este é o ponto conceitual mais importante do projeto inteiro.

O advogado dispara payloads de injection. Três coisas podem acontecer que **não
são** "o app resistiu":

1. O classificador de segurança da API recusa. Vem como **HTTP 200** com
   `stop_reason == "refusal"` e `content` vazio — não como erro.
2. O app alvo está sem chave de LLM e responde a mesma string enlatada para
   qualquer pergunta. O payload "não funcionou" porque **nada** funciona.
3. Docker cai, timeout, teste não coleta.

Nos três casos, um veredito binário produz **absolvição limpa**. E o pior é o
que isso parece: a categoria carro-chefe se esvazia sozinha e **parece rigor**.

```
se timeout, parse quebrado, ferramenta falhou ou stop_reason == "refusal":
    veredito = INCONCLUSIVO      # nunca ABSOLVIDO
```

**Ausência de observação não é refutação.** REFUTADO é um resultado forte e
significa uma coisa só: você testou, o teste rodou, e a acusação não se
sustentou.

---

# PARTE 5 — Os números medidos

Nada aqui é estimativa.

| | |
|---|---|
| 6 promotores (Haiku, paralelo) | ~20 s, **55 acusações brutas** |
| rodada completa, 10 acusações ao advogado | **856 s = 14,3 min** |
| resultado dessa rodada | 5 condenados, 1 descartado, 4 inconclusivos |
| custo da rodada | 149.918 entrada / 30.192 saída / **560.985 de cache** |
| 1 acusação no advogado | ~90–130 s, 2 a 10 voltas de ferramenta |
| prova diferencial | ~14 s (21 s quando há confirmação no base) |
| suíte de testes do produto | 101 rápidas (~31 s) + 5 lentas |

O cache é a linha mais interessante: **560 mil tokens lidos a ~10% do preço**,
porque o diff do PR é o mesmo prefixo em toda chamada. Isso é arquitetura, não
otimização — veio da decisão de dar uma acusação por vez ao advogado.

---

# PARTE 6 — Os erros. A parte mais instrutiva.

Tudo abaixo foi descoberto **medindo**, não revisando. Cada um estava
funcionando "sem erro" — que é o modo de falha caro.

## 6.1 O furo da Regra 0 — o mais grave

A R0 existe para garantir que o LLM não sobrescreva o exit code. O código era:

```python
if artefato is not None:
    if advogado_disse_provado and artefato["estado"] != "PROVADO":
        vale_o_artefato()
    # ↓ e aqui dentro, o aterramento da prova ponta a ponta
    v["prova_ponta_a_ponta"] = declarado_pelo_modelo and artefato_provou
```

**O problema:** `http_request` não gravava artefato nenhum. Então numa acusação
provada só pela API, `artefato is None`, o bloco inteiro era pulado, e a
**auto-declaração do advogado passava sem conferência**.

Combinado com a R2 (*"só prova ponta a ponta sustenta severidade alta"*), o
resultado é que **a palavra do modelo sozinha podia sustentar CRÍTICA** — o
oposto exato do que a regra existe para fazer.

E na outra ponta, o parecer imprimia `EVIDENCIA: nao fechou` para um defeito que
o advogado tinha visto acontecer com os próprios olhos.

> **A lição que generaliza:** *uma guarda que só roda quando já existe evidência
> fica muda exatamente onde a evidência falta — que é onde ela mais importa.*

O conserto: `http_request` grava artefato a cada chamada; o aterramento saiu de
dentro do `if` e virou um AND — o modelo alega, o artefato corrobora.

## 6.2 O regex ganancioso que engolia veredictos

O advogado responde JSON. O parse tinha um fallback explícito para uma acusação
provada não sumir por erro de formato:

```python
m = re.search(r"\{.*\}", texto, re.DOTALL)   # ← ganancioso
```

`.*` com DOTALL casa do **primeiro** `{` até o **último**. E o advogado escreve
prosa antes do JSON. Numa rodada real a prosa citava `` `email = '{email}'` `` e
a rota `` `/documents/{id}/share` ``. O span começou em `{email}`, o parse
quebrou.

**Resultado: 2 de 10 acusações com artefato PROVADO no disco viraram
INCONCLUSIVO por formatação.**

> **A lição:** *o fallback que existia para impedir a perda silenciosa era, ele
> mesmo, a perda silenciosa.* Um `try/except` genérico faz o erro parecer
> tratado.

Conserto: `raw_decode` a partir de cada `{`, do fim para o começo; ganha o
último objeto válido que tenha a chave `veredito`.

## 6.3 "Recusa do classificador" — causa que não aciona nada

Duas acusações morreram com a mensagem *"recusa do classificador (cyber)"*.
Verdadeira, e inútil: não diz o que fazer.

Fomos ler o SDK instalado (não a memória) e descobrimos que a configuração de
fallback estava **correta** — `cyber` é categoria coberta, o parâmetro é aceito.
Logo a recusa significava uma de duas coisas, e nós descartávamos justamente o
campo que distingue:

- `recommended_model` preenchido → **o fallback nem foi tentado** (rate limit ou
  sobrecarga). Acionável: tentar direto nesse modelo.
- sinal de fallback presente → rodou e **também** recusou. Cadeia inteira negou.

E teve um segundo erro em cima do primeiro: eu conferia só o sinal canônico
(`usage.iterations`), e medindo descobri que **no caminho de streaming ele não
vem**. Todo fallback pareceria "não aconteceu". Agora são três vias, e sem
nenhuma delas o texto diz que não dá para afirmar — o terceiro estado aplicado
ao próprio diagnóstico.

## 6.4 O app servia o commit errado

O container serve o código **assado na imagem**, não o checkout do repo. A
máquina estava com a imagem construída a partir da `main`, então:

- `http_request` nunca alcançava o código do PR;
- `prova_ponta_a_ponta` era estruturalmente impossível;
- a R2 rebaixava **tudo** para MÉDIA.

E o sintoma não parece problema de ambiente — **parece o produto não
funcionando.** Numa validação entre duas máquinas, isso queima um ciclo inteiro
de feedback com um bug que não existe. Virou checagem automática que compara os
routers do worktree com os de dentro do container.

## 6.5 `docker compose` devolve exit 1 igual a "teste falhou"

`docker run` puro usa **125** para falha de infraestrutura. **`docker compose`
usa 1** — o mesmo código que o pytest usa para "teste falhou". Medido com daemon
inalcançável, serviço inexistente, mount inválido: **todos exit 1**.

Consequência: um flap do healthcheck do banco entre as duas execuções vira
**acusação crítica falsa**. E docker ruim no início mandava o advogado
*"reescrever o teste para passar no código de hoje"* — instrução para
**enfraquecer um teste correto**.

Conserto: não se pergunta ao exit code se o pytest rodou. Pergunta-se ao pytest
— exige-se a linha de resumo (`N passed`, `N failed`, `no tests ran`) na saída.

## 6.6 Os menores, que também custariam

- **`localhost` resolve `::1` primeiro** no Windows e o caminho IPv6 do Docker
  pendura. 0/8 sucesso em `localhost`, 8/8 em `127.0.0.1`. E é *ReadTimeout*,
  não connection refused — cada chamada gasta o timeout inteiro antes de virar
  inconclusivo. Em massa, a categoria de segurança esvaziaria parecendo rigor.
- **App alvo sem chave de LLM** responde a mesma string para qualquer pergunta.
  Detecção: duas sondas sem nada em comum devolvendo a mesma resposta provam que
  o modelo não leu nenhuma das duas. Note que a detecção **não** compara com a
  string enlatada — isso quebraria se o texto mudasse.
- **Worktree obsoleto:** os ponteiros de worktree do git são caminhos
  **absolutos**, chumbados em quem criou. Clonar em outra máquina encontra um
  ponteiro para caminho que não existe, o `worktree add` falha, e a prova roda
  no **commit errado** registrando no artefato o commit que se pediu, não o que
  se montou. Falso negativo mudo.
- **Sonda virando evidência:** a medição de ambiente batia na API antes de
  existir acusação, e gravava artefato no diretório que o parecer cita como
  prova.

---

# PARTE 7 — As lições que generalizam

Estas valem fora deste projeto. São o que eu levaria para qualquer sistema que
usa LLM para tomar decisão.

**1. A guarda muda.** Uma verificação que depende da existência de evidência
fica silenciosa exatamente no caso em que a evidência falta. Pergunte sempre:
*"em que caminho esta regra NÃO roda, e é justamente o caminho perigoso?"*

**2. O fallback que engole.** `try/except` genérico e regex tolerante fazem o
erro parecer tratado. Se o fallback existe para impedir perda silenciosa,
teste-o com a entrada real que ele deveria salvar.

**3. Meça, não lembre.** Duas vezes a resposta estava no SDK instalado, e as
duas vezes a memória teria dado a resposta errada — sobre o parâmetro de
fallback e sobre qual sinal aparece em streaming. Ler o código instalado custa
30 segundos.

**4. Guarda que nunca falhou não é guarda.** Escreva o teste negativo. E quando
ele "provar" que a guarda não funciona, desconfie do teste primeiro: o meu
estava invertido e quase me fez desfazer código correto.

**5. Nome que promete demais é dívida.** Um campo chamado `alcancado` que
significa "a chamada completou, inclusive um 404" mente para quem lê o artefato.
Renomeamos para `alcancou_a_api` e travamos a semântica num teste, para ninguém
"consertar" achando que é bug. Num produto cuja tese é *não afirmamos sem
prova*, o vocabulário é parte do produto.

**6. O contraste é a prova.** A evidência por API imprimia só a última chamada —
e a última era o 404 do controle, enquanto a prova era o 201 do payload duas
chamadas antes. Agora imprime a sequência:

```
POST /documents/11/share?email=nonexistent' OR '1'='1  como alice -> HTTP 201
POST /documents/11/share?email=nonexistent@nowhere.dev como alice -> HTTP 404
```

O payload passa, o controle não. Duas linhas, e um humano verifica sozinho.

**7. Salve cada etapa em disco.** Promotores → arquivo. Advogado → arquivo. Juiz
lê do arquivo. Ajustar o juiz pela trigésima vez não pode re-executar o
advogado. Isso também é o que permitiu **recuperar veredictos perdidos por bug
de parse sem gastar API de novo** — a saída crua estava preservada.

---

# PARTE 8 — Diferenciação, com honestidade

Duas afirmações que **não** fazemos, e por quê:

🚫 **"Nenhuma ferramenta do mercado faz isso."** É falso e cai em 30 segundos no
celular de um jurado. A Promptfoo Code Scanning escaneia PRs para prompt
injection com análise estática de fluxo de dados.

A frase correta é mais estreita e sobrevive à checagem:

> *"Existe quem escaneie prompt injection no PR — a Promptfoo faz, com análise
> estática. **Ninguém executa o ataque para provar que é alcançável.** É a
> diferença entre 'este padrão é arriscado' e 'eu disparei este payload pela API
> e olha o resultado'."*

🚫 **"Encontrou 4 dos 5 defeitos."** É alegação sobre um gabarito que não temos.

> *"Provou quatro achados com artefato reproduzível, descartou seis com motivo e
> marcou dois como inconclusivos"* — é verdade, está na tela, e é mais forte.

**Sobre a metáfora promotor/advogado/juiz:** ela *não* é o diferencial. O README
do starter kit dos organizadores descreve essa arquitetura textualmente. Todo
time que ler vai construir algo parecido. O diferencial é a camada de baixo — **a
prova diferencial, o veredito como exit code, e as listas de descartados e
inconclusivos.**

---

# PARTE 9 — Glossário

| termo | o que é |
|---|---|
| **acusação** | hipótese de defeito produzida por um promotor. JSON com categoria, local, hipótese, árbitro e `provado_se` |
| **árbitro** | o critério objetivo violado (critério de aceite, invariante, convenção). Sem árbitro citado, é opinião com teste em anexo — e a R1 rebaixa |
| **`provado_se`** | condição de prova, escrita pelo promotor. O advogado já começa sabendo o que procurar em vez de gastar voltas decidindo |
| **artefato** | JSON em disco com o resultado bruto de uma prova. É a autoridade; o modelo não escreve nele |
| **prova diferencial** | rodar o mesmo teste no base e no head e comparar exit codes |
| **prova ponta a ponta** | falha demonstrada pela API rodando, não por chamada direta de função |
| **canário / controle negativo** | o usuário `carol`, que não possui nada. Qualquer dado de outro usuário que apareça para ela é vazamento |
| **LLM alvo dublê** | o app sob teste sem chave de LLM: responde igual para tudo, então injection não é testável por ali |
| **INCONCLUSIVO** | terceiro estado. Não provou e não refutou, com a causa registrada |

---

# PARTE 10 — Perguntas boas para fazer a uma IA de estudos

Se você for usar este documento para aprender, estas são as perguntas que rendem
mais:

1. A prova diferencial exige "passa no base, falha no head". Que classes de
   defeito ela **não** consegue provar, e o que se usa no lugar?
2. A R2 rebaixa toda prova que não é ponta a ponta. Que incentivo perverso isso
   cria no advogado, e como o AND com o artefato o neutraliza?
3. O terceiro estado (INCONCLUSIVO) protege contra absolvição falsa. Qual é o
   custo dele, e como uma lista de inconclusivos inflada enfraquece o parecer
   tanto quanto uma vazia?
4. Os promotores são instruídos a maximizar cobertura, não precisão. Por que
   isso funciona aqui e em que arquitetura deixaria de funcionar?
5. "Uma guarda que só roda quando já existe evidência fica muda onde a evidência
   falta." Onde mais esse padrão aparece em sistemas de software?
6. O cache de prompt paga porque o diff é o mesmo prefixo em toda chamada. O que
   quebraria esse ganho, e como se detecta que ele quebrou?
