"""E-mail diário do alerta: para cada alerta confirmado, as vagas que a coleta viu pela primeira vez
desde o último envio e que batem com os filtros salvos.

Roda no GitHub Actions logo depois da coleta. A busca é a mesma do site (GET /api/vagas com os
filtros e `desde`), então o e-mail mostra exatamente o que a pessoa veria na lista.
"""

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from urllib.parse import parse_qs, urlencode

import httpx

from .coleta import agora_utc

SITE = os.environ.get("CACA_VAGAS_SITE", "https://caca-vagas.pages.dev")
BANCO_ID = "860b0c40-6e57-4bf4-8057-4c5ea08cc27d"
NO_EMAIL = 10

NIVEIS = {"estagio": "Estágio", "junior": "Júnior", "pleno": "Pleno", "senior": "Sênior"}
MODALIDADES = {"remoto": "Remoto", "hibrido": "Híbrido", "presencial": "Presencial"}
ROTULOS = {**NIVEIS, **MODALIDADES, "nao": "não informado", "outros": "outros contratos"}


@dataclass
class Alerta:
    usuario_id: int
    email: str
    filtros: str
    token: str
    ultimo_envio: str


def d1(sql: str, params: list | None = None) -> list[dict]:
    conta = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    resposta = httpx.post(
        f"https://api.cloudflare.com/client/v4/accounts/{conta}/d1/database/{BANCO_ID}/query",
        headers={"Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}"},
        json={"sql": sql, "params": params or []},
        timeout=30,
    )
    resposta.raise_for_status()
    return resposta.json()["result"][0]["results"]


def alertas_confirmados() -> list[Alerta]:
    linhas = d1(
        "SELECT a.usuario_id, u.email, a.filtros, a.token, a.ultimo_envio FROM alertas a "
        "JOIN usuarios u ON u.id = a.usuario_id WHERE a.confirmado = 1"
    )
    return [Alerta(**linha) for linha in linhas]


def descrever(filtros: str) -> str:
    """Mesmo texto do site (descreverFiltros em web/src/alertas.ts)."""
    p = {k: v[0] for k, v in parse_qs(filtros).items()}
    partes = []
    for nome in ("nivel", "modalidade", "contrato", "area"):
        if p.get(nome):
            partes.append(" ou ".join(ROTULOS.get(v, v) for v in p[nome].split(",")))
    if p.get("uf"):
        partes.append(p["uf"] + (" ou remoto" if p.get("incluir_remoto") == "1" else ""))
    if p.get("q"):
        partes.append(f'"{p["q"]}"')
    if p.get("tec"):
        partes.append("suas tecnologias: " + ", ".join(p["tec"].split(",")))
    return " · ".join(partes) or "todas as vagas de TI"


def vagas_novas(cliente: httpx.Client, alerta: Alerta) -> dict:
    resposta = cliente.get(f"{SITE}/api/vagas?{alerta.filtros}&{urlencode({'desde': alerta.ultimo_envio})}")
    resposta.raise_for_status()
    return resposta.json()


def _linha_vaga(vaga: dict) -> tuple[str, str]:
    local = " / ".join(p for p in (vaga["cidade"], vaga["uf"]) if p)
    detalhes = [vaga["empresa"] or "Empresa não informada", local,
                ", ".join(NIVEIS.get(n, n) for n in vaga["niveis"]), MODALIDADES.get(vaga["modalidade"], "")]
    if vaga.get("nota") is not None:
        detalhes.append(f"{vaga['nota']}% de encaixe")
    return vaga["titulo"], " · ".join(d for d in detalhes if d)


