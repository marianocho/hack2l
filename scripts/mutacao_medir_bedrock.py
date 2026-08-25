"""Arnes de mutacao da sonda de `medir_bedrock.py --offline`.

A sonda offline existe para responder "a sonda manda mesmo o que diz que manda?".
Entao ela propria precisa da pergunta de 19/08: *o que eu quebro para ver esta
conferencia ficar vermelha, e e' exatamente o defeito que ela alega pegar?*

🚨 A mutacao 3 e' a razao deste arquivo existir. A primeira versao de
`confere_offline` procurava as betas em `corpo["anthropic_beta"]`, e no cliente
Mantle -- que e' o que `_fab_bedrock()` constroi por padrao -- a beta viaja SO'
no cabecalho `anthropic-beta` e nunca chega ao corpo. A lista vinha vazia nas
cinco celulas, a exigencia passava por VACUIDADE, e a sonda declarava "mascara
perfeita" sem nunca ter olhado para uma beta. Verde, muda, e do lado errado.

O modo `--vacuidade` reproduz o predicado ANTIGO sobre o mesmo dado capturado,
para registrar que ele passava verde com o defeito presente. Nao e' retorica: e'
a diferenca entre "consertei" e "consertei e mostrei o buraco".

⚠️ Muta por INDICE DE LINHA, com a aplicacao conferida antes de rodar. Mutacao
por casamento de string que vira no-op e' indistinguivel de trava fraca -- foi o
que aconteceu em 19/08 no canario das montagens.

    py -3.12 scripts/mutacao_medir_bedrock.py
    py -3.12 scripts/mutacao_medir_bedrock.py --vacuidade
"""
from __future__ import annotations

import argparse
import importlib
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# (nome, arquivo, linha de hoje (sem indentacao a direita), linha mutada,
#  fragmento que DEVE aparecer em alguma falha)
MUTACOES = [
    (
        "a mascara para de remover o task_budget do output_config",
        "veredito/motor.py",
        '            oc = {k: v for k, v in oc.items() if k != "task_budget"}',
        '            oc = dict(oc)',
        "mascara vaza no fio",
    ),
    (
        "a mascara para de remover o fallbacks",
        "veredito/motor.py",
        '        kw.pop("fallbacks", None)',
        '        pass',
        "mascara vaza no fio",
    ),
    (
        "a mascara deixa a beta de primeira parte na chamada",
        "veredito/motor.py",
        '        betas = [b for b in betas if b != _BETA_DE["fallback_de_recusa"]]',
        '        betas = list(betas)',
        "sobreviveu a mascara",
    ),
    (
        "a celula task_budget deixa de mandar o parametro (sonda no-op)",
        "medir_bedrock.py",
        '    tb["output_config"] = {"task_budget": {"type": "tokens", "total": 20000}}',
        '    tb["output_config"] = {"effort": "low"}',
        "sonda no-op",
    ),
    (
        "uma celula passa a usar outro modelo (o diferencial mede o prefixo)",
        "medir_bedrock.py",
        '    fb["fallbacks"] = "default"',
        '    fb["fallbacks"] = "default"; fb["model"] = "outro-modelo"',
        "mesmo modelo",
    ),
]


def _aplica(arquivo: str, alvo: str, novo: str) -> tuple[pathlib.Path, str, int]:
    p = RAIZ / arquivo
    original = p.read_text(encoding="utf-8")
    linhas = original.splitlines()
    achados = [i for i, l in enumerate(linhas) if l == alvo]
    # 🚨 A aplicacao e' CONFERIDA antes de rodar: sem isto, uma mutacao que nao
    # casa vira no-op, a conferencia passa, e o resultado se le como "a trava
    # nao pega". Foi exatamente o erro de 19/08.
    if len(achados) != 1:
        raise AssertionError(
            f"a mutacao nao tem alvo unico em {arquivo}: {len(achados)} "
            f"ocorrencia(s) de {alvo!r}. A linha mudou -- atualize o arnes.")
    i = achados[0]
    linhas[i] = novo
    p.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return p, original, i + 1


def _roda_sonda() -> list[str]:
    """Recarrega os modulos mutados e devolve as falhas que a sonda acusa."""
    import veredito.motor
    import medir_bedrock
    importlib.reload(veredito.motor)
    importlib.reload(medir_bedrock)
    res = medir_bedrock.offline()
    return medir_bedrock.confere_offline(res)


