<!-- tag: hack2l -->

# Próximos passos — reescrito em 11/08/2026

Quadro geral e fila completa. Para **onde retomar**, leia
`HANDOFF_12AGO.md` primeiro.

---

## Onde o produto está

**O motor está medido nos dois sentidos.** Ele condena com artefato quando há o
que condenar, e absolve com motivo quando não há:

| condição | resultado | custo |
|---|---|---|
| PR com defeito plantado | 10 de 10 provados | US$1,38 |
| PR sem defeito | 8 de 8 refutados | US$1,23 |
| PRs de terceiro (10 reais) | 68% refutados | US$0,071/alegação |

**O que impede uso real**, em ordem:

1. **Não tem onde entregar.** O parecer sai no terminal.
2. **Metade só funciona no desafio.** `config.py:88` chumba os quatro usuários,
   então a prova ponta a ponta — a que sustenta severidade alta — não generaliza.
3. **Sem licença.** Repositório público sem `LICENSE` = todos os direitos
   reservados. Ninguém pode legalmente rodar.
4. **Escala quebra.** No `next.js`: 220s por acusação, 6 de 8 inconclusivos.

---

## A fila

### A — Para alguém instalar e rodar

| item | tamanho | nota |
|---|---|---|
| **Licença** | 10 min | decisão de sócio: MIT/Apache se o alvo é adoção |
| ✅ **Contenção do `http_request`** *(14/08)* | | três partes, provada sob carga. Ver abaixo |
| ✅ **`veredito.yml`** *(14–15/08)* | | contas, layout, login, bancos, como o app sobe. **Cinco chumbados saíram do código**, todos achados apontando para o segundo projeto |
| **Entrada "revise este PR"** | horas | hoje é config apontando para pasta local |
| **GitHub Action** | 1–2 dias | ver "Por que Action" abaixo |
| **Repo de demonstração** | 1 dia | PR deliberadamente quebrado, público. É o que converte |

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

**Sem medição ainda.** Duas rodadas foram tentadas e as duas morreram em
configuração nossa, não no modelo. Custaram **264 mil tokens de entrada
somados** — contra ~7 mil de uma rodada saudável — porque o advogado repetia
ferramentas quebradas e cada volta reinjeta o contexto. Saldo esgotado.

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

#### Falta

`py -3.12 roda_bancada.py --top-n 3` quando houver saldo. Deve custar bem menos
que as duas de hoje — o custo veio das ferramentas falhando em cadeia.

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
