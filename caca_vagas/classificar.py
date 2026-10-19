"""Classifica a vaga (área, níveis, tecnologias) e recusa o que não é vaga de TI aberta.

O filtro de perfil (nível, cidade, contrato) não acontece aqui: quem filtra é a
pessoa, no site. Aqui só sai o que nunca interessa: vaga fora de TI, programa de
aprendiz e vaga encerrada.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

from .localidade import normalizar_local
from .modelo import Vaga, normalizar

# Sem prazo de inscrição informado, vaga mais velha que isso é tratada como encerrada.
DIAS_SEM_PRAZO = 45

# A ordem importa: a primeira área que casar com o título vence.
AREAS = [
    ("QA e Testes", r"\bqa\b|quality assurance|\btester\b|\bteste(s)? de software|analista de testes?\b|qualidade de software|\bsdet\b"),
    ("Dados", r"\bdados\b|\bdata (engineer|analyst|scientist|science|analytics)|\bbi\b|business intelligence|\banalytics\b|machine learning|\bml engineer|cientista de dados"),
    ("Infra e DevOps", r"\bdevops\b|\bsre\b|infraestrutura|\bcloud\b|\bredes\b|seguranca da informacao|ciberseguranca|cyber ?security|\bsysadmin\b|administrador de sistemas|\bplatform engineer"),
    ("Suporte", r"\bsuporte (tecnico|de ti|ti|n[1-3])\b|analista de suporte|tecnico de suporte|help ?desk|service ?desk"),
    ("Desenvolvimento", r"desenvolvedor|desenvolvedora|\bprogramador|\bdeveloper\b|\bdev\b|engenheir[oa] de software|software engineer|full ?stack|front ?-?end|back ?-?end|\bmobile\b|\bandroid\b|\bios\b|analista de sistemas|analista desenvolvedor|desenvolvimento de (sistemas|software)|arquitet[oa] de (software|solucoes)|tech lead|\babap\b|\brpa\b"),
]
_AREAS = [(nome, re.compile(padrao)) for nome, padrao in AREAS]

# Títulos com "programação" ou "desenvolvedor" que não são de TI.
NAO_TI = re.compile(r"\bpcp\b|programac?ao de (producao|materiais)|programador (de producao|cnc|de maquinas)|\bcnc\b|usinagem|desenvolvedor (de negocios|comercial)|desenvolvimento (de negocios|humano|organizacional)|business development|suporte ao paciente|suporte administrativo|predial|\bplc\b|\bclp\b|automacao industrial|\bmarketing\b")
APRENDIZ = re.compile(r"\baprendiz\b|jovem aprendiz")

NIVEIS = [
    ("estagio", re.compile(r"\bestagi(o|ario|aria)\b|\bintern(ship)?\b")),
    ("junior", re.compile(r"\b(junior|jr|trainee)\b")),
    # "pl" sozinho casaria com "PL/SQL"; por isso só com fronteira que não seja barra.
    ("pleno", re.compile(r"\bpleno\b|\bpl\b(?!/)|\bmid(dle)?(-level)?\b|\bii\b")),
    ("senior", re.compile(r"\b(senior|sr|iii|especialista|specialist|lead|lider|principal|staff|arquitet[oa])\b")),
]

# Tecnologias reconhecidas na vaga. O nome é o que aparece no site.
TECNOLOGIAS = {
    "JavaScript": r"javascript|(?<![.\w])js\b",  # o "js" de "node.js" não conta
    "TypeScript": r"typescript",
    "Node.js": r"node(\.?js)?\b",
    "React": r"react(\.?js)?\b(?! native)",
    "React Native": r"react native",
    "Angular": r"angular",
    "Vue": r"\bvue(\.?js)?\b",
    "Next.js": r"next\.?js",
    "HTML e CSS": r"\bhtml5?\b|\bcss3?\b",
    "Python": r"python",
    "Django": r"django",
    "Flask": r"\bflask\b",
    "FastAPI": r"fastapi",
    "Java": r"\bjava\b(?!script)",
    "Spring": r"\bspring( boot)?\b",
    "Kotlin": r"kotlin",
    "Swift": r"\bswift\b",
    "Flutter": r"flutter",
    "C#": r"c#|c sharp",
    ".NET": r"\.net\b|dotnet|asp\.net",
    "PHP": r"\bphp\b",
    "Laravel": r"laravel",
    "Ruby": r"\bruby\b",
    "Go": r"golang|\bgo lang\b",
    "Rust": r"\brust\b",
    "C/C++": r"c\+\+|\bc/c\+\+",
    "Delphi": r"delphi",
    "COBOL": r"cobol",
    "SAP/ABAP": r"\babap\b|\bsap\b",
    "Salesforce": r"salesforce|\bapex\b",
    "SQL": r"\bsql\b|pl/sql|t-sql",
    "PostgreSQL": r"postgre(s|sql)?\b",
    "MySQL": r"mysql",
    "SQL Server": r"sql server",
    "Oracle": r"\boracle\b",
    "MongoDB": r"mongo(db)?\b",
    "Redis": r"\bredis\b",
    "Docker": r"docker",
    "Kubernetes": r"kubernetes|\bk8s\b",
    "AWS": r"\baws\b|amazon web services",
    "Azure": r"\bazure\b",
    "GCP": r"\bgcp\b|google cloud",
    "Terraform": r"terraform",
    "Linux": r"\blinux\b",
    "Git": r"\bgit\b|github|gitlab",
    "APIs REST": r"\brest(ful)?\b|\bapis?\b",
    "JSON": r"\bjson\b",
    "GraphQL": r"graphql",
    "Power BI": r"power ?bi",
    "Excel": r"\bexcel\b",
    "Tableau": r"tableau",
    "Spark": r"\bspark\b|pyspark",
    "Airflow": r"airflow",
    "dbt": r"\bdbt\b",
    "Databricks": r"databricks",
    "Pandas": r"pandas",
    "Selenium": r"selenium",
    "Cypress": r"cypress",
    "Playwright": r"playwright",
    "Jest": r"\bjest\b",
    "RPA": r"\brpa\b|uipath|automation anywhere|blue ?prism",
    "Power Platform": r"power ?apps|power automate",
}
_TECNOLOGIAS = {nome: re.compile(padrao) for nome, padrao in TECNOLOGIAS.items()}


@dataclass
class Resultado:
    aceita: bool
    motivo: str = ""


def area_de(titulo: str) -> str:
    t = normalizar(titulo)
    if NAO_TI.search(t):
        return ""
    return next((nome for nome, padrao in _AREAS if padrao.search(t)), "")


# "Desenvolvedor I" é júnior, mas "Especialista I" não: o I romano só vale sem outra palavra de nível.
I_ROMANO = re.compile(r"\bi\b(?=\s*($|[-(|/]))")


def niveis_de(titulo: str, senioridade: str = "") -> list[str]:
    texto = normalizar(f"{titulo} | {senioridade}")
    niveis = [nome for nome, padrao in NIVEIS if padrao.search(texto)]
    if not niveis and I_ROMANO.search(normalizar(titulo)):
        niveis = ["junior"]
    return niveis


def tecnologias_de(vaga: Vaga) -> list[str]:
    texto = normalizar(" ".join([vaga.titulo, vaga.descricao, " ".join(vaga.tags)]))
    return [nome for nome, padrao in _TECNOLOGIAS.items() if padrao.search(texto)]


def classificar(vaga: Vaga, hoje: date | None = None) -> Resultado:
    """Preenche área, níveis, tecnologias e local da vaga. Devolve se ela entra."""
    hoje = hoje or date.today()
    vaga.area = area_de(vaga.titulo)
    if not vaga.area:
        return Resultado(False, "fora da área de TI")
    if APRENDIZ.search(normalizar(vaga.titulo)):
        return Resultado(False, "programa de aprendiz")

    # Quando o portal informa o prazo de inscrição, ele vale mais que a data de publicação.
    if vaga.prazo:
        if vaga.prazo < hoje:
            return Resultado(False, "inscrições encerradas")
    elif vaga.publicada_em and vaga.publicada_em < hoje - timedelta(days=DIAS_SEM_PRAZO):
        return Resultado(False, "publicada há muito tempo")

    vaga.niveis = niveis_de(vaga.titulo, vaga.senioridade)
    vaga.tecnologias = tecnologias_de(vaga)
    vaga.cidade, vaga.uf = normalizar_local(vaga.cidade, vaga.uf)
    if "Estágio" in vaga.contrato and "estagio" not in vaga.niveis:
        vaga.niveis.insert(0, "estagio")
    return Resultado(True)
