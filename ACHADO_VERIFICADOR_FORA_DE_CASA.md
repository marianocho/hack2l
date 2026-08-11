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

## Adendo (11/08) — a fonte precisa ser paga?

A metade B deixou uma dúvida de negócio: se a entrada vem de outra plataforma,
o cliente precisa **usar** outra plataforma? Testado com dois scanners
**gratuitos**, e a resposta é não.

⚠️ **A hipótese que eu tinha estava errada.** Eu apostei que alegação de
**fluxo** (taint) converteria melhor que alegação de **forma** (padrão), porque
fluxo afirma um caminho e caminho se testa. O dado não sustenta isso.

| | repo **sem** defeito | repo **com** defeito |
|---|---|---|
| `bandit` — afirma forma | 10% (1/10) | **50%** (1/2) |
| `semgrep` taint — afirma fluxo | — | **100%** (2/2) |
| revisor de IA — afirma comportamento | 20% (1/5) | 90% (9/10) |

Tudo que converteu no desafio foi **PROVADO** pelo verificador.

**O que o dado diz:**

1. **A variável dominante é ter defeito, não o formato.** O `bandit` foi de 10%
   para 50% *só trocando de repositório* — mesma ferramenta, mesmo tipo de
   alegação.
2. **A diferença entre 50% e 100% é UM achado**: o `bandit` trouxe também um
   `hardcoded_password` no `seed.py`, que o adaptador recusou — corretamente.
   Com n=2 contra n=2, isso não sustenta "taint converte melhor".
