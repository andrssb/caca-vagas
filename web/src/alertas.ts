// Alerta de vaga nova: a pessoa salva os filtros da busca e recebe de manhã as vagas novas que batem.
// Aqui ficam salvar, confirmar e cancelar; o e-mail diário sai da coleta (caca_vagas/alertas.py).

import { WorkerMailer } from "worker-mailer";
import type { Env } from "./index";
import { AREAS, CONTRATOS, MODALIDADES, NIVEIS } from "./vagas";

const MULTIPLOS: Record<string, readonly string[]> = { nivel: NIVEIS, modalidade: MODALIDADES, contrato: CONTRATOS, area: AREAS };
const ROTULOS: Record<string, string> = {
  estagio: "Estágio", junior: "Júnior", pleno: "Pleno", senior: "Sênior", nao: "não informado",
  remoto: "Remoto", hibrido: "Híbrido", presencial: "Presencial", outros: "outros contratos",
};
// Um e-mail de confirmação por conta a cada 10 minutos, para o botão não virar disparador de e-mail.
const REENVIO_MS = 10 * 60 * 1000;

export const agora = () => new Date().toISOString().slice(0, 19) + "Z";

// Os filtros ficam guardados como query string, só com as chaves e valores que a busca entende.
export function limparFiltros(bruto: unknown): string | null {
  if (typeof bruto !== "string" || bruto.length > 2000) return null;
  const entrada = new URLSearchParams(bruto);
  const saida = new URLSearchParams();
  const q = (entrada.get("q") ?? "").trim().slice(0, 80);
  if (q) saida.set("q", q);
  for (const [nome, validos] of Object.entries(MULTIPLOS)) {
    const valores = (entrada.get(nome) ?? "").split(",").filter((v) => validos.includes(v));
    if (valores.length) saida.set(nome, [...new Set(valores)].join(","));
  }
  const uf = (entrada.get("uf") ?? "").toUpperCase();
  if (/^[A-Z]{2}$/.test(uf)) {
    saida.set("uf", uf);
    if (entrada.get("incluir_remoto") === "1") saida.set("incluir_remoto", "1");
  }
  const tecs = (entrada.get("tec") ?? "").split(",").filter((t) => t && t.length <= 40).slice(0, 60);
  if (tecs.length) saida.set("tec", [...new Set(tecs)].join(","));
  return saida.toString();
}

export function descreverFiltros(filtros: string): string {
  const p = new URLSearchParams(filtros);
  const partes: string[] = [];
  for (const nome of Object.keys(MULTIPLOS)) {
    const valores = (p.get(nome) ?? "").split(",").filter(Boolean);
    if (valores.length) partes.push(valores.map((v) => ROTULOS[v] ?? v).join(" ou "));
  }
  if (p.get("uf")) partes.push(p.get("uf") + (p.get("incluir_remoto") === "1" ? " ou remoto" : ""));
  if (p.get("q")) partes.push(`"${p.get("q")}"`);
  if (p.get("tec")) partes.push("suas tecnologias: " + p.get("tec")!.split(",").join(", "));
  return partes.length ? partes.join(" · ") : "todas as vagas de TI";
}

