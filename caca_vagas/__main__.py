"""Uso:
    python -m caca_vagas coletar [--fontes gupy,solides] [--saida vagas.sql]
    python -m caca_vagas alertas [--simular]
"""

import argparse
import os
from pathlib import Path

from . import alertas, coleta
from .fontes import FONTES


def _coletar(args) -> None:
    fontes = args.fontes.split(",") if args.fontes else None
    desconhecidas = set(fontes or []) - set(FONTES)
    if desconhecidas:
        raise SystemExit(f"fonte desconhecida: {', '.join(sorted(desconhecidas))}. Opções: {', '.join(FONTES)}")

    resumo = coleta.rodar(fontes)
    print()
    for nome, n in resumo.coletadas.items():
        print(f"{nome:<13} {n:>5} coletadas  {resumo.aceitas[nome]:>5} aceitas")
    print(f"\ntotal no site: {len(resumo.vagas)}")
    if resumo.recusas:
        print("recusadas por:", ", ".join(f"{motivo} ({n})" for motivo, n in resumo.recusas.most_common()))

    Path(args.saida).write_text(coleta.sql_de(resumo), encoding="utf-8")
    print(f"SQL gravado em {args.saida}")

    for nome, erro in resumo.erros.items():
        print(f"FALHOU {nome}: {erro}")
    # Todas as fontes falharam: não há o que publicar, e o agendador precisa ver o erro.
    if not resumo.fontes_ok:
        raise SystemExit(1)


def _alertas(args) -> None:
    if not args.simular and not (os.environ.get("SMTP_USUARIO") and os.environ.get("SMTP_SENHA")):
        print("SMTP_USUARIO/SMTP_SENHA não configurados: alertas não enviados.")
        return
    if alertas.enviar_todos(simular=args.simular):
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(prog="caca_vagas", description="Caça Vagas: coleta de vagas de TI")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("coletar", help="busca vagas em todos os portais e gera o SQL para o banco do site")
    p.add_argument("--fontes", help=f"lista separada por vírgula ({', '.join(FONTES)})")
    p.add_argument("--saida", default="vagas.sql")
    p.set_defaults(func=_coletar)

    p = sub.add_parser("alertas", help="manda o e-mail das vagas novas para cada alerta confirmado")
    p.add_argument("--simular", action="store_true", help="monta os e-mails sem enviar nem marcar como enviado")
    p.set_defaults(func=_alertas)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
