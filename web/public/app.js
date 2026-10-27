// Caça Vagas: filtros na URL, lista paginada e conta opcional.
// Todo dado de vaga entra na página como texto (textContent), nunca como HTML.

const $ = (seletor, raiz = document) => raiz.querySelector(seletor);
const $$ = (seletor, raiz = document) => [...raiz.querySelectorAll(seletor)];

const NIVEIS = { estagio: "Estágio", junior: "Júnior", pleno: "Pleno", senior: "Sênior" };
const MODALIDADES = { remoto: "Remoto", hibrido: "Híbrido", presencial: "Presencial" };
const FONTES = { gupy: "Gupy", solides: "Sólides", programathor: "Programathor", infojobs: "InfoJobs" };
const MULTIPLOS = ["nivel", "modalidade", "contrato", "area"];
const TECS_VISIVEIS = 24;

const estado = {
  filtros: { q: "", nivel: [], modalidade: [], contrato: [], area: [], uf: "", incluir_remoto: true, ordem: "encaixe", aba: "vagas" },
  tecs: [],
  pagina: 1,
  total: 0,
  usuario: null,
  alerta: null,
  alertaDepoisDeEntrar: false,
  catalogo: [],
  todasTecs: false,
  pedido: 0,
};

// ─── Utilidades ───────────────────────────────────────────

async function api(caminho, { metodo = "GET", corpo } = {}) {
  const resposta = await fetch(caminho, {
    method: metodo,
    credentials: "same-origin",
    headers: corpo === undefined ? {} : { "Content-Type": "application/json" },
    body: corpo === undefined ? undefined : JSON.stringify(corpo),
  });
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw Object.assign(new Error(dados.erro || "Algo deu errado. Tente de novo."), { status: resposta.status });
  return dados;
}

function guardar(chave, valor) {
  try { localStorage.setItem(chave, JSON.stringify(valor)); } catch {}
}
function ler(chave, padrao) {
  try { const v = localStorage.getItem(chave); return v === null ? padrao : JSON.parse(v); } catch { return padrao; }
}

function avisar(texto) {
  $(".aviso-flutuante")?.remove();
  const aviso = Object.assign(document.createElement("div"), { className: "aviso-flutuante", textContent: texto, role: "status" });
  document.body.append(aviso);
  setTimeout(() => aviso.remove(), 3200);
}

const hoje = () => { const d = new Date(); d.setHours(0, 0, 0, 0); return d; };
const dataDe = (iso) => { const [a, m, d] = iso.split("-").map(Number); return new Date(a, m - 1, d); };
const diasAte = (iso) => Math.round((dataDe(iso) - hoje()) / 86_400_000);
const ddmm = (iso) => iso.slice(8, 10) + "/" + iso.slice(5, 7);

function quando(iso) {
  const dias = -diasAte(iso);
  if (dias <= 0) return "publicada hoje";
  if (dias === 1) return "publicada ontem";
  if (dias < 30) return `publicada há ${dias} dias`;
  return `publicada em ${ddmm(iso)}`;
}

// ─── Tema ─────────────────────────────────────────────────