3. **O mesmo defeito converteu nas duas formulações.** A injeção de SQL em
   `shares.py:31` virou alegação testável dita como forma ("SQL montado por
   concatenação") **e** como fluxo ("parâmetro do cliente alcança `text()`"), e
   foi provada nas duas.

### A consequência de negócio

**Não há dependência de plataforma paga.** O `bandit` é grátis, é
`pip install`, roda local — e produziu alegação que converteu e foi provada.

Mas com um limite honesto: **scanner grátis dá precisão sem cobertura.**

- `bandit` no `psf/requests` (maduro): 708 achados, quase todos `assert` em teste
- `bandit` no app do desafio: **2 achados** — pegou a injeção de SQL e mais nada

Ele não viu a quebra de isolamento, nem a config morta, nem o `/shared-with-me`
errado. O scanner é o **teto** do que se consegue verificar.

Então são três fontes, e o verificador é o denominador comum:

| fonte | custo | cobertura | precisão |
|---|---|---|---|
| scanner grátis (`bandit`, `semgrep`) | ~zero | **baixa** | alta |
| nossos promotores | US$0,05/PR | **alta** | baixa |
| revisor de IA do cliente | dele | média | média |

### Duas pedras operacionais

**Os rulesets públicos do Semgrep CE** (`p/python`, `p/security-audit`,
`p/owasp-top-ten`, `p/default`) deram **1–2 achados e ZERO taint** neste app.
Precisou de regra própria — `regras_semgrep/taint.yml`. Isso é custo real
(alguém escreve regra por framework) e também ativo acumulável.

**O Semgrep no Windows lê config em cp1252**: YAML com acento morre com
`UnicodeDecodeError`. O arquivo de regras é ASCII de propósito.

### Ressalva

**n = 2 contra n = 2.** Pequeno demais para afirmar diferença de taxa entre
formatos. O que se afirma com segurança é o pareado: *o mesmo defeito, dito de
dois jeitos por duas ferramentas grátis, converteu e foi provado nas duas.*
Firmar o número exige rodar as duas em 3–4 apps com defeito conhecido.

---

## Adendo 2 (11/08) — o scanner rende mais por dólar? Não.

A ideia testada: o scanner tem precisão alta e volume baixo, então o advogado
deveria **começar pelos achados dele**, que renderiam mais por dólar.

Comparação limpa — **mesmo repo** (PR do desafio), **mesmas ferramentas**
(`read_file`, `grep`), quatro fontes:

| fonte | tipo de alegação | n | PROV | REF | INC | US$ | **US$/decidido** |
|---|---|---|---|---|---|---|---|
| promotores | hipótese (Haiku) | 10 | 9 | 0 | 1 | 0,52 | **0,057** |
| revisor de IA | comportamento, prosa | 9 | 5 | 1 | 3 | 0,47 | 0,078 |
| semgrep taint | fluxo | 2 | 2 | 0 | 0 | 0,11 | **0,057** |
| bandit | forma | 1 | 1 | 0 | 0 | 0,07 | 0,074 |

**Scanner US$0,062 por decisão contra US$0,057 dos promotores — 1,09×.** Sem
vantagem. A premissa não tem base.

A métrica é dólar por veredito **decidido** (provado ou refutado), não por
acusação: inconclusivo é gasto sem decisão, e dividir por acusação esconderia
isso.

### Por que parecia que teria

| promotores em… | veredito |
|---|---|
| PRs de terceiro (metade A) | **68% REFUTADO** |
| PR do desafio | **90% PROVADO, zero refutado** |

Mesma lente, distribuição invertida. **A precisão aparente do scanner era
artefato de comparação:** scanner medido em repo *com* defeito contra
promotores medidos em repo *sem* defeito.

🚨 **Terceira vez nesta rodada de experimentos que a resposta é a mesma:**

> **O repositório domina a fonte.** Ter defeito importa mais do que quem aponta.

Deu na conversão (10% → 90%), deu no bandit (10% → 50%), deu aqui. É o viés que
mais atrapalhou a leitura de todos estes experimentos, e vale conferir contra
ele **antes** de comparar qualquer fonte com qualquer outra.

### O que o teste achou de verdade — e não era o que eu procurava

**O nosso esquema ganha da prosa:**

| | inconclusivos |
|---|---|
| promotores (`provado_se` no esquema) | **1 de 10 — 10%** |
| revisor de IA (prosa livre) | **3 de 9 — 33%** |

`provado_se` é escrito **sabendo quais ferramentas existem**. A prosa do revisor
genérico alega o que exige execução que não temos (concorrência, log HTTP) e
trava no terceiro estado. Três vezes menos gasto sem decisão — é ativo real, e
é argumento a favor de manter o adaptador **traduzindo** para o esquema em vez
de mandar prosa direto ao advogado.

### Ressalva

**n = 3 para o scanner.** Isto **não refuta** a premissa — não dá suporte a ela,
com amostra pequena demais para detectar diferença mesmo que existisse. A frase
honesta é *"nenhuma evidência de vantagem"*, não *"provado que é igual"*.

### Decisão

- ❌ **não reordenar** o advogado por fonte: sem ganho medido, e o scanner não
  tem volume para ser motor (2–3 achados contra 45 dos promotores)
- ❌ **não mostrar ao promotor o que o scanner achou**: ancora (o defeito de
  isolamento mora em `shares.py:92`, três funções abaixo da injeção que o
  scanner pega em `:31`) e destrói o sinal de `_corroborado`
- ✅ **scanner como fonte PARALELA**: é grátis, é preciso, e quando ele e um
  promotor caem na mesma linha a corroboração é genuína
- ✅ **limite de concentração por local** (feito, 11/08) — mas ver o achado 1:
  ele **não** é dedup, e o que parecia duplicata eram alegações distintas

Reproduzir: `py -3.12 comparar_fontes.py` (lê do disco, não gasta API).

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

### 1. O dedup evaporou — e o diagnóstico óbvio estava errado

**A primeira versão deste item dizia que os 4 sobreviventes do `httpx` eram "a
mesma alegação quatro vezes" e propunha fundir por conteúdo. Estava errado**, e
a correção (11/08) vale mais que o achado original.

Lendo o texto completo das quatro, são **preocupações distintas** sobre a mesma
mudança de uma linha:

1. o título diz `3.11+` mas `setup.py`/`pyproject` não foram atualizados
2. dependências foram validadas contra 3.10; a remoção deixa esse usuário sem aviso
3. o título promete `3.11+` mas o diff só remove o 3.10 — divergência de escopo
4. remover o 3.10 pode violar política de suporte documentada

Mesmo **assunto**, alegações **diferentes**. Fundir perderia informação.

E a similaridade lexical confirma que não dá para separar automaticamente:

```
pares que DEVERIAM fundir      Jaccard 0,00 – 0,13
pares que NÃO deveriam         Jaccard 0,00 – 0,06
```

Indistinguível. Pior: **dedup por linha exata falharia no caso que mais
importa** — a injeção de SQL do desafio foi reportada em `shares.py:31`, `:32` e
`:33` por três lentes. Mesma linha, nenhuma. E `:36` (config morta) e `:39`
(race condition) são bugs distintos a 3 linhas de distância. Nem conteúdo nem
proximidade separam.

### O que era o problema de verdade

Medido nos 11 PRs, com o limite de concentração (`MAX_POR_LOCAL = 2`):

| PR | acusações | locais | maior local | despriorizadas |
|---|---|---|---|---|
| `django#21735` | 13 | 3 | **11** | 6 |
| `httpx#3730` | 8 | **1** | 8 | 6 |
| `httpx#3773` | 8 | 3 | 5 | 3 |
| `requests#7576` | 7 | **1** | 7 | 5 |
| `next.js#96932` | 29 | 24 | 4 | 0 |
| `flask#6095` | 20 | 15 | 2 | 0 |
| desafio | 45 | 38 | 2 | 0 |

O limite só dispara nos **PRs pequenos** — e ali não é concentração, é
**sobregeração**: o PR muda uma linha, então claro que todas as acusações
apontam para ela. É o buraco 2 do handoff ("não existe piso"), disfarçado.

**Efeito medido do limite: melhora 1 dos 11 PRs.** No `django#21735` a rodada
passa a verificar 3 locais em vez de 2. Nos de local único não há para onde ir;
nos bem distribuídos não é preciso.

Foi implementado assim mesmo (`promotores.seleciona`, teto **mole** — a
excedente vai para o fim da fila, nunca para o lixo), porque é guarda barata que
não machuca e que passa a valer mais conforme os PRs crescem. Mas **não é o
conserto do httpx.** O conserto do httpx é o piso, e continua aberto.

**Leitura corrigida da metade A: os 5 sobreviventes são ~5 alegações distintas,
não 2.** A afirmação anterior subestimava o falso positivo.

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
py -3.12 experimento_verificador.py                  # metade A, ~US$2,70
py -3.12 experimento_adaptador.py --desafio          # metade B, ~US$0,70
py -3.12 experimento_adaptador.py --semgrep          # adendo: fluxo
py -3.12 experimento_adaptador.py --bandit-desafio   # adendo: forma
py -3.12 experimento_verificador.py --resumo         # relê sem gastar API
```

As fontes do adaptador: `--bandit` (padrão, `psf/requests`), `--ia` (revisor de
IA em PR de terceiro), `--desafio` (revisor de IA no PR do desafio),
`--bandit-desafio` e `--semgrep` (scanners no app do desafio).
