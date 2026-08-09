<!-- tag: hack2l -->

# Veredito — onde paramos e o que vem depois

Escrito na noite de **08/08/2026**, depois do Hack2L. **Segundo lugar.**

Este é o documento para abrir quando alguém voltar ao projeto. Ele existe porque
a coisa mais cara de recuperar não é o código — é o porquê de cada decisão.

---

## 1. O que existe hoje

Nove módulos, seis prompts de promotor, **111 testes**, tudo construído em 08/08.

```
veredito/promotores.py    6 lentes em paralelo (Haiku) + dedup + cota por categoria
veredito/advogado.py      loop de tool_runner (Opus 5) com 5 ferramentas
veredito/ferramentas.py   prova_diferencial, run_tests, read_file, grep, http_request
veredito/juiz.py          6 regras determinísticas, Python puro, SEM modelo
veredito/llm_alvo.py      detecta LLM alvo dublê → força INCONCLUSIVO
veredito/tracing.py       Langfuse; nunca derruba a rodada, por construção
veredito/orquestrador.py  promotores → advogado → juiz
```

**A rodada final, medida:**

| | |
|---|---|
| 5 provados com artefato · 1 descartado com motivo · 0 inconclusivos | |
| 4 críticas | |
| 55 acusações brutas → 6 ao advogado | cota por categoria |
| **329,6 s** (5 min 29 s) | do diff ao parecer |
| **US$ 0,67** | 32.360 entrada · 12.871 saída · 242.002 de cache |

Artefatos e parecer em `saidas/final/rodada_final_1440/`. A rodada das 13h32
está em `saidas/final/rodada_1332/` porque tem o par payload/controle do SQL
injection, que é o melhor artefato visual do projeto.

---

## 2. Isso vira startup?

A resposta honesta: **a tese vale, a demonstração é n=1.** São coisas
diferentes e vale não confundir.

### O que é genuinamente forte

- **"Não reportamos achados, reportamos reproduções"** é posicionamento
  defensável num mercado onde confiança é o gargalo. A história do curl não é
  slide: é prova de que o problema é econômico. Quando confirmar fica caro
  demais, o programa fecha.
- **As duas listas são insight de produto, não truque.** Mostrar o que foi
  descartado e por quê é o que permite confiar na lista que sobrou. Quem dá nota
  pela categoria do bug não consegue fazer isso — precisaria da evidência antes.
- **Unit economics medida no dia um.** A maioria das startups de IA não sabe o
  custo unitário até escalar.

### O que é honestamente demo de hackathon

- **Tudo que sabemos é n=1.** Um PR, um repositório, um dia. A régua que nós
  mesmos escrevemos — *"troca o PR e o agente continua funcionando"* — **nunca
  foi testada.**
- **Cobertura estreita.** 46 das 47 acusações caíram num arquivo só. Seis dos
  onze arquivos do PR eram frontend e receberam **uma** acusação no total.
- **A prova diferencial tem buraco estrutural** exatamente onde a maioria dos PRs
  mexe (ver §4.1).
- **O classificador de cyber recusou um achado ao vivo** e o fallback não pegou
  (§4.2).

### A pergunta que decide: prova é feature ou empresa?

Um incumbente pode acrescentar "e aí a gente roda um teste". Se for só isso, é
feature, e perde para quem tem distribuição.

**Vira empresa se o produto for a infraestrutura de executar ataque real contra
o app do cliente com segurança:** ambiente efêmero por PR, isolamento, gestão de
segredo, controle de raio de explosão, o app do cliente subindo de verdade. É
engenharia chata, cara e demorada — e é exatamente por isso que é fosso.

O segundo fosso é o **artefato de auditoria**. Se o parecer virar peça que o
auditor pede, o comprador não churna. Ferramenta de produtividade se corta;
linha de compliance não.

---

## 3. Os próximos passos, em ordem

### Passo 1 — Rodar contra 10 PRs reais (um fim de semana)

**É o único passo que importa antes de qualquer outra coisa.** Tudo depende de
saber se a régua vale fora deste PR.

