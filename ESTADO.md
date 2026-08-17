<!-- tag: hack2l -->

# ESTADO — 08/08/2026, ~12h00  ⟨HISTÓRICO⟩

> 🚫 **Não é a fila viva.** Este é o handoff do **dia do hackathon**, preservado
> como está — fala de "a máquina do palco" e "o slide". Os números aqui estão
> superados (dizia "53 testes rápidos + 5 lentos"; em 16/08 são 448).
>
> **Onde retomar: `PROXIMOS_PASSOS.md`.**
>
> Não foi atualizado de propósito: uma terceira fonte de verdade ao lado do
> `PROXIMOS_PASSOS.md` e do `Onde retomar.md` do vault divergiria em silêncio —
> e as duas que já existem divergiram **nos dois sentidos** em 15/08.

Handoff para a próxima sessão. O **README.md** explica a arquitetura; o
**CONTRATO.md**, as interfaces. Este arquivo diz só onde paramos e o que fazer.

## O produto está completo e roda ponta a ponta

```bash
python -m veredito.orquestrador --top-n 10     # rodada de verdade
python -m veredito.orquestrador --reusar       # sem re-rodar promotores
python -m veredito.orquestrador --manual       # 1 acusação de bancada, sem promotores
```

| peça | estado |
|---|---|
| `promotores.py` | ✅ 6 lentes em paralelo, cota por categoria, diagnóstico |
| `ferramentas.py` | ✅ 5 tools, 53 testes rápidos + 5 lentos |
| `advogado.py` | ✅ loop do `tool_runner`, terceiro estado, fechamento forçado |
| `juiz.py` | ✅ R0–R4 + parecer |
| `orquestrador.py` | ✅ grava cada etapa em disco |

## Números medidos, não estimados

| | |
|---|---|
| 6 promotores (Haiku, paralelo) | ~20 s, **54 acusações brutas** |
| 1 acusação no advogado (Opus 5) | **~90 s**, 6 voltas, 14,5k entrada / 3,3k saída |
| cache do advogado | **~55–65k lidos por acusação** — o prefixo está estável |
| prova diferencial | ~14 s (21 s quando há confirmação no base) |
| `pytest` do alvo | 2,43 s |
| diff do PR | 19.001 caracteres |

**A rodada final leva ~15 min, não 36.** O doc estimava 12 × 3 min de timeout; o
timeout raramente é atingido. Pode começar 14h30 com folga — mas confirme com
uma rodada cronometrada antes de confiar nisso.

⚠️ **O laço do advogado tem que ficar sequencial.** A prova diferencial roda
`pytest` contra `kb_test`, que dropa o schema entre testes — duas provas em
paralelo colidem. Os *promotores* paralelizam; o advogado não.

## O que falta, em ordem de risco

1. **Rodada completa cronometrada** com `--top-n 10`. Nunca foi feita. É ela que
   valida o número acima e alimenta o slide de resultado.
2. **A máquina do palco nunca rodou o produto.** O Luis fez paridade de
   ambiente, mas o pipeline não rodou lá. Isso é bloqueio de demo.
3. **Severidade travada em MÉDIA.** A R2 rebaixa toda prova que não é ponta a
   ponta, e até agora tudo veio de teste diferencial. Para uma CRÍTICA no
   parecer, o advogado precisa provar por `http_request` também — a instrução já
   está no prompt, falta ver acontecer. **O LLM alvo está VIVO agora**, então
   injection é testável.
4. **Langfuse indefinido.** O CLAUDE.md manda instrumentar (os organizadores
   dizem 2× que link de trace é a prova mais limpa de que o fluxo multiagente
   rodou); o PLANO põe como 1º item de corte. Ninguém decidiu.
5. **Cosmético:** o `local` da acusação vai cru para o parecer, então o slide
   pode mostrar `app/routers/shares.py` onde o caminho real é
   `app/api/app/routers/shares.py`. O `read_file` já resolve as duas grafias; só
   o texto do parecer não normaliza.

## Contaminação — o que esta sessão viu do PR

Relevante porque a régua do desafio é não chumbar achado.

**O diff nunca foi impresso.** É carregado por código, passado ao modelo e nunca
exibido. O que entrou no contexto do assistente:

- 2 nomes de arquivo e `14 files changed, 417 insertions`, de um `git diff --stat`
  no começo do dia;
- nomes dos endpoints de share, vindos do `REVIEW_TASK.md` (briefing público);
- **dois achados concretos, pelo relatório do agente** — um em `GET /shared/{doc_id}`
  e um de SQL injection no share por e-mail. Vieram do parecer, que é o fluxo
  pretendido: o agente achou, o humano leu.

Nenhum prompt do repo cita arquivo, linha ou achado. Os promotores descrevem
**classes de defeito**; a acusação de bancada é a **invariante** do desafio, não
um achado. Troca o PR e tudo continua válido — é isso que sustenta a régua.

## Ambiente desta máquina

Portas **8010 / 3010 / 55432 / 3001** (as padrão estavam ocupadas). Sempre
`127.0.0.1`, nunca `localhost` — o caminho IPv6 do Docker pendura.

**A chave da OpenAI está ativa e o LLM alvo está VIVO.** Se alguém recriar o
banco, **re-semeie**: os chunks precisam ser re-embeddados. O seed é idempotente
e *pula* se os documentos existirem, então limpe antes:

```bash
docker compose ... exec -T db psql -U kb -d kb -c "delete from chunks; delete from documents;"
docker compose ... run --rm seed
```

Sintoma de embedding misturado: duas perguntas diferentes citam os mesmos
documentos na mesma ordem. Confira que cada pergunta rankeia o documento certo
em primeiro antes de confiar em qualquer teste de canário.

## Divisão

`ferramentas.py`, `juiz.py`, `config.py`, `advogado.py`, `orquestrador.py`,
`promotores.py` → Mariano. `llm_alvo.py` e `promotores/*.md` → Luis, que está no
pitch e nas 6 exigências do desafio.
