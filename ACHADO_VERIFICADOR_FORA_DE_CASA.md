<!-- tag: hack2l -->

# O verificador fora de casa — e quem paga pela alegação

Medido em **10–11/08/2026**, com dois experimentos novos:
`experimento_verificador.py` (metade A) e `experimento_adaptador.py` (metade B).
Custo total: **~US$3,60**.

As duas perguntas que o hackathon deixou em aberto e que nenhum experimento
anterior tocou:

```
metade A   o verificador prova ou refuta em repositório que NÃO preparamos?
metade B   achado de OUTRA ferramenta vira alegação testável?
```

A primeira é risco técnico sob qualquer posicionamento. A segunda decide se o
produto pode ser a camada de verificação de achado alheio, em vez de mais um
revisor de PR.

---

## Metade A — 38 acusações, 5 PRs, 3 linguagens

As 144 acusações que os promotores produziram em 10 PRs reais estavam paradas em
disco, **nunca verificadas**. Amostra estratificada por (repo, categoria) —
estratificar importa: a lista vem agrupada por promotor, então um corte simples
mediria uma lente só.

Ferramentas: **só `read_file` e `grep`**. Sem docker, sem app no ar.

| repo | ling | n | REFUT | INCON | SOBREV |
|---|---|---|---|---|---|
| `django#21735` (PR de 1 linha) | Python | 8 | **8** | 0 | 0 |
| `gin#4709` | Go | 8 | **8** | 0 | 0 |
| `flask#6095` | Python | 8 | 7 | 0 | 1 |
| `httpx#3730` | Python | 6 | 1 | 1 | 4 |
| `next.js#96932` | JavaScript | 8 | 2 | **6** | 0 |
| **TOTAL** | | **38** | **26 (68%)** | 7 (18%) | 5 (13%) |

US$2,70 · **US$0,071 por acusação verificada**

**Sem o next.js: 80% refutado, 1 inconclusivo em 30.**

O melhor resultado isolado é o `django#21735` — o PR de **uma linha** que os
promotores encheram de acusações. **8 de 8 refutadas.** US$0,67 para concluir
que não tem nada ali. O verificador limpa o ruído que os promotores fazem.

E ele refuta **lendo o código de verdade**, não por descarte genérico:

> **gin:** *"SaveUploadedFile chama `os.MkdirAll(filepath.Dir(dst), mode)` em
> `context.go:740-741` antes de `os.Create(dst)`, portanto a premissa é falsa."*
>
> **django:** *"o destino `sr_Latn` é o valor canônico do próprio repo:
> `.tx/config:3` já declara `lang_map = sr@latin: sr_Latn`."*

O segundo é o desacoplamento de ontem funcionando: **ele foi procurar a regra
dentro do repositório, achou, e usou como árbitro.** Ninguém precisou saber as
convenções de Transifex do Django.

---

## Metade B — a variável não é o formato da fonte

Três fontes, e o resultado só faz sentido com as três:

| fonte | tipo de alegação | conversão em testável |
|---|---|---|
| `bandit` / `psf-requests` | **padrão** | 1/10 = 10% |
| revisor de IA / `flask#6095` | comportamento | 1/5 = 20% |
| revisor de IA / **PR do desafio** | comportamento | **9/10 = 90%** |

**Errei o experimento duas vezes antes de acertar, e os dois erros são o
achado:**

1. **Fonte errada.** `bandit` reporta *padrão* ("existe um `assert` aqui",
   "falta `timeout=`"). O adaptador exige *comportamento observável*. São
   categorias diferentes de alegação — a conversão baixa era consequência da
   definição, não descoberta. E 9 dos 10 achados caíam em `tests/`.
2. **PR errado.** Os 10 PRs de terceiro foram escolhidos para medir se as
   **lentes disparam**, não por conterem defeito. São PRs de manutenção. Um
   revisor rodando neles produz alegação sobre nomenclatura e clareza — e
   clareza não tem comportamento observável **por definição**.

Com um PR que tem defeito real, ponta a ponta — prosa de revisor genérico
(sem esquema nosso, sem `provado_se`) → adaptador → verificador:

```
9 testáveis  →  PROVADO 5 · REFUTADO 1 · INCONCLUSIVO 3
```

Os cinco provados: injeção de SQL pelo `email`; `/shared-with-me` devolvendo os
documentos do próprio usuário; qualquer autenticado lendo documento de outro;
`MAX_SHARES_PER_DOC` lido e nunca aplicado; resposta sem email e sem título.

**São os mesmos defeitos que o Veredito achou no hackathon** — recuperados
partindo da saída em prosa de outra ferramenta, **sem os promotores**. E o
REFUTADO é o verificador matando uma alegação falsa do revisor.

---

## A assimetria que vale mais que os dois placares

Olhando o que precisou de execução em cada lado:

