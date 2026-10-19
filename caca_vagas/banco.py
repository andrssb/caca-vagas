"""SQLite com o histórico das vagas e o status de cada uma (nova, candidatei, descartada).

Coletar de novo nunca apaga o status: a vaga que você já descartou não volta como nova.
"""

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from .modelo import Vaga
from .perfil import RAIZ

CAMINHO = RAIZ / "dados" / "vagas.db"
STATUS = ("nova", "candidatei", "descartada")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS vagas (
    chave        TEXT PRIMARY KEY,
    fonte        TEXT NOT NULL,
    titulo       TEXT NOT NULL,
    empresa      TEXT NOT NULL,
    url          TEXT NOT NULL,
    cidade       TEXT NOT NULL DEFAULT '',
    uf           TEXT NOT NULL DEFAULT '',
    modalidade   TEXT NOT NULL DEFAULT '',
    contrato     TEXT NOT NULL DEFAULT '',
    salario      TEXT NOT NULL DEFAULT '',
    publicada_em TEXT,
    prazo        TEXT,
    nota         INTEGER NOT NULL,
    habilidades  TEXT NOT NULL DEFAULT '',
    avisos       TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'nova' CHECK (status IN ('nova', 'candidatei', 'descartada')),
    status_em    TEXT,
    primeira_vez TEXT NOT NULL,
    ultima_vez   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vagas_status_nota ON vagas (status, nota DESC);
"""


def conectar(caminho: Path = CAMINHO) -> sqlite3.Connection:
    if str(caminho) != ":memory:":
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(caminho)
    conexao.row_factory = sqlite3.Row
    conexao.executescript(ESQUEMA)
    return conexao


def salvar(conexao: sqlite3.Connection, vaga: Vaga, nota: int, habilidades: list[str], avisos: list[str]) -> bool:
    """Insere ou atualiza a vaga. Devolve True se ela é nova no banco."""
    agora = datetime.now().isoformat(timespec="seconds")
    existia = conexao.execute("SELECT 1 FROM vagas WHERE chave = ?", (vaga.chave,)).fetchone()
    conexao.execute(
        """
        INSERT INTO vagas (chave, fonte, titulo, empresa, url, cidade, uf, modalidade, contrato, salario,
                           publicada_em, prazo, nota, habilidades, avisos, primeira_vez, ultima_vez)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (chave) DO UPDATE SET
            titulo = excluded.titulo, empresa = excluded.empresa, url = excluded.url,
            cidade = excluded.cidade, uf = excluded.uf, modalidade = excluded.modalidade,
            contrato = excluded.contrato, salario = excluded.salario,
            publicada_em = excluded.publicada_em, prazo = excluded.prazo,
            nota = excluded.nota, habilidades = excluded.habilidades, avisos = excluded.avisos,
            ultima_vez = excluded.ultima_vez
        """,
        (
            vaga.chave, vaga.fonte, vaga.titulo, vaga.empresa, vaga.url, vaga.cidade, vaga.uf,
            vaga.modalidade, vaga.contrato, vaga.salario,
            vaga.publicada_em.isoformat() if vaga.publicada_em else None,
            vaga.prazo.isoformat() if vaga.prazo else None,
            nota, ", ".join(habilidades), ", ".join(avisos), agora, agora,
        ),
    )
    conexao.commit()
    return existia is None


def marcar(conexao: sqlite3.Connection, chave: str, status: str) -> None:
    if status not in STATUS:
        raise ValueError(f"status inválido: {status}")
    conexao.execute(
        "UPDATE vagas SET status = ?, status_em = ? WHERE chave = ?",
        (status, datetime.now().isoformat(timespec="seconds"), chave),
    )
    conexao.commit()


def listar(conexao: sqlite3.Connection, status: str = "nova", dias_sem_ver: int = 3) -> list[sqlite3.Row]:
    """Vagas de um status. As novas só aparecem se a última coleta ainda as encontrou."""
    if status == "nova":
        limite = (date.today() - timedelta(days=dias_sem_ver)).isoformat()
        return conexao.execute(
            "SELECT * FROM vagas WHERE status = 'nova' AND ultima_vez >= ? ORDER BY nota DESC, publicada_em DESC",
            (limite,),
        ).fetchall()
    return conexao.execute(
        "SELECT * FROM vagas WHERE status = ? ORDER BY status_em DESC", (status,)
    ).fetchall()


def contagem(conexao: sqlite3.Connection) -> dict[str, int]:
    linhas = conexao.execute("SELECT status, COUNT(*) AS n FROM vagas GROUP BY status").fetchall()
    return {s: 0 for s in STATUS} | {l["status"]: l["n"] for l in linhas}
