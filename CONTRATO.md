<!-- tag: hack2l -->

# Contrato — o que travar antes de codar

Isto existe para as duas pessoas codarem **3 horas sem se bloquear**. Enquanto
estas assinaturas não mudarem, ninguém espera ninguém.

## A costura

O caminho crítico não é atômico. Ele parte em dois pedaços ortogonais:

- **O motor** — o loop do advogado. Não liga pro que a ferramenta faz, só pra
  assinatura dela.
- **A perícia** — as ferramentas. Não ligam pra existência do loop. São Python
  puro, sem uma chamada de LLM.

A fronteira é a assinatura do `@beta_tool`. Quem faz o motor escreve **stubs**
com estas assinaturas exatas e devolve string enlatada. Quem faz a perícia
escreve as de verdade. Integrar = trocar o import. Arquivos diferentes, zero
conflito de merge.

## 1. Assinaturas das ferramentas — `ferramentas.py`

Todas devolvem `str`, porque é o que o modelo lê. A docstring vira a descrição
que o modelo enxerga, então ela é produto, não comentário.

```python
@beta_tool
def run_tests(expressao: str = "") -> str:
    """Roda a suite de testes do app alvo e devolve o resultado.

    Args:
        expressao: filtro -k do pytest. Vazio roda a suite inteira.
    """

@beta_tool
def prova_diferencial(codigo_do_teste: str, nome_do_arquivo: str) -> str:
    """Roda um teste no commit base e no head do PR, e compara.

    Provado = passa no base e falha no head. Qualquer outra combinacao
    nao e' prova.

    Args:
        codigo_do_teste: o arquivo de teste completo, em python.
        nome_do_arquivo: ex. test_vazamento_tenant.py
    """

@beta_tool
def read_file(caminho: str) -> str:
    """Le um arquivo do repo sob revisao.

    Args:
        caminho: caminho relativo a raiz do repo.
    """

@beta_tool
def grep(padrao: str, glob: str = "") -> str:
    """Procura um padrao no repo sob revisao.

    Args:
        padrao: regex.
        glob: filtro de arquivo, ex. **/*.py. Vazio busca em tudo.
    """

@beta_tool
def http_request(metodo: str, caminho: str, corpo: str = "",
                 como_usuario: str = "") -> str:
    """Chama a API do app alvo, autenticado como um dos usuarios seed.

    Args:
        metodo: GET, POST, PATCH, DELETE.
        caminho: ex. /documents/3
        corpo: JSON como string. Vazio para GET.
        como_usuario: demo, alice, bob ou carol. Vazio = sem autenticacao.
    """
```

## 2. 🚨 O exit code não passa pelo modelo

**A decisão de desenho mais importante do dia, e ela cai exatamente na costura.**

`prova_diferencial` faz **duas** coisas:

1. **devolve texto** pro modelo ler e seguir raciocinando;
2. **grava `artefatos/prova_<id>.json`** com os exit codes crus.

```json
{
  "id": "acusacao_03",
  "arquivo_do_teste": "test_vazamento_tenant.py",
  "commit_base": "32a5241",
  "commit_head": "1dd2e5c",
  "exit_base": 0,
  "exit_head": 1,
  "stdout_base": "...",
  "stdout_head": "...",
  "estado": "PROVADO",
  "provado": true,
  "motivo": "passa no commit base e falha no head do PR",
  "erro": null,
  "segundos": 13.8
}
```

**O juiz lê este JSON, nunca o resumo do modelo.** `provado` é calculado em
Python e o LLM não tem como sobrescrever. É isto que faz o veredito ser um exit
code em vez de opinião.

### ⚠️ `motivo` e `erro` são coisas diferentes — não juntar

Custou um bug real em 08/08, pego pelo próprio teste da perícia:

| campo | o que é | quando vem preenchido |
|---|---|---|
| `estado` | **autoritativo.** PROVADO / REFUTADO / INCONCLUSIVO | sempre |
| `motivo` | explicação legível | **sempre**, inclusive no PROVADO |
| `erro` | **só falha de infraestrutura** — timeout, docker fora, git quebrado | quase nunca |

