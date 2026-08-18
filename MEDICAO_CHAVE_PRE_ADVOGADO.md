<!-- tag: hack2l -->

# A chave do pré-advogado: medida, e não afrouxada

> **18/08/2026.** 606 acusações de 27 rodadas no disco. Custo: zero de API.
> **Conclusão: não afrouxar.** O que a fusão de apresentação resolveu com
> segurança, a mesma chave não resolve um nível acima.

## O que se queria

`promotores.deduplica` funde acusações **antes** do advogado, por
`(local, arbitro)` com casamento exato. A fusão de apresentação (`fusao.py`,
18/08) mostrou que essa chave é rígida demais: os dois campos oscilam de
redação, e um defeito passava como três achados.

A pergunta era se a chave nova — `(arquivo, procedência)` com proximidade de
linha — poderia substituir a antiga também na seleção.

## O que a medição achou

| | acusações | fusões |
|---|---|---|
| chave atual | 606 | **11** |
| chave da apresentação | 606 | **88** |

88 contra 11 parece vitória. **É o padrão dos 45% de árbitro:** o número subiu
medindo a coisa errada. Lendo os **41 grupos novos** à mão, ~20 fundem defeitos
genuinamente distintos. O pior caso:

```
correcao_05     MAX_SHARES_PER_DOC é lido e NUNCA USADO; limite não é verificado
padroes_07      leitura de config via os.getenv em vez do módulo
performance_06  lido e parseado a cada POST, sem cache
```

Três defeitos, mesma linha, mesma regra citada. Fundir apaga *"o limite nunca é
verificado"* — bug funcional real — antes de qualquer verificação. É o
contraexemplo do `encode/httpx#3730` do `CLAUDE.md` se repetindo, agora **com o
árbitro preenchido nos dois lados**.

> **A mesma chave é segura para apresentar e perigosa para selecionar.** No
> parecer, uma fusão errada não esconde nada — as hipóteses e as provas seguem
> no bloco. Na seleção, o fundido **nunca é verificado**: ele reaparece só como
> uma linha em "fundidas por duplicata".

## O portão de similaridade: testado, e não separa o bastante

A ideia: exigir que as **hipóteses digam a mesma coisa**, não só que caiam no
mesmo endereço. Chave exige igualdade e paráfrase nunca casa duas vezes — mas
um *portão* só precisa ordenar, e duas paráfrases do mesmo defeito compartilham
vocabulário raro.

⚠️ **A primeira medição estava errada, e o erro era meu.** Agreguei pelo *elo
mais fraco* (o pior par do grupo): um grupo de 6 tem 15 pares e paga pelo pior,
um par tem 1. Isso empurra para baixo justamente as pilhas grandes — as fusões
mais claramente corretas do corpus. Com a média dos pares:

| agregação | bons (15) | ruins (15) | ruins acima do pior bom |
|---|---|---|---|
| elo mais fraco | mediana **0,20** | mediana **0,05** | 8/15 |
| média dos pares | mediana **0,22** | mediana **0,07** | **4/15** |

As medianas separam; **as caudas se tocam**. O custo de cada corte:

| corte | vagas liberadas | fusões certas mantidas | fusões erradas passando |
|---|---|---|---|
| 0,10 | 63 | 15/15 | 4/15 |
| 0,15 | 44 | 12/15 | 2/15 |
| 0,20 | 17 | 8/15 | 1/15 |
| **0,25** | **14** | 6/15 | **0/15** |

## 🚨 E o benefício não é dinheiro

`TOP_N` é **teto DURO** (`promotores.py:536`). O advogado verifica N acusações
e para. A vaga que o dedup libera **é preenchida pela próxima da fila** — a
rodada custa exatamente o mesmo.

O que o dedup compra é **cobertura**: o mesmo dinheiro verificando suspeitas
mais distintas. Handoffs anteriores diziam que afrouxar a chave "economizaria
API de verdade"; está corrigido.

No corte seguro (0,25), são **14 vagas em 27 rodadas** — meia vaga por rodada,
de cobertura, não de custo.

## Por que fica como está

