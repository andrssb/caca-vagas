import pytest

from caca_vagas import banco
from caca_vagas.modelo import Vaga


def vaga(titulo="Desenvolvedor Júnior"):
    return Vaga(fonte="teste", id_externo="1", titulo=titulo, empresa="Empresa", url="https://x")


def test_coletar_de_novo_nao_apaga_o_status():
    conexao = banco.conectar(":memory:")
    assert banco.salvar(conexao, vaga(), 50, ["python"], []) is True
    banco.marcar(conexao, "teste:1", "descartada")

    # Mesma vaga numa coleta seguinte, com título e nota atualizados.
    assert banco.salvar(conexao, vaga("Desenvolvedor Júnior (remoto)"), 70, ["python"], []) is False

    linha = conexao.execute("SELECT * FROM vagas WHERE chave = 'teste:1'").fetchone()
    assert linha["status"] == "descartada"
    assert linha["titulo"] == "Desenvolvedor Júnior (remoto)"
    assert linha["nota"] == 70
    assert banco.listar(conexao, "nova") == []
    assert len(banco.listar(conexao, "descartada")) == 1


def test_lista_ordenada_pela_nota():
    conexao = banco.conectar(":memory:")
    for i, nota in enumerate([30, 90, 60]):
        banco.salvar(conexao, Vaga(fonte="teste", id_externo=str(i), titulo="Dev Jr", empresa="E", url="u"), nota, [], [])
    assert [l["nota"] for l in banco.listar(conexao)] == [90, 60, 30]


def test_status_invalido():
    conexao = banco.conectar(":memory:")
    with pytest.raises(ValueError):
        banco.marcar(conexao, "teste:1", "aprovado")
