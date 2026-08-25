"""Arnes de mutacao para o detector de `veredito.yml`.

🚫 NAO e' coletado pelo pytest (o nome nao casa `test_*.py`), e nao pode ser:
ele REESCREVE `veredito/detector.py` em disco para injetar cada violacao, e
restaura no `finally`. Roda a mao, da raiz do repo:

    py -3.12 tests/mutacao_detector.py

Mesmo desenho dos arnesses de 20/08, e pelos mesmos motivos, que foram todos
comprados com tempo:

  - casa LINHA INTEIRA, nunca substring -- substring casa duas indentacoes e o
    arnes aborta acusando a si mesmo;
  - LEVANTA se o modulo mutado nao compilar -- pytest reporta ERROR e nao
    FAILED, e a leitura vira "nenhuma trava pega";
  - LEVANTA em NameError/ImportError -- trava vermelha pela causa errada e'
    desfecho certo por acidente, e nao mede nada;
  - PREVE o conjunto de mortas antes de rodar. Previsao errada e' informacao:
    diz que a trava e' mais especifica (ou menos) do que eu supunha.

🚨 Por que este arnes importa mais do que a media: o detector ESCREVE o arquivo
que descreve o projeto sob revisao. Um campo chutado nao levanta erro -- ele
parece declarado, e converte a categoria honesta (ausente, que o pre-voo
denuncia) na categoria perigosa (torto, que segue calado ate' a rodada sair
morna). As travas daqui sao a unica coisa entre isso e o cliente.
"""
import ast
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ALVO = pathlib.Path("veredito/detector.py")
SUITE = ["tests/test_detector.py", "tests/test_detector_nu.py"]

# (nome, linha inteira que precisa existir, linha nova, travas que devem morrer)
MUTACOES = [
    # ---------------------------------------------------------------- chutar
    ("o repo NU passa a ganhar um compose que nao existe",
     '        det.falta("app.compose",',
     '        det.poe("app.compose", "docker-compose.yml", "chute"); det.falta("app.compose",',
     {"test_repo_nu_nao_deriva_campo_nenhum",
      "test_repo_nu_produz_yaml_sem_nenhum_campo"}),

    ("o nome do banco descartavel volta a ser chutado quando nao ha banco",
     '        det.falta("banco.descartavel_testes",',
     '        det.poe("banco.descartavel_testes", "kb_veredito", "chute"); det.falta("banco.descartavel_testes",',
     {"test_compose_vazio_tambem_nao_inventa"}),

    # ------------------------------------------------- o que nunca e' emitido
    ("`preparar` passa a ser auto-emitido a partir do servico que parece seed",
     '    det.falta("app.preparar",',
     '    det.poe("app.preparar", [["run", "--rm", "seed"]], "chute"); det.falta("app.preparar",',
     # Duas, e nao uma: `_preparar_nunca` roda TAMBEM no compose vazio, entao o
     # chute aparece la' como campo derivado. A previsao original dizia so' a
     # primeira -- a trava do repo nu e' mais ampla do que eu supunha, e isso e'
     # a favor dela.
     {"test_preparar_NUNCA_e_auto_emitido_mesmo_com_servico_que_roda_e_sai",
      "test_compose_vazio_tambem_nao_inventa"}),

    ("`contexto` passa a ser auto-detectado a partir do primeiro .md plausivel",
     '    det.falta("contexto",',
     '    det.poe("contexto", "docs/REGRAS.md", "chute"); det.falta("contexto",',
     # CINCO. `_o_que_e_sempre_humano` roda ate' no repositorio NU -- de
     # proposito, porque e' la' que o operador mais precisa saber o que falta.
     # Entao o chute aparece num diretorio vazio, e as travas do nu o pegam. De
     # quebra `docs/REGRAS.md` esta na lista de valores de vizinho, e a trava do
     # fallback dispara sozinha. Tres redes independentes pegaram o mesmo chute.
     {"test_contexto_NUNCA_e_auto_detectado_mesmo_havendo_candidato",
      "test_compose_vazio_tambem_nao_inventa",
      "test_nenhum_valor_de_repositorio_VIZINHO_aparece_no_repo_nu",
      "test_repo_nu_nao_deriva_campo_nenhum",
      "test_repo_nu_produz_yaml_sem_nenhum_campo"}),

    # `False and f(...)` curto-circuita: a chamada nao acontece e o modulo
    # continua valido. Arrancar o nome daria NameError e mataria a trava certa
    # pela causa errada.
    ("achar o servico efemero deixa de virar pergunta",
     "        det.avisos.append(",
     "        False and det.avisos.append(",
     {"test_preparar_NUNCA_e_auto_emitido_mesmo_com_servico_que_roda_e_sai"}),

    # -------------------------------------------------------- interpolacao
    ("`${VAR}` sem default volta a ser copiado como se fosse valor",
     "    padrao = m.group(2)",
     "    padrao = m.group(2) if m.group(2) else texto",
     {"test_porta_interpolada_SEM_default_fica_ausente",
      "test_senha_do_banco_interpolada_sem_default_fica_ausente"}),

    ("o split cru volta, e parte DENTRO de `${PORTA:-9911}`",
     "        pedaco = _fatia_por_dois_pontos(str(p))",
     '        pedaco = str(p).split(":")',
     {"test_porta_interpolada_COM_default_usa_o_default"}),

    ("servico com porta nao resolvida some da lista, e a causa vira outra",
     "            and _contexto_de_build(s) and s.get(\"ports\")]",
     "            and _contexto_de_build(s) and _porta_publicada(s)]",
     {"test_porta_interpolada_SEM_default_fica_ausente"}),

    # ------------------------------------------------------ escolha calada
    ("dois candidatos com teste: escolhe o primeiro em vez de perguntar",
     "    if len(com_teste) == 1:",
     "    if len(com_teste) >= 1:",
     {"test_ambiguidade_real_fica_AUSENTE_em_vez_de_escolher"}),

    ("mais de um diretorio de teste: escolhe em ordem alfabetica, calado",
     "    if len(dirs) > 1:",
     "    if False:",
     {"test_mais_de_um_diretorio_de_teste_fica_AUSENTE_com_a_lista"}),

    # ---------------------------------------------------------- multi-stage
    ("o Dockerfile volta a ser lido inteiro, e o estagio `builder` vaza",
     "            inicio = i",
     "            inicio = 0",
     {"test_multi_stage_o_WORKDIR_do_builder_NAO_vaza"}),

    # ---------------------------------------------------------- procedencia
    ("o valor entra sem procedencia -- 'o detector leu' vira 'o detector achou'",
     "        self.campos[campo] = Derivado(valor, de)",
     '        self.campos[campo] = Derivado(valor, "")',
     # A quarta e' consequencia: sem procedencia, `_o_que_e_nosso` deixa de ser
     # reconhecivel como convencao, e os tres campos nossos passam a contar como
     # derivados num compose vazio.
     {"test_todo_campo_derivado_carrega_procedencia",
      "test_cada_campo_do_yaml_vem_com_a_procedencia_ao_lado",
      "test_convencao_nossa_nunca_conta_como_divergencia",
      "test_compose_vazio_tambem_nao_inventa"}),

    # ------------------------------------------------------- sobrescrever
    ("o destino passa a ser o proprio veredito.yml do cliente",
     '    return raiz / "veredito.yml.detectado"',
     '    return raiz / "veredito.yml"',
     {"test_o_destino_NUNCA_e_o_veredito_yml"}),
]


