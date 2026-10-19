"""Programathor: portal só de TI. A lista de vagas júnior vem pronta no HTML."""

import re

import httpx
from bs4 import BeautifulSoup

from ..modelo import Vaga, modalidade_do_texto

BASE = "https://programathor.com.br"
URL = f"{BASE}/jobs"
MAX_PAGINAS = 30


def _icone(card, classe: str) -> str:
    icone = card.select_one(f"i.{classe}")
    return icone.parent.get_text(" ", strip=True) if icone else ""


def parse(html: str) -> list[Vaga]:
    sopa = BeautifulSoup(html, "html.parser")
    vagas = []
    for link in sopa.select(".cell-list > a[href^='/jobs/']"):
        titulo_el = link.select_one("h3")
        if not titulo_el:
            continue
        # Vaga expirada continua na lista com a etiqueta "Vencida".
        if any("vencida" in s.get_text().lower() for s in titulo_el.select("span")):
            continue
        titulo = titulo_el.get_text(" ", strip=True)
        href = link["href"]
        id_externo = re.match(r"/jobs/(\d+)", href).group(1)
        local = _icone(link, "fa-map-marker-alt")
        cidade = re.sub(r"\s*\(.*?\)\s*$", "", local).strip()
        vagas.append(
            Vaga(
                fonte="programathor",
                id_externo=id_externo,
                titulo=titulo,
                empresa=_icone(link, "fa-briefcase"),
                url=BASE + href,
                cidade="" if cidade.lower() == "remoto" else cidade,
                modalidade=modalidade_do_texto(local),
                contrato=_icone(link, "fa-file-alt"),
                senioridade=_icone(link, "fa-chart-bar"),
                salario=_icone(link, "fa-money-bill-alt"),
                tags=[t.get_text(strip=True) for t in link.select(".tag-list")],
            )
        )
    return vagas


def coletar(cliente: httpx.Client, termos: list[str]) -> list[Vaga]:
    # O portal é só de TI, então a lista geral já serve; os termos não são usados aqui.
    # As vagas ativas vêm primeiro: a primeira página só com "Vencida" encerra a leitura.
    vagas: list[Vaga] = []
    vistas: set[str] = set()
    for pagina in range(1, MAX_PAGINAS + 1):
        resposta = cliente.get(URL if pagina == 1 else f"{URL}/page/{pagina}")
        resposta.raise_for_status()
        ativas = [v for v in parse(resposta.text) if v.id_externo not in vistas]
        if not ativas:
            break
        vistas.update(v.id_externo for v in ativas)
        vagas.extend(ativas)
    return vagas
