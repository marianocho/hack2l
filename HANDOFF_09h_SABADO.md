<!-- tag: hack2l -->

# HANDOFF — para a sessão de 09/08

Escrito na madrugada de 09/08. A sessão anterior saturou de contexto.

**Leia este arquivo primeiro.** Ele é o delta do dia 08 à noite e diz exatamente
onde retomar. `PROXIMOS_PASSOS.md` continua válido para o quadro geral, mas
**o passo 1 dele já foi feito** e mudou a prioridade.

---

## 0. Em uma frase

Veredito é um revisor de código multiagente onde o veredito é um exit code, não
opinião de modelo. Segundo lugar no Hack2L (08/08). Ontem à noite testamos fora
do desafio pela primeira vez e **achamos um vício grave no nosso próprio
prompt**.

**Compromisso hoje: conversa com Carlos Dutra, autor do desafio, às 16h30.**

---

## 1. O que mudou desde o hackathon

Dois experimentos novos, os dois já commitados e empurrados:

| script | o que responde | custo |
|---|---|---|
| `generaliza.py` | os promotores funcionam fora do PR do desafio? | ~$0,05/PR |
| `controle_negativo.py` | o advogado mata ruído, ou "prova" o nada? | ~$0,06/acusação |

### Resultado 1 — a régua, em 10 PRs reais

Flask, Django, httpx, Gin, Next.js, Requests. Três linguagens. 209 acusações.

**Passou:** nenhuma lente cega; concentração se espalha em PR multi-arquivo
(39% no next.js de 13 arquivos — os 98% do Hack2L eram anomalia daquele PR, não
defeito sistêmico).

**Falhou:** não existe piso. `django#21735` mudou **uma linha** e recebeu **17
acusações**. E a lente de injection está invertida — **zero** acusações num PR
de 389 linhas de Server Actions, **duas** num conserto de link de markdown.

Detalhe em `ACHADO_REGUA_10_PRS.md`.

### Resultado 2 — 🚨 o árbitro é do Hack2L e viaja junto

**É o achado que importa.** Nas 209 acusações:

```
com árbitro preenchido            94
citando vocabulário do Hack2L     93   (99%)
a 94ª                             "R1 R2 R3 R4 AC1 AC2 AC3 AC4 AC5"
                                  — a lista inteira do prompt, colada
```

Os prompts dos promotores chumbam `AC1`–`AC5`, `R1`–`R4`, `C1`–`C8` — os
critérios de aceite **do desafio da Vindler**. Eles são aplicados a qualquer
repositório. **Fora do Hack2L a taxa real de árbitro é zero.**

Isso explica a lente de `prd` nunca ter ficado vazia em 10 PRs: ela sempre tem
critério pra conferir porque os critérios estão dentro dela. Não lia o
repositório, recitava o desafio.

Detalhe e o conserto proposto em `ACHADO_ARBITRO_CHUMBADO.md`.

### Resultado 3 — o advogado mata ruído (essa é boa)

`psf/requests#7576`, um link de markdown, 11 acusações ao advogado:

```
REFUTADO 7 (64%)  ·  INCONCLUSIVO 2 (18%)  ·  PROVADO 2 (18%)
US$ 0,61 · 328 s
```

A divisão promotor/advogado **funciona** na maior parte. Dos dois sobreviventes,
um é erro de raciocínio (alegou que caminho absoluto em markdown vira URL de
domínio — falso — e acusou o *conserto* de ser o defeito) e o outro é o PRD do
Hack2L aplicado ao `psf/requests`.

---

## 2. ✅ FEITO em 10/08 — o árbitro foi desacoplado

**Os três itens abaixo foram implementados e medidos.** O resultado está em
`ACHADO_ARBITRO_CHUMBADO.md` §"O conserto, aplicado e medido em 10/08".

Em uma linha: **contaminação 93 → 0** nos mesmos 10 PRs, e a taxa de árbitro
deixou de medir o prompt e passou a medir o repositório — **2%** em repo de
terceiro (`null` honesto), **64%** no PR do desafio, que documenta as próprias
regras, com as citações caindo exatamente na linha que alegam.

Ganhou uma segunda via para CRÍTICA (prova ponta a ponta com artefato), sem a
qual nada seria crítico fora de um repo documentado. Ela conserta um furo do
parecer premiado: o mesmo SQL injection era CRÍTICA por uma lente e SUSPEITA por
outra, decidido por qual delas recitou um rótulo chumbado.

Testes: **178 passando** (eram 116), mesmas 4 falhas de Docker.

O que segue é a especificação original, mantida para leitura:

