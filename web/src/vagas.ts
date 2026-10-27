// Busca de vagas com filtros e nota de encaixe pelas tecnologias da pessoa.

import type { Env } from "./index";

const POR_PAGINA = 30;
// Teto de linhas lidas por busca. A nota é calculada aqui, então a ordenação precisa do conjunto filtrado.
const TETO = 4000;

export const NIVEIS = ["estagio", "junior", "pleno", "senior", "nao"] as const;
export const MODALIDADES = ["remoto", "hibrido", "presencial"] as const;
export const CONTRATOS = ["CLT", "PJ", "outros", "nao"] as const;
export const AREAS = ["Desenvolvimento", "Dados", "QA e Testes", "Infra e DevOps", "Suporte"] as const;

type Linha = {
  chave: string; fonte: string; titulo: string; empresa: string; url: string; cidade: string; uf: string;
  modalidade: string; contrato: string; niveis: string; area: string; tecnologias: string; salario: string;
  publicada_em: string | null; prazo: string | null; ativa: number; status: string | null;
};

export function normalizar(texto: string): string {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
}

const lista = (params: URLSearchParams, nome: string, validos: readonly string[]) =>
  params.getAll(nome).flatMap((v) => v.split(",")).filter((v) => validos.includes(v));

export async function buscar(env: Env, params: URLSearchParams, usuarioId: number | null) {
  const onde: string[] = [];
  const valores: unknown[] = [usuarioId ?? -1];

  const aba = ["candidatei", "descartada"].includes(params.get("aba") ?? "") ? params.get("aba")! : "vagas";
  if (aba === "vagas") {
    onde.push("v.ativa = 1", "m.status IS NULL");
  } else {
    onde.push("m.status = ?");
    valores.push(aba);
  }

  const q = normalizar(params.get("q") ?? "").slice(0, 80);
  if (q) {
    for (const palavra of q.split(" ").slice(0, 6)) {
      onde.push("v.busca LIKE ?");
      valores.push(`%${palavra}%`);
    }
  }

  const niveis = lista(params, "nivel", NIVEIS);
  if (niveis.length) {
    onde.push("(" + niveis.map((n) => (n === "nao" ? "v.niveis = ''" : "v.niveis LIKE ?")).join(" OR ") + ")");
    valores.push(...niveis.filter((n) => n !== "nao").map((n) => `%,${n},%`));
  }

  const modalidades = lista(params, "modalidade", MODALIDADES);
  if (modalidades.length) {
    onde.push(`v.modalidade IN (${modalidades.map(() => "?").join(",")})`);
    valores.push(...modalidades);
  }

  const contratos = lista(params, "contrato", CONTRATOS);
  if (contratos.length) {
    const partes = contratos.map((c) => {
      if (c === "nao") return "v.contrato = ''";
      if (c === "outros") return "(v.contrato != '' AND v.contrato NOT LIKE '%CLT%' AND v.contrato NOT LIKE '%PJ%')";
      valores.push(`%${c}%`);
      return "v.contrato LIKE ?";
    });
    onde.push("(" + partes.join(" OR ") + ")");
  }

  const areas = lista(params, "area", AREAS);
  if (areas.length) {
    onde.push(`v.area IN (${areas.map(() => "?").join(",")})`);
    valores.push(...areas);
  }

  const uf = (params.get("uf") ?? "").toUpperCase();
  if (/^[A-Z]{2}$/.test(uf)) {
    // Remoto vale para qualquer estado.
    onde.push(params.get("incluir_remoto") === "1" ? "(v.uf = ? OR v.modalidade = 'remoto')" : "v.uf = ?");
    valores.push(uf);
  }

  // Usado pelo e-mail do alerta: só as vagas que a coleta viu pela primeira vez depois do último envio.
  const desde = params.get("desde") ?? "";
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(desde)) {
    onde.push("v.descoberta_em > ?");
    valores.push(desde);
  }

  const sql = `SELECT v.chave, v.fonte, v.titulo, v.empresa, v.url, v.cidade, v.uf, v.modalidade, v.contrato, v.niveis,
      v.area, v.tecnologias, v.salario, v.publicada_em, v.prazo, v.ativa, m.status
    FROM vagas v LEFT JOIN marcacoes m ON m.chave = v.chave AND m.usuario_id = ?
    WHERE ${onde.join(" AND ")} ORDER BY v.publicada_em DESC LIMIT ${TETO}`;
  const { results } = await env.DB.prepare(sql).bind(...valores).all<Linha>();

  const minhas = new Set(params.getAll("tec").flatMap((t) => t.split(",")).filter(Boolean).slice(0, 60));
  const vagas = results.map((linha) => {
    const tecnologias: string[] = JSON.parse(linha.tecnologias);
    const comuns = tecnologias.filter((t) => minhas.has(t));
    return {
      ...linha,
      tecnologias,
      niveis: linha.niveis.split(",").filter(Boolean),
      comuns,
      // Parte das tecnologias pedidas pela vaga que a pessoa tem. Sem tecnologia na vaga, não há nota.
      nota: minhas.size && tecnologias.length ? Math.round((100 * comuns.length) / tecnologias.length) : null,
    };
  });

  const data = (v: { publicada_em: string | null }) => v.publicada_em ?? "";
  const ordem = params.get("ordem") === "recentes" || !minhas.size ? "recentes" : "encaixe";
  vagas.sort((a, b) =>
    ordem === "encaixe"
      ? (b.nota ?? -1) - (a.nota ?? -1) || b.comuns.length - a.comuns.length || data(b).localeCompare(data(a))
      : data(b).localeCompare(data(a)),
  );

  const pagina = Math.max(1, Math.min(200, Number(params.get("pagina")) || 1));
  return {
    total: vagas.length,
    pagina,
    por_pagina: POR_PAGINA,
    ordem,
    vagas: vagas.slice((pagina - 1) * POR_PAGINA, pagina * POR_PAGINA),
  };
}

export async function opcoes(env: Env) {
  const [ufs, tecs, coleta, total] = await Promise.all([
    env.DB.prepare("SELECT uf, COUNT(*) AS n FROM vagas WHERE ativa = 1 AND uf != '' GROUP BY uf ORDER BY n DESC").all<{ uf: string; n: number }>(),
    env.DB.prepare("SELECT j.value AS nome, COUNT(*) AS n FROM vagas, json_each(vagas.tecnologias) j WHERE ativa = 1 GROUP BY j.value ORDER BY n DESC").all<{ nome: string; n: number }>(),
    env.DB.prepare("SELECT em, vagas FROM coletas ORDER BY id DESC LIMIT 1").first<{ em: string; vagas: number }>(),
    env.DB.prepare("SELECT COUNT(*) AS n FROM vagas WHERE ativa = 1").first<{ n: number }>(),
  ]);
  return { ufs: ufs.results, tecnologias: tecs.results, atualizado_em: coleta?.em ?? null, total: total?.n ?? 0 };
}
