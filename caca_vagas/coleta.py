"""Roda as fontes, classifica e gera o SQL que atualiza o banco do site (Cloudflare D1).

Uma fonte com erro não derruba as outras, e as vagas dela não são desativadas
naquele dia: só sai do ar a vaga que uma fonte que funcionou deixou de mostrar.
"""

import json
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import httpx

from .classificar import classificar
from .fontes import FONTES
from .modelo import Vaga, normalizar

TERMOS = [
    "desenvolvedor",
    "programador",
    "engenheiro de software",
    "analista de sistemas",
    "full stack",
    "front end",
    "back end",
    "mobile",
    "analista de dados",
    "engenheiro de dados",
    "cientista de dados",
    "devops",
    "analista de qa",
    "analista de testes",
    "analista de suporte",
    "estágio ti",
]

# Vaga que nenhuma coleta encontra há esse tempo sai do ar, mesmo que a fonte dela esteja falhando.
DIAS_SEM_VER = 7

# Ritmo de uma pessoa navegando: uma requisição por vez, com pausa entre elas.
PAUSA_SEGUNDOS = 1.5
CABECALHOS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


@dataclass
class Resumo:
    coletadas: Counter = field(default_factory=Counter)
    aceitas: Counter = field(default_factory=Counter)
    recusas: Counter = field(default_factory=Counter)
    erros: dict[str, str] = field(default_factory=dict)
    vagas: list[Vaga] = field(default_factory=list)

    @property
    def fontes_ok(self) -> list[str]:
        return [nome for nome in self.coletadas if nome not in self.erros]


def _pausar(_requisicao: httpx.Request) -> None:
    time.sleep(PAUSA_SEGUNDOS)


def cliente_http() -> httpx.Client:
    return httpx.Client(headers=CABECALHOS, timeout=30, follow_redirects=True, event_hooks={"request": [_pausar]})


def sem_repetidas(vagas: list[Vaga]) -> list[Vaga]:
    """A mesma vaga aparece em vários termos e às vezes em dois portais."""
    vistas: set[str] = set()
    unicas = []
    for vaga in vagas:
        chaves = (vaga.chave, f"{normalizar(vaga.titulo)}|{normalizar(vaga.empresa)}|{normalizar(vaga.cidade)}")
        if any(c in vistas for c in chaves):
            continue
        vistas.update(chaves)
        unicas.append(vaga)
    return unicas


def rodar(fontes: list[str] | None = None, log=print) -> Resumo:
    resumo = Resumo()
    todas: list[Vaga] = []
    with cliente_http() as cliente:
        for nome in fontes or list(FONTES):
            log(f"coletando {nome}...")
            try:
                vagas = FONTES[nome].coletar(cliente, TERMOS)
            except Exception as erro:  # um portal fora do ar não pode parar os outros
                resumo.erros[nome] = f"{type(erro).__name__}: {erro}"
                resumo.coletadas[nome] = 0
                log(f"  erro em {nome}: {resumo.erros[nome]}")
                continue
            resumo.coletadas[nome] = len(vagas)
            todas.extend(vagas)

    for vaga in sem_repetidas(todas):
        resultado = classificar(vaga)
        if resultado.aceita:
            resumo.aceitas[vaga.fonte] += 1
            resumo.vagas.append(vaga)
        else:
            resumo.recusas[resultado.motivo] += 1
    return resumo


# ─── Exportação para o D1 ────────────────────────────────────────────────────

COLUNAS = ["chave", "fonte", "titulo", "empresa", "url", "cidade", "uf", "modalidade", "contrato",
           "niveis", "area", "tecnologias", "salario", "busca", "publicada_em", "prazo", "visto_em"]


def _literal(valor) -> str:
    if valor is None:
        return "NULL"
    texto = str(valor).replace("\x00", "")
    return "'" + texto.replace("'", "''") + "'"


def _linha(vaga: Vaga, hoje: date) -> list:
    return [
        vaga.chave, vaga.fonte, vaga.titulo, vaga.empresa, vaga.url, vaga.cidade, vaga.uf, vaga.modalidade,
        vaga.contrato,
        # Vírgulas nas pontas para o site filtrar com LIKE '%,junior,%'.
        "," + ",".join(vaga.niveis) + "," if vaga.niveis else "",
        vaga.area,
        json.dumps(vaga.tecnologias, ensure_ascii=False),
        vaga.salario,
        normalizar(f"{vaga.titulo} {vaga.empresa} {vaga.cidade}"),
        vaga.publicada_em.isoformat() if vaga.publicada_em else None,
        vaga.prazo.isoformat() if vaga.prazo else None,
        hoje.isoformat(),
    ]


def agora_utc() -> str:
    """Mesmo formato do site (toISOString sem milissegundos), para comparar como texto."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sql_de(resumo: Resumo, hoje: date | None = None, agora: str | None = None) -> str:
    hoje = hoje or date.today()
    agora = agora or agora_utc()
    # descoberta_em entra só na primeira vez: o UPDATE do conflito não mexe nela.
    atualizar = ", ".join(f"{c} = excluded.{c}" for c in COLUNAS if c != "chave")
    linhas = []
    for vaga in resumo.vagas:
        valores = ", ".join(_literal(v) for v in _linha(vaga, hoje))
        linhas.append(
            f"INSERT INTO vagas ({', '.join(COLUNAS)}, ativa, descoberta_em) VALUES ({valores}, 1, {_literal(agora)}) "
            f"ON CONFLICT (chave) DO UPDATE SET {atualizar}, ativa = 1;"
        )
    if resumo.fontes_ok:
        fontes = ", ".join(_literal(f) for f in resumo.fontes_ok)
        linhas.append(f"UPDATE vagas SET ativa = 0 WHERE fonte IN ({fontes}) AND visto_em < {_literal(hoje.isoformat())};")
    limite = (hoje - timedelta(days=DIAS_SEM_VER)).isoformat()
    linhas.append(f"UPDATE vagas SET ativa = 0 WHERE visto_em < {_literal(limite)};")
    linhas.append(
        f"INSERT INTO coletas (em, vagas, fontes_ok, erros) VALUES "
        f"({_literal(hoje.isoformat())}, {len(resumo.vagas)}, {_literal(','.join(resumo.fontes_ok))}, "
        f"{_literal(json.dumps(resumo.erros, ensure_ascii=False))});"
    )
    return "\n".join(linhas) + "\n"
