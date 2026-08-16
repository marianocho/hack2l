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

## O que ainda não sabemos

- se a mudança de fraseado muda o comportamento na prática: **não medido**. Só
  outra varredura da bancada responde.
- `performance` tem 48 de 78 `provado_se` sem experimento nenhum (`descrição`).
  Não foi investigado, e é a próxima pedra desta mesma calçada.

Relacionado: `ACHADO_ARBITRO_CHUMBADO.md` (critério de projeto dentro da lente)
· `ACHADO_APP_SEM_MODELO.md` (absolvição falsa por observação ausente)
