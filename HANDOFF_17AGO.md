<!-- tag: hack2l -->

# Handoff — 17/08/2026, madrugada

> **Leia primeiro:** `CLAUDE.md` (produto) e `../CLAUDE.md` (máquina) carregam
> sozinhos. `PROXIMOS_PASSOS.md` é a fila viva. Este arquivo é só o **delta** da
> sessão de 16–17/08 e a decisão que ficou aberta.

## Estado verificado

**480 testes verdes** (`py -3.12 -m pytest -q -m "not lento"`, ~30s).
`main == origin/main` em `3d9c8b6`. Bancada e desafio conferidos.

⚠️ O comando roda **de dentro de `hack2l/`**, com `-m`. Sem isso não acha o
pacote `veredito` — não há `conftest.py` nem `__init__.py` em `tests/`.

## O que a sessão entregou

Detalhe em `ACHADO_PROVADO_SE_DECIDE_O_VEREDITO.md` e no diário do vault
(`diário/2026-08-16.md`). O essencial:

| | |
|---|---|
| **Licença** | Apache-2.0. Era o bloqueador nº 2 |
| **`revisa_pr.py`** | a entrada "revise este PR". Era o bloqueador nº 1 |
| **`experimento_prompt.py`** | A/B de prompt por centavos, com desfecho colado no número |
| Três guardas mudas consertadas | scanner, encoding do relatório, retrato do banco |
| Controle negativo | voltou a ser negativo (`index=True` na bancada) |

## 🎯 A decisão que está aberta — comece por aqui

A primeira revisão de um PR de terceiro pela porta da frente rodou
(`pallets/flask#6095`, `--top-n 2`, US$~0,15) e deu:

```
34 suspeitas levantadas, 5 testadas.
0 com parecer, 0 descartados com motivo, 5 INCONCLUSIVOS com causa.
```

**Zero refutações** — quando o ativo provado do produto é refutar (68% em repo
de terceiro). E não foi o advogado raciocinando mal: num deles ele escreve que a
hipótese *"contraria a assinatura documentada de pytest, `delenv(name,
raising=True)`"*. Refutação correta, obtida por leitura, com a ferramenta que
funcionava. Saiu INCONCLUSIVO.

**Duas causas, e a segunda é de doutrina:**

**(a) Terceira instância do padrão de chumbado.** `CODIGO_TESTES_NO_REPO` tem
como padrão `app/api/tests` — o layout do desafio ([config.py:412](veredito/config.py:412)).
No Flask não existe, `prova_diferencial` aborta. O comentário logo acima dessa
linha documenta que esse mesmo chumbado já custou uma rodada em 15/08.

> Conserto: caminhos vazios quando não declarados, e `prova_diferencial` recusa
> dizendo isso — igual ao `http_request` desde 17/08. **Seguro, e eu faria.**

**(b) A R3 confunde dois estados.**

| estado | hoje | devia ser |
|---|---|---|
| a ferramenta **quebrou** | INCONCLUSIVO | INCONCLUSIVO ✅ |
| a ferramenta **não existe** porque o projeto não a declarou | INCONCLUSIVO | limite conhecido, não contamina o veredito |

Resultado: num repo sem `veredito.yml`, **toda** acusação vira inconclusiva,
mesmo quando a leitura sozinha foi suficiente. A capacidade medida em 68% fica
inalcançável pela porta nova.

> 🚫 O (b) mexe na regra central do juiz — a que impede absolvição falsa.
> Afrouxar errado ali é o erro mais caro possível neste projeto. **Não fazer sem
> decidir com o Luis.**

## O que 16–17/08 estabeleceu como regra

> **Guarda que não consegue olhar tem que dizer que não olhou.** Diferente de
> olhar e não achar nada. É o terceiro estado, generalizado para fora do veredito.

> **Medição que não separa melhora de variância não é medição.** A varredura da
> bancada (US$2) respondia menos que o A/B (centavos), porque as outras cinco
> lentes se moveram junto sem ninguém tocar nelas.

> **Otimizar a métrica não é otimizar a coisa.** O alvo do `provado_se` nunca
> foi "mais execução", e sim "a prescrição bater com a observabilidade".

E o padrão que se repetiu **cinco vezes** na sessão, sempre igual: *valor padrão
do código apontando para o desafio*. Contas, `APP_API_URL`, `-U kb` do psql,
`py -3.12` no `fontes.py`, e agora `app/api/tests`. O conserto foi sempre trocar
**lista mantida por critério derivado**.

## Armadilhas que morderam nesta sessão

- 🚨 **`pytest ... | tail` engole o exit code.** Commitei com teste vermelho por
  causa disso. O `../CLAUDE.md` avisa sobre o mesmo com `docker compose | tail`.
  Leia o `$?` sem pipe.
- **Emoji em `print()` derruba o console cp1252.** Há teste
  (`test_saida_no_console`); a convenção é `[!]`.
- **Contaminação do árbitro reincide fácil.** Escrevi nome real da bancada dentro
  de uma lente duas vezes no mesmo dia. Agora há trava derivada por contraste
  entre projetos irmãos (`test_prompts_limpos`).
- **O `.env` não define `APP_API_URL`**; funciona por coincidência com o padrão
  do código. Ver a fila.

## Depois da decisão

Pela fila: **entregar o parecer como comentário de PR** — é o que falta entre a
entrada e a Action, e o `PROXIMOS_PASSOS` lista os cinco pontos. Mais o canário
de egresso, junto ao repo de demonstração.
