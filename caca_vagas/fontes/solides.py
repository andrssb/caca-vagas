"""Sólides Vagas: o portal (vagas.solides.com.br) carrega a lista de uma API JSON pública."""

from datetime import date

import httpx

from ..modelo import Vaga, modalidade_do_texto

URL = "https://vagas.solides.com.br/api/vacancies"
# Acima de 14 por página a API responde "Failed to fetch vacancies".
POR_PAGINA = 14
MAX_PAGINAS = 6


def _data(iso: str | None) -> date | None:
    if not iso:
        return None
    try:
        return date.fromisoformat(str(iso)[:10])
    except ValueError:
        return None


def _modalidade(item: dict) -> str:
    if item.get("homeOffice"):
        return "remoto"
    return modalidade_do_texto(item.get("jobType") or "")


def parse(dados: dict) -> list[Vaga]:
    vagas = []
    for item in dados.get("data", []):
        if item.get("currentState") not in (None, "em_andamento"):
            continue
        vagas.append(
            Vaga(
                fonte="solides",
                id_externo=str(item["id"]),
                titulo=item.get("title", "").strip(),
                empresa=(item.get("companyName") or "").strip(),
                url=f"https://vagas.solides.com.br/vaga/{item['id']}",
                cidade=(item.get("city") or {}).get("name") or "",
                uf=(item.get("state") or {}).get("code") or "",
                modalidade=_modalidade(item),
                contrato=" / ".join(c["name"] for c in item.get("recruitmentContractType") or [] if c.get("name")),
                senioridade=" / ".join(s["name"] for s in item.get("seniority") or [] if s.get("name")),
                descricao=item.get("description") or "",
                tags=[h["name"] for h in item.get("hardSkills") or [] if h.get("name")],
                publicada_em=_data(item.get("createdAt") or item.get("date")),
            )
        )
    return vagas


def coletar(cliente: httpx.Client, termos: list[str]) -> list[Vaga]:
    vagas = []
    for termo in termos:
        for pagina in range(1, MAX_PAGINAS + 1):
            resposta = cliente.get(URL, params={"page": pagina, "take": POR_PAGINA, "title": termo, "locations": ""})
            resposta.raise_for_status()
            dados = resposta.json()
            vagas.extend(parse(dados))
            if pagina >= dados.get("totalPages", 0):
                break
    return vagas
