"""Mutacoes contra `entrada.ambiente`, para ver a trava FALHAR.

🚨 O arnes muta por INDICE DE LINHA e CONFERE que aplicou. Mutacao por
casamento de string ja virou no-op neste projeto (19/08, o `\\` na continuacao)
e uma mutacao que nao dispara e' indistinguivel de uma trava que nao pega.

Cada mutacao roda sozinha, e o arquivo e' restaurado sempre -- inclusive se o
pytest explodir.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Derivada de onde ESTE arquivo esta. Caminho de maquina chumbado aqui seria a
# mesma classe do `app/api/app`, e este repositorio e' publico.
RAIZ = Path(__file__).resolve().parent.parent
ALVO = RAIZ / "veredito" / "entrada.py"
# 🚨 O `.pyc` e' revalidado por (mtime, TAMANHO) do fonte: duas mutacoes
# consecutivas de MESMO comprimento, no mesmo tique de mtime, fazem o
# subprocesso importar o bytecode da rodada ANTERIOR, e o arnes reporta o
# kill-set de uma mutacao que nao esta mais no disco. Medido em 20/08 no
# `mutacao_detector.py`. Aqui nunca mordeu porque as mutacoes mudam o
# tamanho do arquivo -- sorte, nao desenho.
_SEM_PYC = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

TRAVA = "tests/test_descricao_do_pr_nao_atravessa.py"

# (rotulo, texto que a linha-ancora PRECISA conter, o que injetar no lugar)
MUTACOES = [
    ("PR_DESCRICAO entra no ambiente",
     '"BASE_JA_RESOLVIDO": "1",',
     '        "BASE_JA_RESOLVIDO": "1",\n        "PR_DESCRICAO": info["descricao"],'),
    ("PR_TITULO entra no ambiente",
     '"BASE_JA_RESOLVIDO": "1",',
     '        "BASE_JA_RESOLVIDO": "1",\n        "PR_TITULO": info["titulo"],'),
    ("ambiente devolve vazio",
     '"CHALLENGE_REPO": str(info["repo_local"]),',
     '        **{}}\n    return {  # noqa'),
    # 🚨 A quarta existe para provar que as tres primeiras NAO sao redundantes
    # com a de igualdade de chaves. Aqui o conjunto de chaves fica IDENTICO e a
    # descricao viaja dentro do valor de uma chave legitima -- que e' como o
    # vazamento aconteceria de verdade, por concatenacao distraida, e nao
    # abrindo uma chave nova chamada PR_DESCRICAO.
    ("descricao contrabandeada dentro de uma chave que ja existe",
     '"CHALLENGE_REPO": str(info["repo_local"]),',
     '        "CHALLENGE_REPO": str(info["repo_local"]) + info["descricao"],'),
]


def linhas_de_ambiente(texto: str) -> tuple[int, int]:
    linhas = texto.splitlines()
    ini = next(i for i, l in enumerate(linhas) if l.startswith("def ambiente("))
    # `ambiente` e' a ultima funcao do arquivo hoje: sem sentinela, o `next`
    # estoura em StopIteration e o arnes morre antes de mutar nada.
    fim = next((i for i in range(ini + 1, len(linhas))
                if linhas[i].startswith("def ") or linhas[i].startswith("class ")),
               len(linhas))
    return ini, fim


def acha_ancora(linhas: list[str], ini: int, fim: int, agulha: str) -> int:
    achados = [i for i in range(ini, fim) if agulha in linhas[i]]
    if len(achados) != 1:
        raise SystemExit(
            f"ancora '{agulha}' apareceu {len(achados)}x em ambiente() -- "
            "o arnes precisa de alvo unico, senao muta o lugar errado")
    return achados[0]


def roda_pytest() -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-m", "pytest", TRAVA, "-q", "--no-header",
                        "-rf", "--tb=no"],
                       cwd=RAIZ, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=_SEM_PYC)
    return r.returncode, r.stdout


def nomes_que_falharam(saida: str) -> list[str]:
    fora = []
    for l in saida.splitlines():
        if l.startswith("FAILED") and "::" in l:
            fora.append(l.split("::")[-1].split()[0])
    return fora


def main() -> int:
    original = ALVO.read_text(encoding="utf-8")

    rc, saida = roda_pytest()
    print(f"sem mutacao: {'VERDE' if rc == 0 else 'VERMELHO'}  ({saida.strip().splitlines()[-1]})")
    if rc != 0:
        print("[!] a trava ja falha sem mutacao -- nada a medir.")
        return 2

    problemas = 0
    try:
        for rotulo, agulha, injecao in MUTACOES:
            linhas = original.splitlines()
            ini, fim = linhas_de_ambiente(original)
            alvo = acha_ancora(linhas, ini, fim, agulha)
            linhas[alvo] = injecao
            mutado = "\n".join(linhas) + "\n"

            # 🚨 Conferir que a mutacao APLICOU, antes de confiar no resultado.
            assert mutado != original, f"{rotulo}: substituicao foi no-op"
            ALVO.write_text(mutado, encoding="utf-8")

            rc, saida = roda_pytest()
            mortos = nomes_que_falharam(saida)
            ultima = saida.strip().splitlines()[-1] if saida.strip() else "?"
            if rc == 0:
                problemas += 1
                print(f"\n[!] {rotulo}\n    a trava passou VERDE com a violacao "
                      f"presente -- ela nao mede o que alega.")
            else:
                print(f"\n[ok] {rotulo}\n     matou: {', '.join(mortos) or '(ver saida)'}"
                      f"\n     {ultima}")
            ALVO.write_text(original, encoding="utf-8")
    finally:
        ALVO.write_text(original, encoding="utf-8")

    rc, _ = roda_pytest()
    print(f"\nrestaurado: {'VERDE' if rc == 0 else 'VERMELHO -- restauracao falhou'}")
    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())
