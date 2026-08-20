<!-- tag: hack2l -->

# HANDOFF — T1, o parecer que o autor lê · 20/08/2026

> Ramo `t1-parecer`, worktree `C:\hack_agents\Hack2L\.worktrees-trilhas\t1-parecer`.
> Commit `0dfe8dd`, sobre `origin/main` em `04fb1d7`.
>
> **Custo em dólares desta sessão: US$ 0,00.** Nenhuma chamada de API. Todo o
> trabalho foi feito com `comentario.do_disco()` relendo a rodada
> `20260818T1928-61cc0a7` — que é exatamente a que produziu o comentário
> publicado no `bancada#1`.

---

## O que foi entregue

Os **sete defeitos** da tabela de `TRILHAS_ATE_01SET.md`, na ordem pedida
(1, 2, 3 → 5, 6 → 4 → 7). O comentário do `bancada#1` foi re-renderizado do
disco antes e depois; o antes bate com o que está no ar (as três diferenças são
código escrito *depois* de 18/08, conferidas uma a uma).

| # | defeito | estado |
|---|---|---|
| 1 | acento no nosso texto | ✅ |
| 2 | `achado(s)`, `suspeita(s)` | ✅ |
| 3 | `[ALTA] [alta]` | ✅ as duas ditas, não separadas em silêncio |
| 4 | `O QUE:` em caixa alta | ✅ markdown no PR, terminal inalterado |
| 5 | `app/main.py:103-106` sem link | ✅ permalink ancorado no commit |
| 6 | `artefatos/prova_*.json` morto | ✅ link para o rastro da execução |
| 7 | oito suspeitas no mesmo trecho | ✅ **mas não como estava previsto** — ver abaixo |

⚠️ **Nada mudou o que o pipeline decide.** Veredito, severidade, as listas de
descartados e inconclusivos: idênticos. A regra da trilha foi respeitada.

### Arquivo novo: `veredito/superficie.py`

A causa comum dos defeitos 1–4 é uma só — **restrição de uma superfície
aplicada onde ela não vale**. O `evidencia` sem acento vinha do console cp1252,
que nem pedia isso (acento *cabe* em cp1252; só emoji não). Agora há um
conteúdo e dois estilos: `TERMINAL` e `Markdown`.

O bloco do parecer deixou de ser texto remontado por casamento de prefixo
(`"O QUE:"` procurado dentro da string já formatada) e passou a ser campos
`(rótulo, valor)`. Aquilo era convenção de string carregando estrutura — item 4
do "como procurar" — e o preço chegaria calado na segunda superfície.

---

## 🚨 O defeito 7 não foi consertado como estava previsto, e isto importa

O plano dizia *"a fusão de 18/08 foi aplicada aos condenados e não à fila"*.
**Medi antes de aplicar, e aplicar a fusão à fila é um no-op:**

```
os 8 itens da fila de 20260818T1928-61cc0a7, com a chave ESTRITA:
  8 -> 7 grupos
```

Três têm `arbitro: null` e três apontam região mais larga que o teto de
corroboração (97-108 = 12 linhas, 89-101 = 13, 95-106 = 12), então **não
produzem chave**. Teria sido uma mudança com cara de conserto e efeito zero.

**O que dá para afirmar sem artefato é o endereço, e só ele.** A fila não tem
veredito nem prova — `prova_de_fusao` precisa de teste que falha, e nenhuma
daquelas suspeitas foi testada. Chamar de "o mesmo defeito" o que ninguém
examinou seria a fusão inferindo em vez de provar, no único lugar do pipeline
onde a tese do produto proíbe isso.

Então: `fusao.agrupa_por_endereco`, **fraca de propósito**, com o docstring
dizendo em voz alta que ela não sustenta afirmação nenhuma — e o texto do
parecer dizendo ao autor que o agrupamento é por endereço:

> ⚠️ **Todas as 8 apontam o mesmo trecho** (`app/main.py:89-108`). Estão juntas
> abaixo para você ler o trecho uma vez — agrupar por endereço **não** é dizer
> que são o mesmo defeito, e nenhuma delas foi examinada.

