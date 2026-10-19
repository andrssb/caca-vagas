import tomllib
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


@dataclass
class Habilidade:
    nome: str
    sinonimos: list[str]
    peso: int


@dataclass
class Perfil:
    termos: list[str]
    dias: int
    contratos: list[str]
    cidades: list[str]
    area: list[str]
    habilidades: list[Habilidade]


def carregar(caminho: Path = RAIZ / "perfil.toml") -> Perfil:
    with open(caminho, "rb") as arquivo:
        dados = tomllib.load(arquivo)
    habilidades = []
    for chave, peso in dados.get("habilidades", {}).items():
        sinonimos = [s.strip() for s in chave.split("|") if s.strip()]
        habilidades.append(Habilidade(nome=sinonimos[0], sinonimos=sinonimos, peso=int(peso)))
    return Perfil(
        termos=dados["busca"]["termos"],
        dias=int(dados["busca"].get("dias", 30)),
        contratos=dados["filtro"].get("contratos", []),
        cidades=dados["filtro"].get("cidades", []),
        area=dados["filtro"].get("area", []),
        habilidades=habilidades,
    )
