# Rodada completa — 11/08, pós-refatoração

Primeira rodada ponta a ponta desde o hackathon (08/08). Todo componente mudou
no intervalo: árbitro com procedência, R1 de duas vias, R3b, pré-voo, seleção
(cota + concentração + orçamento), os seis prompts, injeção de contexto.

`py -3.12 -m veredito.orquestrador --top-n 10` · US$1,26 · 9m50s.

## Resultado

8 condenados · 0 descartados · 2 inconclusivos.

Os cinco defeitos do gabarito estão todos representados. 7 dos 8 condenados têm
árbitro com procedência REAL — as cinco citações batem linha a linha nos docs
do desafio (conferido). Era 93 de 94 citando critério de outro projeto em 09/08.

## O que a rodada revelou

- **recusa cyber, medida:** os 2 inconclusivos são `stop_reason=refusal` do
  classificador, nas duas acusações de SQL injection. O `provado_se` delas
  pedia `DROP TABLE users`. O fallback não engajou pelo tool_runner streaming.
- **duplicata no parecer:** itens #3 e #4 são o mesmo defeito por duas lentes,
  linhas próximas mas diferentes — dedup e cap de concentração não pegam.
- **R1 de duas vias não precisou disparar:** as duas CRÍTICAS já tinham árbitro
  com procedência. O conserto do árbitro resolveu o que a 2ª via compensava.
- **lista de descartados vazia:** o PR do desafio é cheio de defeito real, então
  o verificador confirma em vez de refutar. Num PR normal ela encheria.
