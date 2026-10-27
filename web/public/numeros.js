// Página de números: contagens das vagas abertas, com seletor de nível na URL (?nivel=junior).
// Todo dado entra na página como texto (textContent), nunca como HTML.

const $ = (seletor, raiz = document) => raiz.querySelector(seletor);
const $$ = (seletor, raiz = document) => [...raiz.querySelectorAll(seletor)];

const NIVEIS = { estagio: "Estágio", junior: "Júnior", pleno: "Pleno", senior: "Sênior", nao: "Não informado" };
const MODALIDADES = { remoto: "Remoto", hibrido: "Híbrido", presencial: "Presencial", nao: "Não informada" };
const DE_NIVEL = { "": "das vagas", estagio: "das vagas de estágio", junior: "das vagas júnior", pleno: "das vagas pleno", senior: "das vagas sênior" };

const fmt = (n) => n.toLocaleString("pt-BR");
const pct = (n, total) => (total ? Math.round((100 * n) / total) : 0);
const ddmm = (iso) => iso.slice(8, 10) + "/" + iso.slice(5, 7);
// Algumas empresas usam o slogan como nome, com emoji. Fica só o texto.
const limpo = (texto) => texto.replace(/\p{Extended_Pictographic}|️/gu, "").replace(/\s+/g, " ").trim();

let nivel = new URLSearchParams(location.search).get("nivel") ?? "";
if (!(nivel in DE_NIVEL)) nivel = "";

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

// ─── Desenho ──────────────────────────────────────────────

function destaque(valor, rotulo) {
  const no = Object.assign(document.createElement("div"), { className: "destaque" });
  no.append(Object.assign(document.createElement("strong"), { textContent: valor }), Object.assign(document.createElement("span"), { textContent: rotulo }));
  return no;
}

// Barras horizontais: comprimento relativo ao maior item, valor e porcentagem sempre escritos.
function barras(alvo, itens, { total, nome = (x) => x, link, de = DE_NIVEL[nivel] } = {}) {
  const lista = $(alvo);
  if (!itens.length) {
    lista.replaceChildren(Object.assign(document.createElement("li"), { className: "barras-vazio", textContent: "Sem dados para esse nível." }));
    return;
  }
  const maior = Math.max(...itens.map((i) => i.n));
  lista.replaceChildren(...itens.map((item) => {
    const li = document.createElement("li");
    const rotulo = nome(item.nome);
    const destino = link?.(item.nome);
    const linha = document.createElement(destino ? "a" : "div");
    linha.className = "barra-linha";
    if (destino) linha.href = destino;
    const texto = `${fmt(item.n)} · ${pct(item.n, total)}%`;
    linha.title = `${rotulo}: ${fmt(item.n)} vagas (${pct(item.n, total)}% ${de})`;
    const trilho = Object.assign(document.createElement("span"), { className: "barra-trilho" });
    const preenchida = Object.assign(document.createElement("span"), { className: "barra-cheia" });
    preenchida.style.width = `${Math.max(1.5, (100 * item.n) / maior)}%`;
    trilho.append(preenchida);
    linha.append(
      Object.assign(document.createElement("span"), { className: "barra-nome", textContent: rotulo }),
      Object.assign(document.createElement("span"), { className: "barra-valor", textContent: texto }),
      trilho,
    );
    li.append(linha);
    return li;
  }));
}

// Link para a lista de vagas já filtrada pelo item e pelo nível escolhido.
function paraVagas(filtros) {
  const p = new URLSearchParams(filtros);
  if (nivel && !p.has("nivel")) p.set("nivel", nivel);
  return `/?${p}`;
}

function pintar(d) {
  const t = d.totais;
  const total = t.total;
  $("#estatus").textContent = d.atualizado_em ? `Atualizado em ${ddmm(d.atualizado_em)}, a partir de ${fmt(total)} vagas abertas.` : "";

  const de = DE_NIVEL[nivel];
  $("#destaques").replaceChildren(
    destaque(fmt(total), nivel ? `vagas ${NIVEIS[nivel].toLowerCase()} abertas` : "vagas de TI abertas"),
    destaque(`${pct(t.remoto, total)}%`, `${de} são 100% remotas`),
    destaque(`${pct(t.clt, total)}%`, `${de} são CLT`),
    destaque(`${pct(t.com_salario, total)}%`, `${de} mostram o salário`),
  );

  $("#sub-tecs").textContent = `Em quantas ${de.replace(/^das /, "")} cada tecnologia aparece. ${pct(t.com_tecnologia, total)}% citam pelo menos uma.`;
  barras("#tecnologias", d.tecnologias, { total });
  barras("#niveis", d.niveis.filter((x) => x.n), {
    total: d.total_geral,
    de: "de todas as vagas",
    nome: (x) => NIVEIS[x] ?? x,
    link: (x) => (x === "nao" ? null : `/?nivel=${x}`),
  });
  barras("#modalidades", d.modalidades, { total, nome: (x) => MODALIDADES[x] ?? x, link: (x) => (x === "nao" ? null : paraVagas({ modalidade: x })) });
  barras("#areas", d.areas, { total, link: (x) => paraVagas({ area: x }) });
  barras("#ufs", d.ufs, { total, link: (x) => paraVagas({ uf: x, incluir_remoto: "0" }) });
  barras("#empresas", d.empresas.map((e) => ({ ...e, nome: limpo(e.nome) })), { total, link: (x) => paraVagas({ q: x }) });
}

async function carregar() {
  for (const b of $$("#seletor-nivel button")) b.setAttribute("aria-pressed", String(b.dataset.valor === nivel));
  history.replaceState(null, "", nivel ? `?nivel=${nivel}` : location.pathname);
  $("#painel").setAttribute("aria-busy", "true");
  try {
    const resposta = await fetch(`/api/numeros${nivel ? `?nivel=${nivel}` : ""}`);
    if (!resposta.ok) throw new Error();
    pintar(await resposta.json());
  } catch {
    $("#estatus").textContent = "Não deu para carregar os números. Tente de novo em instantes.";
  } finally {
    $("#painel").removeAttribute("aria-busy");
  }
}

$("#seletor-nivel").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b || b.dataset.valor === nivel) return;
  nivel = b.dataset.valor;
  carregar();
});

carregar();
