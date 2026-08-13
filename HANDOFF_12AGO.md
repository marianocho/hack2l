<!-- tag: hack2l -->

# HANDOFF — para a sessão de 12/08

Escrito no fim de 11/08. **Leia este arquivo primeiro.** Ele é o delta do dia e
diz onde retomar. O `PROXIMOS_PASSOS.md` tem o quadro geral e a fila completa.

---

## 0. Em uma frase

Veredito é um revisor de código multiagente onde **o veredito é um exit code**,
não opinião de modelo. Segundo lugar no Hack2L (08/08). Em 11/08 o motor foi
medido **nos dois sentidos** pela primeira vez, e o produto ganhou uma camada de
segurança que ele não tinha.

**O Carlos Dutra (autor do desafio) demonstrou interesse em investir.** Nenhuma
decisão foi tomada, nada foi assinado.

---

## 1. O estado, em números

```
17 commits em 11/08, tudo empurrado    github.com/marianocho/hack2l
263 testes passando                     (eram 116 no início do dia)
US$ ~1,30 por PR completo (10 acusações verificadas)
```

⚠️ Um teste é **intermitente**: `test_llm_alvo.py::test_duas_sondas_diferentes`
sonda o LLM do app alvo e depende de rede/timing. Falhou uma vez em três
execuções. Não é regressão — rode de novo antes de investigar.

### O placar do produto, com as duas pontas fechadas

| condição | resultado |
|---|---|
| PR **com** defeito plantado | **10 de 10 provados**, com artefato |
| PR **sem** defeito | **8 de 8 refutados**, com motivo |
| PRs de terceiro (10 PRs reais) | 68% refutados, US$0,071/alegação |

É o critério que o Carlos deu em 06/08 — *"precisão vale tanto quanto
cobertura"* — e agora tem número dos dois lados. As rodadas estão em
`saidas/final/`, cada uma com um `LEIA.md`.

---

## 2. O que mudou em 11/08

### O árbitro foi desacoplado (era a tarefa do dia)

Os prompts chumbavam os critérios do desafio e os levavam para dentro de
qualquer repositório: **93 de 94 árbitros citavam a Vindler**. Agora o contexto
entra por `contexto/`, em execução, e o árbitro é **citação com procedência**
(`a regra (arquivo:linha)`) ou `null`.

**Contaminação: 93 → 0.** Numa rodada real, as cinco citações do parecer batem
linha por linha nos docs do desafio — conferidas uma a uma.

### O agente parou de destruir o ambiente que testa

Duas ocorrências no mesmo dia. Ver a seção nova no `CLAUDE.md`. Em resumo:
prova read-only, banco descartável, e rede sem saída no lado base.

**Esta é a mudança que mais importa para virar produto.** Um revisor que apaga o
banco do cliente na primeira rodada não tem segunda chance.

### Precisão

- **piso**: orçamento por lente proporcional ao diff. PRs pequenos −58%,
  amplitude da taxa 185× → 44×
- **concentração**: `MAX_POR_LOCAL=2`
- **R3b**: PROVADO/REFUTADO com zero ferramenta bem-sucedida → INCONCLUSIVO
- **pré-voo**: sonda as ferramentas antes de gastar US$1,30 numa rodada condenada

### Fontes externas

`veredito/fontes.py`: bandit e semgrep em paralelo. Corrobora o que coincide,
acusa o que ninguém viu. `--sem-scanner` desliga.

---

## 3. 🚨 Seis vezes que o dado me contrariou

Vale ler junto, porque é o padrão de trabalho que funcionou:

| foi afirmado | o dado disse |
|---|---|
| taint converte melhor que padrão | não — o que domina é o repo **ter defeito** |
| scanner rende mais por dólar | não — 1,09×, indistinguível |
| os 4 achados do httpx são a mesma alegação | não — quatro preocupações distintas |
| o fallback do Opus não engaja | engaja; a causa era **nosso** payload destrutivo |
| descartamos o rastro do semgrep | não existe no motor gratuito |
| ✅ scanner como fonte paralela *(marcado como feito)* | **não estava integrado** |

A última é a pior: **o documento afirmava algo que o código não fazia.** É
exatamente a divergência que este produto existe para pegar, apontada para nós.

**Regra que isso comprou:** todo script de edição faz `assert s != antes`. Um
`s.replace()` que não casa e imprime "ok" custou uma rodada inteira.

---

## 4. O padrão de bug, agora com sete instâncias

Está no `CLAUDE.md` com a lista e as perguntas de busca. Resumo:

> **A guarda existe, mas está condicionada ao mesmo sinal que ela deveria
> vigiar. Então fica muda exatamente onde é necessária.**

Duas instâncias novas de 11/08 valem destaque:

- **os cinco `print` com emoji** do projeto estavam **todos** em caminho de
  alarme. Cada um mataria o processo em vez de avisar — inclusive o alarme de
  contaminação do árbitro. `tests/test_saida_no_console.py` trava isso agora.
- **`docker network connect`** é no-op quando já existe conexão, mesmo sem o
  alias — a contenção subia "com sucesso" e ficava quebrada.

---

## 5. Onde retomar

**O mais barato que dá orientação:** ler o `PROXIMOS_PASSOS.md`, que foi
reescrito hoje e tem a fila completa com tamanhos.

**Se for mexer em código,** a ordem que eu recomendaria:

1. **Parar de sobrescrever as rodadas** (30 min). Hoje `saidas/veredictos.json`
   guarda só a última — as anteriores se perdem. Dado que você já pagou para
   produzir.
2. **Licença no repositório** (10 min, decisão de sócio). Público sem `LICENSE`
   = todos os direitos reservados; ninguém pode legalmente rodar.
3. **`veredito.yml`** — é o que destrava tudo o mais. Hoje `config.py:88` chumba
   os quatro usuários do desafio, então **metade do produto só funciona nele**.

**Se for conversar com o Carlos,** o `PROXIMOS_PASSOS.md` §"Posicionamento" tem
o reenquadramento discutido em 10/08 (o produto é o **verificador**, não o
pipeline) com as ressalvas honestas.

---

## 6. Ambiente

```bash
powershell -ExecutionPolicy Bypass -File hack2l\scripts\docker-up.ps1
cd C:\hack_agents\Hack2L\desafio && docker compose up -d
```

⚠️ **O Docker morreu 4 vezes em 11/08.** O script conserta em ~15s e é
idempotente. A causa está diagnosticada no `CLAUDE.md` — dois sockets órfãos de
zero byte, em pastas diferentes, que voltam a cada parada.

⚠️ Se a suíte falhar com **401 no login**, o banco perdeu o seed:
`docker compose run --rm seed`.

---

## 7. O que NÃO perder

> **INCONCLUSIVO não é REFUTADO.** Somar os dois e dizer "refutou tudo" quando
> nenhuma ferramenta funcionou é absolvição falsa.

> **Contenção, não predição.** Adivinhar o que o código do cliente faz perdeu
> duas vezes em 11/08. Impor a fronteira de fora funcionou nas duas.

> **Compartilhe a evidência e a técnica. Nunca a conclusão.** Vale para o
> scanner (rastro sim, "o bandit concorda" não) e para memória entre rodadas
> (artefato sim, veredito passado nunca).
