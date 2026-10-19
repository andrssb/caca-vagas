"""Uso:
    python -m caca_vagas coletar [--fontes gupy,solides]
    python -m caca_vagas listar [--top 20]
    python -m caca_vagas painel [--porta 8000]
"""

import argparse
from contextlib import closing

from . import banco, coleta, perfil
from .fontes import FONTES


def _coletar(args) -> None:
    fontes = args.fontes.split(",") if args.fontes else None
    desconhecidas = set(fontes or []) - set(FONTES)
    if desconhecidas:
        raise SystemExit(f"fonte desconhecida: {', '.join(sorted(desconhecidas))}. Opções: {', '.join(FONTES)}")
    resumo = coleta.rodar(perfil.carregar(), fontes)
    print()
    for nome, n in resumo.coletadas.items():
        print(f"{nome:<13} {n:>4} coletadas  {resumo.aceitas[nome]:>3} no perfil")
    print(f"\nnovas no banco: {resumo.novas}")
    if resumo.recusas:
        print("recusadas por:", ", ".join(f"{motivo} ({n})" for motivo, n in resumo.recusas.most_common()))
    for nome, erro in resumo.erros.items():
        print(f"FALHOU {nome}: {erro}")


def _listar(args) -> None:
    with closing(banco.conectar()) as conexao:
        for v in banco.listar(conexao)[: args.top]:
            local = v["modalidade"] or "?"
            if v["cidade"]:
                local += f" {v['cidade']}"
            print(f"{v['nota']:>3}  {v['titulo'][:55]:<55}  {v['empresa'][:22]:<22}  {local[:24]:<24}  {v['url']}")


def _painel(args) -> None:
    import uvicorn

    print(f"painel em http://127.0.0.1:{args.porta}")
    uvicorn.run("caca_vagas.painel:app", host="127.0.0.1", port=args.porta, log_level="warning")


def main() -> None:
    parser = argparse.ArgumentParser(prog="caca_vagas", description="Caça Vagas: vagas de TI júnior ranqueadas pelo seu perfil")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("coletar", help="busca vagas em todos os portais e grava no banco")
    p.add_argument("--fontes", help=f"lista separada por vírgula ({', '.join(FONTES)})")
    p.set_defaults(func=_coletar)

    p = sub.add_parser("listar", help="mostra as melhores vagas ainda não tratadas")
    p.add_argument("--top", type=int, default=20)
    p.set_defaults(func=_listar)

    p = sub.add_parser("painel", help="abre o painel local no navegador")
    p.add_argument("--porta", type=int, default=8000)
    p.set_defaults(func=_painel)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