function temaAtual() {
  const escolhido = document.documentElement.dataset.theme;
  if (escolhido) return escolhido;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
$("#botao-tema").addEventListener("click", () => {
  const novo = temaAtual() === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = novo;
  try { localStorage.setItem("cv_tema", novo === "dark" ? "escuro" : "claro"); } catch {}
});

// ─── Filtros <-> URL ──────────────────────────────────────

function lerUrl() {
  const p = new URLSearchParams(location.search);
  const f = estado.filtros;
  f.q = p.get("q") ?? "";
  for (const nome of MULTIPLOS) f[nome] = p.get(nome) ? p.get(nome).split(",") : [];
  f.uf = p.get("uf") ?? "";
  f.incluir_remoto = p.get("incluir_remoto") !== "0";
  f.ordem = p.get("ordem") === "recentes" ? "recentes" : "encaixe";
  f.aba = ["candidatei", "descartada"].includes(p.get("aba")) ? p.get("aba") : "vagas";
}

function paramsDaBusca() {
  const f = estado.filtros;
  const p = new URLSearchParams();
  if (f.q) p.set("q", f.q);
  for (const nome of MULTIPLOS) if (f[nome].length) p.set(nome, f[nome].join(","));
  if (f.uf) { p.set("uf", f.uf); if (!f.incluir_remoto) p.set("incluir_remoto", "0"); }
  if (f.ordem !== "encaixe") p.set("ordem", f.ordem);
  if (f.aba !== "vagas") p.set("aba", f.aba);
  return p;
}

function escreverUrl() {
  const p = paramsDaBusca().toString();
  history.replaceState(null, "", p ? `?${p}` : location.pathname);
}

function pintarFiltros() {
  const f = estado.filtros;
  $("#campo-busca").value = f.q;
  for (const grupo of $$(".chips[data-filtro]")) {
    const ativos = f[grupo.dataset.filtro];
    for (const b of $$("button", grupo)) b.setAttribute("aria-pressed", String(ativos.includes(b.dataset.valor)));
  }
  $("#campo-uf").value = f.uf;
  $("#campo-remoto").checked = f.incluir_remoto;
  $("#campo-remoto").closest("label").hidden = !f.uf;
  $("#campo-ordem").value = f.ordem;
  for (const b of $$("#abas button")) b.setAttribute("aria-current", String(b.dataset.aba === f.aba));
  const n = MULTIPLOS.reduce((soma, nome) => soma + f[nome].length, 0) + (f.uf ? 1 : 0) + estado.tecs.length;
  $("#n-filtros").textContent = n ? String(n) : "";
}

// ─── Tecnologias ──────────────────────────────────────────

function pintarTecs() {
  const termo = $("#campo-tec").value.trim().toLowerCase();
  const selecionadas = new Set(estado.tecs);
  let lista = estado.catalogo.filter((t) => !termo || t.nome.toLowerCase().includes(termo));
  const mostrarTodas = estado.todasTecs || termo;
  if (!mostrarTodas) {
    const topo = lista.slice(0, TECS_VISIVEIS);
    lista = [...lista.filter((t) => selecionadas.has(t.nome) && !topo.includes(t)), ...topo];
  }
  const caixa = $("#lista-tecs");
  caixa.replaceChildren(...lista.map((t) => {
    const b = document.createElement("button");
    b.type = "button";
    b.dataset.valor = t.nome;
    b.setAttribute("aria-pressed", String(selecionadas.has(t.nome)));
    b.append(t.nome, Object.assign(document.createElement("small"), { textContent: t.n }));
    return b;
  }));
  $("#mais-tecs").hidden = mostrarTodas || estado.catalogo.length <= TECS_VISIVEIS;
}

let salvarTecsDepois;
function trocarTec(nome) {
  estado.tecs = estado.tecs.includes(nome) ? estado.tecs.filter((t) => t !== nome) : [...estado.tecs, nome];
  guardar("cv_tecs", estado.tecs);
  if (estado.usuario) {
    clearTimeout(salvarTecsDepois);
    salvarTecsDepois = setTimeout(() => api("/api/perfil", { metodo: "PUT", corpo: { tecnologias: estado.tecs } }).catch(() => {}), 600);
  }
  pintarTecs();
  pintarFiltros();
  buscar();
}

// ─── Lista de vagas ───────────────────────────────────────

function selo(texto, classe = "") {
  return Object.assign(document.createElement("li"), { textContent: texto, className: classe });
}

function cartao(v) {
  const no = $("#modelo-vaga").content.firstElementChild.cloneNode(true);
  no.dataset.chave = v.chave;
  const titulo = $(".vaga-titulo", no);
  titulo.textContent = v.titulo;
  titulo.href = v.url;
  $(".acao-candidatar", no).href = v.url;

  const local = [v.cidade, v.uf].filter(Boolean).join(" / ");
  $(".vaga-empresa", no).textContent = [v.empresa || "Empresa não informada", local].filter(Boolean).join(" · ");

  if (v.nota !== null) {
    const nota = $(".nota", no);
    nota.hidden = false;
    nota.classList.toggle("alta", v.nota >= 70);
    $("strong", nota).textContent = `${v.nota}%`;
    nota.title = `Você tem ${v.comuns.length} de ${v.tecnologias.length} tecnologias citadas na vaga`;
  }

  const selos = $(".selos", no);
  for (const n of v.niveis) selos.append(selo(NIVEIS[n] ?? n, "nivel"));
  if (v.modalidade) selos.append(selo(MODALIDADES[v.modalidade] ?? v.modalidade));
  if (v.contrato) selos.append(selo(v.contrato));
  if (v.area) selos.append(selo(v.area));
  if (v.salario && /\d/.test(v.salario)) selos.append(selo(v.salario));
  if (v.prazo) {
    const dias = diasAte(v.prazo);
    selos.append(selo(dias === 0 ? "inscrições até hoje" : `inscrições até ${ddmm(v.prazo)}`, dias <= 5 ? "prazo" : ""));
  }

  const comuns = new Set(v.comuns);
  const tecs = $(".tecs-vaga", no);
  const ordenadas = [...v.tecnologias].sort((a, b) => comuns.has(b) - comuns.has(a));
  for (const t of ordenadas.slice(0, 12)) tecs.append(selo(t, comuns.has(t) ? "tem" : ""));
  if (ordenadas.length > 12) tecs.append(selo(`+${ordenadas.length - 12}`));
  if (!ordenadas.length) tecs.remove();

  const datas = [v.publicada_em ? quando(v.publicada_em) : null, `via ${FONTES[v.fonte] ?? v.fonte}`];
  if (!v.ativa) datas.unshift("anúncio encerrado");
  $(".vaga-datas", no).textContent = datas.filter(Boolean).join(" · ");

  const marcar = $(".acao-marcar", no);
  const descartar = $(".acao-descartar", no);
  if (v.status) {
    no.classList.add("marcada");
    descartar.remove();
    marcar.textContent = v.status === "candidatei" ? "Desfazer candidatura" : "Voltar para a lista";
    marcar.addEventListener("click", () => mudarStatus(v, null, no));
  } else {
    marcar.addEventListener("click", () => mudarStatus(v, "candidatei", no));
    descartar.addEventListener("click", () => mudarStatus(v, "descartada", no));
  }
  $(".acao-candidatar", no).addEventListener("click", () => {
    if (estado.usuario && !v.status) setTimeout(() => avisar("Depois de se candidatar, marque \"Já me candidatei\" para tirar a vaga da lista."), 400);
  });
  return no;
}

async function mudarStatus(vaga, status, no) {
  if (!estado.usuario) {
    abrirConta("cadastro", "Crie uma conta grátis para salvar as vagas em que você se candidatou.");
    return;
  }
  try {
    await api("/api/marcar", { metodo: "POST", corpo: { chave: vaga.chave, status } });
    no.remove();
    estado.total -= 1;
    pintarContagem();
    avisar(status === "candidatei" ? "Vaga salva em Candidatei." : status === "descartada" ? "Vaga descartada." : "Vaga de volta à lista.");
    if (!$("#lista").children.length) buscar();
  } catch (erro) {
    avisar(erro.message);
  }
}

function pintarContagem() {
  const t = estado.total;
  const rotulo = { vagas: t === 1 ? "vaga encontrada" : "vagas encontradas", candidatei: t === 1 ? "candidatura salva" : "candidaturas salvas", descartada: t === 1 ? "vaga descartada" : "vagas descartadas" };
  $("#contagem").textContent = `${t.toLocaleString("pt-BR")} ${rotulo[estado.filtros.aba]}`;
}

function vazio() {
  const li = document.createElement("li");
  li.className = "vazio";
  const textos = {
    vagas: ["Nenhuma vaga com esses filtros.", "Tente tirar um filtro ou buscar por outro termo."],
    candidatei: ["Nenhuma candidatura salva ainda.", "Na lista de vagas, use \"Já me candidatei\" depois de se candidatar."],
    descartada: ["Nenhuma vaga descartada.", "As vagas que você descartar ficam aqui e podem voltar para a lista."],
  }[estado.filtros.aba];
  li.append(Object.assign(document.createElement("strong"), { textContent: textos[0] }), textos[1]);
  return li;
}

async function buscar({ mais = false } = {}) {
  const pedido = ++estado.pedido;
  estado.pagina = mais ? estado.pagina + 1 : 1;
  escreverUrl();
  const lista = $("#lista");
  if (!mais) lista.replaceChildren(...Array.from({ length: 4 }, () => Object.assign(document.createElement("li"), { className: "esqueleto" })));
  $("#carregar-mais").hidden = true;

  const p = paramsDaBusca();
  p.set("pagina", String(estado.pagina));
  if (estado.filtros.uf && estado.filtros.incluir_remoto) p.set("incluir_remoto", "1");
  if (estado.tecs.length) p.set("tec", estado.tecs.join(","));

  try {
    const r = await api(`/api/vagas?${p}`);
    if (pedido !== estado.pedido) return;
    estado.total = r.total;
    $("#campo-ordem").value = r.ordem;
    $("#campo-ordem").querySelector('[value="encaixe"]').disabled = !estado.tecs.length;
    const cartoes = r.vagas.map(cartao);
    if (mais) lista.append(...cartoes);
    else lista.replaceChildren(...(cartoes.length ? cartoes : [vazio()]));
    pintarContagem();
    $("#carregar-mais").hidden = r.pagina * r.por_pagina >= r.total;
  } catch (erro) {
    if (pedido !== estado.pedido) return;
    const li = vazio();
    li.replaceChildren(Object.assign(document.createElement("strong"), { textContent: "Não deu para carregar as vagas." }), erro.message);
    lista.replaceChildren(li);
  }
}

// ─── Conta ────────────────────────────────────────────────

let modoConta = "entrar";
// alerta: a pessoa veio pelo botão de alerta e, depois de entrar, a janela do alerta abre sozinha.
function abrirConta(modo = "entrar", subtitulo, { alerta = false } = {}) {
  modoConta = modo;
  estado.alertaDepoisDeEntrar = alerta;
  const cadastro = modo === "cadastro";
  $("#titulo-conta").textContent = cadastro ? "Criar conta" : "Entrar";
  $("#sub-conta").textContent = subtitulo ?? "Salve as vagas em que você se candidatou e as suas tecnologias.";
  $("#enviar-conta").textContent = cadastro ? "Criar conta" : "Entrar";
  $("#conta-senha").autocomplete = cadastro ? "new-password" : "current-password";
  $("#dica-senha").hidden = !cadastro;
  for (const b of $$(".alternar button")) b.setAttribute("aria-selected", String(b.dataset.modo === modo));
  $("#erro-conta").textContent = "";
  const modal = $("#modal-conta");
  if (!modal.open) modal.showModal();
  $("#conta-email").focus();
}

function pintarConta() {
  const u = estado.usuario;
  $("#botao-entrar").hidden = Boolean(u);
  $("#conta").hidden = !u;
  $("#abas").hidden = !u;
  if (u) $("#botao-conta").textContent = u.email;
  if (!u && estado.filtros.aba !== "vagas") estado.filtros.aba = "vagas";
}

async function carregarUsuario() {
  try {
    const { usuario } = await api("/api/eu");
    estado.usuario = usuario;
    if (usuario) {
      // Primeira vez com conta: as tecnologias marcadas sem conta vão para ela.
      if (!usuario.tecnologias.length && estado.tecs.length) {
        api("/api/perfil", { metodo: "PUT", corpo: { tecnologias: estado.tecs } }).catch(() => {});
      } else if (usuario.tecnologias.length) {
        estado.tecs = usuario.tecnologias;
        guardar("cv_tecs", estado.tecs);
      }
    }
  } catch {
    estado.usuario = null;
  }
  pintarConta();
}

$("#form-conta").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const email = $("#conta-email").value.trim();
  const senha = $("#conta-senha").value;
  const erro = $("#erro-conta");
  if (!email || !senha) { erro.textContent = "Informe e-mail e senha."; return; }
  if (modoConta === "cadastro" && senha.length < 8) { erro.textContent = "A senha precisa ter pelo menos 8 caracteres."; return; }
  const botao = $("#enviar-conta");
  botao.disabled = true;
  try {
    await api(modoConta === "cadastro" ? "/api/cadastro" : "/api/entrar", { metodo: "POST", corpo: { email, senha } });
    $("#modal-conta").close();
    $("#form-conta").reset();
    await carregarUsuario();
    await carregarAlerta();
    pintarTecs();
    pintarFiltros();
    buscar();
    if (estado.alertaDepoisDeEntrar) {
      estado.alertaDepoisDeEntrar = false;
      abrirAlerta();
    } else {
      avisar(modoConta === "cadastro" ? "Conta criada. Suas candidaturas agora ficam salvas." : "Você entrou.");
    }
  } catch (e) {
    erro.textContent = e.message;
  } finally {
    botao.disabled = false;
  }
});

