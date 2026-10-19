"""InfoJobs: a busca por palavra-chave devolve os cards de vaga no HTML."""

import re
from datetime import date, datetime

import httpx
from bs4 import BeautifulSoup

from ..modelo import Vaga, contrato_do_texto, modalidade_do_texto

BASE = "https://www.infojobs.com.br"
URL = f"{BASE}/empregos.aspx"
MAX_PAGINAS = 3


def _data(valor: str | None) -> date | None:
    # O card traz a data completa num atributo escondido: "2026/09/26 10:55:00".
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y/%m/%d %H:%M:%S").date()
    except ValueError:
        return None


def parse(html: str) -> list[Vaga]:
    sopa = BeautifulSoup(html, "html.parser")
    vagas = []
    for card in sopa.select("div.js_vacancyLoad[data-id]"):
        titulo_el = card.select_one(".js_vacancyTitle")
        if not titulo_el:
            continue
        titulo = titulo_el.get_text(" ", strip=True)

        local_el = card.select_one("div.mb-8")
        local = ""
        if local_el:
            for escondido in local_el.select("[hidden]"):
                escondido.decompose()
            local = local_el.get_text(" ", strip=True)
        cidade, _, uf = local.partition(" - ")

        # A linha de ícones mistura salário, experiência, escolaridade e modalidade.
        icones = [d.get_text(" ", strip=True) for d in card.select("div.d-inline-flex > div")]
        modalidade = next((m for m in map(modalidade_do_texto, icones) if m), "")
        salario = next((i for i in icones if i.startswith("R$") or "combinar" in i.lower()), "")

        resumo_el = card.select("div.text-medium")
        resumo = resumo_el[-1].get_text(" ", strip=True) if resumo_el else ""
        empresa_el = card.select_one("div.text-body")
        data_el = card.select_one(".js_date")

        vagas.append(
            Vaga(
                fonte="infojobs",
                id_externo=card["data-id"],
                titulo=titulo,
                empresa=empresa_el.get_text(" ", strip=True) if empresa_el else "",
                url=BASE + card.get("data-href", ""),
                cidade=cidade.strip(),
                uf=re.sub(r"\W", "", uf)[:2],
                modalidade=modalidade or modalidade_do_texto(titulo + " " + resumo),
                contrato=contrato_do_texto(titulo + " " + resumo),
                descricao=resumo,
                salario=salario,
                publicada_em=_data(data_el.get("data-value") if data_el else None),
            )
        )
    return vagas


def coletar(cliente: httpx.Client, termos: list[str]) -> list[Vaga]:
    vagas: list[Vaga] = []
    vistas: set[str] = set()
    for termo in termos:
        for pagina in range(1, MAX_PAGINAS + 1):
            resposta = cliente.get(URL, params={"palabra": termo, "page": pagina})
            resposta.raise_for_status()
            novas = [v for v in parse(resposta.text) if v.id_externo not in vistas]
            if not novas:
                break
            vistas.update(v.id_externo for v in novas)
            vagas.extend(novas)
    return vagas
