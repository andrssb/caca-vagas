"""Cada fonte expõe `coletar(cliente, termo)` e uma função pura de parse, testável sem rede."""

from . import gupy, infojobs, programathor, solides

FONTES = {
    "gupy": gupy,
    "solides": solides,
    "programathor": programathor,
    "infojobs": infojobs,
}
