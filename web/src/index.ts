// Caça Vagas: a página estática vem de public/ (Cloudflare Pages); aqui fica a API em /api/*.

import {
  abrirSessao, conferirSenha, criarUsuario, excedeuTentativas, fecharSessao, usuarioDa, validarCadastro,
} from "./auth";
import { cancelarAlerta, confirmarAlerta, lerAlerta, limparFiltros, salvarAlerta } from "./alertas";
import { numeros } from "./numeros";
import { buscar, opcoes } from "./vagas";

export interface Env {
  DB: D1Database;
  // Conta Gmail que envia os e-mails do alerta (senha de app, não a senha da conta).
  SMTP_USUARIO: string;
  SMTP_SENHA: string;
}

const json = (corpo: unknown, status = 200, extras: Record<string, string> = {}) =>
  new Response(JSON.stringify(corpo), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...extras },
  });

const erro = (mensagem: string, status = 400) => json({ erro: mensagem }, status);

async function corpoJson(pedido: Request): Promise<Record<string, unknown>> {
  try {
    const dados = await pedido.json();
    return dados && typeof dados === "object" ? (dados as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

// Escrita só vinda do próprio site: Origin igual e corpo JSON (um formulário de outro site não consegue enviar JSON sem preflight).
function origemValida(pedido: Request, url: URL): boolean {
  return pedido.headers.get("Origin") === url.origin && (pedido.headers.get("Content-Type") ?? "").startsWith("application/json");
}

async function api(pedido: Request, env: Env, url: URL): Promise<Response> {
  const rota = `${pedido.method} ${url.pathname}`;
  if (pedido.method !== "GET" && !origemValida(pedido, url)) return erro("Pedido recusado.", 403);
  const ip = pedido.headers.get("CF-Connecting-IP") ?? "local";

  switch (rota) {
    case "GET /api/vagas": {
      const usuario = await usuarioDa(env, pedido);
      return json(await buscar(env, url.searchParams, usuario?.id ?? null));
    }
    case "GET /api/opcoes":
      return json(await opcoes(env), 200, { "Cache-Control": "public, max-age=600" });

    case "GET /api/numeros":
      return json(await numeros(env, url.searchParams), 200, { "Cache-Control": "public, max-age=1800" });

    case "GET /api/eu": {
      const usuario = await usuarioDa(env, pedido);
      return json({ usuario });
    }

    case "POST /api/cadastro": {
      if (await excedeuTentativas(env, ip)) return erro("Muitas tentativas. Espere alguns minutos.", 429);
      const { email, senha } = await corpoJson(pedido);
      const invalido = validarCadastro(email, senha);
      if (invalido) return erro(invalido);
      const id = await criarUsuario(env, String(email).trim().toLowerCase(), String(senha));
      if (!id) return erro("Já existe uma conta com esse e-mail. Use Entrar.", 409);
      return json({ ok: true }, 201, { "Set-Cookie": await abrirSessao(env, id) });
    }

    case "POST /api/entrar": {
      if (await excedeuTentativas(env, ip)) return erro("Muitas tentativas. Espere alguns minutos.", 429);
      const { email, senha } = await corpoJson(pedido);
      if (typeof email !== "string" || typeof senha !== "string") return erro("Informe e-mail e senha.");
      const id = await conferirSenha(env, email.trim().toLowerCase(), senha);
      if (!id) return erro("E-mail ou senha incorretos.", 401);
      await env.DB.prepare("DELETE FROM sessoes WHERE expira_em < ?").bind(new Date().toISOString()).run();
      return json({ ok: true }, 200, { "Set-Cookie": await abrirSessao(env, id) });
    }

    case "POST /api/sair":
      return json({ ok: true }, 200, { "Set-Cookie": await fecharSessao(env, pedido) });

    // Links do e-mail: valem sem estar logado, o token é a prova.
    case "POST /api/alerta/confirmar":
    case "POST /api/alerta/cancelar": {
      const { token } = await corpoJson(pedido);
      if (typeof token !== "string" || !/^[\w-]{20,64}$/.test(token)) return erro("Link inválido.");
      if (rota.endsWith("confirmar")) {
        const alerta = await confirmarAlerta(env, token);
        return alerta ? json({ ok: true, ...alerta }) : erro("Esse link não vale mais. Crie o alerta de novo no site.", 404);
      }
      return (await cancelarAlerta(env, token)) ? json({ ok: true }) : erro("Esse alerta já tinha sido cancelado.", 404);
    }
  }

  // Daqui para baixo, só com conta.
  const usuario = await usuarioDa(env, pedido);
  if (!usuario) return erro("Entre na sua conta para continuar.", 401);

  switch (rota) {
    case "POST /api/marcar": {
      const { chave, status } = await corpoJson(pedido);
      if (typeof chave !== "string" || chave.length > 200) return erro("Vaga inválida.");
      if (status === null) {
        await env.DB.prepare("DELETE FROM marcacoes WHERE usuario_id = ? AND chave = ?").bind(usuario.id, chave).run();
      } else if (status === "candidatei" || status === "descartada") {
        await env.DB.prepare(
          `INSERT INTO marcacoes (usuario_id, chave, status, em) VALUES (?, ?, ?, ?)
           ON CONFLICT (usuario_id, chave) DO UPDATE SET status = excluded.status, em = excluded.em`,
        ).bind(usuario.id, chave, status, new Date().toISOString()).run();
      } else {
        return erro("Status inválido.");
      }
      return json({ ok: true });
    }

    case "PUT /api/perfil": {
      const { tecnologias } = await corpoJson(pedido);
      if (!Array.isArray(tecnologias)) return erro("Lista de tecnologias inválida.");
      const limpas = [...new Set(tecnologias.filter((t) => typeof t === "string" && t.length <= 40))].slice(0, 60);
      await env.DB.prepare("UPDATE usuarios SET tecnologias = ? WHERE id = ?").bind(JSON.stringify(limpas), usuario.id).run();
      return json({ ok: true });
    }

    case "GET /api/alerta":
      return json({ alerta: await lerAlerta(env, usuario.id) });

    case "PUT /api/alerta": {
      const filtros = limparFiltros((await corpoJson(pedido)).filtros);
      if (filtros === null) return erro("Filtros inválidos.");
      try {
        return json(await salvarAlerta(env, url.origin, usuario, filtros));
      } catch (e) {
        console.error(e);
        return erro("Não deu para enviar o e-mail de confirmação. Tente de novo em alguns minutos.", 502);
      }
    }

    case "DELETE /api/alerta":
      await env.DB.prepare("DELETE FROM alertas WHERE usuario_id = ?").bind(usuario.id).run();
      return json({ ok: true });

    case "DELETE /api/conta": {
      const { senha } = await corpoJson(pedido);
      if (typeof senha !== "string" || !(await conferirSenha(env, usuario.email, senha))) return erro("Senha incorreta.", 401);
      await env.DB.batch([
        env.DB.prepare("DELETE FROM marcacoes WHERE usuario_id = ?").bind(usuario.id),
        env.DB.prepare("DELETE FROM alertas WHERE usuario_id = ?").bind(usuario.id),
        env.DB.prepare("DELETE FROM sessoes WHERE usuario_id = ?").bind(usuario.id),
        env.DB.prepare("DELETE FROM usuarios WHERE id = ?").bind(usuario.id),
      ]);
      return json({ ok: true }, 200, { "Set-Cookie": await fecharSessao(env, pedido) });
    }
  }
  return erro("Não encontrado.", 404);
}

export async function responder(pedido: Request, env: Env): Promise<Response> {
  try {
    return await api(pedido, env, new URL(pedido.url));
  } catch (e) {
    console.error(e);
    return erro("Erro inesperado. Tente de novo.", 500);
  }
}
