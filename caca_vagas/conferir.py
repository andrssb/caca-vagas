"""Aviso de fonte quebrada: olha o histórico de coletas e aponta o portal que parou de funcionar.

A coleta não quebra quando um portal muda: ela só traz zero vagas daquele portal, e em 7 dias
as vagas dele somem do site sem ninguém notar. Este passo roda no Actions depois da coleta e
falha o workflow (o GitHub avisa por e-mail) quando uma fonte:
  - falhou nas duas últimas tentativas;
  - está há 2 dias sem uma coleta que funcionou;
  - trouxe menos da metade da mediana das últimas coletas.
Uma falha isolada vira só aviso: portal fora do ar por uma manhã é comum e volta sozinho.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import median

from .fontes import FONTES

DIAS_SEM_SUCESSO = 2
QUEDA = 0.5
# Abaixo disso a fonte é pequena demais para a mediana dizer alguma coisa (o Programathor tem ~25).
MEDIANA_MINIMA = 10
HISTORICO = 7


@dataclass
class Relatorio:
    problemas: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    resumo: dict[str, str] = field(default_factory=dict)


def analisar(coletas: list[dict], hoje: date, fontes: list[str] | None = None) -> Relatorio:
    """`coletas` vem da tabela, da mais nova para a mais antiga."""
    rel = Relatorio()
    for fonte in fontes or list(FONTES):
        tentativas = []  # (dia, ok, vagas ou erro), da mais nova para a mais antiga
        for c in coletas:
            erros = json.loads(c["erros"] or "{}")
            if fonte in erros:
                tentativas.append((c["em"], False, erros[fonte]))
            elif fonte in (c["fontes_ok"] or "").split(","):
                por_fonte = json.loads(c["por_fonte"]) if c.get("por_fonte") else {}
                tentativas.append((c["em"], True, por_fonte.get(fonte)))

        if not tentativas:
            rel.problemas.append(f"{fonte}: nenhuma coleta registrada")
            continue

        sucessos = [(dia, n) for dia, ok, n in tentativas if ok]
        ultimo_ok = sucessos[0][0] if sucessos else None
        if len(tentativas) >= 2 and not tentativas[0][1] and not tentativas[1][1]:
            rel.problemas.append(f"{fonte}: falhou nas duas últimas coletas ({tentativas[0][2]})")
        elif not tentativas[0][1]:
            rel.avisos.append(f"{fonte}: falhou na coleta de {tentativas[0][0]} ({tentativas[0][2]})")
        if ultimo_ok is None or date.fromisoformat(ultimo_ok) < hoje - timedelta(days=DIAS_SEM_SUCESSO):
            rel.problemas.append(f"{fonte}: sem coleta que funcionou desde {ultimo_ok or 'sempre'}")

        contagens = [n for _, n in sucessos if n is not None]
        if contagens:
            atual, anteriores = contagens[0], contagens[1 : HISTORICO + 1]
            if len(anteriores) >= 3:
                base = median(anteriores)
                rel.resumo[fonte] = f"{atual} vagas (mediana {base:.0f})"
                if base >= MEDIANA_MINIMA and atual < QUEDA * base:
                    rel.problemas.append(f"{fonte}: trouxe {atual} vagas, a mediana das últimas coletas é {base:.0f}")
            else:
                rel.resumo[fonte] = f"{atual} vagas (histórico curto para comparar)"
        elif fonte not in rel.resumo:
            rel.resumo[fonte] = "sem contagem ainda"
    return rel


def texto(rel: Relatorio) -> str:
    linhas = ["## Saúde das fontes", ""]
    linhas += [f"- **{fonte}**: {r}" for fonte, r in rel.resumo.items()]
    if rel.problemas:
        linhas += ["", "### Problemas"] + [f"- {p}" for p in rel.problemas]
    if rel.avisos:
        linhas += ["", "### Avisos"] + [f"- {a}" for a in rel.avisos]
    if not rel.problemas and not rel.avisos:
        linhas += ["", "Tudo certo."]
    return "\n".join(linhas)


def rodar(hoje: date | None = None) -> Relatorio:
    from .banco import d1

    coletas = d1("SELECT em, fontes_ok, erros, por_fonte FROM coletas ORDER BY id DESC LIMIT 60")
    rel = analisar(coletas, hoje or date.today())
    relatorio = texto(rel)
    print(relatorio)
    # No Actions, o relatório aparece na página da execução.
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(relatorio + "\n")
    return rel
