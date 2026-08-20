<!-- tag: hack2l -->

# T5 — Vitrine e régua · handoff de 20/08/2026

> Contrato das trilhas: `TRILHAS_ATE_01SET.md`. Ramo `t5-vitrine`, worktree em
> `.worktrees-trilhas/t5-vitrine`. Este arquivo é o delta desta trilha.

## Estado

| | |
|---|---|
| suíte | **782 verdes**, 0 vermelho (`-m "not lento"`, na worktree, com `.env`) |
| commits | `dc3673c` |
| custo de API gasto | **US$0,00** — nada nesta sessão tocou modelo |
| Docker | **não peguei** em nenhum momento |

---

## 🚨 O achado que vale para as CINCO trilhas: a worktree não herda o `.env`

Rodei a suíte na worktree da T5 e vieram **6 vermelhos** que não existem em
`hack2l/`. A mensagem aponta para o produto:

```
RuntimeError: ref nao encontrada no repo do desafio: main
```

**Não era o produto.** São duas coisas somadas, e nenhuma aparece lendo código:

1. **`.env` está no `.gitignore`** — `git worktree add` não o leva. A worktree
   nasce sem `ANTHROPIC_API_KEY` e sem `CHALLENGE_REPO`, e o `config` cai nos
   padrões, que apontam para `../hack2l-challenge`, inexistente nesta máquina.
2. **`CHALLENGE_REPO=../desafio` é RELATIVO**, e a worktree mora um nível mais
   fundo. Copiar o `.env` sem tocar nele troca um erro por outro — passa a
   procurar `.worktrees-trilhas/desafio`.

Com o `.env` copiado e o caminho absoluto: **782 verdes, 0 vermelho.**

⚠️ **O modo de falha é o pior tipo.** Os 6 vermelhos não se anunciam como
"faltou configuração"; anunciam-se como defeito do produto, num ramo de trilha,
para quem acabou de começar naquela área. É inconclusivo por causa **nossa**
disfarçado de limite do código — a mesma família do `isolamento_bloqueou`.

**Conserto, e é uma linha:**

```bash
py -3.12 scripts/worktree_de_trilha.py t3-bugs
```

Cria a worktree (ou aceita a que já existe) e escreve o `.env` com todo caminho
relativo virado absoluto. 🚫 Não resolvi tirando o `.env` do `.gitignore`: ele
tem a chave da API, e o repositório é público.

⚠️ **A primeira versão do próprio script supunha o layout** —
`__file__.parent.parent` dá a *worktree*, não a árvore principal, e ele tentou
criar `.worktrees-trilhas/.worktrees-trilhas/`. Passou a derivar do git
(`--git-common-dir`), que é fato e não suposição.

**Emenda ao protocolo, para o `TRILHAS_ATE_01SET.md`:** worktree de trilha se
cria com esse script, nunca com `git worktree add` cru. *(Não editei o
`TRILHAS` — quatro sessões estão com o arquivo em checkout, e mexer nele agora
é a colisão que ele existe para evitar.)*

---

## ✅ O canal humano da demo, e a trava que o segura

**O problema:** o repositório de demonstração precisa de um lugar onde o
gabarito seja visível para o **leitor** e invisível para o **agente**. Se mora
na árvore (`README`, comentário no código), o advogado tem `read_file` e chega
nele — e a rodada pareceria excelente pelo pior motivo possível. Mesma regra que
mantém o `bancada_gabarito.yml` fora da bancada.

**Conferido, não suposto:** `entrada.resolve` captura `titulo` e `descricao` do
PR e **nenhum dos dois** é consumido por qualquer coisa que monte prompt — o
`titulo` só vai para um `print`, a `descricao` não vai a lugar nenhum. A
fronteira é `entrada.ambiente(info)`: cinco chaves, e o orquestrador roda em
subprocesso que herda exatamente isso mais os worktrees.

> **A descrição do PR é o canal humano da demonstração.**

`tests/test_descricao_do_pr_nao_atravessa.py` — 4 asserções, 4 mutações rodadas
por `scripts/mutacao_fronteira_do_pr.py`:

| injetada em `ambiente` | matou |
|---|---|
| `"PR_DESCRICAO": info["descricao"]` | `_descricao_` + `_chaves_` |
| `"PR_TITULO": info["titulo"]` | `_titulo_` + `_chaves_` |
| `return {}` | `_CONSEGUE_ver_` + `_chaves_` |
| descrição concatenada **dentro** de `CHALLENGE_REPO` | **só `_descricao_`** |

