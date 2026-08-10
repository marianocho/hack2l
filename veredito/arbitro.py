"""hack2l / Veredito -- o arbitro, e a procedencia que o torna um arbitro.

Medido em 08/08 a noite, em 10 PRs reais de Flask, Django, Gin, Next.js e
Requests: 94 acusacoes trouxeram `arbitro` preenchido, e 94 citavam os criterios
de aceite do desafio da Vindler -- em repositorios que nao tem nada a ver com
ele. A 94a era a lista inteira do prompt colada como se fosse um arbitro so:
"R1 R2 R3 R4 AC1 AC2 AC3 AC4 AC5".

A causa nao era o modelo: os seis prompts chumbavam `AC1`-`AC5`, `R1`-`R4` e
`C1`-`C8`, entao cada lente carregava o PRD do desafio para dentro de qualquer
diff do mundo. FORA DO HACK2L A TAXA REAL DE ARBITRO ERA ZERO -- e os 45% que
comemoramos como "acima do piso" mediam contaminacao, nao cobertura.

Pior: esses rotulos nunca existiram nem no desafio. `grep AC1 docs/` no repo do
desafio nao acha nada -- as exigencias sao lista numerada em
`docs/REVIEW_TASK.md` e as convencoes em `docs/REFERENCE_GUIDE.md`. Nos
inventamos a numeracao ao escrever os prompts e depois mandamos o modelo citar
"verbatim" um vocabulario que nao esta escrito em lugar nenhum.

O conserto e' estrutural, nao de redacao. Arbitro deixa de ser rotulo de
vocabulario fixo e vira CITACAO COM PROCEDENCIA:

    {"regra": "so o dono pode compartilhar", "onde": "docs/REVIEW_TASK.md:39"}

Sem conseguir apontar ONDE a regra esta escrita NAQUELE repositorio, o arbitro
e' None -- que e' a resposta honesta, e a resposta que a maioria dos PRs do
mundo merece.

⚠️ Este modulo nao importa nada do pacote. O juiz depende dele e precisa
continuar rodando sem git, sem rede e sem o resto do Veredito -- e' o que
permite reajustar o parecer trinta vezes lendo so o disco.
"""

from __future__ import annotations

import re

# Os rotulos que chumbamos nos prompts ate 09/08. Ficam aqui como DETECTOR, nao
# como vocabulario: e' com esta lista que `generaliza.py` mede se a
# contaminacao voltou. Se um promotor citar isto revisando o Django, o conserto
# regrediu -- e queremos descobrir por uma assercao, nao por leitura de 209
# acusacoes na madrugada.
VOCABULARIO_CHUMBADO = (
    "AC1", "AC2", "AC3", "AC4", "AC5",
    "R1", "R2", "R3", "R4",
    "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8",
    "INV-ISOLAMENTO", "INV-INSTRUCAO-NAO-E-DADO",
)


def normaliza(bruto) -> dict | None:
    """Devolve `{"regra": str, "onde": str|None}` ou None. Nunca levanta.

    Aceita as tres formas que aparecem em disco:

      dict novo    {"regra": ..., "onde": ...}   -- o formato de hoje
      string velha "AC2"                          -- rodadas antes de 09/08
      None / lixo                                 -- vira None

    A string velha sobrevive como `regra` com `onde=None`, ou seja, SEM
    procedencia. E' a leitura correta e nao e' retroatividade injusta: "AC2"
    nunca apontou onde a regra estava escrita, e a essa altura ja sabemos que na
    maioria das vezes ela nao estava escrita em lugar nenhum.
    """
    if isinstance(bruto, dict):
        regra = str(bruto.get("regra") or "").strip()
        onde = str(bruto.get("onde") or "").strip()
        if not regra:
            return None
        return {"regra": regra, "onde": onde or None}
    if isinstance(bruto, str):
        regra = bruto.strip()
        return {"regra": regra, "onde": None} if regra else None
    return None


def tem_procedencia(bruto) -> bool:
    """Ha' arbitro E ele diz onde a regra esta escrita.

    E' esta funcao, e nao a mera presenca do campo, que a regra R1 do juiz
    consome. Uma regra que o promotor nao consegue localizar no repositorio e'
    indistinguivel de uma regra que ele inventou -- e a diferenca entre as duas
    e' o produto inteiro.
    """
    a = normaliza(bruto)
    return bool(a and a["onde"])


def citado(bruto) -> bool:
    """Ha' arbitro de alguma forma, com procedencia ou sem."""
    return normaliza(bruto) is not None


def formata(bruto) -> str:
    """A linha ARBITRO do parecer. Um humano precisa poder ir conferir."""
    a = normaliza(bruto)
    if a is None:
        return "nenhum citado"
    if not a["onde"]:
        return f"{a['regra']} (sem procedencia citada)"
    return f"{a['regra']} ({a['onde']})"


def chave(bruto) -> str | None:
    """Chave estavel para deduplicacao. None quando nao ha arbitro.

    Normaliza caixa e espaco: `dict` em ordem diferente ou " AC2 " nao podem
    virar duas acusacoes distintas.
    """
    a = normaliza(bruto)
    if a is None:
        return None
    return f"{a['regra'].casefold()}|{(a['onde'] or '').casefold()}"


def cita_vocabulario_chumbado(texto: str) -> list[str]:
    """Quais rotulos do vocabulario chumbado aparecem neste texto.

    Detector de regressao, usado pela regua (`generaliza.py`) e pelos testes.
    Casa token inteiro: "R1" acusa, "R10" e "VAR1" nao -- senao o detector vira
    ruido e ninguem olha para ele, que e' como uma metrica morre.

    ⚠️ A fronteira exclui letra e digito, mas NAO o hifen, e a diferenca pegou um
    falso negativo no proprio teste: a forma mais comum de citar isto e' o
    INTERVALO -- "nenhum requisito R1-R4 ou criterio AC1-AC5" foi literalmente a
    hipotese que sobreviveu ao advogado no psf/requests. Tratando "-" como parte
    do token, "R1-R4" nao casava nem em R1 nem em R4, e o detector deixava
    passar justo a acusacao que motivou o conserto.
    """
    if not texto:
        return []
    return [
        v for v in VOCABULARIO_CHUMBADO
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(v)}(?![A-Za-z0-9])", texto, re.I)
    ]


def parece_chumbado(bruto) -> bool:
    """O arbitro e' um dos rotulos que chumbamos ate 09/08?"""
    a = normaliza(bruto)
    if a is None:
        return False
    return bool(cita_vocabulario_chumbado(f"{a['regra']} {a['onde'] or ''}"))
