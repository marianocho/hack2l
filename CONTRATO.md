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
  "commit_base": "f491ae1",
  "commit_head": "1dd2e5c",
  "exit_base": 0,
  "exit_head": 1,
  "stdout_base": "...",
  "stdout_head": "...",
  "provado": true,
  "erro": null
}
```

**O juiz lê este JSON, nunca o resumo do modelo.** `provado` é calculado em
Python — `exit_base == 0 and exit_head != 0` — e o LLM não tem como
sobrescrever. É isto que faz o veredito ser um exit code em vez de opinião.

Se a execução falhou (timeout, docker fora, teste não compilou): `provado`
fica `false` **e `erro` é preenchido**. O juiz trata `erro != null` como
**INCONCLUSIVO**, nunca como absolvido. É o terceiro estado, mecanicamente.

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

**Estado da verificação, honesto:** o comando acima **roda** (`5 passed` a
partir de um worktree em `main~1`). **Não está provado que o mount sobrepõe o
código assado** — os dois lados dão 5 passed, então o resultado é ambíguo.

**Primeira tarefa da trilha B, 2 minutos:** escrever um teste que falha de
propósito dentro de `<dir-base>\app\api\tests\`, rodar, e confirmar que o exit
code é != 0. Se der 5 passed, o mount **não** está valendo e a prova diferencial
inteira produz falso negativo em silêncio.

## 🚫 Não rodar a suíte de commits anteriores a `32a5241`

A mensagem do commit é *"Stop the test suite from wiping the app database"*.
Antes dele, a suíte **apaga o banco do app** — e leva junto o seed de
demo/alice/bob/carol, que é o canário de vazamento de contexto.

Base e head do PR são posteriores, então o caminho normal é seguro. Mas
qualquer experimento com histórico antigo apaga o ambiente.

## Portas desta máquina ≠ padrão

API `8010`, web `3010`, Postgres `55432`, Langfuse `3001`. Na máquina do Luis
provavelmente são as padrão. **Tudo lê de `.env`** — ver `.env.example`.