1. **Não economiza** o que a fila achava que economizava.
2. O ganho seguro é ~0,5 vaga/rodada de cobertura.
3. O erro que ela arrisca é o caro: defeito real que não chega ao advogado.
4. O problema visível ao cliente **já foi resolvido** na apresentação.

⚠️ **E a calibração não é confiável ainda:** eu escrevi os rótulos de "bom" e
"ruim" *e* desenhei a métrica, sobre 30 grupos. Ajustar um limiar aos próprios
rótulos, nessa amostra, é exatamente o tipo de número que este projeto já
comemorou errado duas vezes. Um limiar só vale com rótulo de terceiro, ou com
gabarito.

## O que destravaria

- **Rótulo independente** dos 41 grupos (não meu), ou um gabarito de quais
  acusações são o mesmo defeito.
- Ou tornar o teto do `TOP_N` **mole para duplicatas** — aí o dedup passaria a
  economizar de verdade, e a conta muda inteira.

---

# A prova empírica: medida em 18/08, e funciona

> **"Mesmo defeito" não precisa ser inferido. Dá para provar por exit code.**
> Custo: zero de API, três execuções de container de menos de um segundo.

## A pergunta

A fusão que subiu hoje decide por **endereço + procedência** — é inferência.
O produto inteiro recusa esse tipo de argumento em todo lugar menos aqui.

O teste empírico: duas acusações são o mesmo defeito se **a mesma mudança faz
os dois testes pararem de falhar**. Os artefatos já guardam o que isso precisa —
o arquivo de teste e os dois commits.

## O caso: `luisfelp07/bancada#1`

Diff de um trecho, com **uma** mudança de comportamento:

```python
-    if t is None or t.project_id not in _projetos_visiveis(db, user):
+    if t is None:
```

O resto é docstring. Três acusações (`correcao_01`, `padroes_01`,
`performance_01`), três arquivos de teste diferentes.

| versão | correcao | padroes | performance | |
|---|---|---|---|---|
| head (o PR) | falha | falha | falha | as três acusam |
| head **− docstring** | falha | falha | falha | ⬅ **controle negativo** |
| head **− a condição** | **passa** | **passa** | **passa** | ⬅ um trecho explica as três |

`4 failed, 1 passed` → `5 passed`, revertendo uma linha.

🚨 **O controle negativo é o que dá sentido ao resultado.** Sem ele, "reverter o
diff conserta" seria trivialmente verdade e não diria nada sobre serem o mesmo
defeito. Com ele, a falha fica atribuída **àquela linha**.

**Veredito: as três acusações são um defeito, provado por exit code.** Sem
modelo, sem limiar, sem os meus rótulos. A heurística que subiu hoje acertou
este caso — mas agora isso é sabido, e não suposto.

## 🚨 A correção que este experimento forçou

Este documento dizia que a seleção "nunca vai poder provar, por necessidade".
**Só vale para a primeira acusação.**

`prova_diferencial` é uma FERRAMENTA (`ferramentas.py:1143`) e grava o artefato
no instante da chamada (`:829`) — no meio do laço, não no fim. Então na acusação
#3 já existem artefatos de #1 e #2.

O que impede o uso disso não é a natureza do problema, é uma linha:

```python
acusacoes, escopo = promotores.seleciona_com_escopo(brutas, teto)  # :323, UMA vez
for i, a in enumerate(acusacoes, 1):                               # :360, o laço caro
```

A fila é montada uma vez e congela. **Re-ranquear a cada artefato** faria a
evidência voltar para a seleção — e encaixa no *teto MOLE* que o `CLAUDE.md` já
descreve: "o excedente vai para o fim da fila, nunca para o lixo".

| | evidência | como decidir |
|---|---|---|
| acusação #1 | nenhuma | heurística, inevitável |
| acusações #2..#N | artefatos das anteriores | **provável — hoje desperdiçado** |
| apresentação | tudo | **provável** |

## Onde não alcança

Precisa de artefato e de Docker: só onde a `prova_diferencial` funciona, isto é,
projeto que declara `codigo` no `veredito.yml`. Em PR de terceiro com só
`read_file` e `grep` não há teste para rodar, e a fusão cai na heurística — a
mesma degradação honesta do resto do produto.