🚨 **A quarta é a que prova que o arquivo não é redundante.** As três primeiras
também morrem na igualdade de chaves, o que sugeriria que a busca pelo canário
sobra. Não sobra: no vazamento realista — concatenação distraída dentro de uma
chave que já existe — o conjunto de chaves fica **idêntico**, e só o canário vê.

---

## 📦 O repo de demonstração: montado localmente, **não publicado**

Mora em `C:\hack_agents\Hack2L\demo\` (fora dos repos, como os outros).
**História nova**, não a da bancada — copiar o `.git` traria junto os outros
dois defeitos plantados, que devem continuar privados.

```
cb965f1  API de projetos, tarefas e membros        ← base
 ├─ f9373a7 + 3209e6a   pr/contagem-de-tarefas     (dois commits)
 └─ 2c19e18             pr/tarefa-por-link
```

**Auditoria de pré-publicação, com o detector do próprio produto**
(`veredito/segredo.py`, nas duas frentes, sobre o histórico **inteiro** da
bancada — 45 objetos, 25 caminhos): zero caminho com convenção de segredo, zero
blob com forma de credencial, zero segredo em mensagem de commit.
⚠️ Ausência de achado não é certificado: o detector é estreito de propósito, e
`ana-senha` não tem forma de credencial nenhuma — ela passa, e deve passar.

**Duas mensagens de commit foram reescritas.** A original do `index=True` dizia
*"este PR é o CONTROLE NEGATIVO da bancada"* e nomeava o defeito: gabarito em
mensagem de commit, visível para qualquer visitante. A justificativa técnica
ficou; a meta saiu.

### O que ainda não fiz, e por quê

Criar o repositório público, abrir os dois PRs e rodar a Action **é publicar**,
e a decisão é do dono da conta. Ver a pergunta no fim.

### Achados do caminho

- 🚨 **`bancada_gabarito.yml` está no `origin/main` do `hack2l`, que é público.**
  O aviso dentro do arquivo é sobre não entrar *na bancada* — protege contra o
  agente ler, não contra o mundo ler. Para uma **vitrine** isso é defensável e
  até bom (o `verificado_em: 2026-08-15` e o histórico do git provam que o
  gabarito precede as rodadas). Para o **instrumento cego**, não é. É decisão,
  não bug — mas hoje ela nunca foi tomada.
- **Os quatro ramos de PR da bancada partem de `f3bdd65`**, e `main` é
  `3105b95`. `git diff main..pr/x` (dois pontos) mostra o workflow inteiro como
  deletado; o diff real do PR é o de **merge-base** (três pontos), e é esse que
  o produto usa. Quem for auditar aquelas rodadas não se assuste.
- **PR de fork não dispara o workflow** (não recebe secrets — política do
  GitHub). Num repo público de demonstração, é o visitante curioso que abre PR
  de fork, e ele vai ver **silêncio**. Não há conserto bom: token de fork é
  read-only, então nem comentar "não rodei" dá. Fica registrado.

---

## ✅ A régua contra o mundo real — pronta para disparar, US$0,00 gastos

`regua/gabarito.yml` + `regua_de_terceiros.py`. **Nove PRs**, gabarito escrito
por terceiros, e tudo o que não custa API já foi conferido.

| grupo | quantos | o que é |
|---|---|---|
| **A** | 4 | PRs que **introduziram** defeito, confirmado depois por outro PR |
| **B** | 5 | rotina, todos mergeados jul–ago/2026 (**depois** do corte dos modelos) |

O melhor do grupo A é `aiohttp#12130`: **+4/-4 linhas**, e o título do PR afirma
que a mudança é intencional e segura (*"Replace unintentional except
BaseException with except Exception"*). Quatro meses depois, `#12798` mostrou
que ela devolve conexão dessincronizada ao pool keep-alive.

🚨 **O que ela NÃO mede.** Nenhum desses repos tem `veredito.yml` ⇒ só
`read_file` e `grep` ⇒ **PROVADO por artefato é inalcançável** e a R2 limita
tudo a MEDIA. *"Achou N de M defeitos"* a partir daqui seria número sem
gabarito. Ela mede cobertura, qualidade da refutação e falso positivo.

🚨 **Contaminação, com direção conhecida.** Três dos quatro consertos são de
jun–jul/2026, pós-corte. `poetry#9304` é o único com conserto anterior e fica de
propósito: **é a sonda** — ir melhor nele que nos outros três é sinal de memória,
não de detecção. E como contaminação só **ajuda** o grupo A, o número do grupo A
é um **teto** e o do grupo B é o robusto.

🚫 `pallets/flask#6095` **excluído**: foi nele que a R3 foi decidida em 17/08.
Medir o caso em que o instrumento foi calibrado produz o próprio reflexo.

**Conferido, de graça:** 4/4 consertos ainda MERGED · 5/5 do grupo B sem
referência nova · **9/9 resolvem, clonam e montam** · encanamento da pontuação
provado contra uma rodada real já gravada.

### O padrão de bug apareceu três vezes dentro do próprio arnês

1. **A conferência do grupo B conclui do SILÊNCIO.** A primeira versão buscava
   `"#NNNN"` por texto — o tokenizador do GitHub descarta o `#`, e ela devolvia
   **27 menções para todo PR do celery**. Virou consulta à *timeline*
   (`cross-referenced` é evento, logo fato), com **controle positivo**: a mesma
   consulta roda nos PRs do grupo A, onde o conserto *tem* que aparecer.
2. **O controle reprovou 2 de 4, por causas diferentes** — scrapy: o conserto
   culpa o commit, nunca o PR, então não há o que achar. poetry: o PR está
   LOCKED e o evento não foi gravado, então ali a consulta **é** cega. Tratar as
   duas igual seria a R3 de 17/08 outra vez. Cada uma declarada com a causa.
3. **`_custo` procurava chaves `usd`/`total_usd` que não existem** em
   `custo.json` nenhum — convenção de string que eu mesmo inventei. Virou
   `_gasto`, que reporta o que o arquivo tem e 🚫 não converte para dólar:
   tabela de preço dentro do código envelhece.

**Para disparar** (~US$13): `py -3.12 regua_de_terceiros.py --rodar`, depois
`--pontuar`.

---

## 🚨 NÃO É MEU, E É URGENTE: 176 linhas que só existem em dois lugares frágeis

A trava do vault ficou vermelha na minha worktree. **O vault está À FRENTE, não
atrás** — 1339 linhas contra 1163 no repo — com uma seção nova,
*"A asserção estática — proposta de 20/08"*.

Procurei em todo lugar:

| onde | tem? |
|---|---|
| `main` e os cinco ramos de trilha | **não** (1163 linhas em todos) |
| worktrees de t1, t2, t3, t4 | **não** |
| **`hack2l/PROXIMOS_PASSOS.md`, não commitado** | **sim** (1339) |
| o vault | **sim** |

Ou seja: existe em **zero commits**. Um `git checkout` ou `git restore` em
`hack2l/` apaga a única cópia editável.

🚫 **E o `--sincronizar` que a própria trava sugere DESTRUIRIA a outra.** A
sincronia é repo → vault e só detecta *diferente*, nunca *qual é mais novo*;
rodá-lo daqui sobrescreveria as 176 linhas com a versão antiga. **Não rodei.**

É a regra do *"um arquivo só, sem cópia"* ao contrário: três cópias, e a única
durável — o git — não tem nada. Quem escreveu aquilo precisa commitar.

⚠️ **Segunda emenda ao protocolo:** o vault espelha `main`, nunca um ramo de
trilha. Rodar `--sincronizar` de dentro de uma worktree publica o estado do ramo
como se fosse canônico.

---

## 📍 Onde retomar

1. **Publicar o parecer na demo** — falta só o secret `ANTHROPIC_API_KEY` em
   `luisfelp07/veredito-demo`; depois é `gh run rerun` nos dois.
2. **Disparar a régua** — `--rodar`, ~US$13. Depende do OK.
3. **Canário de egresso** — a contenção de rede é a única camada sem validação
   empírica em direção nenhuma. 🚫 Não detectando `smtplib` nem mantendo lista
   de API perigosa: isso é predição, e predição já perdeu duas vezes.

## PEDIDOS a outras trilhas

*(nenhum até agora — a T5 não tocou em arquivo de ninguém)*
