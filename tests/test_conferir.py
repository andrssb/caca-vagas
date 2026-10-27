import json
from datetime import date, timedelta

from caca_vagas.conferir import analisar

HOJE = date(2026, 10, 27)


def coleta(dias_atras, ok=None, erros=None):
    """ok: {fonte: vagas}. A lista final vai da mais nova para a mais antiga, como sai do banco."""
    ok = ok or {}
    return {"em": (HOJE - timedelta(days=dias_atras)).isoformat(), "fontes_ok": ",".join(ok),
            "erros": json.dumps(erros or {}), "por_fonte": json.dumps(ok)}


def historico(fonte, contagens):
    return [coleta(i, {fonte: n}) for i, n in enumerate(contagens)]


def test_fonte_estavel_nao_reclama():
    rel = analisar(historico("gupy", [1100, 1120, 1090, 1130, 1105]), HOJE, ["gupy"])
    assert rel.problemas == [] and rel.avisos == []


def test_queda_para_menos_da_metade_e_problema():
    rel = analisar(historico("gupy", [300, 1120, 1090, 1130, 1105]), HOJE, ["gupy"])
    assert rel.problemas == ["gupy: trouxe 300 vagas, a mediana das últimas coletas é 1112"]


def test_portal_que_mudou_e_volta_zero_e_problema():
    rel = analisar(historico("solides", [0, 299, 310, 305]), HOJE, ["solides"])
    assert len(rel.problemas) == 1 and "trouxe 0 vagas" in rel.problemas[0]


def test_fonte_pequena_nao_dispara_pela_mediana():
    rel = analisar(historico("programathor", [3, 8, 9, 7, 8]), HOJE, ["programathor"])
    assert rel.problemas == []


def test_uma_falha_e_aviso_duas_seguidas_e_problema():
    uma = [coleta(0, erros={"gupy": "HTTPError: 503"})] + historico("gupy", [1100, 1120, 1090])[1:]
    rel = analisar(uma, HOJE, ["gupy"])
    assert rel.problemas == [] and rel.avisos == ["gupy: falhou na coleta de 2026-10-27 (HTTPError: 503)"]

    duas = [coleta(0, erros={"gupy": "HTTPError: 503"}), coleta(1, erros={"gupy": "HTTPError: 503"}), coleta(2, {"gupy": 1100})]
    rel = analisar(duas, HOJE, ["gupy"])
    assert rel.problemas == ["gupy: falhou nas duas últimas coletas (HTTPError: 503)"]


def test_fonte_que_parou_de_rodar_e_problema():
    # O Programathor depende do PC ligado: se a tarefa local para de rodar, não sobra nem erro registrado.
    coletas = [coleta(0, {"gupy": 1100}), coleta(1, {"gupy": 1100}), coleta(3, {"programathor": 25})]
    rel = analisar(coletas, HOJE, ["programathor"])
    assert rel.problemas == ["programathor: sem coleta que funcionou desde 2026-10-24"]


def test_coletas_antigas_sem_por_fonte_nao_quebram():
    antigas = [{"em": "2026-10-26", "fontes_ok": "gupy", "erros": "{}", "por_fonte": None}]
    rel = analisar([coleta(0, {"gupy": 1100})] + antigas, HOJE, ["gupy"])
    assert rel.problemas == []
