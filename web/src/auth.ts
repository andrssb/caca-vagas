// Contas: senha com PBKDF2-SHA256 e sessão por cookie HttpOnly.
// O banco guarda só o hash do token da sessão, nunca o token.

import type { Env } from "./index";

// O workerd recusa PBKDF2 acima de 100 mil iterações.
const ITERACOES = 100_000;
const DIAS_SESSAO = 30;
const COOKIE = "cv_sessao";
// Cadastro e login somados, por IP, numa janela de 15 minutos.
const MAX_TENTATIVAS = 10;

export type Usuario = { id: number; email: string; tecnologias: string[] };

const b64 = (bytes: ArrayBuffer | Uint8Array) => btoa(String.fromCharCode(...new Uint8Array(bytes)));
const deB64 = (texto: string) => Uint8Array.from(atob(texto), (c) => c.charCodeAt(0));

async function derivar(senha: string, sal: Uint8Array, iteracoes: number): Promise<string> {
  const chave = await crypto.subtle.importKey("raw", new TextEncoder().encode(senha), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: sal, iterations: iteracoes }, chave, 256);
  return b64(bits);
}

async function sha256(texto: string): Promise<string> {
  return b64(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(texto)));
}

// Comparação em tempo constante, para o tempo de resposta não vazar o hash.
function iguais(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diferenca = 0;
  for (let i = 0; i < a.length; i++) diferenca |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diferenca === 0;
}

export function validarCadastro(email: unknown, senha: unknown): string | null {
  if (typeof email !== "string" || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 200) return "Informe um e-mail válido.";
  if (typeof senha !== "string" || senha.length < 8) return "A senha precisa ter pelo menos 8 caracteres.";
  if (senha.length > 200) return "Senha longa demais.";
  return null;
}

export async function excedeuTentativas(env: Env, ip: string): Promise<boolean> {
  const desde = new Date(Date.now() - 15 * 60_000).toISOString();
  await env.DB.prepare("DELETE FROM tentativas WHERE em < ?").bind(desde).run();
  const linha = await env.DB.prepare("SELECT COUNT(*) AS n FROM tentativas WHERE ip = ? AND em >= ?").bind(ip, desde).first<{ n: number }>();
  if ((linha?.n ?? 0) >= MAX_TENTATIVAS) return true;
  await env.DB.prepare("INSERT INTO tentativas (ip, em) VALUES (?, ?)").bind(ip, new Date().toISOString()).run();
  return false;
}

export async function criarUsuario(env: Env, email: string, senha: string): Promise<number | null> {
  const sal = crypto.getRandomValues(new Uint8Array(16));
  const hash = await derivar(senha, sal, ITERACOES);
  const resultado = await env.DB.prepare(
    "INSERT INTO usuarios (email, senha_hash, sal, iteracoes, criado_em) VALUES (?, ?, ?, ?, ?) ON CONFLICT (email) DO NOTHING RETURNING id",
  ).bind(email, hash, b64(sal), ITERACOES, new Date().toISOString()).first<{ id: number }>();
  return resultado?.id ?? null;
}

export async function conferirSenha(env: Env, email: string, senha: string): Promise<number | null> {
  const linha = await env.DB.prepare("SELECT id, senha_hash, sal, iteracoes FROM usuarios WHERE email = ?")
    .bind(email).first<{ id: number; senha_hash: string; sal: string; iteracoes: number }>();
  // Sem usuário, deriva mesmo assim: e-mail inexistente e senha errada demoram o mesmo.
  const hash = await derivar(senha, linha ? deB64(linha.sal) : new Uint8Array(16), linha?.iteracoes ?? ITERACOES);
  return linha && iguais(hash, linha.senha_hash) ? linha.id : null;
}

export async function abrirSessao(env: Env, usuarioId: number): Promise<string> {
  const token = b64(crypto.getRandomValues(new Uint8Array(32))).replace(/[+/=]/g, (c) => ({ "+": "-", "/": "_", "=": "" })[c]!);
  const expira = new Date(Date.now() + DIAS_SESSAO * 86_400_000);
  await env.DB.prepare("INSERT INTO sessoes (token_hash, usuario_id, expira_em) VALUES (?, ?, ?)")
    .bind(await sha256(token), usuarioId, expira.toISOString()).run();
  return `${COOKIE}=${token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${DIAS_SESSAO * 86_400}`;
}

function tokenDo(pedido: Request): string | null {
  const cookies = pedido.headers.get("Cookie") ?? "";
  const achado = cookies.split(/;\s*/).find((c) => c.startsWith(`${COOKIE}=`));
  return achado ? achado.slice(COOKIE.length + 1) : null;
}

export async function usuarioDa(env: Env, pedido: Request): Promise<Usuario | null> {
  const token = tokenDo(pedido);
  if (!token) return null;
  const linha = await env.DB.prepare(
    `SELECT u.id, u.email, u.tecnologias FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id
     WHERE s.token_hash = ? AND s.expira_em > ?`,
  ).bind(await sha256(token), new Date().toISOString()).first<{ id: number; email: string; tecnologias: string }>();
  return linha ? { id: linha.id, email: linha.email, tecnologias: JSON.parse(linha.tecnologias) } : null;
}

export async function fecharSessao(env: Env, pedido: Request): Promise<string> {
  const token = tokenDo(pedido);
  if (token) await env.DB.prepare("DELETE FROM sessoes WHERE token_hash = ?").bind(await sha256(token)).run();
  return `${COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`;
}
