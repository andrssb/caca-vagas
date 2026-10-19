"""Decide se uma vaga entra na lista. Toda recusa tem um motivo legível."""

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from .modelo import Vaga, normalizar
from .perfil import Perfil

JUNIOR = re.compile(r"\b(junior|jr)\b|\bi\b(?=\s*($|[-(|/]))")
# "pl" fica de fora de propósito: casaria com "PL/SQL".
ACIMA = re.compile(r"\b(senior|sr|pleno|especialista|lead|lider|coordenador|coordenadora|gerente|head|principal|staff|ii|iii)\b")
FORA_DO_PERFIL = re.compile(r"\b(estagio|estagiario|estagiaria|aprendiz)\b")
# Vaga exclusiva para um público (mulheres, PCD, pessoas negras...). Não recusa: só avisa.
AFIRMATIVA = re.compile(r"\b(afirmativa|exclusiva para|exclusivo para|exclusiva pcd|exclusivo pcd|somente pcd|apenas pcd)\b")


@dataclass
class Avaliacao:
    aceita: bool
    junior_explicito: bool = False
    motivo: str = ""
    avisos: list[str] = field(default_factory=list)


def _contem_termo(texto: str, termos: list[str]) -> bool:
    return any(re.search(rf"\b{re.escape(normalizar(t))}\b", texto) for t in termos)


def avaliar(vaga: Vaga, perfil: Perfil, hoje: date | None = None) -> Avaliacao:
    hoje = hoje or date.today()
    titulo = normalizar(vaga.titulo)
    senioridade = normalizar(vaga.senioridade)

    if not _contem_termo(titulo, perfil.area):
        return Avaliacao(False, motivo="fora da área de TI")

    junior = bool(JUNIOR.search(titulo) or "junior" in senioridade)
    # Senioridade "Júnior / Estagiário" aceita os dois níveis, então só o título decide.
    if FORA_DO_PERFIL.search(titulo) or (FORA_DO_PERFIL.search(senioridade) and not junior):
        return Avaliacao(False, motivo="estágio ou aprendiz")

    acima = bool(ACIMA.search(titulo) or (senioridade and not junior and ACIMA.search(senioridade)))
    # "Júnior/Pleno" continua valendo: o júnior explícito vence.
    if acima and not junior:
        return Avaliacao(False, motivo="nível acima de júnior")

    avisos = []
    if AFIRMATIVA.search(titulo):
        avisos.append("vaga afirmativa: confira o público no anúncio")
    if not junior:
        avisos.append("nível não informado")

    if vaga.modalidade != "remoto":
        if vaga.cidade:
            if not _contem_termo(normalizar(vaga.cidade), perfil.cidades):
                return Avaliacao(False, motivo=f"{vaga.modalidade or 'presencial'} fora de BH ({vaga.cidade})")
        else:
            avisos.append("local não informado")

    if vaga.contrato:
        partes = [normalizar(p) for p in re.split(r"[/,]", vaga.contrato)]
        if not any(normalizar(c) in partes for c in perfil.contratos):
            return Avaliacao(False, motivo=f"contrato {vaga.contrato}")
    else:
        avisos.append("contrato não informado")

    # Quando o portal informa o prazo de inscrição, ele vale mais que a data de publicação.
    if vaga.prazo:
        if vaga.prazo < hoje:
            return Avaliacao(False, motivo="inscrições encerradas")
    elif vaga.publicada_em and vaga.publicada_em < hoje - timedelta(days=perfil.dias):
        return Avaliacao(False, motivo=f"publicada há mais de {perfil.dias} dias")

    return Avaliacao(True, junior_explicito=junior, avisos=avisos)
