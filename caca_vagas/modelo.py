"""Formato comum de vaga, igual para todos os portais."""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date


@dataclass
class Vaga:
    fonte: str
    id_externo: str
    titulo: str
    empresa: str
    url: str
    cidade: str = ""
    uf: str = ""
    modalidade: str = ""  # remoto | hibrido | presencial | "" (não informado)
    contrato: str = ""  # CLT, PJ, Estágio... ou "" (não informado)
    senioridade: str = ""
    descricao: str = ""
    tags: list[str] = field(default_factory=list)
    publicada_em: date | None = None
    prazo: date | None = None
    salario: str = ""

    @property
    def chave(self) -> str:
        return f"{self.fonte}:{self.id_externo}"


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento e com espaços simples. Base de toda comparação."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def modalidade_do_texto(texto: str) -> str:
    t = normalizar(texto)
    if "remot" in t or "home office" in t or "home-office" in t:
        return "remoto"
    if "hibrid" in t:
        return "hibrido"
    if "presencial" in t:
        return "presencial"
    return ""


def contrato_do_texto(texto: str) -> str:
    t = normalizar(texto)
    achados = []
    if re.search(r"\bclt\b|efetiv", t):
        achados.append("CLT")
    if re.search(r"\bpj\b|pessoa juridica", t):
        achados.append("PJ")
    if re.search(r"\bestagi", t):
        achados.append("Estágio")
    return " / ".join(achados)
