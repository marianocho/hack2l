"""Arnes de mutacao das travas de tests/test_motor.py.

A pergunta nao e' "passou?". E' "o que eu quebro para ver este teste ficar
vermelho, e e' exatamente o defeito que ele alega pegar?".

⚠️ Muta por INDICE DE LINHA, com a aplicacao conferida antes de rodar. Mutacao
por casamento de string que vira no-op e' indistinguivel de trava fraca -- foi o
que aconteceu em 19/08 no canario das montagens: um literal com continuacao `\`
errada fez o `replace` nao aplicar, a suite passou inteira, e aquilo se leu como
"a trava nao pega".
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

RAIZ = pathlib.Path(r"C:\hack_agents\Hack2L\hack2l")

# (nome, arquivo, linha exata de hoje, linha mutada, testes que DEVEM morrer)
MUTACOES = [
    (
        "forcado sem credencial deixa de levantar",
        "veredito/motor.py",
        "        if not ok:",
        "        if False:",
        {"test_motor_forcado_sem_credencial_LEVANTA",
         "test_pre_voo_reporta_o_engano_do_operador_sem_explodir"},
    ),
    (
        "deteccao automatica passa a chamar o boto3 sempre",
        "veredito/motor.py",
        "    if not _ha_sinal_aws():",
        "    if False:",
        {"test_sem_sinal_o_boto3_nem_e_chamado"},
    ),
    (
        "mascara passa a comer o `effort`, que o Bedrock suporta",
        "veredito/motor.py",
        '            oc = {k: v for k, v in oc.items() if k != "task_budget"}',
        '            oc = {k: v for k, v in oc.items() if k not in ("task_budget", "effort")}',
        # Duas mortes, e as duas conferidas: com as duas chaves removidas o
        # `output_config` fica VAZIO e e' retirado da chamada, entao o teste da
        # remocao do task_budget morre de KeyError. Consequencia real da mutacao,
        # nao trava frouxa -- verificado rodando a mutacao isolada.
        {"test_bedrock_MANTEM_o_que_ele_suporta",
         "test_bedrock_remove_task_budget_e_a_beta_dele"},
    ),
    (
        "mascara passa a valer em TODO motor, inclusive na API direta",
        "veredito/motor.py",
        '    if not m.tem("task_budget"):',
        "    if True:",
        {"test_api_direta_mantem_task_budget_e_fallback",
         "test_claude_platform_on_aws_nao_perde_nada"},
    ),
    (
        "prefixo do Bedrock aplicado em id que ja' tem prefixo",
        "veredito/motor.py",
        '    if id_.startswith(m.prefixo_de_modelo) or ".anthropic." in id_:',
        "    if False:",
        {"test_perfil_de_inferencia_nao_e_prefixado_duas_vezes"},
    ),
    (
        "pre-voo para de dizer o que o motor perde",
        "veredito/motor.py",
        '                      "detalhe": " | ".join([cabeca] + [f"SEM {p}" for p in m.perdas()])}}',
        '                      "detalhe": cabeca}}',
        {"test_pre_voo_do_bedrock_DIZ_O_QUE_SE_PERDE"},
    ),
    (
        "diagnostico da recusa volta a nao perguntar ao motor",
        "veredito/advogado.py",
        '    if not m.tem("fallback_de_recusa"):',
        "    if False:",
        {"test_recusa_no_bedrock_NAO_culpa_rate_limit"},
    ),
]


def falhas_de(saida: str) -> set[str]:
    return set(re.findall(r"FAILED tests/test_motor\.py::(\w+)", saida))


def roda() -> tuple[int, set[str]]:
    p = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_motor.py", "-q",
         "--no-header", "-p", "no:cacheprovider"],
        cwd=RAIZ, capture_output=True, text=True, errors="replace")
    return p.returncode, falhas_de(p.stdout + p.stderr)


def main() -> int:
    codigo, base = roda()
    if codigo != 0 or base:
        print(f"a suite JA' esta vermelha antes de mutar: {sorted(base)}")
        return 1
    print(f"base: 0 falhas\n")

    problemas = []
    for nome, arquivo, velha, nova, esperadas in MUTACOES:
        caminho = RAIZ / arquivo
        original = caminho.read_text(encoding="utf-8")
        linhas = original.split("\n")

        alvos = [i for i, l in enumerate(linhas) if l == velha]
        # 🚨 A aplicacao e' CONFERIDA antes de rodar. Sem isto, mutacao que nao
        # aplica devolve suite verde e se le como trava fraca.
        if len(alvos) != 1:
            print(f"[{nome}]\n  NAO APLICOU: a linha aparece {len(alvos)}x")
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