O erro era mandar o motivo da refutação no campo `erro`. Como o juiz trata
`erro != null` como INCONCLUSIVO, **toda refutação viraria inconclusivo** e a
lista de descartados-com-motivo — que é peça de demo — esvaziaria sozinha,
parecendo rigor.

**Regra para o juiz: leia `estado`.** Não deduza o estado a partir de `erro`.
Quando `erro` vem preenchido, o próprio tool já força `estado` para
INCONCLUSIVO, no `finally` — a última palavra, aconteça o que acontecer.

### ⚠️ `commit_base` é calculado, nunca chumbado

O pai do PR é **`32a5241`**. O `f491ae1` que está na ponta da `main` é **irmão**,
não ancestral — ele só adiciona LICENSE/README/SECURITY:

```
* f491ae1  Add the license, security policy...   <- irmao, NAO e' ancestral
| * 1dd2e5c  Add document sharing                 <- head do PR
|/
* 32a5241  Stop the test suite from wiping...     <- merge-base REAL
```

O código de `app/` é idêntico nos dois, então o resultado do teste não muda —
mas **o artefato é o que o juiz lê e o que vai pro slide**. Alguém rodar
`git log` no palco e ver que a base não é o pai do PR custa caro num pitch cuja
tese é *"todo mundo afirma, nós provamos"*.

Por isso o tool roda **`git merge-base main origin/pr/document-sharing`** em
runtime. Corrige o artefato **e** sobrevive à régua: troca o PR, continua certo.

### O `provado` é mais estrito que "falhou no head"

```python
provado = (exit_base == 0) and (exit_head == 1)
```

`exit_head == 1` e não `!= 0`, de propósito. Códigos do pytest: `1` = teste
falhou; `2` interrompido, `3` erro interno, `4` erro de uso, `5` nenhum teste
coletado. Tratar `!= 0` como prova transformaria **erro de execução em
condenação** — um alarme crítico errado, exatamente o que as regras
determinísticas existem para impedir.

| `exit_base` | `exit_head` | estado |
|---|---|---|
| 0 | 1 | **PROVADO** |
| 0 | 0 | **REFUTADO** — passa nos dois, a mudança não quebrou isso |
| qualquer outro par | | **INCONCLUSIVO**, com `erro` preenchido |

Nunca existe "absolvido por silêncio": se o teste não coletou, se deu timeout,
se o docker caiu, o estado é INCONCLUSIVO **com a causa**. É o terceiro estado,
mecanicamente.

## 3. Esquema da acusação — o que o promotor cospe

JSON, nunca YAML. `try/except` no parse devolvendo a saída crua no fallback:
acusação não morre por erro de formato.

```json
{
  "id": "acusacao_03",
  "categoria": "vazamento_de_contexto",
  "local": "search.py:112",
  "hipotese": "retrieve_docs nao filtra por tenant_id",
  "arbitro": "criterio de aceite no 3",
  "provado_se": "canario do usuario B aparece na resposta do usuario A",
  "confianca": "media"
}
```

`arbitro` é `null` se não houver — e o juiz rebaixa CRÍTICA sem árbitro para
SUSPEITA. `hipotese` é **uma linha**: prosa longa ancora o advogado.

## 4. Veredito — o que o advogado grava e o juiz lê

```json
{
  "id": "acusacao_03",
  "veredito": "PROVADO | REFUTADO | SUSPEITA | INCONCLUSIVO",
  "severidade": "CRITICA | ALTA | MEDIA | BAIXA",
  "artefato": "artefatos/prova_03.json",
  "prova_ponta_a_ponta": true,
  "motivo": "uma frase -- por que refutado, ou o que foi tentado",
  "voltas": 4,
  "tokens_entrada": 18320,
  "tokens_saida": 2210,
  "cache_read": 16100,
  "erro": null
}
```

