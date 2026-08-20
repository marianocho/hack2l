"""Espelha os .md do repo para o `fontes/` do vault, e DENUNCIA divergencia.

🚨 POR QUE ISTO EXISTE

Em 19/08 descobrimos que o mesmo quadro vivia em TRES lugares:

    hack2l/PROXIMOS_PASSOS.md          o repo -- a fila viva
    vault/VEREDITO/Onde retomar.md     resumo escrito A MAO
    vault/VEREDITO/fontes/PROXIMOS...  espelho do repo

E o pior: o `Onde retomar.md` declara `fontes/` como a sua fonte, e o
`fontes/` estava em **11/08** enquanto o repo estava em 19/08. Oito dias. A
fonte declarada era a copia mais velha das tres, e nada avisava.

E' a regra do "um arquivo so, sem copia" do CLAUDE.md sendo violada por tres,
com o agravante de a violacao ser silenciosa. Copia que ninguem confere nao e'
backup, e' desinformacao com carimbo de fonte.

⚠️ O `Onde retomar.md` NAO e' espelho e nunca e' tocado por este script. Ele e'
escrito a mao, com wikilinks e sintese; sobrescreve-lo com o texto do repo
destruiria trabalho. Aqui so' anda o `fontes/`.

---

🚨 A COMPARACAO E' NORMALIZADA, E ISSO NAO E' FROUXIDAO

Medido em 19/08: dos 6 arquivos que `cmp` acusava divergentes, **5 diferiam so'
no fim de linha** -- o repo tem CRLF (git no Windows), o vault tem LF. Um so'
(`ESTADO.md`) divergia de conteudo de verdade.

Trava por byte acusaria os 6 em toda execucao, para sempre. Alarme que dispara
sempre ensina o leitor a pular justamente a linha que existe para o caso raro --
e' a guarda morrendo de EXCESSO, que da' no mesmo que morrer de falta. Foi o
`NAO MEDIDO` do banco, em 17/08.

Entao a comparacao ignora BOM, CRLF e espaco no fim da linha, e **so' isso**.
Diferenca de conteudo continua sendo divergencia.

---

🚨 O CAMINHO DO VAULT VEM DO AMBIENTE, NUNCA CHUMBADO

`hack2l` e' repositorio PUBLICO. O vault e' pessoal, mora no OneDrive de UMA
maquina, e nao esta no git. Escrever `C:\\Users\\luisf\\...` aqui dentro seria a
decima quinta instancia do layout chumbado -- o mesmo mecanismo do `app/api/app`
que custou 15/08 e 17/08.

    set VEREDITO_VAULT_FONTES=C:\\Users\\...\\veredito-obsidian\\VEREDITO\\fontes

Sem a variavel: **NAO SE APLICA**, dito em voz alta, e sai com 0. Maquina que
nao tem vault nao tem divergencia de vault -- isso e' limite honesto, nao falha.

---

USO

    py -3.12 scripts/sync_vault.py                 # confere e RECUSA escrever
    py -3.12 scripts/sync_vault.py --sincronizar   # escreve repo -> vault

⚠️ Conferir e' o padrao de proposito. Sincronizar sobrescreve arquivo do vault;
efeito que apaga trabalho de alguem se pergunta antes, nao se assume.

🚫 Nunca apaga arquivo do vault, e nunca escreve fora de `fontes/`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]          # hack2l/
VARIAVEL = "VEREDITO_VAULT_FONTES"

# 🚨 O unico espelho cujo original mora FORA do git, e de proposito: o
# `../CLAUDE.md` e' o documento de MAQUINA (Python, Docker, sockets), que
# envelhece por laptop e nao por produto. Derivado da raiz, nao chumbado.
ESPELHOS_DE_FORA = {"AMBIENTE-maquina.md": RAIZ.parent / "CLAUDE.md"}


def normaliza(bruto: bytes) -> str:
    """O que conta como "o mesmo arquivo".

    Ignora BOM, CRLF e espaco no fim da linha -- e nada alem disso. Ver o
    docstring do modulo: 5 de 6 divergencias medidas eram so' fim de linha, e
    uma trava que acusa as 6 e' uma trava que ninguem le.

    ⚠️ QUEM FAZ O TRABALHO E' O `rstrip()`, sozinho. A primeira versao tinha
    tambem um `.replace("\\r\\n", "\\n")` antes do split -- e a mutacao mostrou
    que ele era NO-OP: `rstrip()` sem argumento ja come o `\\r`, porque `\\r` e'
    espaco em branco. Dois mecanismos suficientes para a mesma coisa fazem a
    trava perder o poder de discriminar: tirar qualquer um deles deixava os
    testes VERDES, e trava que nao morre com o defeito injetado nao esta
    medindo o defeito. Um mecanismo so, e cada teste mata uma mutacao.

    🚫 Nao normaliza CR sozinho (fim de linha do Mac antigo). Nenhum arquivo
    aqui usa, e cobrir caso que nao existe e' outra forma de guarda que nunca
    e' exercitada.
    """
    texto = bruto.decode("utf-8-sig", errors="replace")
    return "\n".join(linha.rstrip() for linha in texto.split("\n")).strip()


def pares(fontes: Path) -> list[tuple[str, Path, Path]]:
    """(nome, origem no repo, destino no vault), para cada espelho que EXISTE.

    ⚠️ Derivado do que ja esta em `fontes/`, nunca de uma lista mantida aqui.
    Quem decide o que merece espelho e' o dono do vault; o trabalho deste script
    e' manter VERDADEIRO o espelho que ele escolheu, nao opinar sobre a escolha.
    Documento novo no repo simplesmente nao e' espelhado -- e isso e' correto.
    """
    fora = []
    for destino in sorted(fontes.glob("*.md")):
        origem = ESPELHOS_DE_FORA.get(destino.name, RAIZ / destino.name)
        fora.append((destino.name, origem, destino))
    return fora


def confere(fontes: Path) -> dict:
    """Devolve o estado, sem escrever nada."""
    iguais, divergentes, sem_origem = [], [], []
    for nome, origem, destino in pares(fontes):
        if not origem.is_file():
            # Arquivo no vault que nao tem par no repo. Nao e' erro (pode ser
            # nota que so' existe la'), mas e' dito -- silencio aqui leria como
            # "conferido e igual".
            sem_origem.append(nome)
            continue
        if normaliza(origem.read_bytes()) == normaliza(destino.read_bytes()):
            iguais.append(nome)
        else:
            divergentes.append(nome)
    return {"iguais": iguais, "divergentes": divergentes,
            "sem_origem": sem_origem, "total": len(iguais) + len(divergentes)}


def sincroniza(fontes: Path) -> list[str]:
    """Escreve repo -> vault. So' os divergentes, so' dentro de `fontes/`.

    Grava com LF: e' o que o vault ja usa, e escrever CRLF faria o OneDrive
    sincronizar 20 arquivos por nada. A comparacao e' normalizada, entao a
    escolha nao afeta a trava -- afeta o ruido.
    """
    escritos = []
    for nome, origem, destino in pares(fontes):
        if not origem.is_file():
            continue
        conteudo = origem.read_bytes().decode("utf-8-sig", errors="replace")
        novo = conteudo.replace("\r\n", "\n")
        if normaliza(origem.read_bytes()) == normaliza(destino.read_bytes()):
            continue
        destino.write_text(novo, encoding="utf-8", newline="\n")
        escritos.append(nome)
    return escritos


def caminho_do_vault() -> Path | None:
    bruto = os.environ.get(VARIAVEL, "").strip()
    if not bruto:
        return None
    p = Path(bruto).expanduser()
    return p if p.is_dir() else None


def main(argv: list[str]) -> int:
    fontes = caminho_do_vault()
    if fontes is None:
        # 🚫 NAO SE APLICA nao e' NAO MEDIDO, e nao e' falha. Maquina sem vault
        # nao tem divergencia de vault. Sai 0, e diz por que.
        cru = os.environ.get(VARIAVEL, "").strip()
        motivo = (f"{VARIAVEL} aponta para {cru!r}, que nao e' um diretorio"
                  if cru else f"{VARIAVEL} nao esta definida")
        print(f"NAO SE APLICA: {motivo}.")
        print("  Esta maquina nao espelha o vault. Nada a conferir, nada a sincronizar.")
        return 0

    estado = confere(fontes)
    escrever = "--sincronizar" in argv

    print(f"vault: {fontes}")
    print(f"  {len(estado['iguais'])} de {estado['total']} espelho(s) em dia")
    for nome in estado["sem_origem"]:
        print(f"  -- sem par no repo (intocado): {nome}")

    if not estado["divergentes"]:
        print("  tudo em dia.")
        return 0

    print(f"  !! {len(estado['divergentes'])} DIVERGENTE(S):")
    for nome in estado["divergentes"]:
        print(f"       {nome}")

    if not escrever:
        # 🚨 O caminho ABSOLUTO, nao `scripts/sync_vault.py`.
        #
        # A dica relativa so' funciona de dentro de `hack2l/`, e quem roda da
        # raiz de cima (`Hack2L/`) recebe "No such file or directory" -- ou
        # seja, a instrucao devolvia a pessoa exatamente ao erro que ela
        # acabara de cometer. Aconteceu de verdade em 19/08.
        #
        # Instrucao que esta certa so' em um diretorio e' da mesma familia do
        # layout chumbado: funciona onde foi escrita e mente em todo o resto.
        print("\n  Conferencia apenas. Para escrever repo -> vault:")
        print(f'       py -3.12 "{Path(__file__).resolve()}" --sincronizar')
        return 1

    escritos = sincroniza(fontes)
    print(f"\n  sincronizados: {len(escritos)}")
    for nome in escritos:
        print(f"       {nome}")
    restou = confere(fontes)["divergentes"]
    if restou:
        # A conferencia DEPOIS da escrita, e nao o retorno do write. Mesma
        # distincao da R0: quem diz que deu certo e' a medicao, nao o codigo
        # que fez a acao se autodeclarando.
        print(f"  !! ainda divergente depois de escrever: {restou}")
        return 1
    print("  conferido depois de escrever: tudo em dia.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
