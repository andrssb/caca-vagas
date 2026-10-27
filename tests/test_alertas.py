from caca_vagas.alertas import Alerta, descrever, montar_email


def vaga(n, **campos):
    base = dict(titulo=f"Dev Júnior {n}", empresa="Empresa", cidade="Recife", uf="PE", niveis=["junior"],
                modalidade="remoto", url=f"https://x/{n}", nota=None)
    return base | campos


ALERTA = Alerta(usuario_id=1, email="pessoa@x.com", filtros="nivel=junior&modalidade=remoto&tec=Python%2CSQL",
                token="tok_123456789012345678901", ultimo_envio="2026-10-27T10:00:00Z")


def test_descrever_igual_ao_site():
    assert descrever("nivel=junior%2Cpleno&uf=MG&incluir_remoto=1&q=react") == 'Júnior ou Pleno · MG ou remoto · "react"'
    assert descrever("") == "todas as vagas de TI"


def test_email_mostra_dez_e_aponta_o_resto():
    resultado = {"total": 14, "vagas": [vaga(i) for i in range(14)]}
    msg = montar_email(ALERTA, resultado, "alertas@x.com")
    assert msg["Subject"] == "14 vagas novas no Caça Vagas"
    assert msg["List-Unsubscribe"] == f"<https://caca-vagas.pages.dev/alerta?cancelar={ALERTA.token}>"
    texto = msg.get_body("plain").get_content()
    assert "Dev Júnior 9" in texto and "Dev Júnior 10" not in texto
    assert "E mais 4 no site" in texto


def test_email_escapa_html_do_anuncio():
    resultado = {"total": 1, "vagas": [vaga(1, titulo="<script>alert(1)</script>", empresa="A & B")]}
    html = montar_email(ALERTA, resultado, "alertas@x.com").get_body("html").get_content()
    assert "<script>" not in html
    assert "&lt;script&gt;" in html and "A &amp; B" in html
    assert "1 vaga nova" in html
