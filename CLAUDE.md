# CLAUDE.md — Projeto Veredito

> Documento de PRODUTO. **v5 — 14/08/2026.** Versionado desde 14/08.
>
> O que é da **máquina** — Python, Docker, sockets, worktrees, armadilhas de
> shell — saiu para `../CLAUDE.md`, um nível acima, **fora do git de propósito**:
> envelhece por máquina, não por produto, e mudaria a cada laptop novo.
>
> O que era do dia do hackathon está em `ARQUIVO_HACKATHON.md`. Nada foi apagado.

⚠️ Os exemplos de comando usam `py -3.12` porque é o lançador desta bancada de
desenvolvimento. Em outra máquina, troque pelo interpretador de lá — o
`../CLAUDE.md` explica por que aqui `python` não serve.

---

## ONDE AS COISAS ESTÃO

Três repositórios lado a lado, sob uma raiz comum:

```
<raiz>\
├── desafio\           repo do desafio — NÃO é legado, é o fixture de teste
├── bancada\           NOSSO app de medição, com defeitos plantados (14/08)
└── hack2l\            nosso repo (github.com/marianocho/hack2l), público
    └── CLAUDE.md      ← este arquivo
```

O caminho absoluto e o que mais for da máquina estão em `../CLAUDE.md`, fora do
git.

### A `bancada\` é o segundo projeto, e existe para medir

Repositório git próprio em **`github.com/luisfelp07/bancada`**, **privado**
*(criado em 15/08)*. App de **projetos, tarefas e membros** — domínio
deliberadamente diferente do desafio, que é documentos compartilhados.

```bash
git clone https://github.com/luisfelp07/bancada.git
git clone --branch pr/reconvite-de-membro ...   # os 4 PRs são RAMOS, não tags
```

🚨 **Sendo privado, quem não é colaborador não enxerga — e o erro mente.** O
GitHub responde **404**, não 403, para repositório privado sem acesso: a
mensagem diz *"repository not found"*, que se lê como "não existe" e manda
procurar no lugar errado. Hoje o único colaborador é `luisfelp07`. Para dar
acesso a alguém:

```bash
gh api -X PUT repos/luisfelp07/bancada/collaborators/<usuario>
```

⚠️ Fica sob `luisfelp07` e não sob `marianocho` porque **conta pessoal não
aceita repositório criado por terceiro** — nem colaborador do `hack2l` pode. A
transferência (Settings → General → Transfer ownership) é o caminho quando o
Mariano estiver por perto; a URL antiga redireciona.

⚠️ **Os quatro PRs são ramos, e um `clone` raso ou de um ramo só não os traz.**
Sem eles não há o que medir — é `git clone` normal, ou `git fetch origin
'+refs/heads/*:refs/remotes/origin/*'` se já existir uma cópia parcial.

Mesmas invariantes de isolamento do desafio, substantivos diferentes: se tivesse
a forma dele, os defeitos plantados cairiam exatamente onde as lentes já sabem
olhar, e a medição seria o nosso próprio reflexo.

O ramo `main` está **conferido limpo** (11 asserções de isolamento contra o app
rodando). Isso é pré-requisito: se o `main` tivesse defeito, os plantados nos
PRs deixariam de ser os únicos.

🚫 **O gabarito NÃO mora lá.** O advogado lê o repositório sob revisão por
worktree; um `GABARITO.md` na árvore seria resposta servida na bandeja, e a
rodada pareceria excelente.

⚠️ Ela **já se pagou antes de medir nada**: foi ao escrever o `veredito.yml`
dela que apareceu o layout chumbado em `_roda_pytest` (ver o padrão de bug).

**Veredito** — revisor de código autônomo que trata cada suspeita como acusação:
nada vira parecer sem prova reproduzível. **O veredito é um exit code, não
opinião de modelo.** Segundo lugar no Hack2L (08/08/2026).

### Por que o `desafio\` fica

É o **único ambiente com gabarito** e o único com toolset completo (prova
diferencial, `http_request`, banco). Em repositório de terceiro só existe
`read_file` e `grep`. Medido em 10/08: a métrica de conversão deu 10% e 20% em
PRs de terceiro — que não têm defeito — e **90% no PR do desafio**. Sem ele o
produto perde a capacidade de se testar.

### Leitura de contexto, por ordem

| Preciso saber… | Leia |
|---|---|
| **onde retomar** | **`hack2l/PROXIMOS_PASSOS.md`** ← comece aqui, é a fila viva |
| como configurar um projeto novo | `hack2l/projetos/desafio.yml` e `bancada/veredito.yml` |
| o que já foi medido | `hack2l/ACHADO_*.md` e `hack2l/saidas/final/*/LEIA.md` |
| o contrato promotor↔código | `hack2l/promotores/00_LEIA-ME.md` |
| o delta de 11/08 | `hack2l/HANDOFF_12AGO.md` *(histórico, não é mais o ponto de partida)* |
| o que era do dia 08/08 | `hack2l/ARQUIVO_HACKATHON.md` |