`prova_ponta_a_ponta` é o que a regra nº 2 do juiz consome: prova vinda de
chamada direta de função não sustenta severidade alta, só `http_request`
sustenta.

## 5. Layout em disco

A disciplina nº 2 do doc (salvar cada etapa) é também a fronteira entre as duas
pessoas. Ajustar o juiz pela trigésima vez não pode re-executar o advogado.

```
hack2l/
├── promotores/*.md          <- prompts, texto puro. Integrar = dar commit.
├── saidas/acusacoes.json    <- promotores -> advogado
├── saidas/veredictos.json   <- advogado -> juiz
├── artefatos/prova_*.json   <- a prova crua. O juiz le daqui.
└── saidas/parecer.md        <- a saida final
```

---

# ⚠️ Achados de ambiente que mudam o desenho

## O código da API é assado na imagem — não tem bind mount

`app/api/Dockerfile` faz `COPY app ./app` e `COPY tests ./tests`, e o
`docker-compose.yml` **não monta volume nenhum no serviço `api`**. Então
`docker compose run --rm api python -m pytest` roda o código **da imagem**, não
o do disco.

**Consequência: `git stash` / `git checkout` sozinho não muda nada.** O plano
original do doc para a prova diferencial não funciona como escrito.

**O que funciona** — `git worktree` + bind-mount, sem rebuild e sem mexer na
árvore que o app está servindo:

```powershell
git -C <desafio> worktree add --detach <dir-base> <commit-base>
git -C <desafio> worktree add --detach <dir-head> origin/pr/document-sharing

docker compose ... run --rm `
  -v "<dir-base>\app\api\app:/code/app" `
  -v "<dir-base>\app\api\tests:/code/tests" `
  api python -m pytest tests -q
```

Melhor que `git stash` por três motivos: os dois lados existem ao mesmo tempo,
o app que está no ar não quebra no meio da revisão, e não há conflito de stash
quando um agente chama isso em loop.

## ✅ PROVADO — os dois mounts sobrepõem o código assado

Canário rodado às ~10h50. Ele testa **os dois mounts separadamente**, porque
`/code/tests` valer e `/code/app` não valer produziria falso negativo em toda
prova diferencial — o que difere entre base e head é o código do app.

Arquivos que existem **só no worktree**, nunca na imagem:

- `app/api/app/_canario_hack2l.py` → `VALOR = "veio-do-worktree"`
- `app/api/tests/test_canario_hack2l.py` → importa esse módulo e afirma o valor

```
1 failed, 2 passed, 5 deselected     EXIT CODE: 1
```

- `test_mount_de_app_vale` **passou** — o import de um módulo que só existe no
  worktree funcionou. **`/code/app` sobrepõe.**
- `test_mount_de_tests_vale` passou e um `assert False` separado falhou —
  **`/code/tests` sobrepõe.**
- **O exit code propagou como `1`.** O "veredito é um exit code" tem base
  física, não é figura de linguagem.

**Plano B, medido, caso o Docker da outra máquina se comporte diferente:**
`docker compose build api` leva **41 s** com as camadas de `pip install` em
cache — só as duas camadas de `COPY` refazem. Dá para trocar mount por rebuild
sem mudar a arquitetura, ao custo de ~82 s por acusação em vez de ~5 s.

## 🚫 Não rodar a suíte de commits anteriores a `32a5241`

A mensagem do commit é *"Stop the test suite from wiping the app database"*.
Antes dele, a suíte **apaga o banco do app** — e leva junto o seed de
demo/alice/bob/carol, que é o canário de vazamento de contexto.

Base e head do PR são posteriores, então o caminho normal é seguro. Mas
qualquer experimento com histórico antigo apaga o ambiente.

## Portas desta máquina ≠ padrão

API `8010`, web `3010`, Postgres `55432`, Langfuse `3001`. Na máquina do Luis
provavelmente são as padrão. **Tudo lê de `.env`** — ver `.env.example`.
