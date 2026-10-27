-- 27/10/2026: alerta de vaga nova por e-mail.
ALTER TABLE vagas ADD COLUMN descoberta_em TEXT;
-- As vagas que já estavam no ar não contam como novas no primeiro e-mail.
UPDATE vagas SET descoberta_em = '2026-10-27T00:00:00Z' WHERE descoberta_em IS NULL;
CREATE TABLE IF NOT EXISTS alertas (
    usuario_id   INTEGER PRIMARY KEY REFERENCES usuarios (id) ON DELETE CASCADE,
    filtros      TEXT NOT NULL,
    token        TEXT NOT NULL UNIQUE,
    confirmado   INTEGER NOT NULL DEFAULT 0,
    criado_em    TEXT NOT NULL,
    ultimo_envio TEXT
);
