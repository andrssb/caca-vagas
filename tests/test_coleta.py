import sqlite3
from datetime import date
from pathlib import Path

from caca_vagas.coleta import Resumo, sem_repetidas, sql_de
from caca_vagas.modelo import Vaga

ESQUEMA = (Path(__file__).parent.parent / "web" / "schema.sql").read_text(encoding="utf-8")
HOJE = date(2026, 10, 19)


def vaga(id_externo="1", fonte="gupy", **campos):
    base = dict(fonte=fonte, id_externo=id_externo, titulo="Desenvolvedor Júnior", empresa="Empresa", url="https://x")
    return Vaga(**(base | campos))


def banco():
    conexao = sqlite3.connect(":memory:")
    conexao.row_factory = sqlite3.Row
    conexao.executescript(ESQUEMA)
    return conexao


def test_sql_roda_no_esquema_do_site_e_escapa_aspas():
    resumo = Resumo(vagas=[vaga(titulo="Dev d'Ávila; DROP TABLE vagas", niveis=["junior", "pleno"], tecnologias=["Python"])])
    resumo.coletadas["gupy"] = 1
    conexao = banco()
    conexao.executescript(sql_de(resumo, HOJE))
    linha = conexao.execute("SELECT * FROM vagas").fetchone()
    assert linha["titulo"] == "Dev d'Ávila; DROP TABLE vagas"
    assert linha["niveis"] == ",junior,pleno,"
    assert linha["tecnologias"] == '["Python"]'
    assert linha["ativa"] == 1


def test_vaga_que_sumiu_sai_do_ar_so_se_a_fonte_funcionou():
    conexao = banco()
    ontem = Resumo(vagas=[vaga("1", "gupy"), vaga("2", "solides", titulo="Dev Pleno")])
    ontem.coletadas.update({"gupy": 1, "solides": 1})
    conexao.executescript(sql_de(ontem, date(2026, 10, 18)))

    # Hoje a Gupy funcionou e não trouxe a vaga 1; a Sólides falhou.
    hoje = Resumo(vagas=[])
    hoje.coletadas.update({"gupy": 0, "solides": 0})
    hoje.erros["solides"] = "HTTPError: 503"
    conexao.executescript(sql_de(hoje, HOJE))

    ativas = {l["chave"]: l["ativa"] for l in conexao.execute("SELECT chave, ativa FROM vagas")}
    assert ativas == {"gupy:1": 0, "solides:2": 1}
    assert conexao.execute("SELECT COUNT(*) FROM coletas").fetchone()[0] == 2


def test_vaga_que_volta_e_reativada():
    conexao = banco()
    for dia in (date(2026, 10, 17), date(2026, 10, 18), HOJE):
        resumo = Resumo(vagas=[] if dia.day == 18 else [vaga()])
        resumo.coletadas["gupy"] = len(resumo.vagas)
        conexao.executescript(sql_de(resumo, dia))
    assert conexao.execute("SELECT ativa FROM vagas").fetchone()[0] == 1


def test_sem_repetidas_entre_termos_e_portais():
    vagas = [
        vaga("1", "gupy"),
        vaga("1", "gupy"),  # mesmo id em dois termos
        vaga("9", "infojobs"),  # mesma vaga em outro portal
        vaga("2", "gupy", cidade="Recife"),  # mesmo título, outra cidade: é outra vaga
    ]
    assert [v.chave for v in sem_repetidas(vagas)] == ["gupy:1", "gupy:2"]