1. **Tirar `AC1`–`AC5`, `R1`–`R4`, `C1`–`C8` dos seis prompts** em
   `promotores/*.md`. Eles passam a entrar como *contexto do PR sob revisão*,
   quando existirem, não como vocabulário permanente da lente.

2. **Árbitro vira citação com procedência:** em vez de `"AC2"`, algo como
   `{"regra": "...", "onde": "docs/CONTRIBUTING.md:14"}`. Sem conseguir apontar
   onde a regra está escrita **naquele repositório**, o árbitro é `null` — que é
   a resposta honesta.

3. **⚠️ Consequência séria, decidir junto:** com `null` honesto na maioria dos
   casos, a regra R1 do juiz rebaixa quase tudo para SUSPEITA, e **nada consegue
   ser crítico fora de um repositório que documente seus próprios critérios**.

   Isso não é bug da R1 — é a R1 dizendo a verdade. Mas o produto passa a
   precisar de **uma segunda via para severidade alta que não dependa de
   árbitro**. O candidato natural é a reprodução ponta a ponta sozinha
   (`http_request` com artefato), que já existe.

**Validar rodando `generaliza.py` de novo depois do conserto** e comparando: a
taxa de árbitro deve **cair** (é o esperado e é o certo), e as acusações não
podem mais citar `AC*`/`R*`/`C*` em repo de terceiro.

> ✅ Validado. Caiu de 45% para 2%, e a contaminação foi de 93 para **zero em
> 144 acusações**. O detector agora é uma asserção (`tests/test_prompts_limpos.py`
> e o bloco "contaminacao" do `--resumo`), não leitura de 209 acusações na
> madrugada.

---

## 3. Estado do repositório

```
github.com/marianocho/hack2l     público, SEM licença (= todos os direitos reservados)
último commit                    c9444fe
testes                           116 passando, 4 falhando SÓ por Docker fora
```

**Os 4 testes que falham** (`test_ferramentas` ×3, `test_llm_alvo` ×1) precisam
da stack do desafio no ar. Suba antes de rodar a suíte:

```bash
cd C:\hack_agents\Hack2L\desafio
docker compose up -d
```

Se o Docker Desktop não subir, a receita está em `ESTADO.md` — **esta máquina não
consegue apagar sockets mortos** e precisa de rename manual da pasta.

### 🚨 10/08: a receita do rename NÃO resolve mais

O Docker Desktop está caindo na subida, sempre no mesmo ponto:

```
initializing Inference manager: listening on
unix://C:/Users/luisf/AppData/Local/Docker/run/dockerInference:
remove ...: The file cannot be accessed by the system.
(listener: The filename, directory name, or volume label syntax is incorrect.)
```

Tentado hoje, sem sucesso: renomear `AppData\Local\Docker\run` (funciona, o
Docker recria a pasta e **cai igual** — não é socket velho, ele não consegue nem
criar o novo); e `EnableInference: false` + `InferenceCanUseGPUVariant: false` no
`settings-store.json` (revertido, não adiantou; `EnableDockerAI` já era `false`).

A segunda linha do erro — *"volume label syntax is incorrect"* — sugere que ele
está tentando criar um **socket unix num caminho Windows**, o que é bug de versão
do Docker Desktop, não sujeira de estado. **Próximo passo provável: atualizar ou
reinstalar o Docker Desktop**, não mais mexer em pasta.

