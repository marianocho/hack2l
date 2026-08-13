# Controle negativo — 11/08

O buraco de evidência que as duas rodadas completas deixaram: a **lista de
descartados**, que é a assinatura do produto, saiu **vazia** nas duas, porque o
PR do desafio é cheio de defeito real. Toda a evidência de refutação (68%) vinha
de PRs de terceiro com ferramentas restritas.

**Alvo:** `30b5f98..32a5241` — um commit real do autor do desafio ("Stop the test
suite from wiping the app database, and harden the cold start"), 5 arquivos,
+69/−15. Não é a armadilha.

## Resultado

```
0 condenados · 8 descartados com motivo · 0 inconclusivos
US$ 1,23 · 9m35s · 30 chamadas de ferramenta, ZERO erro
```

**Zero falso positivo chegando ao humano.** Em 5 das 8, o advogado rodou teste
diferencial nos dois commits para mostrar que a hipótese era falsa.

A qualidade das refutações é o ponto — não são descartes genéricos:

> *"o serviço langfuse é image-only (linha 82, sem `build:`), logo não existe
> 'rebuild' que possa dessincronizar… a acusação inverte a semântica de
> `environment:` (runtime) com `build.args` (build-time)"*

> *"a acusação usa como árbitro exatamente a mitigação que o PR introduziu"*

> *"Medido no container: a suíte inteira roda em 0.68s nos dois lados, e o
> helper já existia idêntico no commit base — o PR só trocou o literal `"kb"`
> pela constante `APP_DATABASE`"*

## O placar, com as duas pontas fechadas

| condição | resultado |
|---|---|
| PR **com** defeito plantado | 10 de 10 provados, com artefato |
| PR **sem** defeito | **8 de 8 refutados, com motivo** |
| PRs de terceiro | 68% refutados, US$0,071/alegação |

## ⚠️ Rodou sem `http_request`, de propósito

O app no ar foi construído em `1dd2e5c`, **com** os defeitos plantados. Deixar o
advogado bater nele enquanto revisa outro diff faria ele "provar" coisa que não
está na mudança sob revisão — o controle negativo viraria mentira.

A prova diferencial não tem esse problema: roda em worktrees nos commits certos,
e foi ela que sustentou 5 das 8 refutações.

## 🚨 E o agente apagou o banco do app

O commit base (`30b5f98`) é **anterior** ao conserto "stop the test suite from
wiping the app database". A prova diferencial roda a suíte nos **dois** lados —
então, ao rodar no base, a suíte apagou o banco da aplicação. Quatro usuários e
cinco documentos, zerados.

Não é acidente deste experimento: é a mesma classe do `DROP TABLE` de hoje de
manhã. **O agente executa código de teste do commit base, e o commit base pode
fazer qualquer coisa.** Aqui foi benigno porque o seed reconstrói; num
repositório de cliente, seria destruição de dado real.

Conserto ainda não feito. Ver `PROXIMOS_PASSOS`.
