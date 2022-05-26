-- This script only contains the table creation statements and does not fully represent the table in the database. 
-- It's still missing: indices, triggers. Do not use it as a backup.

-- Table Definition
CREATE TABLE "terna"."downloaded_measure_files" (
    "nome_file" text NOT NULL,
    "anno" int4,
    "mese" int4,
    "tipologia" text,
    "sapr" text,
    "codice_up" text,
    "codice_psv" text,
    "vers" int4,
    "validazione" text,
    "dispacciato_da" text,
    PRIMARY KEY ("nome_file")
);