---

## ARQUITETURA

**Promotores acusam → advogado testa → juiz sentencia.** Um orquestrador, três
tipos de chamada.

```
pre_voo()                          # ferramentas funcionam? senão a rodada nem começa

acusacoes = []
para cada lente em [injection, vazamento, prd, correcao, padroes, performance]:
    acusacoes += chamada_de_modelo(diff + contexto + orçamento, lente)   # Haiku

acusacoes = cruza(acusacoes, scanner_gratis(diff))   # bandit/semgrep EM PARALELO

veredictos = []
para cada acusacao em seleciona(acusacoes, TOP_N, COTAS, MAX_POR_LOCAL):
    veredictos.append( advogado(acusacao) )                  # ← o loop caro

parecer = juiz(veredictos)                                   # regras + formato
```

**As três camadas de `seleciona`** (todas com teto MOLE — o excedente vai para o
fim da fila, nunca para o lixo):

| camada | o que impede |
|---|---|
| **cota** por categoria | uma lente barulhenta engolir as vagas das outras |
| **`MAX_POR_LOCAL=2`** | um ponto quente comer a rodada |
| **orçamento por lente** | 13 acusações num PR de UMA linha |

`orcamento_por_lente(diff) = clamp(1, ceil((3+linhas)/6), 10)`. Medido nos 10
PRs: a contagem era **constante** (7 a 29) com o diff variando 400×. Amplitude
da taxa: 185× → 44×. **Isso não é pedir seletividade** — "emita até N" é
calibração de escala; "reporte só o relevante" faz o modelo engolir achado real.

### Fontes externas (`veredito/fontes.py`)

Scanner grátis (bandit, semgrep) roda **em paralelo**, nunca em série: mostrar o
achado dele ao promotor ancora a lente e destrói o sinal de corroboração.

- coincide com um promotor (mesmo arquivo, faixa ±2 linhas, região ≤10 linhas)
  → **corrobora**, não gasta vaga, e o parecer cita a ferramenta **verbatim**
- ninguém viu → **entra como acusação**
- `arbitro` do scanner é **sempre `null`**: a regra é da ferramenta, não do repo

⚠️ Teto baixo: 2–3 achados contra 45 dos promotores. É corroboração, não motor.

### 1. Promotores (6, em paralelo)

Leem o diff **e o código em volta**. Queremos **volume** — acusar é barato e essa
lista ninguém vê.

⚠️ **O prompt do promotor não pode pedir seletividade.** "Reporte apenas
problemas relevantes" faz o modelo se autocensurar. O trabalho dele é cobertura;
a filtragem é do advogado, que tem ferramenta.

⚠️ **E não pode chumbar critério de projeto nenhum.** Ver "O árbitro" abaixo — é
o erro mais caro que já cometemos.

### 2. Advogado — a peça central

Única peça que é agente de verdade: **loop** pensa → ferramenta → resultado →
decide. **Não argumenta, TESTA.** Vê **uma acusação por vez, isolado**.

#### A prova diferencial (base vs. head)

Roda a prova **nos dois lados**. Só é **provado** se **passa antes e falha
depois**. O falso alarme se elimina sozinho, e a evidência vira *"este teste
passa no seu código de hoje e quebra com a sua mudança"*.

⚠️ **Não serve para superfície NOVA** (endpoint que não existe no base): o teste
dá 404 no base por ausência, não por defeito. Aí é teste que falha no head, ou
reprodução contra o app rodando.

⚠️ **O LLM não pode sobrescrever o exit code.** Ele produz o artefato; quem
decide se provou é código que um humano lê.

### 3. Juiz

Organiza, deduplica, ordena. Aplica as regras determinísticas. As regras estão
em `veredito/juiz.py` e têm teste; a síntese em linguagem natural ainda **não
existe** (`MODEL_JUIZ` está no config e só é consumido pelo
`experimento_adaptador.py`, como revisor externo dublê — não pelo juiz).

---

## A REGRA CENTRAL

> **Veredito + confiança + evidência. A severidade acompanha a FORÇA DA PROVA,
> não a gravidade teórica. Nada é descartado em silêncio.**

| Situação | Resultado |
|---|---|
| Provado com artefato | Severidade alta |
| Suspeita fundamentada, não confirmada | Baixa, **rotulada**, com o que foi tentado |
| Refutado pela perícia | Lista de descartados, **com motivo** |
| **Execução falhou** | **INCONCLUSIVO, com a causa** — nunca "absolvido" |

