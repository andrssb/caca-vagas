# Caça Vagas

Coleta vagas de TI júnior em vários portais, filtra pelo meu perfil e ranqueia pelo encaixe com o meu currículo. A candidatura continua sendo feita por mim, na página da vaga: o sistema resolve a parte cansativa, que é procurar, comparar e lembrar o que já foi visto.

```
coletar (4 portais)  ->  normalizar  ->  filtrar  ->  pontuar  ->  SQLite  ->  painel local
```

## Portais

| Portal | Como é lido |
| --- | --- |
| Gupy | API JSON pública da busca do portal (traz contrato, modalidade e prazo de inscrição) |
| Sólides Vagas | API JSON pública do portal (traz senioridade, contrato e habilidades pedidas) |
| Programathor | HTML da lista de vagas júnior (vagas "Vencida" são descartadas) |
| InfoJobs | HTML da busca por palavra-chave (contrato deduzido do título e do resumo) |

Cada portal vira o mesmo formato (`Vaga`, em `caca_vagas/modelo.py`). As requisições são sequenciais, com pausa entre elas, no ritmo de uma pessoa navegando. Se um portal falhar, os outros continuam.

Indeed e Glassdoor ficaram de fora: os dois bloqueiam leitura automatizada.

## Filtro

Tudo é configurado em `perfil.toml`:

- **Área:** o título precisa ser de desenvolvimento, sistemas ou dados.
- **Nível:** recusa pleno, sênior, especialista, estágio e aprendiz. "Júnior/Pleno" passa, porque o júnior explícito vence. "PL/SQL" não é confundido com pleno.
- **Local:** remoto de qualquer lugar; presencial ou híbrido só em BH e região metropolitana.
- **Contrato:** CLT ou PJ (CLT ganha bônus na nota). Vaga sem contrato informado passa com aviso.
- **Data:** o prazo de inscrição, quando existe, vale mais que a data de publicação.
- **Vaga afirmativa:** não é recusada, mas aparece com aviso para conferir o público.

Toda recusa tem motivo, e o resumo da coleta mostra quantas vagas caíram em cada um.

## Nota de encaixe (0 a 100)

- até 60 pontos pelas habilidades do perfil citadas na vaga, com pesos e sinônimos (`node.js|nodejs|node`). O painel mostra com quais habilidades a vaga bate, o que ajuda a ajustar o currículo para cada candidatura;
- +15 se o título diz júnior;
- +10 se o contrato CLT é confirmado;
- +8 se o local é remoto ou em BH;
- +7 se a vaga foi publicada nos últimos 3 dias (+4 até 7 dias).

## Uso

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

python -m caca_vagas coletar            # todos os portais
python -m caca_vagas coletar --fontes gupy,solides
python -m caca_vagas listar --top 20    # as melhores no terminal
python -m caca_vagas painel             # http://127.0.0.1:8000
```

Para coletar todo dia sozinho, o `coletar-diario.bat` pode ser agendado no Agendador de Tarefas do Windows. A saída de cada coleta fica em `dados/coleta.log`.

No painel, o título abre a vaga no portal. Depois de se candidatar, o botão **Candidatei** tira a vaga da lista; **Descartar** tira sem candidatura. Coletar de novo nunca apaga esse status, então uma vaga descartada não volta como nova.

## Testes

```bash
pytest
```

Os testes de parse rodam sobre respostas reais gravadas em `tests/amostras`, sem rede. Os de filtro e nota cobrem os casos que já deram problema: Java contra JavaScript, PL/SQL, "Júnior / Estagiário", prazo contra data de publicação.

## Estrutura

```
caca_vagas/
  fontes/        um módulo por portal: coletar() com rede e parse() puro
  modelo.py      formato comum da vaga e normalização de texto
  filtros.py     aceita ou recusa, sempre com motivo
  ranking.py     nota de encaixe
  banco.py       SQLite com histórico e status
  coleta.py      orquestra fontes, filtro, nota e banco
  painel.py      painel local em FastAPI
perfil.toml      termos de busca, filtros e habilidades com peso
```
