"""Arnes de mutacao para o rotulo da corrida do bind-mount.

🚫 NAO e' coletado pelo pytest (o nome nao casa `test_*.py`), e nao pode ser:
ele REESCREVE `veredito/ferramentas.py` em disco para injetar cada violacao,
e restaura no `finally`. Roda a mao, da raiz do repo:

    py -3.12 tests/mutacao_corrida_do_mount.py

Ele existe porque neste projeto teste verde nao e' evidencia ate' a mutacao
existir. A pergunta nao e' "passou?", e' "o que eu quebro para ver este teste
ficar vermelho, e e' exatamente o defeito que ele alega pegar?".

19/08 comprou a licao: `replace` por casamento exato de string vira NO-OP em
silencio, e mutacao que nao aplica e' indistinguivel de trava que nao pega.
Por isso aqui a mutacao e' por INDICE DE LINHA, a linha alvo e' CONFERIDA antes
de rodar, e:

🚨 O ARNES LEVANTA SE O MODULO MUTADO NAO COMPILA. Foi assim que a primeira
rodada mentiu: tres mutacoes tinham indentacao errada, o import quebrava, o
pytest reportava ERROR (nao FAILED), e a leitura era "nenhuma trava pegou" --
ou seja, o arnes acusava as travas de fracas por um defeito DELE. Mesmo formato
de erro que ele existe para procurar.
"""
import ast
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

_SEM_PYC = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

ALVO = pathlib.Path("veredito/ferramentas.py")

# (nome, trecho que a linha PRECISA conter, linha nova COM a indentacao certa,
#  travas que devem morrer)
MUTACOES = [
    ("o ingenuo: rotular o lado que falhou, sem exigir que o OUTRO tenha rodado",
     '    vivos = [lado for lado in suspeitos if art.get(f"rodou_{outro[lado]}")]',
     '    vivos = suspeitos[:1]',
     {"test_os_dois_lados_negando_o_alvo_NAO_e_corrida",
      "test_o_outro_lado_tambem_mudo_NAO_e_corrida"}),

    ("sem conferir que o arquivo esta em disco no host",
     "            return no_disco.is_file()",
     "            return True",
     {"test_arquivo_ausente_no_worktree_NAO_e_corrida",
      "test_sinal_exige_o_alvo_EXATO_e_o_arquivo_em_disco"}),

    ("casando a frase solta em vez do alvo EXATO",
     '        if achado.group("alvo").strip().rstrip("/") == alvo.strip().rstrip("/"):',
     "        if True:",
     {"test_not_found_de_OUTRO_caminho_NAO_e_corrida",
      "test_sinal_exige_o_alvo_EXATO_e_o_arquivo_em_disco"}),

    ("o conserto tentador: rotulou, logo nao e' erro -- e a R3 para de converter",
     '            art["erro"] = (',
     '            art["erro"] = None if corrida else (',
     {"test_o_rotulo_nao_muda_o_veredito_nem_afrouxa_a_R3",
      "test_rotulada_quando_um_lado_so_nao_ve_o_arquivo"}),
]

SUITE = "tests/test_corrida_do_mount.py"


def _falhas(saida: str) -> set[str]:
    fora = set()
    for linha in saida.splitlines():
        if linha.startswith("FAILED "):
            fora.add(linha.split("::")[-1].split()[0].split("[")[0])
    return fora


def main() -> int:
    original = ALVO.read_text(encoding="utf-8")
    guardado = pathlib.Path(tempfile.mkdtemp()) / "ferramentas.py.bak"
    guardado.write_text(original, encoding="utf-8")
    problemas = []
    try:
        base = subprocess.run(
            [sys.executable, "-m", "pytest", SUITE, "-q", "--no-header",
             "-p", "no:cacheprovider"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=_SEM_PYC)
        if _falhas(base.stdout + base.stderr):
            print("a suite ja esta vermelha SEM mutacao -- nada a medir")
            return 1

        for nome, marca, nova, esperadas in MUTACOES:
            linhas = original.splitlines(keepends=True)
            idx = [i for i, ln in enumerate(linhas) if ln.rstrip("\n") == marca]
            assert len(idx) == 1, f"{nome}: a marca casou {len(idx)} linhas, nao 1"
            linhas[idx[0]] = nova.rstrip("\n") + "\n"
            mutado = "".join(linhas)
            assert mutado != original, f"{nome}: a mutacao foi NO-OP"
            # 🚨 A conferencia que a primeira rodada comprou.
            try:
                ast.parse(mutado)
            except SyntaxError as e:
                raise AssertionError(
                    f"{nome}: o modulo mutado NAO COMPILA ({e}). O arnes esta "
                    "errado, nao a trava -- conserte a mutacao.") from None
            ALVO.write_text(mutado, encoding="utf-8")

            r = subprocess.run(
                [sys.executable, "-m", "pytest", SUITE, "-q", "--no-header",
                 "-p", "no:cacheprovider"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=_SEM_PYC)
            saida = r.stdout + r.stderr
            if " error" in saida.lower() and "errors" in saida.lower():
                raise AssertionError(f"{nome}: a suite deu ERRO de coleta:\n{saida[-800:]}")
            mortas = _falhas(saida)
            ok = mortas == esperadas
            if not ok:
                problemas.append((nome, sorted(esperadas), sorted(mortas)))
            print(("OK  " if ok else "!!  ") + nome)
            print(f"      esperado: {sorted(esperadas)}")
            print(f"      morreu  : {sorted(mortas) or 'NENHUMA -- a trava nao pega'}")
    finally:
        ALVO.write_text(guardado.read_text(encoding="utf-8"), encoding="utf-8")
        shutil.rmtree(guardado.parent, ignore_errors=True)

    print()
    if problemas:
        print("PROBLEMAS:")
        for nome, esperadas, mortas in problemas:
            print(f"  {nome}\n    esperava {esperadas}\n    veio     {mortas}")
        return 1
    print(f"{len(MUTACOES)} mutacoes aplicadas, todas compilaram, "
          "e cada uma matou exatamente o conjunto que alega prender.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
