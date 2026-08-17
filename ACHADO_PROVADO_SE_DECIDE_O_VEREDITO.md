<!-- tag: hack2l -->

# O `provado_se` decide o veredito — medido em 15–16/08/2026

> **O mesmo defeito, a mesma regra citada com procedência, as mesmas ferramentas
> funcionando. O que virou o veredito foi o experimento que o PROMOTOR
> prescreveu.**

## O caso

`pr/reconvite-de-membro` da bancada carrega dois defeitos: o TOCTOU plantado e
um acidental — o campo `convidado_por` devolvido na resposta de
`adiciona_membro`, fora do contrato.

Duas rodadas, mesmo commit (`7df223d`), só o `--top-n` mudando:

| rodada | quem julgou o defeito acidental | `provado_se` | veredito |
|---|---|---|---|
| `--top-n 3` | `padroes_01` | *"**grep** por `def adiciona_membro` mostra return anterior com apenas project_id, user_id, novo…"* | **REFUTADO** |
| `--top-n 8` | `prd_01` | *"**chamar** adiciona_membro e verificar se a resposta contém campo `convidado_por`…"* | **PROVADO** |

O que NÃO explica a diferença, conferido:

- **não é o árbitro.** As duas citaram a mesma regra, com procedência, no mesmo
  `docs/REGRAS.md`. Foi a primeira hipótese e estava errada.
- **não é ferramenta quebrada.** `ferramentas_ok=3, erro=0` nas duas.
- **não é orçamento.** Mesmo com `--top-n 8` sobraram acusações sobre este
  defeito fora do julgamento, por cota cheia (22ª na fila). O teto não foi o
  gargalo — foi *qual* acusação entrou.

O que explica: quem mandou **ler** produziu veredito argumentado. O advogado leu
o fonte, não achou `response_model` declarado, e concluiu que não havia contrato
a violar. Quem mandou **chamar** produziu prova: teste diferencial que passa em
`f3bdd65` e falha em `7df223d`.

E o motivo do que provou trata a objeção do outro de frente — *"fora do contrato
de resposta ({project_id, user_id, novo}) **e sem response_model declarado**,
violando docs/REGRAS.md:31"*. A regra tem duas orações; a refutação leu uma.

## Não foi acaso: está escrito no prompt

Varredura das 19 rodadas gravadas, 503 `provado_se` classificados por prescrever
**execução**, **leitura**, **misto** ou nenhum experimento (**descrição**):

| lente | execução | leitura | misto | descrição | % leitura |
|---|---|---|---|---|---|
| correcao | 87 | 4 | 4 | 19 | 4% |
| prd | 71 | 6 | 2 | 29 | 6% |
| **padroes** | **10** | **52** | **10** | **19** | **57%** |
| vazamento_de_contexto | 77 | 3 | 3 | 5 | 3% |
| performance | 21 | 6 | 3 | 48 | 8% |
| injection | 17 | 0 | 0 | 7 | 0% |

A causa estava em `promotores/padroes.md`, explícita:

> *"Violação de convenção é, em geral, **estática** — provável por leitura de
> código, não com o app rodando. Fraseie como uma verificação observável de
> `read_file`/`grep`."*

As outras cinco lentes dizem o oposto: *"Diz em `provado_se` o teste ou a chamada
que prova."*

## O custo, dentro da mesma lente

O corte que controla o tipo de defeito — só acusações de `padroes`, julgadas:

| `provado_se` | PROVADO | REFUTADO | INCONCLUSIVO | n |
|---|---|---|---|---|
| execução | **6** | 0 | 0 | 6 |
| leitura | 4 | 6 | 1 | 11 |

⚠️ **n=6 e n=11.** Poucos. E o classificador é heurística de palavra-chave
escrita para esta varredura, não instrumento validado. A direção é consistente
com o mecanismo observado nas duas rodadas, mas isto não estabelece taxa.

⚠️ E a pergunta obrigatória da casa — *isto pode estar medindo outra coisa?* O
corte dentro da lente controla o tipo de defeito, mas não controla a
possibilidade de acusações mais fracas tenderem, elas próprias, a virar
`provado_se` de leitura.

## Por que é o padrão de bug da casa, um andar acima

A arquitetura promete **"não argumenta, TESTA"**. Mas quem decide se o advogado
vai testar é um campo que o **promotor** escreve, e o `CLAUDE.md` diz para que
ele existe: *"o advogado já começa sabendo o que procurar, em vez de gastar
voltas do loop decidindo"*.

Aqui ele fez o contrário: apontou para leitura estática, e a absolvição falsa
entrou **pelo campo que existe para dirigir a prova**. A guarda central do
produto pode ser contornada por uma lente que prescreve `grep`, e nada avisa.

Mesma forma do R0b, do R3, do dedup e do `_bandit`: a guarda existe, mas está
condicionada a uma entrada que ninguém confere.

## O conserto

`promotores/padroes.md`, seção `Como escrever provado_se`: a lente passa a
perguntar **primeiro** se a convenção é observável de fora, e só cai na leitura
quando ela existe **só** no código. Na dúvida, prescreve execução — porque errar
para o lado da execução custa voltas do laço, e errar para o lado da leitura
custa defeito real dado como refutado.

