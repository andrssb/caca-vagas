"""Roda as fontes, filtra, pontua e grava. Uma fonte com erro não derruba as outras."""

import time
from collections import Counter
from dataclasses import dataclass, field

import httpx

from . import banco, filtros, ranking
from .fontes import FONTES
from .modelo import Vaga, normalizar
from .perfil import Perfil

# Ritmo de uma pessoa navegando: uma requisição por vez, com pausa entre elas.
PAUSA_SEGUNDOS = 1.5
CABECALHOS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


@dataclass
class Resumo:
    coletadas: Counter = field(default_factory=Counter)
    aceitas: Counter = field(default_factory=Counter)
    novas: int = 0
    recusas: Counter = field(default_factory=Counter)
    erros: dict[str, str] = field(default_factory=dict)


def _pausar(_requisicao: httpx.Request) -> None:
    time.sleep(PAUSA_SEGUNDOS)


def cliente_http() -> httpx.Client:
    return httpx.Client(
        headers=CABECALHOS,
        timeout=30,
        follow_redirects=True,
        event_hooks={"request": [_pausar]},
    )


def _sem_repetidas(vagas: list[Vaga]) -> list[Vaga]:
    """A mesma vaga aparece em vários termos e às vezes em dois portais."""
    vistas: set[str] = set()
    unicas = []
    for vaga in vagas:
        for chave in (vaga.chave, f"{normalizar(vaga.titulo)}|{normalizar(vaga.empresa)}"):
            if chave in vistas:
                break
        else:
            vistas.update((vaga.chave, f"{normalizar(vaga.titulo)}|{normalizar(vaga.empresa)}"))
            unicas.append(vaga)
    return unicas


def rodar(perfil: Perfil, fontes: list[str] | None = None, conexao=None, log=print) -> Resumo:
    resumo = Resumo()
    conexao = conexao or banco.conectar()
    todas: list[Vaga] = []

    with cliente_http() as cliente:
        for nome in fontes or list(FONTES):
            log(f"coletando {nome}...")
            try:
                vagas = FONTES[nome].coletar(cliente, perfil.termos)
            except Exception as erro:  # um portal fora do ar não pode parar os outros
                resumo.erros[nome] = f"{type(erro).__name__}: {erro}"
                log(f"  erro em {nome}: {resumo.erros[nome]}")
                continue
            resumo.coletadas[nome] = len(vagas)
            todas.extend(vagas)

    for vaga in _sem_repetidas(todas):
        avaliacao = filtros.avaliar(vaga, perfil)
        if not avaliacao.aceita:
            resumo.recusas[avaliacao.motivo.split(" (")[0]] += 1
            continue
        nota = ranking.pontuar(vaga, avaliacao, perfil)
        resumo.aceitas[vaga.fonte] += 1
        if banco.salvar(conexao, vaga, nota.valor, nota.habilidades, avaliacao.avisos):
            resumo.novas += 1

    return resumo