def _com_mutacao(mutacoes, fn):
    aplicadas = []
    try:
        for arquivo, alvo, novo in mutacoes:
            aplicadas.append(_aplica(arquivo, alvo, novo))
        return fn()
    finally:
        for p, original, _ in reversed(aplicadas):
            p.write_text(original, encoding="utf-8")


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--vacuidade", action="store_true",
                   help="reproduz o predicado ANTIGO (so' o corpo) sobre o "
                        "dado capturado sob mutacao, e registra que ele passava verde")
    args = a.parse_args()

    # Linha de base: sem mutacao, a sonda tem que estar limpa. Senao qualquer
    # vermelho abaixo pode ser dela, nao da mutacao.
    limpa = _roda_sonda()
    if limpa:
        print("[x] a sonda ja' acusa SEM mutacao -- conserte antes de medir:")
        for f in limpa:
            print(f"     {f}")
        return 1
    print("[ok] linha de base limpa: sem mutacao, a sonda nao acusa nada.\n")

    if args.vacuidade:
        nome, arq, alvo, novo, _ = MUTACOES[2]
        print("REGISTRO DA VACUIDADE -- o mesmo dado, os dois predicados\n")
        print(f"  mutacao: {nome}\n")

        def _mede():
            import medir_bedrock
            import veredito.motor
            importlib.reload(veredito.motor)
            importlib.reload(medir_bedrock)
            res = medir_bedrock.offline()
            return medir_bedrock, res, medir_bedrock.confere_offline(res)

        mb, res, agora = _com_mutacao([(arq, alvo, novo)], _mede)
        msk = next(l for l in res["celulas"] if l["celula"] == "mascarado")

        # 🚫 O predicado antigo e' REPRODUZIDO sobre o mesmo dado capturado, nao
        # re-encenado por mutacao do fonte. Reverter so' a extracao deixaria de
        # pe as exigencias positivas -- que sao PARTE do conserto -- e o
        # resultado mediria a mistura das duas versoes, nao a antiga.
        no_corpo = msk["betas_no_corpo"] or []
        antigo_passava = (mb.BETA_TASK_BUDGET not in no_corpo
                          and mb.BETA_FALLBACK not in no_corpo)

        print(f"  a beta REALMENTE sai na chamada mascarada? "
              f"{bool(msk['betas_no_fio'])}  {msk['betas_no_fio']}")
        print(f"  onde ela sai:      cabecalho={msk['header_beta']!r}  "
              f"corpo={msk['betas_no_corpo']!r}")
        print()
        print(f"  predicado ANTIGO (so' o corpo):          "
              f"{'PASSOU VERDE' if antigo_passava else 'ACUSOU'}")
        print(f"  conferencia de HOJE (cabecalho + corpo): "
              f"{'ACUSOU' if agora else 'PASSOU VERDE'}")
        for f in agora:
            print(f"     -> {f}")

        print()
        if msk["betas_no_fio"] and antigo_passava and agora:
            print("MEDIDO: a beta de primeira parte sai na chamada, e o predicado "
                  "antigo passava\nverde assim mesmo -- ele lia um campo que no "
                  "Mantle nunca e' preenchido.\nVacuidade, nao rigor.")
            return 0
        print("[x] o registro NAO fechou: esperava beta no fio, antigo verde, "
              "novo vermelho.")
        return 1

    falhou = 0
    for nome, arq, alvo, novo, esperado in MUTACOES:
        try:
            falhas = _com_mutacao([(arq, alvo, novo)], _roda_sonda)
        except AssertionError as e:
            print(f"[x] {nome}\n     a mutacao nem aplicou: {e}")
            falhou += 1
            continue

        casou = [f for f in falhas if esperado in f]
        if not falhas:
            print(f"[x] {nome}\n     a sonda passou VERDE com o defeito presente")
            falhou += 1
        elif not casou:
            # Vermelho pela causa errada nao vale mais que verde: e' a licao das
            # duas travas de 19/08 que morriam no `except` generico.
            print(f"[x] {nome}\n     acusou, mas nao pelo motivo esperado "
                  f"({esperado!r}): {falhas}")
            falhou += 1
        else:
            print(f"[ok] {nome}\n     -> {casou[0]}")

    print()
    print(f"{len(MUTACOES) - falhou}/{len(MUTACOES)} mutacoes mataram a "
          f"conferencia que elas alegam matar.")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