for (const b of $$(".alternar button")) b.addEventListener("click", () => abrirConta(b.dataset.modo, $("#sub-conta").textContent, { alerta: estado.alertaDepoisDeEntrar }));
$("#botao-entrar").addEventListener("click", () => abrirConta("entrar"));

const menu = $("#menu-conta");
$("#botao-conta").addEventListener("click", (e) => {
  e.stopPropagation();
  menu.hidden = !menu.hidden;
  $("#botao-conta").setAttribute("aria-expanded", String(!menu.hidden));
});
document.addEventListener("click", () => { menu.hidden = true; $("#botao-conta").setAttribute("aria-expanded", "false"); });

$("#botao-sair").addEventListener("click", async () => {
  await api("/api/sair", { metodo: "POST", corpo: {} }).catch(() => {});
  estado.usuario = null;
  estado.alerta = null;
  pintarConta();
  pintarAlerta();
  pintarFiltros();
  buscar();
  avisar("Você saiu da conta.");
});

$("#botao-excluir").addEventListener("click", () => { $("#erro-excluir").textContent = ""; $("#modal-excluir").showModal(); });
$("#cancelar-excluir").addEventListener("click", () => $("#modal-excluir").close());
$("#form-excluir").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  try {
    await api("/api/conta", { metodo: "DELETE", corpo: { senha: $("#excluir-senha").value } });
    $("#modal-excluir").close();
    estado.usuario = null;
    estado.alerta = null;
    pintarAlerta();
    estado.tecs = [];
    guardar("cv_tecs", []);
    pintarConta();
    pintarTecs();
    pintarFiltros();
    buscar();
    avisar("Conta excluída. Seus dados foram apagados.");
  } catch (e) {
    $("#erro-excluir").textContent = e.message;
  }
});