function novoToken(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(24));
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function enviarConfirmacao(env: Env, origem: string, email: string, token: string, filtros: string) {
  const link = `${origem}/alerta?confirmar=${token}`;
  const resumo = descreverFiltros(filtros);
  await WorkerMailer.send(
    { host: "smtp.gmail.com", port: 465, secure: true, credentials: { username: env.SMTP_USUARIO, password: env.SMTP_SENHA }, authType: "plain" },
    {
      from: { name: "Caça Vagas", email: env.SMTP_USUARIO },
      to: email,
      subject: "Confirme seu alerta de vagas",
      text: `Olá!\n\nVocê pediu para receber por e-mail as vagas novas do Caça Vagas com estes filtros:\n${resumo}\n\nPara ativar, abra o link:\n${link}\n\nSe não foi você, ignore este e-mail: sem confirmar, nada é enviado.\n\nCaça Vagas\n${origem}`,
      html: `<div style="font:15px/1.5 Arial,sans-serif;color:#14171f;max-width:520px">
<p>Olá!</p>
<p>Você pediu para receber por e-mail as vagas novas do Caça Vagas com estes filtros:</p>
<p style="background:#eef1f6;border-radius:8px;padding:10px 14px">${escapar(resumo)}</p>
<p><a href="${link}" style="display:inline-block;background:#1f4fe0;color:#fff;text-decoration:none;font-weight:bold;padding:10px 18px;border-radius:8px">Ativar alerta</a></p>
<p style="color:#6b7385;font-size:13px">Se não foi você, ignore este e-mail: sem confirmar, nada é enviado.</p>
</div>`,
    },
  );
}

const escapar = (texto: string) =>
  texto.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

type Alerta = { filtros: string; token: string; confirmado: number; criado_em: string };

export async function lerAlerta(env: Env, usuarioId: number) {
  const a = await env.DB.prepare("SELECT filtros, confirmado FROM alertas WHERE usuario_id = ?").bind(usuarioId).first<Alerta>();
  return a ? { filtros: a.filtros, confirmado: Boolean(a.confirmado), resumo: descreverFiltros(a.filtros) } : null;
}

// Alerta já confirmado só troca os filtros. Novo, ou ainda não confirmado, manda o e-mail de confirmação.
export async function salvarAlerta(env: Env, origem: string, usuario: { id: number; email: string }, filtros: string) {
  const atual = await env.DB.prepare("SELECT filtros, token, confirmado, criado_em FROM alertas WHERE usuario_id = ?").bind(usuario.id).first<Alerta>();
  if (atual?.confirmado) {
    await env.DB.prepare("UPDATE alertas SET filtros = ? WHERE usuario_id = ?").bind(filtros, usuario.id).run();
    return { confirmado: true, enviado: false };
  }
  if (atual && Date.now() - Date.parse(atual.criado_em) < REENVIO_MS) {
    await env.DB.prepare("UPDATE alertas SET filtros = ? WHERE usuario_id = ?").bind(filtros, usuario.id).run();
    return { confirmado: false, enviado: false };
  }
  const token = novoToken();
  await env.DB.prepare(
    `INSERT INTO alertas (usuario_id, filtros, token, confirmado, criado_em) VALUES (?, ?, ?, 0, ?)
     ON CONFLICT (usuario_id) DO UPDATE SET filtros = excluded.filtros, token = excluded.token, criado_em = excluded.criado_em`,
  ).bind(usuario.id, filtros, token, agora()).run();
  try {
    await enviarConfirmacao(env, origem, usuario.email, token, filtros);
  } catch (e) {
    // O e-mail não saiu: libera o reenvio na hora, senão a pessoa fica 10 minutos presa.
    await env.DB.prepare("UPDATE alertas SET criado_em = '1970-01-01T00:00:00Z' WHERE usuario_id = ?").bind(usuario.id).run();
    throw e;
  }
  return { confirmado: false, enviado: true };
}

// A partir da confirmação, só vaga descoberta depois entra no e-mail.
export async function confirmarAlerta(env: Env, token: string) {
  const r = await env.DB.prepare("UPDATE alertas SET confirmado = 1, ultimo_envio = COALESCE(ultimo_envio, ?) WHERE token = ? RETURNING filtros")
    .bind(agora(), token).first<{ filtros: string }>();
  return r ? { filtros: r.filtros, resumo: descreverFiltros(r.filtros) } : null;
}

export async function cancelarAlerta(env: Env, token: string) {
  const r = await env.DB.prepare("DELETE FROM alertas WHERE token = ? RETURNING usuario_id").bind(token).first();
  return Boolean(r);
}
