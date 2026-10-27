-- 27/10/2026: vagas por fonte em cada coleta, para avisar quando um portal quebra.
ALTER TABLE coletas ADD COLUMN por_fonte TEXT;