// ─── Alerta por e-mail ────────────────────────────────────

// Os filtros do alerta são os da busca atual, sem ordem e aba. Remoto entra junto do estado, como na lista.
function filtrosDoAlerta() {
  const f = estado.filtros;
  const p = new URLSearchParams();
  if (f.q) p.set("q", f.q);
  for (const nome of MULTIPLOS) if (f[nome].length) p.set(nome, f[nome].join(","));
  if (f.uf) { p.set("uf", f.uf); if (f.incluir_remoto) p.set("incluir_remoto", "1"); }
  if (estado.tecs.length) p.set("tec", estado.tecs.join(","));
  return p.toString();
}

const ROTULOS_ALERTA = { ...NIVEIS, ...MODALIDADES, nao: "não informado", outros: "outros contratos" };
function descreverFiltros(filtros) {
  const p = new URLSearchParams(filtros);
  const partes = MULTIPLOS.map((nome) => (p.get(nome) ?? "").split(",").filter(Boolean).map((v) => ROTULOS_ALERTA[v] ?? v).join(" ou ")).filter(Boolean);
  if (p.get("uf")) partes.push(p.get("uf") + (p.get("incluir_remoto") === "1" ? " ou remoto" : ""));
  if (p.get("q")) partes.push(`"${p.get("q")}"`);
  if (p.get("tec")) partes.push("suas tecnologias: " + p.get("tec").split(",").join(", "));
  return partes.length ? partes.join(" · ") : "todas as vagas de TI";
}

