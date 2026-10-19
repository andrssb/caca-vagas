"""Painel local: a lista ranqueada, com o link da vaga e os botões Candidatei e Descartar."""

import threading
from contextlib import closing
from datetime import date
from html import escape

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from . import banco, coleta, perfil

app = FastAPI(title="Caça Vagas")
_coleta = {"rodando": False, "ultimo": ""}

ABAS = {"nova": "Para candidatar", "candidatei": "Candidatei", "descartada": "Descartadas"}
MODALIDADES = {"remoto": "Remoto", "hibrido": "Híbrido", "presencial": "Presencial", "": "Modalidade não informada"}

ESTILO = """
:root { --fundo:#f6f7f9; --cartao:#fff; --texto:#1c1f26; --suave:#5a6172; --borda:#e2e5ea; --cor:#1f4fe0; --ok:#1a7f4b; }
@media (prefers-color-scheme: dark) {
  :root { --fundo:#121318; --cartao:#1b1d24; --texto:#e8eaf0; --suave:#9aa1b0; --borda:#2c2f38; --cor:#6d93ff; --ok:#4cc38a; }
}
* { box-sizing:border-box; }
body { margin:0; font-family:"Segoe UI",Arial,sans-serif; background:var(--fundo); color:var(--texto); }
main { max-width:980px; margin:0 auto; padding:24px 16px 48px; }
header { display:flex; flex-wrap:wrap; gap:12px; align-items:center; justify-content:space-between; }
h1 { margin:0; font-size:22px; }
nav { display:flex; gap:6px; margin:18px 0; flex-wrap:wrap; }
nav a { padding:7px 12px; border-radius:8px; text-decoration:none; color:var(--suave); border:1px solid var(--borda); }
nav a.ativa { background:var(--cor); color:#fff; border-color:var(--cor); }
.vaga { background:var(--cartao); border:1px solid var(--borda); border-radius:10px; padding:14px 16px; margin-bottom:10px;
        display:grid; grid-template-columns:52px minmax(0,1fr) auto; gap:14px; align-items:center; }
.nota { font-size:20px; font-weight:700; color:var(--cor); text-align:center; }
.titulo { font-weight:600; color:var(--texto); text-decoration:none; }
.titulo:hover { color:var(--cor); text-decoration:underline; }
.meta, .hab, .aviso { font-size:13px; color:var(--suave); margin-top:3px; }
.hab b { color:var(--ok); font-weight:600; }
.acoes { display:flex; gap:6px; }
button { font:inherit; font-size:13px; padding:7px 11px; border-radius:8px; border:1px solid var(--borda);
         background:var(--cartao); color:var(--texto); cursor:pointer; }
button.principal { background:var(--cor); border-color:var(--cor); color:#fff; }
.vazio { color:var(--suave); padding:30px 0; }
.status { font-size:13px; color:var(--suave); }
@media (max-width:640px) {
  .vaga { grid-template-columns:44px minmax(0,1fr); }
  .acoes { grid-column:1 / -1; }
}
"""


def _data_br(iso: str | None) -> str:
    return date.fromisoformat(iso).strftime("%d/%m") if iso else ""


def _cartao(v, aba: str) -> str:
    local = MODALIDADES.get(v["modalidade"], v["modalidade"])
    if v["cidade"]:
        local += f" · {v['cidade']}" + (f"/{v['uf']}" if v["uf"] else "")
    partes = [escape(v["empresa"] or "Empresa não informada"), escape(local)]
    if v["contrato"]:
        partes.append(escape(v["contrato"]))
    if v["salario"]:
        partes.append(escape(v["salario"]))
    if v["publicada_em"]:
        partes.append("publicada " + _data_br(v["publicada_em"]))
    if v["prazo"]:
        partes.append("<b>inscrição até " + _data_br(v["prazo"]) + "</b>")
    partes.append(escape(v["fonte"]))

    habilidades = f'<div class="hab">Bate com: <b>{escape(v["habilidades"])}</b></div>' if v["habilidades"] else ""
    avisos = f'<div class="aviso">{escape(v["avisos"])}</div>' if v["avisos"] else ""

    def botao(status: str, rotulo: str, classe: str = "") -> str:
        return (f'<form method="post" action="/marcar"><input type="hidden" name="chave" value="{escape(v["chave"])}">'
                f'<input type="hidden" name="status" value="{status}"><input type="hidden" name="aba" value="{aba}">'
                f'<button class="{classe}">{rotulo}</button></form>')

    if aba == "nova":
        acoes = botao("candidatei", "Candidatei", "principal") + botao("descartada", "Descartar")
    else:
        acoes = botao("nova", "Voltar para a lista")

    return f"""
    <div class="vaga">
      <div class="nota" title="nota de encaixe">{v["nota"]}</div>
      <div>
        <a class="titulo" href="{escape(v["url"])}" target="_blank" rel="noopener">{escape(v["titulo"])}</a>
        <div class="meta">{" · ".join(partes)}</div>
        {habilidades}{avisos}
      </div>
      <div class="acoes">{acoes}</div>
    </div>"""


@app.get("/", response_class=HTMLResponse)
def inicio(aba: str = "nova") -> str:
    aba = aba if aba in ABAS else "nova"
    with closing(banco.conectar()) as conexao:
        vagas = banco.listar(conexao, aba)
        totais = banco.contagem(conexao)
    abas = "".join(
        f'<a href="/?aba={chave}" class="{"ativa" if chave == aba else ""}">{rotulo} ({len(vagas) if chave == aba else totais[chave]})</a>'
        for chave, rotulo in ABAS.items()
    )
    lista = "".join(_cartao(v, aba) for v in vagas) or '<p class="vazio">Nenhuma vaga aqui.</p>'
    estado = "Coletando agora, atualize em alguns minutos." if _coleta["rodando"] else escape(_coleta["ultimo"])
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Caça Vagas</title><style>{ESTILO}</style></head>
<body><main>
  <header>
    <h1>Caça Vagas</h1>
    <form method="post" action="/coletar"><span class="status">{estado}</span>
      <button class="principal" {"disabled" if _coleta["rodando"] else ""}>Coletar agora</button></form>
  </header>
  <nav>{abas}</nav>
  {lista}
</main></body></html>"""


@app.post("/marcar")
def marcar(chave: str = Form(...), status: str = Form(...), aba: str = Form("nova")) -> RedirectResponse:
    with closing(banco.conectar()) as conexao:
        banco.marcar(conexao, chave, status)
    return RedirectResponse(f"/?aba={aba}", status_code=303)


def _coletar_em_segundo_plano() -> None:
    try:
        resumo = coleta.rodar(perfil.carregar(), log=lambda _msg: None)
        _coleta["ultimo"] = f"Última coleta: {sum(resumo.aceitas.values())} vagas no perfil, {resumo.novas} novas."
        if resumo.erros:
            _coleta["ultimo"] += " Falhou: " + ", ".join(resumo.erros)
    except Exception as erro:
        _coleta["ultimo"] = f"A coleta falhou: {erro}"
    finally:
        _coleta["rodando"] = False


@app.post("/coletar")
def coletar() -> RedirectResponse:
    if not _coleta["rodando"]:
        _coleta["rodando"] = True
        threading.Thread(target=_coletar_em_segundo_plano, daemon=True).start()
    return RedirectResponse("/", status_code=303)