Carlos Dutra (autor do desafio, 06/08): *"passar um defeito real é mais
problemático do que um falso alarme. No falso alarme, o importante é ser
interpretável... precisão vale tanto quanto cobertura."*

### 🚨 O terceiro estado é obrigatório

Sem artefato não há prova — e num veredito binário isso vira **absolvição
limpa**. A categoria carro-chefe se esvazia sozinha e **parece rigor**.

```
se timeout, parse quebrado, ferramenta falhou ou stop_reason == "refusal":
    veredito = INCONCLUSIVO      # nunca ABSOLVIDO
```

⚠️ **INCONCLUSIVO não é REFUTADO.** Somar os dois e dizer "refutou tudo" quando
nenhuma ferramenta funcionou é absolvição falsa — o erro exato que o produto
existe para impedir. Já foi cometido duas vezes nos nossos próprios relatórios.

---

## 🚨 O AGENTE PODE DESTRUIR O QUE ELE TESTA

Aconteceu duas vezes em 11/08. **É a classe de risco mais séria do produto**, e
não é bug pontual — é consequência direta do desenho.

**Caso 1 — o payload.** O promotor pedia `provado_se` com
`email="admin'; DROP TABLE users--"`, e o advogado tem `http_request` apontado
para o app rodando. O classificador de cibersegurança recusou 2 de 10 acusações
e **estava nos protegendo** — tratar a recusa como obstáculo teria consertado a
coisa errada. Injeção se prova por **leitura**: `' OR '1'='1` devolvendo linhas
demais. Mesma demonstração, sem tocar em estado.

