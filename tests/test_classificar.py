from datetime import date

import pytest

from caca_vagas.classificar import area_de, classificar, niveis_de
from caca_vagas.localidade import normalizar_local
from caca_vagas.modelo import Vaga

HOJE = date(2026, 10, 19)


def vaga(**campos):
    base = dict(fonte="teste", id_externo="1", titulo="Desenvolvedor Júnior", empresa="Empresa", url="https://x",
                publicada_em=HOJE)
    return Vaga(**(base | campos))


@pytest.mark.parametrize("titulo, area", [
    ("Pessoa Desenvolvedora Fullstack Júnior", "Desenvolvimento"),
    ("Analista de Sistemas Pleno", "Desenvolvimento"),
    ("Engenheiro(a) de Dados Sênior", "Dados"),
    ("Analista de BI", "Dados"),
    ("Analista de QA Jr", "QA e Testes"),
    ("Analista DevOps", "Infra e DevOps"),
    ("Analista de Suporte Técnico N2", "Suporte"),
    ("Analista de PCP Júnior - Programação", ""),
    ("Programador CNC", ""),
    ("Desenvolvedor de Negócios", ""),
    ("Analista de Atendimento Júnior - Programa Suporte ao Paciente", ""),
    ("Programador de PLC / Automação Industrial", ""),
    ("Analista de Suporte Administrativo e Predial", ""),
    ("Analista de Suporte de TI", "Suporte"),
])
def test_area(titulo, area):
    assert area_de(titulo) == area


@pytest.mark.parametrize("titulo, senioridade, niveis", [
    ("Desenvolvedor Júnior", "", ["junior"]),
    ("Desenvolvedor Jr/Pl", "", ["junior", "pleno"]),
    ("Desenvolvedor Back End I", "", ["junior"]),
    ("Pessoa Desenvolvedora Backend Python Especialista I - V", "", ["senior"]),
    ("Dev Back End II", "", ["pleno"]),
    ("Desenvolvedor Sr.", "", ["senior"]),
    ("Tech Lead Java", "", ["senior"]),
    ("Estágio em Desenvolvimento", "", ["estagio"]),
    ("Desenvolvedor PL/SQL", "", []),
    ("Desenvolvedor Python", "Pleno", ["pleno"]),
])
def test_niveis(titulo, senioridade, niveis):
    assert niveis_de(titulo, senioridade) == niveis


@pytest.mark.parametrize("cidade, uf, esperado", [
    ("São Paulo", "São Paulo", ("São Paulo", "SP")),
    ("Belo Horizonte", "Minas Gerais", ("Belo Horizonte", "MG")),
    ("São Paulo, São Paulo, Brasil", "", ("São Paulo", "SP")),
    ("Mato Grosso - Cuiabá", "", ("Cuiabá", "MT")),
    ("Belo Horizonte/MG", "", ("Belo Horizonte", "MG")),
    ("Todo Brasil", "", ("", "")),
    ("BELO HORIZONTE", "MG", ("Belo Horizonte", "MG")),
])
def test_local(cidade, uf, esperado):
    assert normalizar_local(cidade, uf) == esperado


def test_classificar_preenche_campos():
    v = vaga(titulo="Desenvolvedor Full Stack Pleno", descricao="Node.js, React, PostgreSQL e Docker. Não é Java.",
             cidade="Belo Horizonte", uf="Minas Gerais")
    assert classificar(v, HOJE).aceita
    assert v.area == "Desenvolvimento"
    assert v.niveis == ["pleno"]
    assert {"Node.js", "React", "PostgreSQL", "Docker", "Java"} <= set(v.tecnologias)
    assert "JavaScript" not in v.tecnologias
    assert (v.cidade, v.uf) == ("Belo Horizonte", "MG")


@pytest.mark.parametrize("titulo,empresa,url", [
    ("[Modelo] - Pessoa Desenvolvedora Fullstack - TESTE CONVOCAÇÂO", "VAGAS TESTES BONDY", "https://bondy-demo.gupy.io/job/x"),
    ("Analista De Suporte Atendimento Logístico I", "VAGAS TESTES BONDY", "https://bondy-demo.gupy.io/job/y"),
])
def test_vaga_de_teste_do_portal_e_recusada(titulo, empresa, url):
    assert not classificar(vaga(titulo=titulo, empresa=empresa, url=url), HOJE).aceita


def test_testes_no_titulo_nao_e_vaga_de_teste():
    v = vaga(titulo="Analista de Testes de Intrusão (Pentest)", empresa="Logiks", url="https://vagas.solides.com.br/vaga/a")
    assert classificar(v, HOJE).aceita


def test_java_e_javascript_sao_diferentes():
    v = vaga(descricao="Experiência com JavaScript.")
    classificar(v, HOJE)
    assert "JavaScript" in v.tecnologias and "Java" not in v.tecnologias


def test_react_native_nao_conta_como_react():
    v = vaga(descricao="App em React Native.")
    classificar(v, HOJE)
    assert v.tecnologias == ["React Native"]


def test_contrato_de_estagio_vira_nivel():
    v = vaga(titulo="Desenvolvedor Front End", contrato="Estágio")
    classificar(v, HOJE)
    assert v.niveis == ["estagio"]


@pytest.mark.parametrize("campos, motivo", [
    (dict(titulo="Analista de PCP"), "fora da área de TI"),
    (dict(titulo="Programador Jovem Aprendiz"), "programa de aprendiz"),
    (dict(prazo=date(2026, 10, 18)), "inscrições encerradas"),
    (dict(publicada_em=date(2026, 8, 1)), "publicada há muito tempo"),
])
def test_recusas(campos, motivo):
    assert classificar(vaga(**campos), HOJE).motivo == motivo


def test_prazo_vale_mais_que_data_de_publicacao():
    assert classificar(vaga(publicada_em=date(2026, 8, 1), prazo=date(2026, 10, 30)), HOJE).aceita
