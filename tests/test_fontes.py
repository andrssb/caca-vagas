"""Parse de cada portal sobre respostas reais gravadas em tests/amostras (sem rede)."""

import json
from datetime import date
from pathlib import Path

from caca_vagas.fontes import gupy, infojobs, programathor, solides

AMOSTRAS = Path(__file__).parent / "amostras"


def _json(nome):
    return json.loads((AMOSTRAS / nome).read_text(encoding="utf-8"))


def _html(nome):
    return (AMOSTRAS / nome).read_text(encoding="utf-8")


def test_gupy_traduz_contrato_modalidade_e_datas():
    vagas = gupy.parse(_json("gupy.json"))
    zenvia = next(v for v in vagas if v.empresa == "Zenvia Jobs")
    assert zenvia.contrato == "CLT"
    assert zenvia.modalidade == "remoto"
    assert zenvia.publicada_em == date(2026, 10, 15)
    assert zenvia.prazo == date(2026, 10, 22)
    assert zenvia.url.startswith("https://zenvia.gupy.io/job/")
    assert zenvia.chave == "gupy:12542291"


def test_solides_monta_url_e_le_senioridade():
    vagas = solides.parse(_json("solides.json"))
    primeira = vagas[0]
    assert primeira.url == f"https://vagas.solides.com.br/vaga/{primeira.id_externo}"
    assert primeira.senioridade == "Junior"
    assert primeira.contrato == "CLT"
    assert (primeira.cidade, primeira.uf) == ("São Paulo", "SP")


def test_programathor_ignora_vaga_vencida():
    vagas = programathor.parse(_html("programathor.html"))
    # A amostra tem 2 vagas ativas e 1 vencida.
    assert len(vagas) == 2
    assert all("Vencida" not in v.titulo for v in vagas)


def test_programathor_le_icones_e_tags():
    omni = next(v for v in programathor.parse(_html("programathor.html")) if v.empresa == "Omni Saúde")
    assert omni.modalidade == "hibrido"
    assert omni.contrato == "PJ"
    assert omni.senioridade == "Júnior"
    assert omni.cidade == "São Paulo, São Paulo, Brasil"
    assert "Node.js" in omni.tags


def test_infojobs_separa_cidade_uf_e_le_data_escondida():
    vagas = infojobs.parse(_html("infojobs.html"))
    primeira = vagas[0]
    assert (primeira.cidade, primeira.uf) == ("Sorocaba", "SP")
    assert primeira.modalidade == "presencial"
    assert primeira.salario == "R$ 2.500,00"
    assert primeira.publicada_em == date(2026, 9, 16)
    # O InfoJobs não tem campo de contrato: vem do título ("Desenvolvedor Junior - CLT").
    assert primeira.contrato == "CLT"