function pintarAlerta() {
  const a = estado.alerta;
  const botao = $("#botao-alerta");
  botao.classList.toggle("ativo", Boolean(a?.confirmado));
  $("#rotulo-alerta").textContent = !a ? "Alerta por e-mail" : a.confirmado ? "Alerta ativo" : "Confirme o alerta";
  botao.title = a ? `Seu alerta: ${a.resumo}` : "Receba por e-mail as vagas novas destes filtros";
}

function abrirAlerta() {
  if (!estado.usuario) {
    abrirConta("cadastro", "Crie uma conta grátis para receber por e-mail as vagas novas destes filtros.", { alerta: true });
    return;
  }
  const a = estado.alerta;
  const atuais = filtrosDoAlerta();
  const iguais = a && a.filtros === atuais;
  $("#erro-alerta").textContent = "";
  $("#cancelar-alerta").hidden = !a;
  $("#salvar-alerta").hidden = Boolean(iguais);
  $("#resumo-alerta").textContent = iguais || !a ? descreverFiltros(atuais) : a.resumo;
  if (!a) {
    $("#sub-alerta").textContent = `Toda manhã, se aparecer vaga nova com estes filtros, ela chega em ${estado.usuario.email}:`;
    $("#dica-alerta").textContent = "Antes, mandamos um link para confirmar o e-mail. Só um e-mail por dia, e só quando tiver vaga nova.";
    $("#salvar-alerta").textContent = "Criar alerta";
  } else {
    $("#sub-alerta").textContent = a.confirmado ? `Alerta ativo para ${estado.usuario.email}, com estes filtros:` : `Falta confirmar: abra o link que mandamos para ${estado.usuario.email}. Filtros do alerta:`;
    $("#dica-alerta").textContent = iguais ? "" : `Os filtros da tela agora são outros: ${descreverFiltros(atuais)}.`;
    $("#salvar-alerta").textContent = "Usar os filtros da tela";
  }
  $("#modal-alerta").showModal();
}

