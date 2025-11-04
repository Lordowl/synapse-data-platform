-- Aggiunge colonne anno, settimana, mese alla tabella publication_logs
-- Per tracciare il periodo di riferimento delle pubblicazioni

ALTER TABLE publication_logs ADD COLUMN anno INTEGER;
ALTER TABLE publication_logs ADD COLUMN settimana INTEGER;
ALTER TABLE publication_logs ADD COLUMN mese INTEGER;
