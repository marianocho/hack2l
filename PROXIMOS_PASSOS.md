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
| **`veredito.yml`** | meio dia | como o app sobe, como autentica, contas de teste, **banco descartável**. Destrava tudo o mais |
| **Entrada "revise este PR"** | horas | hoje é config apontando para pasta local |
| **GitHub Action** | 1–2 dias | ver "Por que Action" abaixo |
| **Repo de demonstração** | 1 dia | PR deliberadamente quebrado, público. É o que converte |

### B — Memória e custo

| item | tamanho | nota |
|---|---|---|
| **Parar de sobrescrever** | 30 min | `saidas/rodadas/<data-commit>/`. Hoje só a última sobrevive |
| **Cache de ferramenta na rodada** | meio dia | se A leu `shares.py`, B não relê |
| **Fusão por artefato no juiz** | 1 dia | duas acusações com o mesmo artefato **são** o mesmo defeito — fato, não palpite |
| **Biblioteca de andaimes por repo** | 1–2 dias | corta voltas do laço, que é onde mora o custo |
| ❌ **Mostrar veredito passado ao advogado** | — | **nunca.** Precedente não é evidência, e código muda |

### C — Evidência que falta

| item | custo | o que responde |
|---|---|---|
| **PR de terceiro com IA** | US$0,05 | a lente de injection ficou vazia nos 10 PRs porque nenhum tem modelo. Silêncio correto ou lente quebrada? |
| **`$PARAM` nas regras do semgrep** | 3 linhas | dá ao advogado o nome da variável envenenada, poupando volta de laço |
| **Taxa de aceitação** | depende do bot | de cada achado postado, qual fração o autor conserta. É a métrica que prova a tese |

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
