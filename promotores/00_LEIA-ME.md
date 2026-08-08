<!-- tag: hack2l -->

# promotores/ — o contrato de integração (Luis → Mariano)

Seis prompts de promotor, texto puro. **O código lê esta pasta; não importa nada
daqui.** Integração = commit. Cada `.md` é um prompt **completo e autônomo**.

Escritos **sem ler o diff do PR** — só com o PRD, os critérios de aceite, as 8
convenções e o mapa do app (tudo do lado limpo do muro de contaminação). A régua
se mantém: troca o PR, os prompts continuam válidos, porque descrevem **classes
de defeito**, não achados chumbados.

## Os arquivos

| Arquivo | `categoria` que emite | bucket (p/ a cota do juiz) |
|---|---|---|
| `prd.md` | `prd` | prd |
| `injection.md` | `injection` | seguranca_ia |
| `vazamento_contexto.md` | `vazamento_de_contexto` | seguranca_ia |
| `correcao.md` | `correcao` | correcao |
| `padroes.md` | `padroes` | padroes |
| `performance.md` | `performance` | performance |

Segurança de IA foi **dividida em dois** promotores (injection + vazamento) — é
o degrau 2 da escada de conserto do doc, e é onde investimos. Os dois caem no
bucket `seguranca_ia`.

## Como montar a mensagem de cada promotor

```
[ diff do PR + código em volta ]      <- prefixo grande, IGUAL nos 6
[ conteúdo do arquivo .md ]           <- a lente, específica de cada um
```

**Ordem importa para o cache.** Ponha o diff **antes** da lente. O prefixo é
idêntico nas 6 chamadas → o Opus/Haiku cacheia o diff uma vez e relê a ~10% nas
outras cinco. Conferir `cache_read_input_tokens > 0` na 1ª rodada; se vier zero,
tem algo variando no prefixo (timestamp/ordem de dict).

Cada `.md` já traz o esquema de saída e o exemplo de formato. O modelo responde
**um array JSON** e nada mais. Mantenha o `try/except` no parse com fallback pra
saída crua — está no CONTRATO, e é o que impede a acusação de morrer por formato.

## Esquema que os promotores emitem (o do CONTRATO, sem alterações)

```json
{ "id": "...", "categoria": "...", "local": "arquivo:linha",
  "hipotese": "uma linha", "arbitro": "AC2 | C3 | INV-... | null",
  "provado_se": "uma linha", "confianca": "alta|media|baixa" }
```

**`id` é prefixado por categoria** (`prd_01`, `injection_01`, …) para não colidir
entre os 6 promotores rodando em paralelo. Se você preferir `acusacao_NN` global,
renumere no merge — a única exigência da fronteira é que sejam únicos.

## Vocabulário do campo `arbitro` (para as regras determinísticas do juiz)

- **PRD:** `R1 R2 R3 R4 AC1 AC2 AC3 AC4 AC5`
- **Isolamento/injection:** `INV-ISOLAMENTO`, `INV-INSTRUCAO-NAO-E-DADO`
- **Padrões:** `C1`…`C8`
- **Correção/performance:** em geral `null`

A regra do juiz "CRÍTICA sem árbitro → SUSPEITA" consome exatamente este campo.

## ⚠️ Dois pontos de integração que preciso te passar

**1. `prova_diferencial` não serve para bug em endpoint NOVO.** Os endpoints de
share (`/documents/{id}/share`, `/shared-with-me`, `/shared/{id}`) **não existem
no commit base** — um teste que os chama dá 404 no base (falha) e funciona no
head. Isso é o **inverso** do padrão "passa no base, falha no head". Então:

- Regressão em comportamento **que já existia** (isolamento de `/documents`,
  `/chat`, a linha de base) → `prova_diferencial`. É aqui que ela brilha, e a
  linha de base (`demo=3, alice=1, bob=1, carol=0`) é um diferencial de uma linha.
- Bug **em endpoint novo** → teste que **falha no head** expressando o certo, ou
  `http_request` mostrando o errado. **Não** diferencial.

Os `provado_se` dos promotores já vêm roteados por essa distinção. O advogado
precisa saber escolher a ferramenta na mesma lógica — senão vira INCONCLUSIVO à
toa.

**2. A cota do juiz não tem vaga de `performance`.** A tabela da rodada final é
seguranca_ia(3) · prd(2) · correcao(2) · padroes(2) · curinga(1) = 10. Como
adicionei a 5ª categoria que o enunciado nomeia, ou você dá 1 vaga a performance
(total 11), ou ela disputa só o curinga. Recomendo `performance: 1`. É uma linha
no orquestrador — decide junto com o `TOP_N` das 12h, com a medição.

## Contaminação

Estes prompts não citam nenhum arquivo nem linha do diff. Os nomes de endpoint
que aparecem (`/share`, `/shared-with-me`, `/shared/{id}`) vêm da **descrição do
PR no `REVIEW_TASK.md`** — briefing público, não o diff. Nada aqui chumba achado.
