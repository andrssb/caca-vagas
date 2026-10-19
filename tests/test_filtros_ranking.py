from datetime import date

import pytest

from caca_vagas import filtros, ranking
from caca_vagas.modelo import Vaga
from caca_vagas.perfil import carregar

HOJE = date(2026, 10, 19)


@pytest.fixture(scope="module")
def perfil():
    return carregar()


def vaga(**campos):
    base = dict(fonte="teste", id_externo="1", titulo="Desenvolvedor Júnior", empresa="Empresa", url="https://x",
                modalidade="remoto", contrato="CLT", publicada_em=HOJE)
    return Vaga(**(base | campos))


def motivo(v, perfil):
    return filtros.avaliar(v, perfil, HOJE).motivo


def test_aceita_junior_remoto_clt(perfil):
    avaliacao = filtros.avaliar(vaga(), perfil, HOJE)
    assert avaliacao.aceita and avaliacao.junior_explicito


@pytest.mark.parametrize("titulo", ["Analista de PCP Júnior - Programação", "Analista de Atendimento Júnior"])
def test_recusa_fora_da_area(perfil, titulo):
    assert motivo(vaga(titulo=titulo), perfil) == "fora da área de TI"


@pytest.mark.parametrize("titulo", ["Desenvolvedor Pleno", "Desenvolvedor Sr", "Dev Back End II", "Desenvolvedor Tech Lead"])
def test_recusa_nivel_acima(perfil, titulo):
    assert motivo(vaga(titulo=titulo), perfil) == "nível acima de júnior"


@pytest.mark.parametrize("titulo", ["Desenvolvedor Júnior/Pleno", "Desenvolvedor Back End I", "Dev Jr"])
def test_junior_explicito_vence(perfil, titulo):
    assert filtros.avaliar(vaga(titulo=titulo), perfil, HOJE).junior_explicito


def test_pl_sql_nao_e_pleno(perfil):
    assert filtros.avaliar(vaga(titulo="Desenvolvedor PL/SQL Júnior"), perfil, HOJE).aceita


def test_estagio_recusado_mas_senioridade_mista_passa(perfil):
    assert motivo(vaga(titulo="Estágio em Desenvolvimento de Software"), perfil) == "estágio ou aprendiz"
    assert filtros.avaliar(vaga(titulo="Desenvolvedor Front End", senioridade="Junior / Estagiário"), perfil, HOJE).aceita


def test_presencial_so_na_regiao_de_bh(perfil):
    assert filtros.avaliar(vaga(modalidade="presencial", cidade="Contagem"), perfil, HOJE).aceita
    assert motivo(vaga(modalidade="hibrido", cidade="São Paulo"), perfil).startswith("hibrido fora de BH")


def test_vaga_afirmativa_passa_com_aviso(perfil):
    avaliacao = filtros.avaliar(vaga(titulo="Desenvolvedora Júnior (Vaga afirmativa para Mulheres)"), perfil, HOJE)
    assert avaliacao.aceita
    assert any("afirmativa" in a for a in avaliacao.avisos)


def test_contrato(perfil):
    assert motivo(vaga(contrato="Cooperado"), perfil) == "contrato Cooperado"
    assert filtros.avaliar(vaga(contrato="PJ"), perfil, HOJE).aceita
    assert filtros.avaliar(vaga(contrato="CLT / PJ"), perfil, HOJE).aceita
    assert "contrato não informado" in filtros.avaliar(vaga(contrato=""), perfil, HOJE).avisos


def test_prazo_vale_mais_que_data_de_publicacao(perfil):
    antiga = date(2026, 8, 1)
    assert motivo(vaga(publicada_em=antiga), perfil).startswith("publicada há mais de")
    assert filtros.avaliar(vaga(publicada_em=antiga, prazo=date(2026, 10, 30)), perfil, HOJE).aceita
    assert motivo(vaga(prazo=date(2026, 10, 18)), perfil) == "inscrições encerradas"


def test_nota_sobe_com_habilidades_do_perfil(perfil):
    simples = vaga(descricao="Vaga para trabalhar com Delphi.")
    alinhada = vaga(descricao="Stack: JavaScript, TypeScript, Node.js, React e PostgreSQL, integrações via API REST.")
    nota_simples = ranking.pontuar(simples, filtros.avaliar(simples, perfil, HOJE), perfil, HOJE)
    nota_alinhada = ranking.pontuar(alinhada, filtros.avaliar(alinhada, perfil, HOJE), perfil, HOJE)
    assert nota_alinhada.valor > nota_simples.valor
    assert {"javascript", "node.js", "react", "postgresql", "api rest"} <= set(nota_alinhada.habilidades)


def test_java_nao_casa_com_javascript(perfil):
    v = vaga(descricao="Experiência com JavaScript.")
    habilidades = ranking.pontuar(v, filtros.avaliar(v, perfil, HOJE), perfil, HOJE).habilidades
    assert "javascript" in habilidades and "java" not in habilidades


def test_nota_nunca_passa_de_100(perfil):
    v = vaga(descricao=" ".join(h.nome for h in perfil.habilidades))
    assert ranking.pontuar(v, filtros.avaliar(v, perfil, HOJE), perfil, HOJE).valor <= 100
