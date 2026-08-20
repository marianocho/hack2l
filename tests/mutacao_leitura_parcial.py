"""Arnes de mutacao para o rotulo de leitura parcial (escala).

🚫 NAO e' coletado pelo pytest (o nome nao casa `test_*.py`), e nao pode ser:
ele REESCREVE `veredito/ferramentas.py` em disco para injetar cada violacao, e
restaura no `finally`. Roda a mao, da raiz do repo:

    py -3.12 tests/mutacao_leitura_parcial.py

Mesmo desenho do `mutacao_corrida_do_mount.py`, pelo mesmo motivo: neste projeto
teste verde nao e' evidencia ate' a mutacao existir. Casa LINHA INTEIRA (a
substring casava indentacoes diferentes e abortava), e LEVANTA se o modulo
mutado nao compilar -- porque na primeira rodada do outro arnes tres mutacoes
quebravam o import, o pytest reportava ERROR e nao FAILED, e a leitura era
"nenhuma trava pega": o arnes acusando as travas por um defeito dele.
"""
import ast
import pathlib
import shutil
import subprocess
import sys
import tempfile

ALVO = pathlib.Path("veredito/ferramentas.py")
SUITE = "tests/test_leitura_parcial.py"

# (nome, linha inteira que precisa existir, linha nova, travas que devem morrer)
MUTACOES = [
    ("sem a poda: o resgate volta a descer no node_modules",
     "        dirnames[:] = [d for d in dirnames if d not in _IGNORA]",
     "        dirnames[:] = list(dirnames)",
     {"test_o_resgate_nao_desce_no_node_modules"}),

    ("sem o teto: a varredura anda ate' o fim, custe o que custar",
     "        if vistos >= teto:",
     "        if False:",
     {"test_varredura_para_no_teto_e_DIZ_que_parou",
      "test_desistir_de_procurar_NAO_e_dizer_que_nao_existe"}),

    ("desistir de procurar volta a se passar por 'o arquivo nao existe'",
     "        if varredura_parcial:",
     "        if False:",
     {"test_desistir_de_procurar_NAO_e_dizer_que_nao_existe"}),

    # Sem emoji no nome de proposito: isto e' impresso em console cp1252, e o
    # `print` levanta UnicodeEncodeError. Mesma restricao que vazou para o
    # comentario do PR (defeito 1 da tabela do TRILHAS) -- aqui ela e' o caso.
    ("parcial contaminando o desfecho -- a R3 converteria por TAMANHO de repo",
     "    if _FALHA_DA_CHAMADA is not None:",
     "    if _FALHA_DA_CHAMADA is not None or _PARCIAL_DA_CHAMADA:",
     {"test_parcial_NUNCA_vira_erro"}),

    # Tres travas, e nao uma: as outras duas montam o cenario delas com um
    # arquivo CORTADO, entao esta linha e' o que faz as tres terem o que medir.
    # A previsao original dizia uma so' e o arnes reprovou -- a previsao estava
    # errada, nao o codigo, e registrar isso e' o ponto de prever antes.
    ("o corte do arquivo volta a ser mudo",
     "        _marca_parcial(detalhe)",
     "        pass",
     {"test_arquivo_cortado_avisa_que_o_modelo_esta_vendo_o_FIM",
      "test_parcial_NUNCA_vira_erro",
      "test_parcial_de_uma_chamada_nao_vaza_para_a_seguinte"}),

    # `False and f(...)` curto-circuita: a chamada nao acontece e o codigo
    # continua valido. Trocar o NOME da funcao daria NameError, e as travas
    # morreriam pela causa ERRADA -- desfecho certo por acidente, que e' o que
    # 19/08 mandou parar de aceitar.
    ("o teto do grep volta a ser mudo para o parecer",
     "                    _marca_parcial(",
     "                    False and _marca_parcial(",
     {"test_grep_no_teto_avisa_que_ha_mais",
      "test_leitura_parcial_nomeia_a_ferramenta"}),
]


def _falhas(saida: str) -> set[str]:
    fora = set()
    for linha in saida.splitlines():
        if linha.startswith("FAILED "):
            fora.add(linha.split("::")[-1].split()[0].split("[")[0])
    return fora


def _roda() -> str:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", SUITE, "-q", "--no-header",
         "-p", "no:cacheprovider"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout + r.stderr


def main() -> int:
    original = ALVO.read_text(encoding="utf-8")
    guardado = pathlib.Path(tempfile.mkdtemp()) / "ferramentas.py.bak"
    guardado.write_text(original, encoding="utf-8")
    problemas = []
    try:
        if _falhas(_roda()):
            print("a suite ja esta vermelha SEM mutacao -- nada a medir")
            return 1

        for nome, marca, nova, esperadas in MUTACOES:
            linhas = original.splitlines(keepends=True)
            idx = [i for i, ln in enumerate(linhas) if ln.rstrip("\n") == marca]
            assert len(idx) == 1, f"{nome}: a marca casou {len(idx)} linhas, nao 1"
            linhas[idx[0]] = nova.rstrip("\n") + "\n"
            mutado = "".join(linhas)
            assert mutado != original, f"{nome}: a mutacao foi NO-OP"
            try:
                ast.parse(mutado)
            except SyntaxError as e:
                raise AssertionError(
                    f"{nome}: o modulo mutado NAO COMPILA ({e}). O arnes esta "
                    "errado, nao a trava -- conserte a mutacao.") from None
            ALVO.write_text(mutado, encoding="utf-8")

            saida = _roda()
            # 🚨 A trava tem que morrer porque a GUARDA sumiu, nunca porque o
            # modulo quebrou. Mutacao que arranca um nome levanta NameError, as
            # travas certas ficam vermelhas, e o arnes daria OK -- o desfecho
            # certo pela causa errada, que foi o defeito de 19/08. O `ast.parse`
            # acima nao pega: nome indefinido so' explode em execucao.
            for quebra in ("NameError", "AttributeError", "ImportError",
                           "SyntaxError", "IndentationError"):
                if quebra in saida:
                    raise AssertionError(
                        f"{nome}: a mutacao QUEBROU o modulo ({quebra}), nao a "
                        f"guarda. Conserte a mutacao.\n{saida[-600:]}")
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
