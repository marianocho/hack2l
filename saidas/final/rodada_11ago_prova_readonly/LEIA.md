# Rodada 11/08 — depois do conserto da prova read-only

Mesma configuração da `rodada_11ago_pos_refatoracao`, com um conserto entre as
duas. US$1,38 · 13m28s.

## O que mudou

| | antes | depois |
|---|---|---|
| recusas do classificador | **2 de 10** | **0** |
| condenados | 8 | **10** |
| inconclusivos | 2 | **0** |
| payload destrutivo no `provado_se` | `DROP TABLE users` | **0 em 45 acusações** |

## A causa que estava por trás

Os 2 inconclusivos da rodada anterior eram `stop_reason=refusal` do
classificador de cibersegurança, nas duas acusações de SQL injection. O motivo
não era o classificador ser sensível demais — era o `provado_se` gerado pelo
Haiku pedir:

    email="admin@x.dev'; DROP TABLE users--"

E o advogado tem `http_request` apontado para o app rodando, com o banco real.
**A recusa estava impedindo o agente de apagar a tabela do app que ele testa.**

Injeção de SQL se prova por LEITURA: `' OR '1'='1` devolvendo linhas que não
deveria. Mesma demonstração, sem tocar em estado, e sem gatilho.

## Conserto em duas camadas

- **fonte** — `correcao` e `padroes` mandam prova read-only, com o payload
  não-destrutivo como padrão e `DROP`/`DELETE` proibidos
- **salvaguarda** — o `SISTEMA` do advogado proíbe executar operação destrutiva
  mesmo que um promotor peça, e manda parar com INCONCLUSIVO em vez de
  destruir o alvo

Três testes travam as duas camadas.

## ⚠️ O que esta rodada NÃO exercita

**Zero refutados, pela segunda vez seguida.** O PR do desafio é cheio de defeito
real, então o verificador confirma em vez de refutar. A lista de descartados —
que é a assinatura do produto — está vazia nas duas rodadas completas.

Toda a evidência de refutação (68%) vem dos PRs de terceiro, com ferramentas
restritas. **O caminho de refutação nunca rodou no pipeline completo.** É o
próximo buraco de teste, não de produto.