def montar_email(alerta: Alerta, resultado: dict, remetente: str) -> EmailMessage:
    total = resultado["total"]
    vagas = resultado["vagas"][:NO_EMAIL]
    resumo = descrever(alerta.filtros)
    ver_todas = f"{SITE}/?{alerta.filtros}&ordem=recentes"
    cancelar = f"{SITE}/alerta?cancelar={alerta.token}"
    titulo = f"{total} vaga nova" if total == 1 else f"{total} vagas novas"

    texto = [f"{titulo} com os seus filtros ({resumo}):", ""]
    for vaga in vagas:
        nome, detalhes = _linha_vaga(vaga)
        texto += [nome, detalhes, vaga["url"], ""]
    if total > len(vagas):
        texto.append(f"E mais {total - len(vagas)} no site: {ver_todas}")
    texto += ["", "Você recebe este e-mail porque criou um alerta no Caça Vagas.", f"Cancelar o alerta: {cancelar}"]

    itens = []
    for vaga in vagas:
        nome, detalhes = _linha_vaga(vaga)
        itens.append(
            f'<li style="margin:0 0 14px"><a href="{escape(vaga["url"])}" style="color:#1f4fe0;font-weight:bold;text-decoration:none">'
            f'{escape(nome)}</a><br><span style="color:#4a5263;font-size:13px">{escape(detalhes)}</span></li>'
        )
    mais = (f'<p><a href="{escape(ver_todas)}" style="color:#1f4fe0">Ver as outras {total - len(vagas)} no site</a></p>'
            if total > len(vagas) else "")
    html = f"""<div style="font:15px/1.5 Arial,sans-serif;color:#14171f;max-width:560px">
<p style="font-size:18px;font-weight:bold;margin:0 0 4px">{escape(titulo)}</p>
<p style="color:#4a5263;margin:0 0 18px">Filtros do alerta: {escape(resumo)}</p>
<ol style="padding-left:18px;margin:0">{''.join(itens)}</ol>
{mais}
<p style="color:#6b7385;font-size:12px;margin-top:24px">Você recebe este e-mail porque criou um alerta no
<a href="{SITE}" style="color:#6b7385">Caça Vagas</a>. Para trocar os filtros, crie o alerta de novo no site.
<a href="{escape(cancelar)}" style="color:#6b7385">Cancelar o alerta</a>.</p>
</div>"""

    msg = EmailMessage()
    msg["From"] = formataddr(("Caça Vagas", remetente))
    msg["To"] = alerta.email
    msg["Subject"] = f"{titulo} no Caça Vagas"
    msg["List-Unsubscribe"] = f"<{cancelar}>"
    msg.set_content("\n".join(texto))
    msg.add_alternative(html, subtype="html")
    return msg


def enviar_todos(simular: bool = False, log=print) -> int:
    """Devolve quantos alertas falharam. Um erro num alerta não impede os outros."""
    inicio = agora_utc()
    alertas = alertas_confirmados()
    log(f"{len(alertas)} alertas confirmados")
    remetente = os.environ.get("SMTP_USUARIO", "")
    falhas = 0
    smtp = None
    with httpx.Client(timeout=30) as cliente:
        try:
            for alerta in alertas:
                try:
                    resultado = vagas_novas(cliente, alerta)
                    if resultado["total"]:
                        msg = montar_email(alerta, resultado, remetente)
                        if simular:
                            log(f"  [simulado] {alerta.email}: {msg['Subject']}")
                        else:
                            if smtp is None:
                                smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30)
                                smtp.login(remetente, os.environ["SMTP_SENHA"])
                            smtp.send_message(msg)
                            log(f"  enviado para o alerta {alerta.usuario_id}: {resultado['total']} vagas")
                    # Sem vaga nova também avança: amanhã conta a partir de agora.
                    if not simular:
                        d1("UPDATE alertas SET ultimo_envio = ? WHERE usuario_id = ?", [inicio, alerta.usuario_id])
                except Exception as erro:
                    falhas += 1
                    log(f"  FALHOU o alerta {alerta.usuario_id}: {type(erro).__name__}: {erro}")
        finally:
            if smtp is not None:
                smtp.quit()
    return falhas