Pastas `run.old-*` acumuladas em `AppData\Local\Docker\` podem ser apagadas.

**O que isso custa:** só os 4 testes de integração (`test_ferramentas` ×3,
`test_llm_alvo` ×1). A régua (`generaliza.py`), os promotores, o juiz e a suíte
inteira rodam sem Docker — 178 testes passam.

### Arquivos novos de ontem à noite

```
generaliza.py                 régua: 6 promotores contra PR do GitHub, só o diff
controle_negativo.py          advogado com read_file+grep num clone raso
prs.txt                       10 PRs candidatos, verificados
ACHADO_REGUA_10_PRS.md        resultado da régua
ACHADO_ARBITRO_CHUMBADO.md    o achado do árbitro, com o conserto
saidas/generaliza/*.json      dado bruto, não apagar — reprocessar não custa API
```

---

## 4. Buracos que continuam abertos

Em ordem de valor, e todos com detalhe em `PROXIMOS_PASSOS.md` §4:

1. ~~**Árbitro chumbado**~~ ✅ feito em 10/08
2. **Sem piso** — *melhorou, não resolvido*. Tirei dos prompts o "se saíram menos
   de ~5 acusações você foi conservador demais", que fabricava volume; o
   `django#21735` de uma linha caiu de 17 para 13 acusações e o
   `psf/requests#7576` de 11 para 7. Ainda não existe critério de parada: a cota
   continua sendo orçamento, não julgamento.
3. **Lente de injection** — *mudou de forma, precisa de medição nova*. Agora ela
   diz explicitamente que sem modelo no código a resposta certa é silêncio: 0 nos
   10 PRs (nenhum tem LLM) e 3 no PR do desafio (que tem `/chat` com RAG). Mas
   **"0 em todos" e "quebrada" são indistinguíveis pelo número** enquanto não
   houver um PR de terceiro *com* IA no `prs.txt`. É o próximo teste barato.
4. **Prova diferencial não serve para endpoint novo** (não existe no base)
5. **Fallback do Opus não pegou a recusa cyber** apesar da config correta
6. **Juiz não tem síntese**: `MODEL_JUIZ` está no config e nunca é consumido
7. **Artefatos versionados são saída por rodada** — devia estar no `.gitignore`
8. **Bot que comenta no PR** — o parecer já é markdown com âncora arquivo:linha

---

## 5. Para a conversa das 16h30

**Carlos escreveu o desafio. Ele é o gabarito** — sabe quantos defeitos plantou
e quais eram falsos alarmes deliberados. É a pergunta mais valiosa da conversa,
e resolve o passo 2 do `PROXIMOS_PASSOS.md` de graça:

> *"Quantos defeitos você plantou, e quais? A gente provou cinco e descartou um.
> Queria saber o que passamos e se algum dos nossos era falso alarme plantado."*

**Conecte com o critério que ele mesmo deu** em 06/08 — *"precisão vale tanto
quanto cobertura; no falso alarme o importante é ser interpretável"*. A lista de
descartados é a resposta a isso, e agora temos número: 7 de 11 refutados com
motivo num PR sem defeito.

**A narrativa, agora com o conserto no fim — é uma história melhor que a de
ontem, porque tem desfecho medido:**

> Testamos em dez PRs reais de Flask, Django, Gin, Next.js e Requests. A
> cobertura generaliza — nenhuma lente cega, e a concentração num arquivo só que
> vimos no seu desafio era anomalia daquele PR.
>
> A precisão não generaliza. Um PR de uma linha gerou dezessete acusações.
>
> E achamos um vício nosso: noventa e quatro de noventa e quatro árbitros
> citavam os critérios de aceite do **seu** desafio, aplicados a repositórios que
> não têm nada a ver. A métrica que a gente comemorou estava medindo
> contaminação. Pior: os rótulos que a gente mandava o modelo citar *verbatim*
> nem existiam no seu repositório — nós tínhamos inventado a numeração.
>
> Consertamos hoje. O árbitro deixou de ser rótulo e virou citação com
> procedência: a regra, e o arquivo e a linha onde ela está escrita. Sem
> conseguir apontar onde, é `null` — que é a resposta honesta. A contaminação foi
> de noventa e três para **zero em cento e quarenta e quatro acusações**, e a
> taxa de árbitro passou a medir o repositório em vez do nosso prompt: dois por
> cento em repo de terceiro, sessenta e quatro por cento no seu, que documenta as
> próprias regras.
>
> O verificador aguentou desde o começo: refutou sete de onze num PR de
> documentação, com motivo.

**Se sobrar tempo, o detalhe que ele vai gostar** — o conserto expôs um furo no
parecer que ele avaliou: o *mesmo* SQL injection saiu CRÍTICA por uma lente e
SUSPEITA por outra, as duas com prova diferencial e artefato HTTP. A diferença
era só qual delas tinha recitado um rótulo. Agora prova ponta a ponta com
artefato é via própria para severidade alta, e a severidade acompanha a força da
prova — que era o princípio desde o começo, e não estava sendo cumprido.

**Outras perguntas para levar:** o que o primeiro lugar fez de diferente; onde
ele acha que a abordagem quebra; quem compra isso na experiência dele; e — o que
não achamos escrito em lugar nenhum — **se existe termo de propriedade
intelectual dos projetos submetidos**.

**Postura:** aberta, sem paranoia de IP. Ele é o autor do desafio, não um
comprador. Só uma linha de disciplina: **não assinar nada na conversa**.

---

## 6. O que não perder

As sete decisões que custaram caro estão em `PROXIMOS_PASSOS.md` §5. A que mais
importa hoje, porque foi violada duas vezes em 24 horas — inclusive por mim,
ontem à noite, no relatório do `controle_negativo.py`:

> **INCONCLUSIVO não é REFUTADO.** Somar os dois e dizer "refutou tudo" quando
> nenhuma ferramenta funcionou é absolvição falsa — o erro exato que o produto
> existe para impedir.
