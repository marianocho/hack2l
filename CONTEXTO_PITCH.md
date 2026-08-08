<!-- tag: hack2l -->

# Contexto do pitch e do discovery — 08/08, 15h

Este arquivo cobre o que foi **decidido e argumentado em conversa**, e que não
está em nenhum outro lugar do repo. Os operacionais continuam sendo:

- `HANDOFF_12h55.md` — estado técnico e o que falta fazer
- `CONTEXTO_ESTUDO.md` — explicação completa do produto, para estudo
- `PITCH.md` — o roteiro de 3 min do Luis, com marcas de tempo
- `README.md` — arquitetura, regras, landmines medidas

---

## 1. A notícia que muda o pitch: a frase central agora tem tela

O `PITCH.md` diz, em 2:15:

> *"Ninguém executa o ataque para provar que é alcançável. É a diferença entre
> 'este padrão é arriscado' e **'eu disparei este payload pela API e olha o
> resultado'**."*

**Até 13h de hoje essa frase não tinha como ser mostrada.** Prova por
`http_request` não gerava artefato, e o parecer imprimia `EVIDENCIA: nao fechou`
justamente nos achados provados por ataque executado. A afirmação mais forte do
pitch era a única sem respaldo na tela.

Agora sai assim, direto do parecer:

```
EVIDENCIA: contra o app rodando --
  POST /documents/11/share?email=nonexistent' OR '1'='1  como alice -> HTTP 201
  POST /documents/11/share?email=nonexistent@nowhere.dev como alice -> HTTP 404
```

O payload passa, o controle não. **Duas linhas, e o jurado verifica sozinho.**

É a melhor tela do demo, e ela não existia quando o roteiro foi escrito.

---

## 2. O diferencial, em três camadas — liderar pela terceira

**Camada 1 — a metáfora promotor/advogado/juiz.** ❌ **Não é diferencial.** Os
organizadores descreveram essa arquitetura no README do starter kit. Metade das
equipes vai apresentar algo parecido. Serve como explicação, nunca como
argumento.

**Camada 2 — executar em vez de analisar.** ✅ Defensável. A Promptfoo escaneia
PR para prompt injection com análise estática de fluxo de dados; é explicitamente
estática. Nós subimos o app e disparamos o ataque.

**Camada 3 — e é aqui que está o produto: invertemos o que a severidade mede.**

Toda ferramenta do mercado dá nota ao **mundo** ("SQL injection é crítico"). Nós
damos nota à **nossa própria evidência** ("provamos que é real e alcançável?").

Parece detalhe filosófico. É a raiz, e tudo mais é consequência:

- nota sobre a evidência → falta de evidência precisa de nome → **terceiro estado**
- nota sobre a evidência → o que testamos e caiu precisa aparecer → **lista de descartados**
- nota sobre a evidência → o modelo não pode dar a nota → **regras determinísticas**

Ninguém copia isso adicionando uma feature. É decisão de raiz.

---

## 3. As três perguntas do discovery — respostas

### 3.1 Qual é o trabalho que alguém precisa fazer?

**Não é "revisar código"** — isso é o cargo. O trabalho específico, repetitivo e
frustrante é:

> **Triar um achado de revisão para decidir se ele é real e se importa.**

O loop, por achado, por PR:

1. Chega o alerta — *"possível SQL injection na linha 33"*
2. Alguém lê o código em volta
3. Decide se é **alcançável na prática** ou só teoricamente feio
4. Na dúvida — quase sempre — faz checkout, sobe o app, tenta reproduzir
5. Decide se bloqueia o merge
6. Se descartar, escreve a justificativa. **E se não escrever, a próxima pessoa
   refaz tudo.**

Quem faz: mantenedor, revisor de segurança, quem está de plantão na fila de PRs.

**A parte que dói:** a maior parte do esforço é gasta *desprovando*. O número do
curl quantifica — taxa de confirmação abaixo de 5% significa que **mais de 95%
do trabalho de triagem foi descobrir que não era nada.**

### 3.2 Por que ainda é feito manualmente?