| | precisa do app? | custo |
|---|---|---|
| **Refutar** alegação fraca ou falsa | **não** — 26 refutações com leitura | US$0,07 |
| **Provar** defeito de comportamento | **quase sempre sim** | + ambiente |

Os 3 inconclusivos da metade B são todos do segundo tipo. Ou seja: **o problema
de rodar o app do cliente não some no reposicionamento, ele se desloca.**

A leitura de produto: **a primeira coisa vendável é a refutação, não a prova.**
É a metade que funciona sem infraestrutura do cliente, hoje, a sete centavos.

---

## Quatro achados sobre o próprio produto

### 1. O dedup evaporou, e apareceu medido em 12 horas

Os **4 sobreviventes do httpx são a mesma alegação** — mesmo arquivo, **mesma
linha** (`test-suite.yml:17`), `arbitro=None` nos quatro, lentes diferentes
dizendo que o título "3.11+" não bate com o diff.

A chave de dedup é `(local, arbitro)`. Com árbitro nulo ela devolve `None`, não
deduplica, e a mesma coisa foi verificada **quatro vezes a US$0,07** — e
chegaria ao humano como quatro achados.

É exatamente o efeito colateral registrado em `promotores.py::_chave_dedup` na
manhã de 10/08, ao desacoplar o árbitro. Ficou anotado em vez de consertado às
escondidas; doze horas depois ele é **4 dos 5 falsos positivos do experimento
inteiro**.

**Leitura corrigida da metade A: 5 sobreviventes são 2 alegações distintas.**

Conserto candidato: com árbitro nulo, deduplicar por `local` exato
(arquivo **e** linha, não só arquivo) e marcar `_corroborado=True`. Quatro
lentes na mesma linha é um achado com quatro corroborações, não quatro achados.

### 2. O advogado disse PROVADO com todas as ferramentas falhando

Na rodada com a worktree corrompida, ele escreveu no próprio motivo *"as
ferramentas de leitura/grep falharam"* e marcou **PROVADO**. Duas vezes.

A R3 do juiz pega (`execução falhou → INCONCLUSIVO`), mas o advogado não
deveria fazer isso. É a absolvição falsa pelo avesso: **condenação falsa.**

E o modo de falha da infraestrutura foi *"PROVADO"*, não *"erro"* — o que é
pior que quebrar. Falta uma checagem de sanidade das ferramentas antes da
rodada.

### 3. O produto não sabe provar defeito de concorrência

O `externo_04` alega corrida no check-then-act do share: duas requisições
simultâneas passam as duas pelo `SELECT COUNT(*)` e inserem as duas.

Sequencialmente **o código está certo** — o próprio verificador anotou isso. O
defeito só existe na corrida, e **nenhuma ferramenta dispara requisições em
paralelo**: `http_request` é sequencial.

É uma classe inteira fora de alcance — race condition, check-then-act, TOCTOU —
e é onde bug de verdade se esconde. Não é limitação de ambiente: com Docker no
ar continua sem fechar.

### 4. Escala quebra a leitura

No `next.js` (repositório gigante): **~220s por acusação** contra ~30s nos
outros, **6 de 8 inconclusivos**. A fatia que a alegação tocava não coube em 3
voltas de ferramenta.

O modo de falha confirma a teoria do produto: ele nunca entende o sistema, faz
um ato de compreensão **estreito e dirigido pela alegação**. Quando essa fatia
não cabe, ele não degrada para "não sei" com elegância — ele gasta 220s e aí
diz não sei.

---

## O que fica de pé

| | |
|---|---|
| Verificador decide sem executar | 68% refutado (80% sem next.js), 3 linguagens |
| Refuta o ruído dos próprios promotores | PR de 1 linha: 8 de 8 |
| Custo por verificação | **US$0,071** |
| Achado externo vira alegação testável | **90%**, quando o PR tem defeito |
| Recupera defeito real de fonte alheia | 5 de 5, sem os promotores |
| **Dedup não funciona com árbitro nulo** | **4 falsos positivos = 1 alegação** |
| **Concorrência fora de alcance** | classe inteira, sem ferramenta |
| **Escala quebra** | next.js: 6 de 8 inconclusivos |

### Ressalvas, para ninguém citar com mais confiança que o dado tem

- a "ferramenta externa" é o Sonnet 5 com prompt genérico — stand-in fiel do
  Greptile/CodeRabbit, mas **não é o produto deles**
- n pequeno na metade B: 10 achados, 1 PR com defeito
- o PR do desafio é ambiente preparado — atenuado por a verificação ter usado
  **só `read_file` e `grep`**
- a metade A rodou em PRs **sem defeito** e a metade B num PR **cheio de
  defeito**: os dois placares não são comparáveis diretamente

## Reproduzir

```bash
py -3.12 experimento_verificador.py            # metade A, ~US$2,70
py -3.12 experimento_adaptador.py --desafio    # metade B, ~US$0,70
py -3.12 experimento_verificador.py --resumo   # relê sem gastar API
```
