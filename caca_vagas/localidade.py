"""Cada portal escreve o local de um jeito. Aqui tudo vira (cidade, UF)."""

import re

from .modelo import normalizar

ESTADOS = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
    "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul", "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
    "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
    "SE": "Sergipe", "TO": "Tocantins",
}
_POR_NOME = {normalizar(nome): uf for uf, nome in ESTADOS.items()}
_SEM_CIDADE = {"", "brasil", "todo brasil", "remoto", "home office"}


def uf_de(texto: str) -> str:
    """'MG', 'mg' ou 'Minas Gerais' -> 'MG'. Vazio se não reconhecer."""
    t = normalizar(texto)
    if t.upper() in ESTADOS:
        return t.upper()
    return _POR_NOME.get(t, "")


def normalizar_local(cidade: str, uf: str = "") -> tuple[str, str]:
    """Separa cidade e UF de textos como 'São Paulo, São Paulo, Brasil', 'Mato Grosso - Cuiabá' ou 'Belo Horizonte/MG'."""
    partes = [p.strip() for p in re.split(r"[,/]|\s-\s", cidade) if p.strip()]
    uf_final = uf_de(uf)
    cidade_final = ""
    for parte in partes:
        reconhecida = uf_de(parte)
        if reconhecida:
            uf_final = uf_final or reconhecida
            # "São Paulo, São Paulo": o primeiro é a cidade, o segundo o estado.
            if not cidade_final and normalizar(parte) in ("sao paulo", "rio de janeiro") and parte is partes[0]:
                cidade_final = parte
            continue
        if normalizar(parte) in _SEM_CIDADE:
            continue
        if not cidade_final:
            cidade_final = parte
    return cidade_final.strip().title() if cidade_final.isupper() else cidade_final.strip(), uf_final