**Caso 2 — a suíte do base.** A prova diferencial roda a suíte do repositório
nos **dois** commits. O base era anterior ao conserto do próprio autor ("stop
the test suite from wiping the app database") e **apagou o banco**: 4 usuários,
5 documentos. O advogado nunca julgou aquele código — para ele o base é ponto de
controle, tipo grupo placebo. **O desenho trata o base como referência inerte, e
rodar código não é inerte.**

⚠️ E o diagnóstico óbvio estava errado: procurar `DROP` no diff não pega nada. O
`DROP SCHEMA` existe **igual nos dois commits**; o que o PR acrescentou foi para
onde ele aponta. O perigo estava no código que a mudança **não tocou**.

### O princípio: contenção, não predição

Adivinhar o que o código faz perdeu as duas vezes. O que funciona é **impor a
fronteira de fora**:

| camada | mecanismo | onde |
|---|---|---|
| **prova read-only** | promotores proíbem `DROP`/`DELETE`; advogado se recusa a executar | prompts + `SISTEMA` |
| **banco descartável** | `-e DATABASE_URL=…kb_veredito` imposto no container | `_roda_pytest` |
| **rede sem saída** | `docker network --internal` — banco dentro, internet fora | só no lado **base** |
| **app em cópia** *(14/08)* | `pg_dump` → banco novo → api reapontada durante a rodada | `contencao_app.py` |

### 🚨 Caso 3 (14/08) — a prova pela API altera estado, e a regra era impossível

Rodada real: `shares` saiu de 0 para 3. Nada destruído, mas o advogado **alterou
o app real** — provar injection na rota de compartilhamento exige chamar
`POST /share`, que cria linha.

E só apareceu porque tiramos retrato do banco **à mão**, por precaução. Nada no
sistema avisaria.

**A regra antiga não se sustentava.** *"Prove de forma que só LÊ"* é impossível
de cumprir quando o defeito mora num endpoint de escrita. Não foi desobediência
do modelo — foi regra que o desenho viola por construção. E regra impossível no
mesmo prompt ensina que as regras dali são aproximadas, sendo que as outras são
as que impedem ele de apagar o banco do cliente.

A linha certa não é entre ler e escrever, é entre **criar e destruir**:

- 🚫 o **payload** injetado é sempre read-only (`DROP`/`DELETE`/`UPDATE`/`INSERT` proibidos)
- ✅ a **chamada** a endpoint documentado pode criar registro, quando o defeito mora nele
- 🚫 em qualquer via: apagar ou modificar o que **já existia**

**O conserto, em três partes:** regra verdadeira no prompt · app em cópia
descartável (`APP_EM_BANCO_DESCARTAVEL`, desligada por padrão) · delta de estado
gravado por rodada e impresso no parecer.

🚫 **`CREATE DATABASE ... TEMPLATE` está PROIBIDO.** Testado com o app conectado:
**derrubou o servidor Postgres**. `pg_dump` ao vivo é seguro (0,6s / 171KB) e é
o caminho usado.

⚠️ **Recriar o container relê o ambiente inteiro**, não só a `DATABASE_URL`. Um
`.env` editado depois de o app subir entra em vigor no meio da rodada, e o
sintoma aparece longe da causa. Quem depurar "o app quebrou durante a rodada"
olha o `.env` do alvo **antes** de olhar a contenção.

Conferência grátis, em segundos: `py -3.12 checar_contencao.py`.

**Por que só o base:** a CI do cliente roda o head a cada push — risco marginal
nosso é zero. O base ninguém roda mais. É lá que o risco é só nosso.

**A escotilha:** `PERMITIR_REDE_NO_BASE=1`, desligada por padrão. Se o arnês de
teste precisar de internet, o base vira **INCONCLUSIVO rotulado** dizendo que
foi o isolamento e não o PR. Efeito irreversível se pergunta **antes**, e quem
decide é quem conhece a suíte.

🚨 Dois detalhes que só apareceram rodando, e os dois quebravam em silêncio:
`docker network connect` precisa de **`--alias db`** (senão o banco fica
inalcançável) e é **no-op quando já existe conexão**, mesmo sem o alias — por
isso `_garante_rede_isolada` devolve o resultado da **conferência**, não do
`connect`.

---

## 🚨 O ÁRBITRO — o erro mais caro do projeto

Medido em 08/08 à noite, em 10 PRs reais: **94 acusações com árbitro preenchido,
93 citando os critérios de aceite do desafio da Vindler** — aplicados a
repositórios que não têm nada a ver com ele. Os prompts chumbavam `AC1`–`AC5`,
`R1`–`R4`, `C1`–`C8`, então cada lente carregava o PRD do desafio para dentro de
qualquer diff do mundo.

Pior: **esses rótulos nunca existiram nem no desafio.** Nós inventamos a
numeração e mandamos o modelo citá-la "verbatim".

**A regra que isso comprou: regra sem procedência é opinião.**

Consertado em 10/08 (`veredito/arbitro.py`, commit `e9041f1`):

- o que o repositório documenta entra por **`contexto/`**, em tempo de execução,
  nunca chumbado na lente. Aponte `CONTEXTO_REPO` para outro arquivo e você
  revisa outro repositório.
- árbitro deixou de ser sigla e virou **citação com procedência**
- sem conseguir apontar **onde** a regra está escrita naquele repo, é `null` — e
  `null` é a resposta honesta para a maioria dos repositórios do mundo

🚫 **Nunca reintroduzir critério de projeto específico dentro de
`promotores/*.md`.** `tests/test_prompts_limpos.py` verifica isso
mecanicamente — prompt regride em silêncio, asserção não.

---

## ESQUEMA DA ACUSAÇÃO

Saída do promotor, **JSON** — nunca YAML, o Haiku quebra YAML e a acusação some
em silêncio.

```json
{
  "id": "vazamento_01",
  "categoria": "vazamento_de_contexto",
  "local": "search.py:112",
  "hipotese": "retrieve_docs não filtra por tenant_id",
  "arbitro": {"regra": "quem não é dono não pode ler",
              "onde": "docs/PRD.md:43"},
  "provado_se": "canário do usuário B aparece na resposta do usuário A",
  "confianca": "media"
}
```

- **`arbitro`** — o objeto acima **ou `null`**. Nunca uma sigla solta. Só conta
  com `onde` preenchido: `veredito/arbitro.py::tem_procedencia`.
- **`provado_se`** — o advogado já começa sabendo o que procurar, em vez de
  gastar voltas do loop decidindo.
- **`hipotese`** é uma linha. Prosa longa ancora o advogado e o juiz.

⚠️ **`try/except` no parse, devolvendo a saída crua no fallback.** Acusação nunca
morre por erro de formato.

---

## AS REGRAS DETERMINÍSTICAS DO JUIZ

Regra escrita em prosa não acontece sob pressão. **Vira código ou não existe** —
estão em `veredito/juiz.py::aplica_regras`, com teste.

```
R0   artefato ganha do advogado: ele disse PROVADO e o exit code disse não? vale o exit code
R0b  prova ponta a ponta é fato do artefato, nunca autodeclaração do modelo
R1   CRITICA exige UMA das duas: árbitro com procedência OU prova ponta a ponta
R2   prova que não é ponta a ponta → severidade no máximo MEDIA
R3   execução falhou → INCONCLUSIVO, nunca absolvido
R3b  PROVADO/REFUTADO com ZERO ferramenta bem-sucedida → INCONCLUSIVO
R4   REFUTADO + LLM do app alvo dublê → INCONCLUSIVO (ver ACHADO_APP_SEM_MODELO)
```

**A R1 tem duas vias desde 10/08, e não é afrouxamento.** No parecer premiado, o
mesmo SQL injection saiu CRITICA por uma lente (que recitou um rótulo chumbado)
e SUSPEITA por outra (árbitro nulo) — as duas com prova diferencial e artefato
http. A severidade seguiu o acaso, não a força da prova. O que continua barrado
é opinião de modelo sem nenhuma das duas.

**A única conferência que sobra pra humano:** olhar o artefato de um achado
crítico e perguntar se ele convence. 30 segundos, e só nos críticos.

---

## 🚨 O PADRÃO DE BUG DESTE PROJETO

> **A guarda existe, mas está condicionada ao mesmo sinal que ela deveria
> vigiar. Então ela fica muda exatamente onde é necessária.**

Aconteceu **quatro vezes**, sempre com cara diferente, sempre custando caro.
Não é descuido pontual — é o formato de erro que esta arquitetura convida,
porque quase toda regra aqui confere um artefato, e a ausência do artefato é
justamente o caso perigoso.

| onde | a guarda | ficava muda quando |
|---|---|---|
| **R0b** | confere se `prova_ponta_a_ponta` bate com o artefato | morava dentro de `if artefato is not None` — e prova por `http_request` não gera artefato de teste. A conferência sumia justo na única via que sustenta severidade alta. |
| **R3** | execução falhou → INCONCLUSIVO | olha `artefato.erro`. Verificação só estática não gera artefato nenhum. |
| **R3b** | *(o vão que a R3 deixou)* | o advogado disse PROVADO com **todas** as ferramentas falhando, e escreveu isso no próprio motivo. |
| **dedup** | funde por `(local, arbitro)` | o conserto do árbitro fez `arbitro` virar `null` na maioria — a chave evaporou junto. |
| **`ERRO` como string** | contar ferramenta que falhou | dependia do prefixo no retorno `-> str`. ✅ 13/08: quem sabe que falhou passou a ser quem falhou — a ferramenta registra o desfecho. |
| **`http_request` fora da contenção** | banco descartável, rede sem saída | aplicadas só ao caminho da `prova_diferencial`; o `http_request` fala com o app de verdade. ⚠️ **Meio consertado em 14/08:** o `contencao_app.py` fechou o BANCO; a rede não — não há função de rede naquele módulo. Ver "o vão que sobrou" em `PROXIMOS_PASSOS.md`. |
| **retrato do banco chumbado** | delta de estado por rodada, contra efeito colateral | `_psql` fixava `-U kb`: contra a bancada todo retrato falhava, `delta_do_banco` lia só `tabelas` e ignorava `erro`, e seis rodadas gravaram `"limpo": true` sem terem olhado. O console usava **a mesma frase do sucesso**. ✅ 16/08. |
| **`provado_se` de leitura** | "não argumenta, TESTA" | a regra vale, mas quem decide se o advogado testa é um campo que o PROMOTOR escreve. `padroes.md` mandava `grep` em 57% dos casos, e a absolvição falsa entrou por aí. ✅ 16/08, medido em A/B. |
| **layout do repo chumbado** | — | `_roda_pytest` fixava `app/api/app` e `app/api/tests`: a prova diferencial, única que assina PROVADO, só funcionava num repositório. ✅ 14/08. |
| **a chave em dois lugares** | — | `load_dotenv` não sobrescreve o ambiente: a do Windows vencia o `.env` **em silêncio**, e trocar o arquivo não mudava nada. Custou 4 tentativas. |

**Um primo, na mesma família:** métrica que mede a coisa errada. O diagnóstico
contava *"árbitro preenchido"*, e 94 de 94 estavam preenchidos **com lixo
reciclado**. Preenchido não é válido.

### Como procurar

1. Toda guarda dentro de um `if`: **o que acontece quando a condição é falsa?**
   Se a resposta é "passa batido", a guarda não existe no caso que importa.
2. Toda métrica: **isto pode estar medindo outra coisa?** Foi a pergunta que
   faltou nos 45% de árbitro.
3. Toda chave derivada de um campo: **e se o campo sumir?** Foi o dedup.
4. Toda checagem que depende de convenção de string: **e se a convenção não
   valer?**
5. 🆕 **O que só existe num caso não é testado pelo caso que existe.** Os 375
   testes rodam todos contra o desafio, então tudo específico dele é invisível
   para eles. Foi preciso apontar o produto para um **segundo** projeto — a
   bancada — para o layout chumbado aparecer.

### 🚨 E toda guarda precisa ser vista FALHANDO

Guarda que nunca foi testada com a violação injetada não é guarda, é decoração.

Isso se pagou na hora em 13/08: das três travas escritas para o conserto do
`ERRO`, **a do meio passou com o defeito presente**. Ela conferia se
`_fecha_chamada` aparecia *em algum lugar* da função; tirar o registro do
caminho de **sucesso** e deixar o do `except` passava batido — e todo sucesso
viraria chamada não registrada, contada como erro, gerando INCONCLUSIVO falso.

**O padrão de bug apareceu dentro da guarda escrita contra o padrão de bug**, e
só apareceu porque a guarda foi testada em vez de confiada.

⚠️ E duas travas erradas **por substring** no mesmo dia: uma comparava nome de
banco, e `kb` casa dentro de `kb_veredito_app`; outra procurava `override=True`
no fonte e casava com o comentário que explicava por que ele está desligado. As
duas viraram comparação estrutural (AST / argumento `-d`).

> **Teste que acusa a coisa errada não vale mais que teste que não acusa nada.**

---

## FORMATO DO PARECER

```
[SEVERIDADE] [CONFIANÇA] Categoria — arquivo:linha
O QUE: uma frase.
ÁRBITRO: <a regra (arquivo:linha)>  ou  "nenhum citado"
EVIDÊNCIA: <artefato: teste que falha base→head / chamadas HTTP / query>
           ou: o que foi tentado e por que não fechou
CONSERTO SUGERIDO: uma frase.        ← só para condenados
```

Mais **a lista dos descartados com motivo** e **a lista dos inconclusivos com a
causa**. Essas duas listas são a peça que nenhum concorrente tem — e precisam ser
enquadradas **em voz alta**, senão soam como confissão de erro.

---

## O APP ALVO — mapa operacional

```bash
cd C:\hack_agents\Hack2L\desafio && docker compose up -d
```

| Serviço | Onde |
|---|---|
| Web (Next.js 15) | http://localhost:3000 |
| API (FastAPI) | http://localhost:8000 — docs em `/docs` |
| Langfuse | http://localhost:3001 — `demo@hack2l.dev` / `hack2l-password` |
| Postgres | `localhost:5432`, banco `kb`, user/senha `kb`/`kb` |

🚨 **Use `127.0.0.1`, nunca `localhost`.** Medido: `localhost` resolve `::1`
primeiro, o caminho IPv6 aceita a conexão e nunca responde — 0/8 sucesso contra
8/8. Não dá ConnectionRefused, dá ReadTimeout.

```bash
docker compose run --rm api python -m pytest tests -q        # suíte deles: 5 testes, todos passam
docker compose exec db psql -U kb -d kb -c "\d shares"       # schema real
```

Tabelas: `users`, `documents`, `chunks` (`embedding vector(1536)`),
`conversations`, `messages`, `shares` (adicionada pelo PR).

### Os 4 usuários existem para testar isolamento

*"anything involving one user's access to another user's data needs at least
three accounts to test properly."*

| Login | Senha | Tem |
|---|---|---|
| `demo@hack2l.dev` | `demo-password` | 3 documentos |
| `alice@hack2l.dev` | `alice-password` | 1 documento |
| `bob@hack2l.dev` | `bob-password` | 1 documento |
| `carol@hack2l.dev` | `carol-password` | **nada** — controle negativo |

Linha de base antes do PR: `demo=3, alice=1, bob=1, carol=0`.

⚠️ Desde 14/08 essas contas **não estão mais no nosso código** — vêm do
`veredito.yml` do projeto. Ver a seção abaixo.

---

## 🧩 O `veredito.yml` — o projeto se descreve

Até 14/08 as contas estavam chumbadas em `config.py`, e era isso que fazia
**metade do produto só funcionar no desafio**: a prova ponta a ponta, a única
via que sustenta CRÍTICA junto com o árbitro, dependia de quatro emails escritos
no nosso repositório.

| arquivo | descreve | muda por |
|---|---|---|
| `veredito.yml` | **o projeto revisado**: como sobe, como autentica, layout do código, onde é seguro escrever | cliente |
| `.env` | **como nós operamos**: modelo, orçamento, `TOP_N`, timeouts | nunca |

Precedência: **variável de ambiente > `veredito.yml` > padrão do código**. Por
isso `APP_EM_BANCO_DESCARTAVEL=1 py -3.12 -m veredito.orquestrador` continua
servindo para uma rodada pontual.

**Onde mora:** a raiz do projeto revisado (`bancada/veredito.yml`). O do desafio
vive em `hack2l/projetos/desafio.yml` só porque não dá para commitar dentro de
repositório de terceiro.

### Ausente não é vazio, e errado não é ausente

- **sem arquivo** → roda com leitura e grep, e o pré-voo **diz o que perdeu**
- **arquivo errado** → **levanta** (conta sem senha, nomes repetidos, `contas: []`)

Ausência é limite honesto de um projeto que não se descreveu. Arquivo torto é
engano do operador, e seguir com metade dele produz rodada que **parece boa e
não é**.

### O pré-voo diz o que o projeto não vai provar, antes de gastar

Menos de três contas, nenhuma com `possui: 0`, contexto ausente ou apontando
para arquivo inexistente. O **controle negativo** é deduzido de `possui: 0` —
declarar duas vezes é convidar as duas a divergirem.

### Como o app sobe (`subir: true`)

Duas regras, e as duas protegem o ambiente de quem roda:

1. **não derruba o que não subiu** — app de pé é do operador
2. **`preparar` (seed) só roda se NÓS levantamos os containers** — seed reseta
   banco; rodá-lo num app que já servia apagaria dado que não é nosso

Consequência: **`subir: true` num app já no ar é no-op completo** (verificado,
zero comandos ao Docker). É o que torna a opção segura de deixar ligada.

🚫 `preparar` é **lista de argumentos, nunca string com shell** — vem de arquivo
do projeto revisado.

### O PRD, os critérios e as convenções

Estão em **`hack2l/contexto/hack2l.md`**, com arquivo e linha de cada regra nos
docs do desafio (`docs/REVIEW_TASK.md`, `docs/REFERENCE_GUIDE.md`).

🚫 **Não copiar para dentro de prompt.** Foi exatamente isso que causou a
contaminação de 93 acusações. Eles entram por `CONTEXTO_REPO`, em execução.

### Traces

Langfuse sobe provisionado: `LANGFUSE_PUBLIC_KEY=pk-lf-hack2l-public`,
`LANGFUSE_SECRET_KEY=sk-lf-hack2l-secret`, `LANGFUSE_HOST=http://localhost:3001`.

⚠️ **SDK tem que ser `langfuse==2.57.0`** — o servidor é `langfuse/langfuse:2`.
A v4 não conversa com ele.

### ⚠️ A chave da OpenAI é do app deles, não nossa

O app alvo chama `gpt-4o-mini` e `text-embedding-3-small`. Sem `OPENAI_API_KEY`
ele responde **a mesma coisa para qualquer pergunta**, inclusive um payload de
injection — e "não obedeceu" viraria REFUTADO, absolvição falsa. É a regra R4 e
o módulo `llm_alvo.py`. Ver `ACHADO_APP_SEM_MODELO.md`.

---

# ⚠️ API DA ANTHROPIC — medido, não lido na doc

## ❌ `budget_tokens` foi removido (400 no Opus 5)

```
thinking={"type": "adaptive", "display": "summarized"}
output_config={"effort": "high"}          # low | medium | high | xhigh | max
```

- Raciocínio vem **ligado por padrão**; omitir `thinking` não desliga.
- `max_tokens` limita **raciocínio + resposta somados**. Dar folga: 64000.

## 🚨 O raciocínio come o `max_tokens` e a resposta sai VAZIA

Medido em 10/08, e mordeu mesmo com o aviso acima escrito aqui: um prompt de
revisão sobre um diff de **3313 caracteres** voltou `stop_reason="max_tokens"`,
**um bloco `thinking` e ZERO texto** — com `max_tokens=8000` e depois com 16000.

Com `output_config={"effort": "medium"}` foram **947 tokens** e resposta normal.

**Sempre checar `stop_reason` e o tipo dos blocos antes de usar `.text`.** Bloco
de texto ausente não é erro da API — é orçamento mal posto.

⚠️ E `max_tokens` alto demais em chamada não-streaming dá
`ValueError: Streaming is required for operations that may take longer than 10
minutes`. 16000 passa; 32000 não.

## ❌ `temperature`, `top_p`, `top_k` → 400 no Opus 5

Qualquer exemplo copiado com `temperature=0` quebra.

## 🚨 O classificador de cibersegurança pode derrubar o advogado

Recusa **não vem como erro**: HTTP 200, `stop_reason == "refusal"`, `content`
vazio. `response.content[0].text` vira `IndexError`.

**(a)** Checar `stop_reason` **antes** de ler `content`, sempre.
**(b)** O fallback (testado, mas **nunca chegou a pegar uma recusa de verdade**):

```
betas=["server-side-fallback-2026-07-01"]
fallbacks="default"
```

**(c)** E o terceiro estado: recusa vira INCONCLUSIVO, nunca absolvição.

## ❌ Não usar Fable 5 em rodada que vale

Salvaguardas do Fable 5 miram biologia e **a maior parte de cibersegurança** —
exatamente onde investimos.

## ✅ O loop do advogado já existe no SDK

```
from anthropic import beta_tool

@beta_tool
def nome_da_ferramenta(arg: str) -> str:
    """Docstring vira a descrição que o modelo lê.

    Args:
        arg: descrição do argumento.
    """
    return "resultado"

runner = client.beta.messages.tool_runner(
    model=..., max_tokens=..., tools=[...], messages=[...]
)
for msg in runner:      # ← log, teto de voltas, medição
    ...
```

## ✅ Teto por acusação

```
output_config={"task_budget": {"type": "tokens", "total": 30000}}
betas=["task-budgets-2026-03-13"]
```
Mínimo 20.000. O modelo **sabe** que tem orçamento e fecha o parecer.

## ✅ Cache de prompt

Opus 5 cacheia a partir de **512 tokens**; leitura custa ~10%. O diff é o mesmo
prefixo em toda chamada — conferir `usage.cache_read_input_tokens`. Zero = tem
timestamp/UUID/ordem de dicionário variando no prefixo.

⚠️ Disparar as 6 chamadas juntas faz todas pagarem preço cheio: a entrada de
cache só fica legível depois que a primeira resposta começa a chegar. Por isso
`promotores.acusa` roda a primeira sozinha e as outras cinco depois.

---

## MODELOS

```
promotores  → claude-haiku-4-5-20251001
advogado    → claude-opus-5           (adaptive + effort high)
juiz        → claude-sonnet-5
```

**Modelo em variável de ambiente.** *"Haiku para gerar hipóteses, Opus para
verificar, Sonnet para sintetizar — modelo caro só onde a decisão acontece."*

Custo medido: **US$0,071 por acusação verificada** (Opus 5, read_file + grep).

---

## DISCIPLINA DE EXECUÇÃO

1. **`break` no `for` do `tool_runner`** após 10 voltas. Advogado que nunca para
   de pedir ferramenta é o jeito mais rápido de perder a tarde.
2. **Salvar cada etapa em disco.** Promotores → arquivo. Advogado → arquivo.
   Juiz lê do arquivo. Ajustar o juiz pela trigésima vez não pode re-executar o
   advogado. Meia hora que se paga dez vezes.
3. **`TOP_N=2` no dev.**
4. **Conferir o cache na 1ª rodada.**
5. **Somar o `usage` dentro do `for`** → custo por acusação, latência, e o rastro
   de auditabilidade.

---

## SE OS PROMOTORES DEIXAREM PASSAR

**Descubra onde vazou** — imprima a lista bruta. Nunca acusou = cobertura.
Acusou mas não entrou no `TOP_N` = ranking. Conserto diferente.

**Escada, do mais barato ao mais caro:**
1. **Contexto** — promotor de PRD sem PRD não acha nada, com qualquer prompt.
2. **Dividir o promotor** — "segurança de IA" vira injection + vazamento.
3. **Pedir volume explicitamente** (sem pedir seletividade).
4. **Rodar por arquivo**, não por diff inteiro.
5. **Só então trocar de modelo.**

Nenhum depende de saber o que tem no PR. Todos sobrevivem à troca de PR.

**Régua:** se trocássemos o PR por outro, o agente teria que continuar
funcionando. Toda melhoria precisa sobreviver a essa troca.

---

---

## FATOS DE MERCADO — verificados, use estes

- **Promptfoo Code Scanning** escaneia PRs para prompt injection, PII e agência
  excessiva — **com análise estática, não roda a aplicação.** 🚫 Nunca dizer
  "nenhuma ferramenta do mercado faz": é falso e cai em 30 segundos.
- **O curl fechou o bug bounty no fim de janeiro de 2026.** Taxa de confirmação
  acima de 15% por anos, **abaixo de 5% em 2025** com a enxurrada de relatórios
  gerados por IA. US$100 mil pagos por 87 vulnerabilidades antes de desligar.
- **A Cursor comprou a Graphite em 19/12/2025**, acima de ~US$290M.
- **Greptile** já revisou 1 bilhão+ de linhas — por isso não usar "volante de
  dados" como defensibilidade.
- **VulTrial** (ICSE 2026) tem enquadramento multiagente parecido; lá os agentes
  debatem por escrito.

🚫 **Não falar:** "18,6% no PrimeVul Paired", "HackerOne pausou o IBB em março de
2026", "exatamente a mesma arquitetura". Nada disso foi verificado.

🚫 **Não afirmar número sem gabarito.** "Encontrou 4 dos 5 defeitos" é alegação
sobre um gabarito que não temos. *"Provou quatro achados com artefato
reproduzível, descartou seis com motivo e marcou dois como inconclusivos"* é
verdade, está na tela, e é mais forte.

---

## PRINCÍPIOS

1. **Formato da saída primeiro.** Sabendo a cara da saída, o agente se desenha.
2. **Pipeline inteiro rodando cedo**, mesmo burro, antes de refinar peça.
3. **Uma ferramenta boa > quatro pela metade.**
4. **Demoável > sofisticado e invisível.**
5. **Log de tudo** — o rastro responde auditabilidade, custo e latência de uma
   vez.
6. **Medir antes de comemorar.** Os 45% de árbitro que comemoramos mediam
   contaminação. Toda métrica nova merece a pergunta "isto pode estar medindo
   outra coisa?"
