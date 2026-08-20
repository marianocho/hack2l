<!-- tag: hack2l -->

# Handoff — T4, narrativa não técnica — 20/08/2026

> Trilha **T4** de `TRILHAS_ATE_01SET.md`. Ramo `t4-narrativa`.
> Escrita permitida: `site/`, arquivos `.md` novos de narrativa, este handoff.
> **`veredito/` não foi aberto para escrita.** Nenhum arquivo de outra trilha
> foi tocado.

## Custo desta sessão

**US$ 0,00 em API.** Nenhuma rodada foi disparada; todo o material saiu de
`saidas/` e dos `.md` já no repositório. A única execução foi a suíte de testes,
que é local.

## Docker

**Não peguei o Docker em momento nenhum.** Rodei apenas
`py -3.12 -m pytest -q -m "not lento"`, o modo que as quatro sessões
não-detentoras podem usar. Está livre.

---

## O que entrou

### 1. `NARRATIVA.md` — o documento

Doze seções, lido de ponta a ponta sem abrir código. Cobre os cinco conteúdos
que a trilha pede:

| pedido pela T4 | seção |
|---|---|
| o que o produto faz | 1, 3, 4 |
| os melhores achados, `bancada#1` por extenso | 6 |
| os doze bugs de 18/08 e o que cada um ensinou | 9 |
| o árbitro chumbado como história de rigor | 8 |
| o terceiro estado, sem jargão | 5 |

Mais três seções que não estavam no pedido e que eu defendo:

- **7 — a medição com gabarito.** É a resposta à pergunta que o investidor faz
  primeiro (*"como vocês sabem que funciona fora do exemplo de vocês?"*), e a
  linha vermelha dos quatro PRs está lá, explicada, não escondida.
- **11 — o que ainda não sabemos.** Cinco buracos conhecidos, em ordem de
  importância, começando pela taxa de aceitação com **zero medições**.
  Documento que só lista vitória mede a habilidade de escrever documento.
- **12 — ficha de procedência.** Cada cifra e o arquivo onde ela mora, mais o
  que o documento deliberadamente **não** afirma. É a regra *"regra sem
  procedência é opinião"* aplicada ao nosso próprio texto de marketing.

🚨 **Toda cifra tem endereço.** Nenhum número entrou por memória, estimativa ou
arredondamento. A ficha da seção 12 é conferível linha a linha.

### 2. `site/index.html` — alinhado ao documento

A seção **Estado** tinha três fatos (custo, prêmio, código) e agora tem seis. Os
três novos são medidos e batem com a narrativa:

| fato novo | procedência |
|---|---|
| pull request limpo → **0 condenações** (3 acusações, 3 refutadas com motivo) | `saidas/final/bancada_15ago/LEIA.md` |
| efeito no banco → **nenhum** (161 s de injeção; banco idêntico tabela por tabela) | `saidas/final/rodada_14ago_contencao/LEIA.md` + `saidas/rodadas/20260814T2131-1dd2e5c/efeito_no_banco.json` |
| suíte → **787 testes** verdes | medido em 20/08, abaixo |

O do PR limpo é o mais importante dos três para quem chega na página: ele
responde ao medo real de quem instala um revisor automático, que é **falso
positivo**, não cobertura.

✅ Conferido renderizado, não só no fonte: a grade `auto-fit` acomoda os seis em
**3×2 exatos**, sem linha órfã, e o HTML fecha todas as tags.

---

## Medição feita nesta sessão

```
py -3.12 -m pytest -q -m "not lento"
787 passed, 1 skipped, 6 deselected in 94.99s
```

O único `skipped` é `tests/test_tracing.py:158`, *"Langfuse fora do ar"* —
benigno. ✅ E **não** é o pulo perigoso do `../CLAUDE.md`:
`VEREDITO_VAULT_FONTES` está definida nesta máquina, então
`tests/test_sync_vault.py` rodou de verdade.

---

## PEDIDOS

### 1. 🚨 Para a sessão principal — o trabalho de 19/08 e as trilhas não estão no `origin/main`

Este é o achado operacional da sessão, e ele atinge as cinco trilhas.

`TRILHAS_ATE_01SET.md` foi commitado em `3be9750`, no ramo
`19ago/canario-raiz-de-import-e-senha-em`. A sessão da T2 mergeou esse ramo em
`04fb1d7` — mas **`04fb1d7` está só local, no ramo `t2-aws`**. O `origin/main`
continua em `ec109a5`.

