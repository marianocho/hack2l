"""Segredo do projeto revisado: o que NAO ENTRA, e o que NAO SAI.

🚨 O BURACO, conferido em 19/08 e aberto desde sempre:

  - `read_file` e `grep` nao tinham restricao de caminho nenhuma;
  - nao havia redacao em lugar nenhum do pipeline;
  - o parecer e' POSTADO como comentario no PR.

Logo `.env`, `id_rsa`, `.npmrc`, `terraform.tfvars` do cliente eram todos
alcancaveis pelo advogado, iam para a API do modelo, e podiam voltar citados
num comentario publico. E a lente `padroes` procura exatamente por
"credencial em codigo", entao ela LEVA o advogado ate' esses arquivos.

O `senha_em` (mesmo dia) tirou a senha do NOSSO arquivo. Isto aqui e' o resto.

DUAS FRENTES, e nenhuma das duas basta sozinha:

    caminho_sensivel()   ENTRADA -- o conteudo nunca chega ao modelo
    redige()             SAIDA   -- o que ja entrou (pelo diff, por exemplo)
                                   nao sai no comentario

⚠️ A frente da saida sozinha nao resolve: o segredo ja teria ido para a API. A
da entrada sozinha tambem nao: o diff do PR entra no prompt inteiro, e um
segredo commitado NAQUELE diff passa por fora do `read_file`.

🚨 E A LICAO 0 GOVERNA AS DUAS. Guarda que nao consegue ficar quieta morre de
excesso: bloqueio largo demais faz o advogado bater em recusa o tempo todo, e
redacao larga demais destroi a evidencia que o parecer existe para mostrar.
Por isso as duas sao ESTREITAS de proposito, e cada uma tem trava provando que
fica calada no caso normal.
"""
from __future__ import annotations

import re

# --------------------------------------------------------------- ENTRADA

# 🚨 Isto E' uma lista mantida, e o projeto tem cicatriz disso (`app/api/app`).
# A diferenca que a torna aceitavel: sao CONVENCOES UNIVERSAIS de ecossistema
# -- `.env` e' dotenv em qualquer lugar do mundo, `id_rsa` e' OpenSSH em
# qualquer lugar -- e nao o layout de um projeto especifico. Um valor que so'
# vale para o desafio nunca poderia estar aqui.
#
# Extensivel pelo projeto (`sensiveis` no veredito.yml). NAO ha fallback para
# lista de ninguem: o projeto ACRESCENTA, nunca substitui.
_PADROES = [
    (re.compile(r"(^|/)\.env(\.|$)"), "dotenv"),
    (re.compile(r"(^|/)\.?(npmrc|netrc|pypirc|htpasswd)$"), "credencial de ferramenta"),
    (re.compile(r"(^|/)id_(rsa|dsa|ecdsa|ed25519)(\.|$)"), "chave SSH"),
    (re.compile(r"\.(pem|key|p12|pfx|jks|keystore|ppk)$"), "chave/certificado"),
    (re.compile(r"\.tfvars(\.json)?$"), "variaveis do terraform"),
    (re.compile(r"(^|/)secrets?\.(ya?ml|json|toml|ini)$"), "arquivo de segredos"),
    (re.compile(r"(^|/)(service-account|serviceaccount)[^/]*\.json$"), "conta de servico"),
    (re.compile(r"(^|/)\.(ssh|aws|gnupg|docker)/"), "diretorio de credencial"),
    (re.compile(r"(^|/)credentials?(\.|$)"), "credencial"),
]

# 🚨 A EXCECAO E' O QUE FAZ A GUARDA UTIL EM VEZ DE IRRITANTE. `.env.example`
# existe para ser lido -- e' documentacao de quais variaveis o projeto quer, e
# e' frequentemente o arquivo que o revisor MAIS precisa. Bloquea-lo seria a
# guarda disparando no caso em que ela nao tem nada a proteger.
_ISENTOS = re.compile(
    r"(^|/)[^/]*\.(example|examples|sample|template|dist|tpl)(\.[^/]*)?$"
    r"|(^|/)(example|sample|template)[^/]*$", re.I)


def caminho_sensivel(rel: str, extra: list[str] | None = None) -> str | None:
    """O motivo, quando este caminho e' convencao universal de segredo.

    `None` quando nao e' -- e `None` e' a resposta para a esmagadora maioria
    dos arquivos de qualquer repositorio, que e' exatamente o ponto.
    """
    # ⚠️ NUNCA `lstrip("./")`: ele remove QUALQUER um daqueles caracteres, entao
    # `.env` virava `env` e a guarda ficava muda no arquivo mais obvio de todos.
    # Pego no smoke test, nao na leitura.
    caminho = str(rel).replace("\\", "/")
    while caminho.startswith("./"):
        caminho = caminho[2:]
    if _ISENTOS.search(caminho):
        return None
    for rx, motivo in _PADROES:
        if rx.search(caminho):
            return motivo
    for p in extra or []:
        try:
            if re.search(str(p), caminho):
                return f"declarado em `sensiveis` no veredito.yml ({p})"
        except re.error:
            continue
    return None


