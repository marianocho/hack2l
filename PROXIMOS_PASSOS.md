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
| 🚨 **Contenção do `http_request`** | meio dia | a prova pela API **altera estado do app real**. Medido 14/08. Ver abaixo |
| **`veredito.yml`** | meio dia | como o app sobe, como autentica, contas de teste, **banco descartável**. Destrava tudo o mais |
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
| 🎯 **A bancada com gabarito** | 2–3 dias | **destrava a métrica que nunca tivemos.** Ver abaixo |

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

### Como seria

| passo | nota |
|---|---|
| 1. `veredito.yml` | **pré-requisito duro.** Hoje `config.py:155` chumba os quatro usuários; sem isso a bancada só funciona se ela imitar o desafio, e aí não prova generalização nenhuma |
| 2. app mínimo rodável | API + banco + suíte. Rodável é obrigatório: sem app no ar só se mede o promotor, e o diferencial é a prova por execução |
| 3. um defeito por PR | PR com dois defeitos torna ambíguo qual achado corresponde a qual, e a conta de recall vira palpite |
| 4. PRs limpos no meio | controle negativo, sem avisar qual é qual a quem mede |
| 5. rodar e contar | recall (dos N plantados, quantos provados), precisão (das M condenações, quantas batem), e a **distribuição dos inconclusivos com causa** |

### O que ela permite dizer, e que hoje é proibido

> *"Provou 4 dos 5 defeitos plantados, com artefato reproduzível."*

Isso hoje é alegação sobre gabarito que não temos — está listado nos 🚫 do
`CLAUDE.md`. Com a bancada, passa a ser verdade conferível. É a frase que muda
uma conversa de investidor.

### ⚠️ Custo, que não é desprezível

Cada rodada completa custa US$0,40–1,30. Uma varredura de 10 PRs é **US$4–13**,
e toda mudança de prompt pede varredura nova. Isso vira o maior item de custo
recorrente do projeto — e é o preço de parar de andar às cegas.

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