Consequência direta: o protocolo manda `git checkout -b t<n>-<nome> origin/main`,
e quem obedecer literalmente **não recebe o arquivo de contrato das trilhas nem
o trabalho de 19/08**. A trilha começa sem saber o que é dela.

Eu contornei ramificando de `04fb1d7`. Sugestão: empurrar esse merge para
`origin/main` antes que a T1, a T3 e a T5 abram seus ramos.

### 2. Para a T3 — a suíte rápida não é hermética

Rodei `-m "not lento"` num worktree limpo (sem os arquivos ignorados pelo git) e
deu **7 falhas**. No checkout principal, os mesmos testes passam. A diferença
não é Docker — é estado local ignorado pelo git (`.env`, `.repos`, e as pastas
de saída não rastreadas).

```
test_advogado.py::test_sonda_distingue_chave_de_saldo
test_advogado.py::test_sonda_gasta_um_token_so
test_contencao_app.py::test_a_copia_nunca_escreve_no_banco_de_origem
test_efeito_nao_medido.py::test_psql_usa_as_credenciais_do_projeto_e_nao_as_do_desafio
test_ferramentas.py::test_base_e_o_pai_do_pr_nao_a_ponta_da_main
test_fusao_provada_no_parecer.py::test_o_caminho_FELIZ_chega_ao_fim_sem_erro_de_encanamento
test_prompts_limpos.py::test_o_detector_pega_a_violacao_injetada
```

Por que isso importa e não é frescura: **quem clonar o repositório do zero vai
ler essas 7 como regressão.** Ou elas pulam com a causa dita em voz alta
(*"precisa de `.env`"*), ou não são testes da suíte rápida. É a distinção que a
R3 comprou em 17/08 — *não conseguiu olhar* ≠ *olhou e não achou* — aplicada à
nossa própria suíte.

⚠️ **Uma delas se comportou certo e merece nota:**
`test_prompts_limpos.py::test_o_detector_pega_a_violacao_injetada` falhou com
*"conjunto derivado vazio: o detector nao detectaria nada"*. Isto é uma guarda
**se recusando a passar vazia** em vez de ficar muda — exatamente o contrário do
padrão de bug da casa. Não mexa nessa; ela está certa.

### 3. Para mim mesmo, depois do merge — o link no rodapé

**Deliberadamente não coloquei** um link para `NARRATIVA.md` no rodapé do site.
Enquanto o arquivo não estiver no `main`, o link seria um **404 na superfície
que o cliente lê** — a mesma classe do `Artefato: artefatos/prova_correcao_01.json`
apontando para um caminho que o autor do PR não tem, que é o defeito nº 6 da
lista da T1.

Entra assim que `NARRATIVA.md` chegar ao `main`, e não antes.

---

## Onde retomar

1. **Ler `NARRATIVA.md` inteiro de cabo a rabo** com olho de leitor, não de
   autor. É o único teste que o documento tem: se cansa, ficou longo demais.
2. **Decidir o destino dele.** Hoje é um `.md` no repositório. Se a ideia é
   mandar para o pessoal do Activate ou para investidor, o formato provável é
   uma página como a do site, ou PDF — e aí a seção 12 vira anexo, não corpo.
3. **A seção 11 tem prazo de validade curto.** Assim que a T2 fizer a primeira
   chamada real no Bedrock e a T5 rodar a régua nos ~10 PRs públicos, dois dos
   cinco buracos fecham e o texto precisa mudar no mesmo dia. **Buraco fechado e
   não atualizado vira mentira em documento de marketing** — pior que buraco
   aberto.
4. **A cifra da suíte envelhece a cada commit.** `787` está carimbada com a data
   nos dois lugares (documento e site). Se alguém reescrever sem a data, o número
   perde procedência e vira alegação.

## O que eu NÃO fiz, de propósito

- **Não toquei em `veredito/`**, nem para ler-e-corrigir um typo.
- **Não mexi em `PROXIMOS_PASSOS.md` nem nos dois `CLAUDE.md`** — são da sessão
  principal.
- **Não inventei número.** Onde não havia medição, o documento **diz que não
  há** (seção 11) em vez de estimar.
- **Não encurtei as listas de descartados e inconclusivos** em lugar nenhum: a
  narrativa as trata como o diferencial que são, e a seção 5 existe para
  enquadrá-las em voz alta.
