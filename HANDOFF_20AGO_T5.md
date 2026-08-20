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

## 📍 Onde retomar

1. **Publicar** — depende da resposta abaixo.
2. **Canário de egresso** — a contenção de rede é a única camada sem validação
   empírica em direção nenhuma. 🚫 Não detectando `smtplib` nem mantendo lista
   de API perigosa: isso é predição, e predição já perdeu duas vezes.
3. **A régua contra o mundo real** — ~10 PRs já mergeados de repos públicos,
   ~US$15. ⚠️ Pontuar **pelo parecer**, nunca por `veredictos.json`.

## PEDIDOS a outras trilhas

*(nenhum até agora — a T5 não tocou em arquivo de ninguém)*