def recusa_de_leitura(rel: str, motivo: str, bytes_: int, linhas: int) -> str:
    """O texto que o advogado recebe no lugar do conteudo.

    🚨 RECUSA O CONTEUDO, CONFIRMA A EXISTENCIA -- e essa divisao e' o que
    impede a guarda de destruir a acusacao legitima. Para provar "o PR commitou
    um segredo", o fato e' a PRESENCA do arquivo no repositorio; o valor la'
    dentro nao acrescenta prova nenhuma, e e' justamente o que nao pode viajar.

    ⚠️ Nao passa por `_marca_falha` nem por `_marca_indisponivel`: a chamada
    NAO falhou (nada quebrou) e a ferramenta NAO e' inexistente (ela leu o
    arquivo). Ela devolveu um fato verdadeiro e util. Marcar como falha faria a
    R3 converter em INCONCLUSIVO um veredicto que se sustenta -- o erro exato
    que 17/08 comprou.
    """
    return (
        f"RECUSADO: `{rel}` casa com convencao universal de arquivo de segredo "
        f"({motivo}).\n"
        f"O arquivo EXISTE: {bytes_} bytes, {linhas} linha(s).\n\n"
        "O conteudo nao foi entregue porque ele iria para a API do modelo e "
        "poderia acabar citado no comentario do PR.\n"
        "Para acusar 'segredo commitado', isto BASTA: o fato e' o arquivo estar "
        "versionado, nao o valor dentro dele. Cite o caminho e o tamanho."
    )


# ----------------------------------------------------------------- SAIDA

_MASCARA = "«REDIGIDO:{}»"

# Prefixos que sao credencial POR CONSTRUCAO -- nao ha falso positivo plausivel
# para `AKIA` seguido de 16 maiusculas, nem para um bloco PEM.
_FORMAS = [
    (re.compile(r"-----BEGIN[A-Z ]*PRIVATE KEY-----.*?-----END[A-Z ]*PRIVATE KEY-----",
                re.S), "chave-privada"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{16,}"), "chave-anthropic"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}"), "chave-openai"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"), "token-github"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "token-github"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "chave-aws"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}"), "token-slack"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "chave-google"),
]

# Placeholders NAO sao segredo, e redigi-los seria a guarda destruindo o texto
# que ela deveria preservar -- inclusive o conserto sugerido, que muitas vezes
# e' literalmente "troque por ${VAR}".
_PLACEHOLDER = re.compile(
    r"^(\*+|x+|<.*>|\$\{.*\}|\{\{.*\}\}|changeme|senha|password|secret|token|"
    r"redacted|placeholder|seu[-_].*|your[-_].*)$", re.I)

# Atribuicao explicita. Teto de 8 caracteres e exigencia de mistura para nao
# casar com `campo_senha: senha`, que e' NOME DE CAMPO e aparece no veredito.yml
# de qualquer projeto -- redigir isso mutilaria a evidencia legitima.
#
# ⚠️ Sem `\b` na frente, e de proposito: em `DB_PASSWORD` o `_` e' caractere de
# palavra, entao `\b(password)` NAO casa -- e `DB_PASSWORD=...` e' a forma mais
# comum que existe. Pego no smoke test.
_ATRIBUICAO = re.compile(
    r"(?i)([A-Za-z0-9_.\-]*(?:password|passwd|senha|secret|api[_-]?key|"
    r"access[_-]?token|client[_-]?secret))(\s*[:=]\s*)([\"']?)([^\s\"',;]{8,})\3")


def _parece_valor(v: str) -> bool:
    """Tem cara de VALOR de credencial, e nao de nome/placeholder/expressao."""
    if _PLACEHOLDER.match(v):
        return False
    if v.startswith(("$", "{", "<", "os.", "process.", "settings.", "cfg.")):
        return False          # referencia a variavel: e' o CONSERTO, nao o bug
    return bool(re.search(r"\d", v)) and bool(re.search(r"[A-Za-z]", v))


def redige(texto: str) -> tuple[str, int]:
    """Mascara o que tem FORMA de credencial. Devolve (texto, quantos).

    🚨 A contagem sai junto de proposito: redacao silenciosa nao da' para
    auditar, e "zero" e' um resultado tao informativo quanto "tres". O parecer
    diz quantas vezes mascarou.

    ⚠️ ESTREITA DE PROPOSITO. Um parecer normal cita codigo, nomes de campo e
    consertos como `senha_em: VEREDITO_SENHA_ANA` -- e nada disso pode ser
    mutilado, senao a guarda destroi a evidencia que o produto existe para
    entregar. `tests/test_segredo.py` prende isso com pareceres reais.
    """
    n = 0
    for rx, tipo in _FORMAS:
        texto, k = rx.subn(_MASCARA.format(tipo), texto)
        n += k

    def _troca(m: re.Match) -> str:
        valor = m.group(4)
        if not _parece_valor(valor):
            return m.group(0)
        nonlocal n
        n += 1
        return f"{m.group(1)}{m.group(2)}{m.group(3)}{_MASCARA.format('valor')}{m.group(3)}"

    texto = _ATRIBUICAO.sub(_troca, texto)
    return texto, n
