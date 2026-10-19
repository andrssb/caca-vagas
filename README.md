# Caça Vagas

Vagas de TI de Gupy, Sólides, Programathor e InfoJobs num lugar só, atualizadas todo dia. Qualquer pessoa filtra por nível, modalidade, estado, contrato e área, marca as tecnologias que usa e recebe uma nota de encaixe para cada vaga. Com uma conta (opcional), salva as vagas em que se candidatou. A candidatura acontece sempre no anúncio original.

```
GitHub Actions (todo dia, 7h)                    Cloudflare
┌──────────────────────────────┐       ┌───────────────────────────────┐
│ Python: coleta nos 4 portais │  SQL  │ D1 (SQLite)                   │
│ classifica nível, área,      │ ────> │ Worker: API de vagas, contas, │
│ local e tecnologias          │       │ sessões e marcações           │
└──────────────────────────────┘       │ Página estática (HTML/CSS/JS) │
                                       └───────────────────────────────┘
```

## Coleta (`caca_vagas/`, Python)

| Portal | Como é lido |
| --- | --- |
| Gupy | API JSON pública da busca do portal (contrato, modalidade e prazo de inscrição) |
| Sólides Vagas | API JSON pública do portal (senioridade, contrato e habilidades pedidas) |
| Programathor | HTML das páginas de vagas; a leitura para na primeira página só com vagas "Vencida" |
| InfoJobs | HTML da busca por palavra-chave (contrato deduzido do título e do resumo) |

- Cada portal vira o mesmo formato (`Vaga`, em `modelo.py`). As requisições são sequenciais, com pausa entre elas, no ritmo de uma pessoa navegando.
- `classificar.py` decide a **área** pelo título (Desenvolvimento, Dados, QA e Testes, Infra e DevOps, Suporte), os **níveis** (estágio a sênior; "Jr/Pl" fica nos dois; "PL/SQL" não é pleno), as **tecnologias** citadas (Java não casa com JavaScript, React não casa com React Native) e recusa o que nunca interessa: vaga fora de TI, programa de aprendiz e vaga encerrada.
- `localidade.py` transforma "São Paulo, São Paulo, Brasil", "Mato Grosso - Cuiabá" e "Belo Horizonte/MG" em cidade e UF.
- `coleta.py` gera o SQL de atualização. Uma vaga só sai do ar quando a fonte dela funcionou e deixou de mostrá-la: um portal fora do ar num dia não apaga as vagas dele.
- Indeed e Glassdoor ficaram de fora porque bloqueiam leitura automatizada. O site mostra só o resumo da vaga e leva ao anúncio original; o texto do anúncio não é republicado.

## Site (`web/`, Cloudflare Workers + D1)

- **Busca:** filtros combináveis na URL (dá para compartilhar o link de uma busca). A nota de encaixe é a parte das tecnologias pedidas pela vaga que a pessoa marcou.
- **Contas:** senha com PBKDF2-SHA256 e sal; sessão em cookie HttpOnly, Secure e SameSite=Lax, com só o hash do token no banco; comparação de hash em tempo constante; limite de tentativas por IP; escrita aceita só com Origin do próprio site e corpo JSON; exclusão de conta pelo próprio usuário (LGPD).
- **Página:** HTML, CSS e JavaScript sem framework. Tema claro e escuro (segue o sistema até a pessoa escolher), layout de celular com filtros em gaveta e CSP restrita. Todo dado de vaga entra na página como texto, nunca como HTML.

## Rodando

```bash
# coleta
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
pytest
python -m caca_vagas coletar --saida vagas.sql

# site
cd web
npm install
npx wrangler d1 execute caca-vagas --local --file schema.sql
npx wrangler d1 execute caca-vagas --local --file ../vagas.sql
npx wrangler dev
```

Publicação: `npx wrangler pages deploy --branch main` em `web/`. A coleta diária de Gupy, Sólides e InfoJobs roda em `.github/workflows/coleta.yml` (segredos `CLOUDFLARE_API_TOKEN` com edição no D1 e `CLOUDFLARE_ACCOUNT_ID`, variável `COLETA_ATIVA=true`). O Programathor bloqueia os IPs do GitHub, então é coletado por `coletar-diario.bat` no Agendador de Tarefas do Windows. Vaga que nenhuma coleta encontra há 7 dias sai do ar.

## Testes

- `pytest`: parse de cada portal sobre respostas reais gravadas em `tests/amostras` (sem rede), classificação e o SQL gerado, executado contra o mesmo `schema.sql` do site.
- `npx tsc --noEmit` em `web/`.