async function carregarAlerta() {
  estado.alerta = null;
  if (estado.usuario) {
    try { estado.alerta = (await api("/api/alerta")).alerta; } catch {}
  }
  pintarAlerta();
}

$("#botao-alerta").addEventListener("click", abrirAlerta);
$("#salvar-alerta").addEventListener("click", async () => {
  const botao = $("#salvar-alerta");
  botao.disabled = true;
  try {
    const r = await api("/api/alerta", { metodo: "PUT", corpo: { filtros: filtrosDoAlerta() } });
    await carregarAlerta();
    $("#modal-alerta").close();
    avisar(r.confirmado ? "Alerta atualizado com os filtros da tela." : r.enviado ? "Mandamos um link para o seu e-mail. Abra para ativar o alerta." : "Filtros salvos. Falta abrir o link que mandamos para o seu e-mail.");
  } catch (e) {
    $("#erro-alerta").textContent = e.message;
  } finally {
    botao.disabled = false;
  }
});
$("#cancelar-alerta").addEventListener("click", async () => {
  try {
    await api("/api/alerta", { metodo: "DELETE", corpo: {} });
    estado.alerta = null;
    pintarAlerta();
    $("#modal-alerta").close();
    avisar("Alerta cancelado. Nenhum e-mail novo vai chegar.");
  } catch (e) {
    $("#erro-alerta").textContent = e.message;
  }
});

// ─── Eventos dos filtros ──────────────────────────────────

$("#form-busca").addEventListener("submit", (e) => {
  e.preventDefault();
  estado.filtros.q = $("#campo-busca").value.trim();
  buscar();
});

for (const grupo of $$(".chips[data-filtro]")) {
  grupo.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    const lista = estado.filtros[grupo.dataset.filtro];
    const i = lista.indexOf(b.dataset.valor);
    if (i >= 0) lista.splice(i, 1); else lista.push(b.dataset.valor);
    pintarFiltros();
    buscar();
  });
}

$("#campo-uf").addEventListener("change", (e) => { estado.filtros.uf = e.target.value; pintarFiltros(); buscar(); });
$("#campo-remoto").addEventListener("change", (e) => { estado.filtros.incluir_remoto = e.target.checked; buscar(); });
$("#campo-ordem").addEventListener("change", (e) => { estado.filtros.ordem = e.target.value; buscar(); });
$("#carregar-mais").addEventListener("click", () => buscar({ mais: true }));
$("#lista-tecs").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) trocarTec(b.dataset.valor); });
$("#campo-tec").addEventListener("input", pintarTecs);
$("#mais-tecs").addEventListener("click", () => { estado.todasTecs = true; pintarTecs(); });

for (const b of $$("#abas button")) {
  b.addEventListener("click", () => { estado.filtros.aba = b.dataset.aba; pintarFiltros(); buscar(); });
}

$("#limpar").addEventListener("click", () => {
  Object.assign(estado.filtros, { q: "", nivel: [], modalidade: [], contrato: [], area: [], uf: "", incluir_remoto: true });
  pintarFiltros();
  buscar();
});

const painelFiltros = $("#filtros");
function filtrosAbertos(abrir) {
  painelFiltros.classList.toggle("aberto", abrir);
  $("#veu").hidden = !abrir;
  document.body.style.overflow = abrir ? "hidden" : "";
}
$("#abrir-filtros").addEventListener("click", () => filtrosAbertos(true));
$("#fechar-filtros").addEventListener("click", () => filtrosAbertos(false));
$("#veu").addEventListener("click", () => filtrosAbertos(false));

// ─── Início ───────────────────────────────────────────────

async function carregarOpcoes() {
  try {
    const o = await api("/api/opcoes");
    estado.catalogo = o.tecnologias;
    $("#botao-alerta").hidden = !o.alertas;
    const select = $("#campo-uf");
    for (const { uf, n } of o.ufs) select.append(new Option(`${uf} (${n.toLocaleString("pt-BR")})`, uf));
    select.value = estado.filtros.uf;
    const atualizado = o.atualizado_em ? ` · atualizado em ${ddmm(o.atualizado_em)}` : "";
    $("#estatus").textContent = `${o.total.toLocaleString("pt-BR")} vagas abertas agora${atualizado}`;
    pintarTecs();
  } catch {
    $("#estatus").textContent = "";
  }
}

lerUrl();
estado.tecs = ler("cv_tecs", []);
pintarFiltros();
await carregarUsuario();
pintarFiltros();
buscar();
carregarOpcoes();
carregarAlerta();
