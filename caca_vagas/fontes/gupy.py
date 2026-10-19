"""Gupy: a busca do portal (portal.gupy.io) lê uma API JSON pública."""

from datetime import date

import httpx

from ..modelo import Vaga

URL = "https://portal.gupy.io/api/job-search/jobs"
POR_PAGINA = 100
MAX_POR_TERMO = 1000

CONTRATOS = {
    "vacancy_type_effective": "CLT",
    "vacancy_legal_entity": "PJ",
    "vacancy_type_internship": "Estágio",
    "vacancy_type_apprentice": "Aprendiz",
    "vacancy_type_temporary": "Temporário",
    "vacancy_type_talent_pool": "Banco de talentos",
    "vacancy_type_associate": "Cooperado",
    "vacancy_type_outsource": "Terceirizado",
    "vacancy_type_freelancer": "Freelancer",
    "vacancy_type_autonomous": "Autônomo",
    "vacancy_type_lecturer": "Docente",
    "vacancy_type_summer": "Temporário",
    "vacancy_type_trainee": "Trainee",
}

MODALIDADES = {"remote": "remoto", "hybrid": "hibrido", "on-site": "presencial"}


def _data(iso: str | None) -> date | None:
    if not iso:
        return None
    try:
        return date.fromisoformat(iso[:10])
    except ValueError:
        return None


def parse(dados: dict) -> list[Vaga]:
    vagas = []
    for item in dados.get("data", []):
        vagas.append(
            Vaga(
                fonte="gupy",
                id_externo=str(item["id"]),
                titulo=item.get("name", "").strip(),
                empresa=item.get("careerPageName", "").strip(),
                url=item.get("jobUrl", ""),
                cidade=item.get("city") or "",
                uf=item.get("state") or "",
                modalidade=MODALIDADES.get(item.get("workplaceType", ""), ""),
                contrato=CONTRATOS.get(item.get("type", ""), ""),
                descricao=item.get("description", ""),
                publicada_em=_data(item.get("publishedDate")),
                prazo=_data(item.get("applicationDeadline")),
            )
        )
    return vagas


def coletar(cliente: httpx.Client, termos: list[str]) -> list[Vaga]:
    vagas = []
    for termo in termos:
        offset = 0
        while True:
            resposta = cliente.get(URL, params={"jobName": termo, "limit": POR_PAGINA, "offset": offset})
            resposta.raise_for_status()
            dados = resposta.json()
            pagina = parse(dados)
            vagas.extend(pagina)
            offset += POR_PAGINA
            # O "total" da resposta acompanha a página, não a busca: o fim é a página incompleta.
            if len(pagina) < POR_PAGINA or offset >= MAX_POR_TERMO:
                break
    return vagas