🚫 **Não troque isso por `fusao.agrupa`.** As duas funções existem lado a lado e
a diferença é a tese do produto: `agrupa` exige os dois fatos (endereço vizinho
**e** mesma procedência) por causa do contraexemplo medido no `encode/httpx#3730`.

---

## 🚨 Uma trava minha passou VERDE com o defeito presente

`scripts/mutacao_parecer.py` — **14 mutações, cada uma reintroduzindo um dos
defeitos.** Todas matam exatamente as travas previstas hoje. Mas na primeira
rodada do arnês:

`test_o_terminal_continua_em_caixa_alta` **passava com o terminal já mutado para
markdown.** Eu tinha escrito a asserção como `TERMINAL.rotulo(juiz.O_QUE) in
bloco` — justamente para não duplicar a convenção de string em dois lugares — e
com isso **os dois lados da comparação saíam da função mutada**. A guarda
condicionada ao mesmo sinal que ela deveria vigiar, dentro de uma trava escrita
nesta trilha, pela quarta vez na história do projeto.

O corte que ficou:

- afirmação sobre **ordem** ("convergência antes do conserto") → pergunta ao
  estilo. Sobrevive à troca de tipografia, e deve mesmo sobreviver.
- afirmação sobre **tipografia** ("o terminal é caixa alta") → literal escrito
  no teste. É a própria convenção que está sendo afirmada.

E duas previsões minhas de kill-set estavam erradas — as duas para menos, o que
significa que as travas são mais específicas do que eu supunha. Estão corrigidas
para o medido, com o porquê de cada morte extra escrito ao lado.

⚠️ **Rode o arnês antes de mexer no parecer.** Ele leva ~40s e é a única coisa
que distingue "verde" de "guardado".

```bash
py -3.12 scripts/mutacao_parecer.py
```

---

## Como conferir sem gastar API

O comentário inteiro sai do disco. Não precisa de rede, de Docker nem de chave:

```bash
py -3.12 posta_parecer.py https://github.com/luisfelp07/bancada/pull/1 --saida antes.md
```

(dry-run é o padrão; `--postar` é que publica.)

---

## Estado da suíte

**790 passam.** As 6 que falham nesta worktree falham por **ambiente**, não por
esta mudança — conferido rodando a suíte com as minhas alterações guardadas
antes de começar, e o conjunto é exatamente o mesmo:

```
test_advogado.py::test_sonda_distingue_chave_de_saldo
test_advogado.py::test_sonda_gasta_um_token_so
test_contencao_app.py::test_a_copia_nunca_escreve_no_banco_de_origem
test_efeito_nao_medido.py::test_psql_usa_as_credenciais_do_projeto_e_nao_as_do_desafio
test_ferramentas.py::test_base_e_o_pai_do_pr_nao_a_ponta_da_main
test_fusao_provada_no_parecer.py::test_o_caminho_FELIZ_chega_ao_fim_sem_erro_de_encanamento
```

Precisam de Docker, do clone do desafio e de histórico de git — nada disso
viaja para uma worktree de trilha. **Não peguei o Docker em momento nenhum**;
rodei sempre `-m "not lento"`, como o protocolo pede.

---

## ⚠️ Nota de processo: o ponto de partida

Comecei ramificando de `3be9750` em vez de `origin/main`, de propósito e
errado: naquele momento `origin/main` estava em `ec109a5` e **não tinha o
`segredo.redige`** em `comentario.py` — ramificar dali teria derrubado em
silêncio a última porta antes do público, no arquivo que eu ia reescrever
inteiro. O `merge --ff-only origin/main` que você mandou resolveu de vez: o
`04fb1d7` já trazia tudo, e a preocupação evaporou.

E o segundo aviso estava certo e era mais sério: eu estava editando o diretório
compartilhado enquanto a T2 tinha `medir_bedrock.py` sem rastrear ali e a T3
tinha stash próprio. **T3, T4 e T5 já tinham saído; eu era o último no
compartilhado.** Agora estou na worktree, e o `hack2l/` voltou para o ramo em
que eu o encontrei (`19ago/canario-raiz-de-import-e-senha-em`), sem tocar nos
arquivos das outras trilhas.