**a) Provar exige executar, e executar exige ambiente.** Análise estática não
responde *"isso é alcançável?"*. Para responder é preciso o app no ar, com dados
semeados, credenciais de usuários diferentes — e o **commit anterior também**,
para saber se a mudança causou. Isso é infraestrutura por achado, e saía caro
demais para um alerta que provavelmente é falso.

**b) Não existe oráculo.** Para bug comum você tem a suíte. Mas *"este PR quebrou
o isolamento entre usuários no RAG?"* não tem asserção em lugar nenhum — a
invariante mora na cabeça de alguém. Automação não tinha contra o que conferir.

**c) A severidade parecia exigir julgamento humano.** Parcialmente exige. Mas o
corte é este: **não é preciso julgamento para dar nota ao mundo — só para nomear
o critério violado.** O resto é mecânico, e virou as seis regras em código.

**d) O *why now*: a IA barateou a parte errada.** Gerar suspeita ficou quase de
graça nos últimos 18 meses. Isso não reduziu o trabalho, **multiplicou** — cada
suspeita gerada vira triagem humana. O gargalo migrou de *achar* para *provar*, e
ninguém foi atrás do gargalo novo.

Ao mesmo tempo, o que era caro ficou viável: rodar o teste nos dois commits custa
14 s, e uma rodada de PR inteira sai por menos de dois dólares. **A prova por
execução ficou barata o suficiente para ser feita por achado.**

### 3.3 O que muda para quem usa?

**Erro eliminado — e é um que ninguém mais nomeia.** A **absolvição falsa**: o
achado descartado como "não se sustenta" quando na verdade *ninguém conseguiu
observar*. Aconteceu conosco hoje: o app estava sem chave de modelo, respondia a
mesma frase para qualquer pergunta, e os payloads "não funcionaram". Um revisor
comum escreveria "injection: refutado" seis vezes, com aparência de rigor. Isso é
vazamento passando com carimbo de aprovado.

**Decisão mais rápida.** O merge deixa de depender de discussão e passa a depender
de artefato. Duas linhas resolvem.

**Tempo economizado, onde exatamente.** O passo 4 do loop — checkout, subir o app,
reproduzir — sai da mão do humano nos achados que o agente prova ou descarta.
Sobra o que é genuinamente indeciso, e isso vem com a causa.

**Custo:** menos de dois dólares por PR, desassistido, medido no log.

⚠️ **O que NÃO medimos, e não vamos inventar:** quanto tempo de triagem humana
isso economiza. Sabemos o nosso lado (14 min, US$ 1,78). O lado humano é a
primeira coisa a instrumentar num piloto — e dizer isso é mais forte que chutar
um "70% mais rápido" que qualquer jurado derruba pedindo a fonte.

---

## 4. Valor por comprador

| comprador | o que ganha | mecanismo |
|---|---|---|
| **Dev** | volta a ler o review | a lista de descartados devolve a confiança que o alarme falso tirou |
| **Segurança** | prova de **alcance**, não padrão de risco | "está acontecendo agora" ≠ "este padrão é arriscado" |
| **Compliance** | laudo auditável | prova reproduzível + cadeia de regras por nota |
| **Eng. manager** | diagnóstico do próprio processo | 19 de 55 acusações sem árbitro = critérios de aceite frouxos |

A última linha é insight novo e vale no pitch: **agregando as regras que
dispararam ao longo de vários PRs, o cliente descobre onde o processo dele
vaza.** Nenhum scanner que só cospe severidade entrega isso.

---

## 5. Defensibilidade

🚫 **Não usar "volante de dados".** Todo concorrente diz isso em escala maior — a
Greptile já revisou mais de 1 bilhão de linhas.

✅ **Usar estes dois:**

1. **A categoria é nova.** Revisar *código de agente* — prompts, RAG, isolamento
   de tenant — é classe de defeito sem oráculo em nenhum incumbente.
2. **O laudo é artefato de compliance.** "Menos ruído no PR" é conforto de dev e
   não tem comprador claro. "Merge com laudo" tem departamento e orçamento.