Escolher 10 PRs já mergeados de projetos open source diferentes, com stacks
diferentes. Rodar o pipeline em cada um. Medir:

- acusações por categoria — alguma lente sempre vazia?
- distribuição por arquivo — sempre concentra em um só, ou foi deste PR?
- provados / descartados / inconclusivos por rodada
- segundos e dólar por PR

**O que invalida o projeto:** se em 10 PRs a taxa de provados cair para perto de
zero, o que temos é um agente afinado num PR, não um produto.

### Passo 2 — Medir contra gabarito de verdade

O hackathon não tinha gabarito, e por isso o pitch nunca afirmou "achou N de M".
Fora do hackathon **dá para ter gabarito**: PRs que corrigiram CVE conhecido. O
defeito é público, a correção é pública, e o commit anterior tem o bug.

É a única forma de dizer precisão e recall sem inventar.

### Passo 3 — Fechar o caso do endpoint novo (§4.1)

É o buraco no mecanismo carro-chefe. Enquanto não fechar, metade dos achados de
qualquer PR que adiciona rota depende só do `http_request`.

### Passo 4 — Falar com cinco pessoas de AppSec

Descobrir se elas compram artefato, ou se isso cai no orçamento de SAST que elas
já odeiam. Perguntas:

- Quando o auditor pede evidência de revisão, o que você entrega hoje?
- Você deixaria uma ferramenta disparar payload real contra o staging?
- Quem assina: engenharia, segurança ou compliance?

**Não construir mais nada antes de o passo 1 e o passo 4 estarem feitos.**

---

## 4. Buracos conhecidos, com detalhe suficiente para agir

### 4.1 Prova diferencial não funciona em endpoint novo

`prova_diferencial` exige **passa no base, falha no head**. Endpoint que o PR
adiciona **não existe no base** — o teste dá 404 lá e passa no head, que é o
inverso do padrão.

Hoje o `test_share_sql_injection.py` "passa no base" só porque a rota não existe:
a docstring escrita pelo próprio advogado admite isso. O achado continua válido
(o `http_request` provou), mas o diferencial é vazio.

**Direção:** para rota nova, a prova é o `http_request` sozinho, e o parecer
deveria dizer isso em vez de imprimir um diferencial vácuo. Talvez um terceiro
tipo de artefato: `alcance` em vez de `regressao`.

### 4.2 O fallback do Opus não pegou a recusa cyber

Configuração está **correta** — verificada no `advogado.py`:

```python
betas=["task-budgets-2026-03-13", "server-side-fallback-2026-07-01"]
fallbacks="default"
```

Mesmo assim, na rodada das 14h21 a acusação 1 tomou recusa `categoria cyber`,
`entrada 177 saida 269` (recusa no meio do stream), e nenhum dos três sinais de
fallback apareceu. O diagnóstico do `advogado._diagnostico_da_recusa` registrou
honestamente "não dá para afirmar se a cadeia inteira negou".

**Investigar:** se `fallbacks` funciona através do `tool_runner` em modo
streaming. A assinatura aceita o parâmetro; aceitar não é o mesmo que funcionar
nesse caminho.

### 4.3 Cobertura de frontend

46 de 47 acusações em `shares.py`. Quatro das oito convenções do repo (C5–C8)
são de frontend e o promotor de padrões não produziu nenhuma acusação lá.

**Degrau de conserto já mapeado no doc original:** rodar por arquivo em vez de
por diff inteiro. Custa uma rodada a mais de promotores (~$0,05).

### 4.4 O promotor de segurança não cita árbitro para injection

A acusação de SQL injection saiu com `arbitro: null` tendo o **R1** disponível
(*"o dono pode compartilhar com outro usuário identificado por email"* — email
inexistente não é outro usuário). Sem árbitro, a **R1 do juiz rebaixa crítica
para suspeita**, então o achado mais forte do PR nunca pode ser crítico.

**Conserto:** uma linha no `promotores/injection.md` dando exemplos de quando
um requisito do PRD serve de árbitro para um achado de segurança.

### 4.5 Desempate por árbitro: ideia certa, efeito errado