---

## PEDIDOS

### → T3 (`veredito/promotores.py`)

**`_MOTIVO_DE_FORA` tem plural de formulário, e ele aparece no comentário do
PR.** É o defeito 2 sobrevivendo num arquivo que não é meu. Em
`veredito/promotores.py:626-633`:

```python
"local_concentrado": "despriorizada: o local ja tinha {max} vaga(s)",
```

Sai no parecer como `_(despriorizada: o local ja tinha 2 vaga(s))_`. Peço:

- `vaga(s)` → concordância com `{max}` (`1 vaga` / `2 vagas`)
- `ja` → `já`, `orcamento` → `orçamento` nas quatro entradas do dicionário

🚫 **Não é para eu fazer:** esses textos são gravados no `escopo.json` pelo
pipeline, e eu só os renderizo. Comportamento vai antes de texto — se você
mudar as strings, eu não preciso rebasear nada, elas passam direto.

⚠️ E o `print` das linhas 607-608 do mesmo arquivo é console: ali `acusacao(oes)`
pode ficar, ou não — é a sua superfície, não a do cliente.

### → T3 (`corrida_do_mount`)

Quando o campo `corrida_do_mount: true` existir no artefato, **eu desenho**. O
lugar já está preparado: é mais um campo em `juiz._campos`, e a `Markdown` o
renderiza sem mudança nenhuma. Me avise o nome exato do campo e onde ele mora
no artefato.

### → T2 (`.github/workflows/veredito.yml`)

**Nada é obrigatório** — o link do defeito 6 já funciona sem tocar no workflow,
porque `GITHUB_REPOSITORY`, `GITHUB_SERVER_URL` e `GITHUB_RUN_ID` são postos
pelo próprio GitHub em todo passo.

Mas há uma melhoria barata: hoje o passo *"Guardar o rastro da rodada"* roda
**depois** do *"Comentar no PR"*, então no momento do comentário o artefato
ainda não existe e eu só consigo linkar a **página da execução**. Se o
`upload-artifact` subisse antes do comentário, o `artifact-url` que ele devolve
apontaria para o **artefato exato**, e eu passaria a linkar direto.

🚫 Só faça se não custar nada: a página da execução já resolve o defeito (o
autor chega ao rastro em um clique), e o passo do rastro tem `if: always()` de
propósito, o que é mais importante que a precisão do link.

⚠️ Além disso: `GITHUB_SHA` **não** serve para o permalink. Em evento de
`pull_request` ele é o commit de *merge* que o GitHub fabrica, não o head do PR.
O commit sai do carimbo da rodada, e o casamento é estrito de propósito.

---

## O que sobrou da T1, em ordem

1. **Bloco ` ```suggestion `** para o `CONSERTO SUGERIDO` (item 2 da trilha).
   Não comecei: o conserto de hoje é frase em prosa do modelo, e `suggestion`
   precisa do **texto exato** das linhas que substitui, senão quebra o build de
   quem clicar — a trilha já proíbe `suggestion` inventado. Precisa das linhas
   originais do diff, e provavelmente de um campo novo que o advogado produza.
   ⚠️ Isso é comportamento, não texto: pode virar PEDIDO dependendo de onde o
   campo nascer.
2. **Comentário único vs. review inline** (item 3) — a trilha manda **decidir
   medindo**, nos dois formatos, no repo de demonstração da T5. Depende da T5.
3. **`veredito init`** (item 4). Intocado.

---

## Onde olhar primeiro, se for retomar

- `veredito/superficie.py` — o módulo novo, e o porquê de ele existir
- `veredito/juiz.py::_campos` — o bloco como fatos rotulados
- `veredito/juiz.py::_fila_por_regiao` — o defeito 7, e a medição que mudou o plano
- `scripts/mutacao_parecer.py` — as 14 travas vistas falhando
