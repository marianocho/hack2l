"""Arnes de mutacao das travas do parecer que o autor le (trilha T1).

A pergunta nao e' "passou?". E' *"o que eu quebro para ver este teste ficar
vermelho, e e' exatamente o defeito que ele alega pegar?"*.

Cada mutacao aqui REINTRODUZ um dos sete defeitos medidos no comentario que
estava no ar em `bancada#1`. Se a trava correspondente nao morrer, ela nao mede
o que diz medir -- e teste que acusa a coisa errada nao vale mais que teste que
nao acusa nada.

⚠️ Muta por INDICE DE LINHA, com a aplicacao CONFERIDA antes de rodar. Mutacao
que vira no-op devolve suite verde e se le como trava fraca -- foi o que
aconteceu em 19/08 no canario das montagens.

🚫 E nao muta por `\\` nem por sequencia de escape: em 20/08 a propria edicao
destes arquivos foi mordida duas vezes por `\\n` virando quebra de linha de
verdade no caminho ate' o disco. Linha inteira, comparada com `==`.

    py -3.12 scripts/mutacao_parecer.py
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

_SEM_PYC = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

RAIZ = pathlib.Path(__file__).resolve().parents[1]

ARQUIVOS_DE_TESTE = [
    "tests/test_superficie_do_pr.py",
    "tests/test_comentario_de_pr.py",
    "tests/test_fusao_por_defeito.py",
    "tests/test_escopo_no_parecer.py",
    "tests/test_juiz.py",
    "tests/test_posta_o_parecer.py",
    "tests/test_fusao_provada_no_parecer.py",
]

# ⚠️ Precisa de Docker e de um clone com historico: numa worktree de trilha ele
# falha por AMBIENTE, nao por defeito. Deixa-lo entrar tornaria a base vermelha
# e o arnes se recusaria a rodar -- o que e' o comportamento certo do arnes, e
# por isso a exclusao e' explicita e nomeada em vez de silenciosa.
DESELECIONADOS = [
    "tests/test_fusao_provada_no_parecer.py::"
    "test_o_caminho_FELIZ_chega_ao_fim_sem_erro_de_encanamento",
]

# (nome, arquivo, linha exata de hoje, linha mutada, travas que DEVEM morrer)
MUTACOES = [
    # ---------------------------------------------- defeito 2: plural de formulario
    (
        "o resumo volta ao plural de formulario (`1 achado(s)`)",
        "veredito/comentario.py",
        '        return f"**{superficie.conta(c, \'achado\')} com evidência.**{cauda}"',
        '        return f"**{c} achado(s) com evidência.**{cauda}"',
        # Quatro mortes: alem das duas travas do plural, os dois testes da
        # contagem do comentario conferem a linha de resumo por extenso
        # ("**2 achados com evidência.**"), entao o plural quebrado os derruba
        # junto. Consequencia real -- e' a mesma linha de texto.
        {"test_o_plural_nao_e_de_formulario",
         "test_resumo_com_condenado_poe_o_achado_na_frente",
         "test_a_CONTAGEM_do_comentario_segue_a_prova",
         "test_sem_prova_a_contagem_e_a_da_heuristica"},
    ),
    # ------------------------------------------------------- defeito 1: o acento
    (
        "a legenda volta a sair sem acento",
        "veredito/comentario.py",
        '        "**provado** = há artefato reproduzível (um teste que passa no commit "',
        '        "**provado** = ha artefato reproduzivel (um teste que passa no commit "',
        {"test_o_texto_que_o_autor_le_vem_acentuado"},
    ),
    # ------------------------------- defeito 3: severidade e confianca iguais
    (
        "o cabecalho volta a `[ALTA] [alta]`",
        "veredito/superficie.py",
        "            f\"#### {sev} &middot; {cabeca.get('categoria', '?')} em {local}\",",
        '            f"[{sev}] [{conf}] {cabeca.get(\'categoria\', \'?\')} - {local}",',
        {"test_severidade_e_confianca_nao_saem_como_duas_etiquetas_iguais"},
    ),
    # ------------------------- defeito 4: caixa alta de terminal no markdown
    (
        "o markdown volta a usar o rotulo do terminal",
        "veredito/superficie.py",
        '        return f"**{rotulo}.**"',
        '        return f"{rotulo.upper()}:"',
        {"test_o_bloco_nao_sai_com_rotulo_de_terminal"},
    ),
    (
        "a frase da fusao volta a gritar o estado em caixa alta",
        "veredito/prova_de_fusao.py",
        '        return (f"Provada por medição: revertendo um único trecho do diff, os "',
        '        return (f"FUSAO PROVADA: revertendo um único trecho do diff, os "',
        # So' uma: a contagem do comentario nao le o TEXTO da frase, so' o
        # veredito da fusao. Previ duas e estava errado -- e a diferenca e'
        # exatamente a separacao que se quer entre contar e redigir.
        {"test_MESMO_mantem_junto_e_diz_que_provou"},
    ),
    # ------------------------------------------------- defeito 5: o permalink
    (
        "o local volta a ser texto, sem link",
        "veredito/superficie.py",
        "        url = self.ligacao.arquivo(texto) if self.ligacao else None",
        "        url = None",
        {"test_o_local_vira_permalink_ancorado_no_COMMIT"},
    ),
    (
        "a ligacao passa a nascer sem exigir repo e commit (link chutado)",
        "veredito/superficie.py",
        '        if not repo or not head or repo.count("/") != 1:',
        "        if False:",
        # A segunda morte e' a MESMA invariante vista uma camada abaixo: o
        # teste de posta_parecer termina em `Ligacao.de(meta) is None`, e com a
        # ligacao nascendo sem procedencia ele deixa de valer. Duas travas para
        # o mesmo defeito e' redundancia de proposito -- o link errado e' o
        # unico defeito desta trilha que MANDA o autor para o lugar errado.
        {"test_sem_repo_ou_commit_o_parecer_NAO_inventa_endereco",
         "test_sem_carimbo_com_commit_o_campo_head_NAO_e_inventado"},
    ),
    (
        "o carimbo volta a casar frouxo, e o horario vira `commit`",
        "veredito/superficie.py",
        '_HEAD_NO_CARIMBO = re.compile(r"^\\d{8}T\\d{4}-([0-9a-f]{7,40})$")',
        '_HEAD_NO_CARIMBO = re.compile(r"^(.*)$")',
        # Tres mortes, e as duas extras sao consequencia direta: o
        # `head_do_carimbo` alimenta o `_meta_da_rodada`, entao afrouxar o
        # casamento estraga tambem o `head` que chega ao permalink.
        {"test_o_commit_sai_do_carimbo_da_rodada_e_o_casamento_e_ESTRITO",
         "test_o_repo_sai_da_URL_do_PR_e_nao_do_ambiente",
         "test_sem_carimbo_com_commit_o_campo_head_NAO_e_inventado"},
    ),
    # --------------------------------------------- defeito 6: o caminho morto
    (
        "o artefato volta a sair como caminho local, sem o rastro",
        "veredito/superficie.py",
        "        url = self.ligacao.rastro() if self.ligacao else None",
        "        url = None",
        {"test_o_artefato_aponta_para_o_rastro_da_execucao"},
    ),
    # ------------------------------------------------- defeito 7: a fila inflada
    (
        "a fila volta a sair item a item, sem agrupar por endereco",
        "veredito/fusao.py",
        "            if a == arq and ini - TOLERANCIA_LINHAS <= u and p - TOLERANCIA_LINHAS <= fim:",
        "            if False:",
        {"test_a_fila_toda_no_mesmo_trecho_sai_como_UM_agrupamento",
         "test_o_agrupamento_por_endereco_DIZ_que_e_por_endereco"},
    ),
    (
        "o agrupamento da fila junta TUDO, ate' o que esta longe",
        "veredito/fusao.py",
        "            if a == arq and ini - TOLERANCIA_LINHAS <= u and p - TOLERANCIA_LINHAS <= fim:",
        "            if True:",
        # Duas mortes, e a segunda e' consequencia REAL da mutacao, nao trava
        # frouxa: agrupando tudo, os dois itens daquele teste (que estao em
        # ARQUIVOS diferentes) caem no mesmo grupo, e dentro de um grupo o
        # caminho sai do item e vira cabecalho da regiao. Os dois caminhos que
        # ele confere deixam de aparecer. Verificado lendo o teste.
        {"test_suspeitas_em_trechos_DIFERENTES_nao_sao_juntadas",
         "test_secao_de_nao_testadas_lista_cada_uma_com_motivo"},
    ),
    # ------------------------- a procedencia do link, em posta_parecer.py
    (
        "o repo passa a vir do ambiente, e nao do PR que estamos comentando",
        "posta_parecer.py",
        '        meta["repo"] = f"{dono}/{repo}"',
        "        pass",
        {"test_o_repo_sai_da_URL_do_PR_e_nao_do_ambiente"},
    ),
    (
        "o head passa a sair do nome da pasta sem conferir o formato",
        "posta_parecer.py",
        "    head = superficie.head_do_carimbo(cfg.RODADA.name)",
        "    head = cfg.RODADA.name",
        # A outra morte e' consequencia: aquele teste confere `head ==
        # "61cc0a7"`, e com a mutacao o `head` vira o nome inteiro da pasta.
        {"test_sem_carimbo_com_commit_o_campo_head_NAO_e_inventado",
         "test_o_repo_sai_da_URL_do_PR_e_nao_do_ambiente"},
    ),
    # --------------- o parecer de TERMINAL nao pode regredir junto com o do PR
    (
        "o terminal passa a usar a tipografia do markdown",
        "veredito/superficie.py",
        '        return f"{rotulo.upper()}:"',
        '        return f"**{rotulo}.**"',
        # 🚨 A previsao inicial estava ERRADA aqui, e o erro foi util.
        #
        # Eu esperava que as travas da fusao morressem tambem. Elas NAO morrem,
        # e estao certas em nao morrer: elas perguntam ao estilo qual e' o
        # rotulo dele (`TERMINAL.rotulo(...)`) porque a afirmacao delas e' sobre
        # ORDEM -- "convergencia antes do conserto" -- e ordem sobrevive a
        # troca de tipografia.
        #
        # O que morre sao as tres que afirmam a TIPOGRAFIA do terminal, com o
        # literal escrito. E foi esta mutacao que mostrou que
        # `test_o_terminal_continua_em_caixa_alta` passava VERDE com o defeito
        # presente enquanto ela tambem perguntava ao estilo: os dois lados da
        # comparacao saiam da funcao mutada. Ver o comentario em
        # tests/test_superficie_do_pr.py.
        {"test_o_terminal_continua_em_caixa_alta",
         "test_corroboracao_externa_aparece_no_parecer",
         "test_parecer_de_condenado_cita_os_dois_commits"},
    ),
]


def falhas_de(saida: str) -> set[str]:
    return set(re.findall(r"FAILED tests/[\w_]+\.py::(\w+)", saida))


def roda() -> tuple[int, set[str]]:
    p = subprocess.run(
        [sys.executable, "-m", "pytest", *ARQUIVOS_DE_TESTE, "-q",
         "--no-header", "-p", "no:cacheprovider",
         *[a for d in DESELECIONADOS for a in ("--deselect", d)]],
        cwd=RAIZ, capture_output=True, text=True, errors="replace",
        env=_SEM_PYC)
    return p.returncode, falhas_de(p.stdout + p.stderr)


def main() -> int:
    codigo, base = roda()
    if codigo != 0 or base:
        print(f"a suite JA' esta vermelha antes de mutar: {sorted(base)}")
        return 1
    print("base: 0 falhas\n")

    problemas = []
    for nome, arquivo, velha, nova, esperadas in MUTACOES:
        caminho = RAIZ / arquivo
        original = caminho.read_text(encoding="utf-8")
        linhas = original.split("\n")

        alvos = [i for i, l in enumerate(linhas) if l == velha]
        # 🚨 A aplicacao e' CONFERIDA antes de rodar. Sem isto, mutacao que nao
        # aplica devolve suite verde e se le como trava fraca.
        if len(alvos) != 1:
            print(f"!! [{nome}]\n     NAO APLICOU: a linha aparece {len(alvos)}x")
            problemas.append(nome)
            continue

        linhas[alvos[0]] = nova
        caminho.write_text("\n".join(linhas), encoding="utf-8")
        try:
            _, mortas = roda()
        finally:
            caminho.write_text(original, encoding="utf-8")

        marca = "OK " if mortas == esperadas else "!! "
        print(f"{marca}[{nome}]")
        print(f"     morreram: {sorted(mortas) or 'NENHUMA'}")
        if mortas != esperadas:
            print(f"     esperava: {sorted(esperadas)}")
            problemas.append(nome)

    print()
    if problemas:
        print(f"{len(problemas)} mutacao(oes) sem trava especifica: {problemas}")
        return 1
    print(f"as {len(MUTACOES)} mutacoes mataram exatamente as travas previstas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