Tentado às 13h45 (`d551e67`), revertido às 13h50 (`cfb3e25`). Preferir acusação
com árbitro em empate de confiança **melhorou o parecer no papel** (1/3 → 3/3 com
árbitro) mas **empurrou o SQL injection para fora do top-10** — porque a versão
com árbitro daquele mesmo defeito estava enquadrada como violação de convenção,
e acusação de padrões pede verificação estática, não disparo de payload.

**A causa raiz é 4.4, não a seleção.** Consertar o prompt primeiro, e só então
reintroduzir o desempate.

### 4.6 O juiz não tem síntese em linguagem natural

`MODEL_JUIZ=claude-sonnet-5` está no config e **nunca é consumido**. O `juiz.py`
não importa `anthropic`. Isso é deliberado para o veredito (o exit code não pode
passar pelo modelo) mas significa que **não há deduplicação semântica** nem
redação do parecer.

Três dos cinco condenados da rodada final são o mesmo SQL injection visto por
três lentes. O dedup determinístico não os funde porque local e árbitro diferem.

**Ou** tirar `MODEL_JUIZ` do `.env.example` para ninguém achar que existe modelo
ali, **ou** construir a camada de síntese — que é o que os organizadores chamam
de *"a synthesizer that de-duplicates and ranks"*.

### 4.7 Artefatos versionados são saída por rodada

`artefatos/*.json` está no git mas é regenerado a cada rodada. Duas máquinas
sobrescrevem uma à outra, e pior: **se o artefato commitado for de uma rodada e
o parecer de outra, os dois não batem** — e o parecer cita o nome do arquivo.

Mesmo problema que o `ambiente.json` teve de manhã e que foi resolvido com
`.gitignore`. Fazer o mesmo, commitando só o que vai para `saidas/final/`.

### 4.8 O bot que comenta no PR

Era a ideia certa na hora errada. O parecer já é markdown com âncora
`arquivo:linha` — falta o canal, não o conteúdo.

**Não postar no repo dos organizadores.** Criar um PR no nosso repo e postar lá
demonstra o mecanismo sem escrever no código de terceiro.

---

## 5. O que não perder

Decisões que custaram caro para aprender. Se alguém for refatorar, **estas não
são preferência de estilo:**

1. **O exit code não passa pelo modelo.** A Regra 0 do juiz existe porque o
   advogado, uma vez, disse PROVADO com o artefato dizendo o contrário.

2. **Terceiro estado obrigatório.** Recusa, timeout, ferramenta quebrada e LLM
   alvo dublê viram INCONCLUSIVO, nunca "absolvido". Absolvição falsa é pior que
   falso alarme porque enche a lista de descartados e **parece rigor**.

3. **O promotor não pede seletividade.** "Reporte apenas o relevante" faz o
   modelo se autocensurar. Cobertura é do promotor, filtragem é do advogado —
   e essa divisão é o produto inteiro.

4. **A primeira chamada vai sozinha, as outras em paralelo.** Cache só fica
   legível depois que a primeira resposta começa a chegar. Disparando as seis
   juntas, cinco pagam preço cheio pelo mesmo diff. Medido duas vezes, por duas
   pessoas independentes.

5. **O prefixo é o diff, e vem antes da lente.** 242 mil dos tokens vieram de
   cache por causa disso.

6. **Severidade acompanha a força da prova, não a gravidade da categoria.**
   Aceitar subestimar um bug real para nunca superestimar um que não existe.

7. **Nunca afirmar número sem gabarito.** "Provou N com artefato, descartou M com
   motivo" é verdade e é mais forte que qualquer porcentagem inventada.

---

## 6. Se for para continuar

O caminho mais curto para saber se isso é real:

```
sábado    10 PRs open source, rodada em cada um, planilha com os números
domingo   5 conversas de AppSec (LinkedIn, comunidade, ex-colegas)
segunda   decidir com dado, não com entusiasmo de pós-hackathon
```

Se em 10 PRs a taxa de provados se sustentar **e** duas das cinco pessoas de
AppSec disserem "eu pagaria por isso", aí vale conversar sério.

Se não, o projeto ainda foi um segundo lugar merecido e um baita fim de semana
de engenharia.
