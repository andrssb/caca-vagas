// Links do e-mail do alerta: /alerta?confirmar=<token> ativa na hora; /alerta?cancelar=<token> pede um clique,
// para o leitor de links do provedor de e-mail não cancelar o alerta sozinho.

const $ = (seletor) => document.querySelector(seletor);
const p = new URLSearchParams(location.search);

function mostrar(titulo, texto, resumo) {
  $("#titulo").textContent = titulo;
  $("#texto").textContent = texto;
  $("#resumo").hidden = !resumo;
  if (resumo) $("#resumo").textContent = resumo;
}

async function enviar(acao, token) {
  const r = await fetch(`/api/alerta/${acao}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token }) });
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(dados.erro || "Algo deu errado. Tente de novo.");
  return dados;
}

// O token sai da barra de endereço depois de lido.
history.replaceState(null, "", location.pathname);

if (p.get("confirmar")) {
  try {
    const { resumo, filtros } = await enviar("confirmar", p.get("confirmar"));
    mostrar("Alerta ativado.", "A partir de amanhã, toda manhã que aparecer vaga nova com estes filtros, ela chega no seu e-mail:", resumo);
    $("#voltar").href = `/?${filtros}`;
  } catch (e) {
    mostrar("Não deu para ativar.", e.message);
  }
} else if (p.get("cancelar")) {
  const token = p.get("cancelar");
  mostrar("Cancelar o alerta?", "Você para de receber os e-mails de vagas novas. Dá para criar outro quando quiser.");
  const botao = $("#confirmar-cancelamento");
  botao.hidden = false;
  botao.addEventListener("click", async () => {
    botao.disabled = true;
    try {
      await enviar("cancelar", token);
      mostrar("Alerta cancelado.", "Nenhum e-mail novo vai chegar.");
    } catch (e) {
      mostrar("Não deu para cancelar.", e.message);
    }
    botao.hidden = true;
  });
} else {
  mostrar("Link incompleto.", "Abra o link direto do e-mail, ou crie um alerta na página de vagas.");
}