---

## 6. Transparência da prova — e a lacuna que sobrou

**O que fica no disco, por achado:**

```
artefatos/
  teste_<id>_<nome>.py    ← o código-fonte do teste que o advogado escreveu
  prova_<id>.json         ← commits, exit codes, stdout dos DOIS lados
  http_<id>.json          ← as chamadas HTTP, com status e corpo
```

O cliente não precisa acreditar nem rodar nada: lê o teste, lê a saída dos dois
lados, confere se o exit 0 → 1 é real.

E a mensagem de falha é escrita **para humano** — quando o teste falha no head, o
stdout já contém o vazamento impresso. A saída do teste **é** a evidência.

**A classificação correta das duas provas** (e o parecer hoje não rotula):

| via | o que é de fato | rede? | banco |
|---|---|---|---|
| `prova_diferencial` | **teste de integração em processo** (TestClient) | não | `kb_test` |
| `http_request` | **end-to-end de verdade** | sim | `kb`, seed real |

E isso é **imposto por código**: existe guarda que recusa o teste antes de
executar se ele tentar falar com o serviço `api` no ar — porque a imagem serve o
mesmo código nos dois lados, e aí a diferença viria de estado acumulado, não da
mudança do PR.

### ⬜ Duas melhorias pendentes, da mesma família

Ambas são o mesmo defeito: **informação correta, vocabulário nosso.**

**(a) Traduzir as regras.** Hoje sai `REGRAS: R1: CRITICA sem arbitro citado ->
SUSPEITA`. "R1" não significa nada para o cliente. Deveria sair:

```
POR QUE NÃO É CRÍTICA: o defeito foi provado e é alcançável, mas ninguém
apontou qual critério de aceite ou convenção ele viola. Aponte o critério
e a severidade sobe.
```

O `R1` continua no artefato JSON, onde é nosso.

**(b) Rotular o tipo da prova.** Hoje o leitor infere pela presença da linha
`E TAMBÉM:`. Deveria dizer:

```
EVIDENCIA: teste de integração (TestClient + banco de teste)
           test_invariante_terceiro_nao_le_documento.py
           passa em 32a5241, falha em 1dd2e5c (exit 0 -> 1)
E TAMBEM:  reprodução end-to-end contra o app rodando --
           GET /shared/9 como carol -> HTTP 200 com o conteúdo
```

São ~20 linhas no `juiz._bloco`. É o que separa "relatório de ferramenta" de
"laudo que alguém assina".

---

## 7. Os quatro critérios de avaliação (pesos iguais)

| critério | onde estamos |
|---|---|
| **Protótipo / aderência** | forte — roda ponta a ponta, 101 testes, artefatos no disco |
| **Viabilidade** | seção 3 e 4 acima. O ponto vendável é *laudo tem comprador, "menos ruído" não tem* |
| **Pitch** | roteiro pronto no `PITCH.md`, agora com a tela que faltava |
| **Criatividade** | ⚠️ **ponto de atenção** |

**O risco na criatividade:** a metáfora promotor/advogado/juiz está no README dos
organizadores. Todo time que leu vai apresentar algo parecido. **Liderar por ela
entra na média.**

O que é nosso e ninguém mais terá: **a inversão do que a severidade mede** e as
duas listas que nascem disso. É isso que vai no slide de criatividade.

---

## 8. Pontos fracos reais — ter a resposta pronta

- **Um PR, um app, sem gabarito.** → *"não temos gabarito, e por isso não
  afirmamos porcentagem. O que afirmamos está na tela com artefato."*
- **14 minutos por PR.** → não é bloqueio de CI, é revisão assíncrona, e custa
  menos de dois dólares.
- **Ainda não roda em CI.** → disparar payload real em ambiente de cliente pede
  sandbox efêmero. É engenharia, não pesquisa.
- **Validado numa máquina só.** → é o que está sendo feito agora.

---

## 9. A frase-síntese

> **"Todo revisor de IA afirma. Nós provamos — e quando não conseguimos provar,
> dizemos isso em vez de absolver."**
