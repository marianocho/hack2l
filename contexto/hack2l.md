<!-- tag: hack2l -->

# Contexto do repositório sob revisão — desafio Hack2L (Vindler)

> **Este arquivo não é uma lente.** É o material que o repositório sob revisão
> documenta sobre si mesmo, carregado em tempo de execução e colado no contexto
> dos promotores **quando ele existe**.
>
> Até 09/08 este conteúdo estava chumbado dentro dos seis prompts de
> `promotores/`, e portanto viajava para dentro de qualquer diff do mundo: 94 de
> 94 árbitros nos 10 PRs de Flask, Django, Gin, Next.js e Requests citavam os
> critérios de aceite **daqui**. Ver `ACHADO_ARBITRO_CHUMBADO.md`.
>
> A regra que isso comprou: **regra sem procedência é opinião.** Cada item
> abaixo traz o arquivo e a linha onde está escrito, no repositório do desafio —
> é isso que permite ao promotor preencher `arbitro.onde` com algo conferível em
> vez de recitar um rótulo.

---

## O que o PR se propõe a fazer

Fonte: `docs/REVIEW_TASK.md:19-28`.

Permitir compartilhar um documento com um colega em vez de copiar e colar.
Adiciona:

- `POST /documents/{doc_id}/share` com um `email` — compartilha um documento meu
  com outro usuário.
- `GET /shared-with-me` — lista os documentos que outras pessoas compartilharam
  comigo.
- `GET /shared/{doc_id}` — lê um documento que foi compartilhado comigo.

No frontend: um controle de Share em cada linha da página de documentos, uma
página "Shared with me", e um leitor em `/shared/{id}`.

Compartilhar é idempotente, e **só o dono** do documento pode compartilhá-lo. Os
endpoints existentes ficam inalterados.

## Objetivo declarado

`docs/REVIEW_TASK.md:35` — permitir que o dono de um documento conceda acesso de
**leitura** a outro usuário registrado, por **email**.

## Requisitos

Fonte: `docs/REVIEW_TASK.md:37-49`. Lista numerada no original; a numeração
abaixo é a do próprio arquivo.

| # | Onde | Regra |
|---|---|---|
| 1 | `docs/REVIEW_TASK.md:39` | O dono pode compartilhar com outro usuário identificado por email. **Só o dono** pode compartilhar. Compartilhar o mesmo documento com o mesmo usuário mais de uma vez é **no-op (idempotente)**. A resposta identifica o destinatário por **email** e inclui o **título** do documento. |
| 2 | `docs/REVIEW_TASK.md:43` | Um usuário pode ler um documento compartilhado **com ele**. Quem não é dono nem destinatário **não pode** ler. |
| 3 | `docs/REVIEW_TASK.md:45` | `GET /shared-with-me` devolve o que outros compartilharam **com o usuário atual**. **Não** pode devolver os documentos do próprio usuário. Cada entrada mostra o título e o email do dono. |
| 4 | `docs/REVIEW_TASK.md:48` | Compartilhar concede **só leitura**. O destinatário não pode editar, apagar nem recompartilhar. As regras de posse dos endpoints originais **permanecem inalteradas**. |

## Critérios de aceite

Fonte: `docs/REVIEW_TASK.md:51-58`. **No original são bullets sem numeração** —
cite-os pelo texto e pela linha, não por um rótulo inventado.

| Onde | Critério |
|---|---|
| `docs/REVIEW_TASK.md:53` | Compartilhar um documento que você não possui retorna **404 ou 403**, nunca um share. |
| `docs/REVIEW_TASK.md:54` | Depois de A compartilhar D com B: **B lê D**; um terceiro **C não lê D**. |
| `docs/REVIEW_TASK.md:55` | Compartilhar D com B **duas vezes** deixa **exatamente um** share. |
| `docs/REVIEW_TASK.md:56` | `GET /shared-with-me` de B lista D (com título e email de A) e **não** lista nenhum documento do próprio B. |
| `docs/REVIEW_TASK.md:58` | A resposta de "A compartilha D com B" contém o **email de B** e o **título de D**. |

## Convenções que o próprio repositório declara seguir

Fonte: `docs/REFERENCE_GUIDE.md:63-82`, sob o título *"Conventions the codebase
follows"*. O guia diz que lê-las torna óbvias as violações de convenção no PR.

**Backend**

| Onde | Convenção |
|---|---|
| `docs/REFERENCE_GUIDE.md:69` | Configuração se lê **só** por `settings` em `config.py`, nunca `os.getenv` solto. |
| `docs/REFERENCE_GUIDE.md:70` | Persistência passa pelos modelos do ORM; **não há SQL cru** no app. |
| `docs/REFERENCE_GUIDE.md:71` | Todo endpoint devolve um **schema Pydantic** de `schemas.py`. |
| `docs/REFERENCE_GUIDE.md:72` | Toda rota protegida depende de `get_current_user`, e o **dono é checado antes** de devolver o recurso. |

**Frontend**

| Onde | Convenção |
|---|---|
| `docs/REFERENCE_GUIDE.md:77` | Componente nunca chama `fetch`; todo request passa por função nomeada em `lib/api.ts`. |
| `docs/REFERENCE_GUIDE.md:79` | Respostas são tipadas em `lib/types.ts`, espelhando os schemas do backend. |
| `docs/REFERENCE_GUIDE.md:81` | Páginas com sessão envolvem o conteúdo em `AuthGate`. |
| `docs/REFERENCE_GUIDE.md:82` | Request que falha levanta `ApiError` e vira elemento `.error` — não log silencioso. |

---

## O app, para desenhar o experimento de `provado_se`

O backend é FastAPI em `app/api/app/`, o frontend Next.js em `app/web/`. O
`/chat` faz RAG: recupera trechos de documentos e os injeta no contexto de um
modelo para responder, com citações.

**Os quatro usuários do seed** existem para testar isolamento — o próprio guia
diz que acesso de um usuário ao dado de outro precisa de pelo menos três contas
para testar direito:

| Login | Senha | Tem |
|---|---|---|
| `demo@hack2l.dev` | `demo-password` | 3 documentos |
| `alice@hack2l.dev` | `alice-password` | 1 documento |
| `bob@hack2l.dev` | `bob-password` | 1 documento |
| `carol@hack2l.dev` | `carol-password` | **nada** — controle negativo |

**Linha de base, medida em 08/08 no commit base, antes de qualquer um ter visto
o PR:** `GET /documents` devolve demo=3, alice=1, bob=1, **carol=0**. Se depois
do PR esses números mudarem, é achado diferencial de uma linha.

**Rotas que já existiam no base:** `POST /auth/login`, `POST /auth/register`,
`POST /chat`, `GET|POST /documents`, `GET|DELETE /documents/{doc_id}`,
`GET /health`. As três rotas de share **não existem no base** — chegam com o PR.

⚠️ Consequência para a ferramenta de prova: em endpoint **novo**, prova
diferencial não fecha (404 no base é o inverso do padrão "passa no base, falha
no head"). Regressão em comportamento **que já existia** → diferencial. Bug em
endpoint **novo** → teste que falha no head, ou reprodução contra o app rodando.
