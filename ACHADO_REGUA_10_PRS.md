<!-- tag: hack2l -->

# A régua, medida — 10 PRs reais fora do Hack2L

Rodado em **08/08/2026, à noite**, com `generaliza.py`. Dez PRs mergeados de
seis projetos open source, três linguagens. Só os promotores: o advogado precisa
do app do cliente rodando, e essa é a pergunta seguinte.

**209 acusações. ~$0,50. 21 minutos.**

---

## O que passou

**Nenhuma lente cega.** As seis categorias produziram acusação em pelo menos um
PR de cada linguagem. Os prompts não morrem fora do repositório para o qual
foram escritos — que era o medo principal.

**A concentração se espalha em PR multi-arquivo.** Este era o achado feio do
Hack2L: 46 de 47 acusações num arquivo só, 98%. Nos PRs grandes daqui:

| PR | arquivos | concentração |
|---|---|---|
| next.js#96932 | 13 | **39%** |
| next.js#96945 | 4 | **41%** |
| gin#4707 | 2 | 53% |
| django#21725 | 2 | 59% |
| flask#6095 | 2 | 62% |

Os 100% da tabela são todos de PR de **um arquivo só** — onde 100% é a única
resposta possível, não uma falha.

**Conclusão:** os 98% do Hack2L foram anomalia daquele PR, não defeito
sistêmico. O agente lê o diff inteiro.

**Árbitro em 45%** (Hack2L: 69%). Caiu, como esperado — o vocabulário `AC1`–`AC5`
e `C1`–`C8` é do PRD e das convenções do desafio, e não existe no Flask. Mas
ficou acima do piso que eu tinha estipulado como sinal ruim (40%).

---

## O que falhou, e é o que importa

### 1. Não existe piso. O agente acusa mesmo quando não há o que acusar.

| PR | mudança | acusações |
|---|---|---|
| `django#21735` | **1 linha adicionada** | **17** |
| `httpx#3730` | 2 linhas, arquivo de CI | 12 |
| `requests#7576` | **1 link de markdown** | **11** |

Onze acusações num PR que conserta um link em `CONTRIBUTING.md`. E não é
alucinação — são observações tecnicamente defensáveis e **inúteis**, do tipo
*"caminho relativo virou absoluto e isso muda a semântica em renderizadores
diferentes"*. Três acusações diferentes sobre a mesma linha.

### 2. A lente de injection está invertida

| PR | conteúdo | acusações de injection |
|---|---|---|
| `next.js#96932` | 13 arquivos, 389 linhas, **Server Actions** | **0** |
| `requests#7576` | um link de markdown | **2** |

O PR mais longo e mais relevante para segurança da amostra recebeu **zero**
acusações de injection. Um conserto de link recebeu duas. Isso não é ruído
aleatório — é o critério da lente não discriminando.

### 3. Confiança é sinal fraco, não filtro

| | alta | média | baixa |
|---|---|---|---|
| PRs ≤ 15 linhas | 11% | 38% | **52%** |
| PRs > 15 linhas | 17% | 50% | 33% |

A confiança **acompanha** a substância — o ruído pende para baixa. Mas não o
suficiente para filtrar: `django#21735`, com **uma linha**, produziu **4
acusações de confiança alta**.

---

## O diagnóstico: a cota é orçamento, não critério

Os promotores fazem o que foram mandados fazer. O prompt diz, com todas as
letras, *"cobertura, não seletividade — não filtre por relevância"*. Eles não
estão quebrados; estão obedecendo.

O problema é a divisão de trabalho a jusante. `seleciona()` reparte por **cota
de categoria** — seguranca_ia 3, prd 2, correcao 2, padroes 2, performance 1 —
e manda ao advogado até o teto, **sempre**. A cota é um orçamento fixo, não um
limiar.

Consequência: num PR de uma linha sem nenhum defeito, o sistema ainda manda seis
acusações ao advogado, que gasta **~130 s de Opus 5 em cada uma** para refutar
o nada. **O custo por PR não escala com a substância do PR.**

E é exatamente o critério que o Carlos deu:

> *"Passar um defeito real é mais problemático do que um falso alarme. No falso
> alarme, o importante é ser interpretável… precisão vale tanto quanto
> cobertura."*

Cobertura generaliza. **Precisão não foi testada até hoje — e não passou.**

---

## O que fazer, em ordem

1. **Rodar o advogado nos controles negativos.** A pergunta que falta: ele
   refuta as 11 acusações do PR de markdown, ou "prova" alguma? Se refutar
   todas, a divisão de trabalho está certa e o problema é só custo. Se provar
   alguma, o problema é sério. **Custa ~$4 e é o próximo experimento.**

2. **Piso proporcional ao diff.** Nada no pipeline liga o número de acusações ao
   tamanho ou natureza da mudança. Um PR de uma linha não deveria ter seis vagas
   no advogado.

3. **Árbitro sem vocabulário chumbado.** Hoje as lentes citam `AC1`–`AC5` e
   `C1`–`C8`, que só existem no Hack2L. Em repo qualquer o campo colapsa — e sem
   árbitro a regra R1 rebaixa tudo, então **nada consegue ser crítico fora do
   desafio**.

4. **Investigar a lente de injection.** Zero num PR de Server Actions é o
   resultado mais estranho da amostra.

---

## Reproduzir

```bash
py -3.12 generaliza.py --lote prs.txt     # ~21 min, ~$0,50
py -3.12 generaliza.py --resumo           # relê sem gastar API
```

Um JSON por PR em `saidas/generaliza/`. Nada é apagado entre rodadas.
