-- Banco do site (Cloudflare D1). A coleta em Python escreve em `vagas` e `coletas`;
-- o Worker escreve em `usuarios`, `sessoes`, `marcacoes`, `alertas` e `tentativas`.
-- O envio diário dos alertas (caca_vagas/alertas.py) só atualiza `alertas.ultimo_envio`.

CREATE TABLE IF NOT EXISTS vagas (
    chave        TEXT PRIMARY KEY,           -- fonte:id no portal
    fonte        TEXT NOT NULL,
    titulo       TEXT NOT NULL,
    empresa      TEXT NOT NULL DEFAULT '',
    url          TEXT NOT NULL,
    cidade       TEXT NOT NULL DEFAULT '',
    uf           TEXT NOT NULL DEFAULT '',
    modalidade   TEXT NOT NULL DEFAULT '',   -- remoto | hibrido | presencial | ''
    contrato     TEXT NOT NULL DEFAULT '',
    niveis       TEXT NOT NULL DEFAULT '',   -- ",junior,pleno," para filtrar com LIKE
    area         TEXT NOT NULL DEFAULT '',
    tecnologias  TEXT NOT NULL DEFAULT '[]', -- JSON
    salario      TEXT NOT NULL DEFAULT '',
    busca        TEXT NOT NULL DEFAULT '',   -- título, empresa e cidade sem acento, para a busca por texto
    publicada_em TEXT,
    prazo        TEXT,
    visto_em     TEXT NOT NULL,              -- último dia em que a coleta encontrou a vaga
    ativa        INTEGER NOT NULL DEFAULT 1,
    descoberta_em TEXT                       -- quando a coleta viu a vaga pela 1ª vez (UTC); base do alerta de vaga nova
);
CREATE INDEX IF NOT EXISTS idx_vagas_ativa_data ON vagas (ativa, publicada_em DESC);

CREATE TABLE IF NOT EXISTS coletas (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    em        TEXT NOT NULL,
    vagas     INTEGER NOT NULL,
    fontes_ok TEXT NOT NULL,
    erros     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usuarios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT NOT NULL UNIQUE,
    senha_hash  TEXT NOT NULL,               -- PBKDF2-SHA256, base64
    sal         TEXT NOT NULL,
    iteracoes   INTEGER NOT NULL,
    tecnologias TEXT NOT NULL DEFAULT '[]',
    criado_em   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessoes (
    token_hash TEXT PRIMARY KEY,             -- SHA-256 do token do cookie; o token em si não fica no banco
    usuario_id INTEGER NOT NULL REFERENCES usuarios (id) ON DELETE CASCADE,
    expira_em  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS marcacoes (
    usuario_id INTEGER NOT NULL REFERENCES usuarios (id) ON DELETE CASCADE,
    chave      TEXT NOT NULL,
    status     TEXT NOT NULL CHECK (status IN ('candidatei', 'descartada')),
    em         TEXT NOT NULL,
    PRIMARY KEY (usuario_id, chave)
);

-- Um alerta por conta: os filtros da busca, guardados como a query string da página.
-- Só recebe e-mail depois de confirmar pelo link, para ninguém cadastrar o e-mail de outra pessoa.
CREATE TABLE IF NOT EXISTS alertas (
    usuario_id   INTEGER PRIMARY KEY REFERENCES usuarios (id) ON DELETE CASCADE,
    filtros      TEXT NOT NULL,
    token        TEXT NOT NULL UNIQUE,      -- vai nos links de confirmar e de cancelar
    confirmado   INTEGER NOT NULL DEFAULT 0,
    criado_em    TEXT NOT NULL,
    ultimo_envio TEXT                       -- vagas descobertas depois disso entram no próximo e-mail
);

-- Limite de tentativas de login e cadastro por IP.
CREATE TABLE IF NOT EXISTS tentativas (
    ip TEXT NOT NULL,
    em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tentativas ON tentativas (ip, em);