def _falhas(saida: str) -> set[str]:
    fora = set()
    for linha in saida.splitlines():
        if linha.startswith("FAILED "):
            fora.add(linha.split("::")[-1].split()[0].split("[")[0])
    return fora


def _roda() -> str:
    """🚨 `PYTHONDONTWRITEBYTECODE=1` NAO E' HIGIENE -- e' o conserto de um
    defeito que fez este arnes medir a mutacao ERRADA.

    Medido, nao suposto. A mutacao da procedencia matou `test_multi_stage`, que
    e' a trava da mutacao ANTERIOR, e nenhuma das tres que ela devia matar.
    Reproduzido a mao, a mesma mutacao matou exatamente as tres previstas.

    A causa: o `.pyc` e' revalidado por (mtime, TAMANHO) do fonte. Duas mutacoes
    consecutivas que preservam o tamanho do arquivo -- `inicio = i` -> `inicio =
    0` e `Derivado(valor, de)` -> `Derivado(valor, "")`, as duas de mesmo
    comprimento -- escritas dentro do mesmo tique de mtime fazem o subprocesso
    importar o BYTECODE DA RODADA ANTERIOR. O arnes entao reporta o kill-set de
    uma mutacao que nao esta mais no disco.

    E' a quarta variacao de "mutacao que nao mede o que alega" em tres dias, e a
    mais dificil das quatro: as outras deixavam o modulo quebrado ou a suite
    inteira verde, que sao sinais. Esta produz um conjunto de mortas PLAUSIVEL
    -- travas de verdade, vermelhas de verdade, pela mutacao errada. Se as duas
    linhas trocadas fossem vizinhas no assunto, ninguem notaria.

    ⚠️ Os outros arnesses (`mutacao_leitura_parcial`, `mutacao_corrida_do_mount`,
    `mutacao_parecer`, `mutacao_fronteira_do_pr`) tem a mesma forma e a mesma
    exposicao. Eles nao foram mordidos porque as mutacoes deles mudam o tamanho
    do arquivo -- o que e' sorte, nao desenho.
    """
    ambiente = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    for cache in pathlib.Path("veredito").glob("__pycache__/detector.*.pyc"):
        cache.unlink(missing_ok=True)
    r = subprocess.run(
        [sys.executable, "-m", "pytest", *SUITE, "-q", "--no-header",
         "-p", "no:cacheprovider"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=ambiente)
    return r.stdout + r.stderr


def main() -> int:
    original = ALVO.read_text(encoding="utf-8")
    guardado = pathlib.Path(tempfile.mkdtemp()) / "detector.py.bak"
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