🚫 O exemplo do prompt é **genérico de propósito**. A primeira versão desta
edição usava `POST /projects/{id}/members`, rota real da bancada — a mesma forma
de contaminação que os 93 árbitros do desafio custaram.

## O conserto, medido — e a varredura não bastava

A varredura seguinte da bancada **pareceu** confirmar, e não confirmava: as
outras cinco lentes, que ninguém tocou, tinham se movido na mesma direção
(`prd` 85%→100%, `vazamento` 94%→100%, `performance` 71%→100%). Com 2–4
acusações por PR, "melhorou" e "variou" têm a mesma cara — e a varredura custa
~US$2 para não distinguir as duas.

O A/B distingue (`experimento_prompt.py`): mesmo diff, mesmo modelo, N
repetições, só o prompt mudando. 48 chamadas de Haiku, centavos.

| prompt | exec | leit | **% execução** |
|---|---|---|---|
| antes | 1 | 42 | **2%** |
| depois da 1ª versão | 14 | 35 | 29% |
| depois de endurecido | 20 | 29 | **41%** |

E generaliza — nos três diffs, apertado: 40%, 43%, 40%. A primeira versão dava
31%, 12%, 41%, que é dispersão de quem acertou num caso.

### O alvo NÃO é 100%, e por pouco eu errei isso

Escrevi "60–70%" como meta antes de olhar o conteúdo. Número sem fundamento.
Lendo as 17 prescrições de leitura que sobravam, **~12 estavam certas** —
camada pulada, consulta no handler, comentário, padrão de migração: convenção
que só existe no código. O teto útil nestes diffs é ~40–45%, e empurrar além
faria a lente inventar enquadramento executável para o que não é observável.

Isso é o primo do padrão de bug — otimizar a métrica em vez da coisa. O
endurecimento mirou **as duas classes mal atribuídas**, não a porcentagem:

| classe | antes | depois |
|---|---|---|
| forma da resposta *(o defeito falsamente refutado)* | 11% | **82%** |
| SQL montado por interpolação | 0% | 46% |

## O que ainda não sabemos

- **fraseado não é veredito.** O A/B mede o que a lente emite; a ponte para o
  veredito é a tabela 6/6 contra 4/11, com n minúsculo. Número melhor aqui é
  hipótese de melhora lá.
- **variância é grande.** Numa amostra de N=4 o prompt antigo deu 25% num diff
  onde a de N=8 deu 0%. Rodar uma vez e comemorar é o erro que este arnês
  existe para evitar — inclusive quando o resultado agrada.
## ❌ A pedra seguinte não era pedra — investigada em 16/08

Ficou registrado aqui que `performance` tinha **48 de 78** `provado_se` sem
experimento nenhum (`descrição`), e que era "a próxima pedra desta mesma
calçada". **Foi investigado e não se sustenta.**

| `provado_se` de `performance` | PROVADO | REFUTADO | INCONCL. | n |
|---|---|---|---|---|
| execução | 2 | 1 | 0 | 3 |
| **descrição** | **5** | **0** | 2 | 7 |

Nenhuma das 7 descrições julgadas citava medida, e 5 foram provadas assim mesmo.
As 2 inconclusivas são infraestrutura — a rodada com o layout chumbado (4
ferramentas com erro) e um `BadRequestError` de saldo da API. Nenhuma
atribuível ao fraseado.

**O erro foi meu, e é de categoria:** tratei `descrição` e `leitura` como a mesma
coisa porque o classificador chama as duas de "não-execução". São opostas no que
importa:

- **leitura** *(o defeito real)* — **desvia** o advogado para um método que
  produz absolvição falsa. Ele lê, não acha o que violar, encerra o assunto.
- **descrição** *(não é defeito)* — **deixa o método aberto**, e o advogado
  escolhe um bom. O PROVADO do PR limpo em 16/08 veio de uma descrição sem
  medida citada, e ele inventou a carga de 800 linhas e o `EXPLAIN` sozinho.

O que torna a leitura nociva não é ela deixar de ser execução — é ela
**prescrever o método errado**. Um campo vago não faz mal; um campo que aponta
para o lugar errado, sim.

⚠️ n=7 e n=3. Isto não prova que descrição é boa — prova que **o caso para
mexer não está feito**, que é diferente. Mexer no prompt aqui seria otimizar a
métrica contra o conteúdo, exatamente o que a seção acima diz para não fazer.

## O que ainda não sabemos

- **fraseado não é veredito.** O A/B mede o que a lente emite; a ponte para o
  veredito é a tabela 6/6 contra 4/11, com n minúsculo. Número melhor aqui é
  hipótese de melhora lá.
- **variância é grande.** Numa amostra de N=4 o prompt antigo deu 25% num diff
  onde a de N=8 deu 0%. Rodar uma vez e comemorar é o erro que este arnês
  existe para evitar — inclusive quando o resultado agrada.

Relacionado: `ACHADO_ARBITRO_CHUMBADO.md` (critério de projeto dentro da lente)
· `ACHADO_APP_SEM_MODELO.md` (absolvição falsa por observação ausente)
