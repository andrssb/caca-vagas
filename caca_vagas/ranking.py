"""Nota de 0 a 100: quanto a vaga encaixa no perfil.

A maior parte vem das habilidades do perfil que a vaga cita. O resto são bônus
pequenos e explicáveis: júnior escrito no título, CLT confirmado, local e
vaga recente.
"""

import re
from dataclasses import dataclass
from datetime import date

from .filtros import Avaliacao
from .modelo import Vaga, normalizar
from .perfil import Habilidade, Perfil

# Peso de habilidades que já vale a nota cheia dessa parte.
PESO_CHEIO = 12
PONTOS_HABILIDADES = 60


@dataclass
class Nota:
    valor: int
    habilidades: list[str]


def _cita(texto: str, habilidade: Habilidade) -> bool:
    for sinonimo in habilidade.sinonimos:
        termo = re.escape(normalizar(sinonimo))
        # \b não funciona depois de ponto ("node.js"), por isso o lookaround.
        if re.search(rf"(?<![\w.]){termo}(?![\w])", texto):
            return True
    return False


def pontuar(vaga: Vaga, avaliacao: Avaliacao, perfil: Perfil, hoje: date | None = None) -> Nota:
    hoje = hoje or date.today()
    texto = normalizar(" ".join([vaga.titulo, vaga.descricao, " ".join(vaga.tags)]))

    citadas = [h for h in perfil.habilidades if _cita(texto, h)]
    peso = sum(h.peso for h in citadas)
    valor = round(min(peso, PESO_CHEIO) / PESO_CHEIO * PONTOS_HABILIDADES)

    if avaliacao.junior_explicito:
        valor += 15
    if "CLT" in vaga.contrato:
        valor += 10
    if vaga.modalidade == "remoto" or vaga.cidade:
        valor += 8
    if vaga.publicada_em:
        dias = (hoje - vaga.publicada_em).days
        if dias <= 3:
            valor += 7
        elif dias <= 7:
            valor += 4

    return Nota(valor=min(valor, 100), habilidades=[h.nome for h in citadas])
