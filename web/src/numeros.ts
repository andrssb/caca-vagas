// Página "O mercado em números": contagens das vagas ativas, opcionalmente de um nível só.

import type { Env } from "./index";
import { NIVEIS } from "./vagas";

type Contagem = { nome: string; n: number };

export async function numeros(env: Env, params: URLSearchParams) {
  const nivel = params.get("nivel") ?? "";
  const filtro = (NIVEIS as readonly string[]).includes(nivel) && nivel !== "nao" ? nivel : "";
  // Todas as consultas abaixo leem só as vagas ativas do nível escolhido.
  const onde = filtro ? "ativa = 1 AND niveis LIKE ?" : "ativa = 1";
  const valores = filtro ? [`%,${filtro},%`] : [];
  const contar = (sql: string) => env.DB.prepare(sql).bind(...valores).all<Contagem>().then((r) => r.results);

  const [niveis, geral, totais,modalidades, areas, ufs, tecnologias, empresas, coleta] = await Promise.all([
    // A divisão por nível é sempre do total, para o seletor mostrar quanto cada nível pesa.
    // Uma vaga pode valer para dois níveis ("júnior/pleno") e conta nos dois.
    env.DB.prepare(
      `SELECT SUM(niveis LIKE '%,estagio,%') AS estagio, SUM(niveis LIKE '%,junior,%') AS junior,
         SUM(niveis LIKE '%,pleno,%') AS pleno, SUM(niveis LIKE '%,senior,%') AS senior, SUM(niveis = '') AS nao
       FROM vagas WHERE ativa = 1`,
    ).first<Record<string, number>>().then((r) => Object.entries(r ?? {}).map(([nome, n]) => ({ nome, n: n ?? 0 }))),
    env.DB.prepare("SELECT COUNT(*) AS n FROM vagas WHERE ativa = 1").first<{ n: number }>(),
    env.DB.prepare(
      `SELECT COUNT(*) AS total,
         SUM(modalidade = 'remoto') AS remoto,
         SUM(salario GLOB '*[0-9]*') AS com_salario,
         SUM(contrato LIKE '%CLT%') AS clt,
         SUM(contrato LIKE '%PJ%') AS pj,
         SUM(tecnologias != '[]') AS com_tecnologia
       FROM vagas WHERE ${onde}`,
    ).bind(...valores).first<Record<string, number>>(),
    contar(`SELECT CASE WHEN modalidade = '' THEN 'nao' ELSE modalidade END AS nome, COUNT(*) AS n FROM vagas WHERE ${onde} GROUP BY 1 ORDER BY n DESC`),
    contar(`SELECT area AS nome, COUNT(*) AS n FROM vagas WHERE ${onde} AND area != '' GROUP BY 1 ORDER BY n DESC`),
    contar(`SELECT uf AS nome, COUNT(*) AS n FROM vagas WHERE ${onde} AND uf != '' GROUP BY 1 ORDER BY n DESC LIMIT 10`),
    contar(`SELECT j.value AS nome, COUNT(*) AS n FROM vagas, json_each(vagas.tecnologias) j WHERE ${onde} GROUP BY 1 ORDER BY n DESC LIMIT 15`),
    contar(`SELECT empresa AS nome, COUNT(*) AS n FROM vagas WHERE ${onde} AND empresa != '' AND empresa NOT LIKE '%confidencial%' GROUP BY 1 ORDER BY n DESC LIMIT 10`),
    env.DB.prepare("SELECT em FROM coletas ORDER BY id DESC LIMIT 1").first<{ em: string }>(),
  ]);

  return {
    nivel: filtro,
    atualizado_em: coleta?.em ?? null,
    totais: Object.fromEntries(Object.entries(totais ?? {}).map(([k, v]) => [k, v ?? 0])),
    total_geral: geral?.n ?? 0,
    niveis,
    modalidades,
    areas,
    ufs,
    tecnologias,
    empresas,
  };
}
