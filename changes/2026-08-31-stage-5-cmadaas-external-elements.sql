-- Stage 5 T5-02: run once against a schema-v2 database, then import the
-- canonical vocabulary with the CLI.  Review this text, not SQLite bytes.
PRAGMA foreign_keys = ON;
BEGIN;
CREATE TABLE external_elements (
    namespace TEXT NOT NULL CHECK (namespace GLOB '[a-z][a-z0-9_-]*'),
    code TEXT NOT NULL CHECK (code GLOB '[A-Z][A-Z0-9_]*'),
    description_cn TEXT NOT NULL CHECK (length(trim(description_cn)) > 0),
    source_ref TEXT NOT NULL CHECK (length(trim(source_ref)) > 0),
    PRIMARY KEY (namespace, code)
);
CREATE TABLE entry_external_elements (
    entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    namespace TEXT NOT NULL,
    code TEXT NOT NULL,
    PRIMARY KEY (entry_id, namespace),
    UNIQUE (namespace, code),
    FOREIGN KEY (namespace, code) REFERENCES external_elements(namespace, code) ON DELETE RESTRICT
);
CREATE INDEX idx_entry_external_elements_code ON entry_external_elements(namespace, code);
UPDATE schema_meta SET value = '3' WHERE key = 'schema_version';
COMMIT;

-- After importing the vocabulary, these five manually reviewed mappings are
-- the only initial mappings.  Never insert variants into this table.
INSERT INTO entry_external_elements(entry_id, namespace, code)
SELECT id, 'cmadaas', 'TEM' FROM entries WHERE parameter_id = 'cedarkit.t';
INSERT INTO entry_external_elements(entry_id, namespace, code)
SELECT id, 'cmadaas', 'GPH' FROM entries WHERE parameter_id = 'cedarkit.h.any';
INSERT INTO entry_external_elements(entry_id, namespace, code)
SELECT id, 'cmadaas', 'WIU' FROM entries WHERE parameter_id = 'cedarkit.u';
INSERT INTO entry_external_elements(entry_id, namespace, code)
SELECT id, 'cmadaas', 'WIV' FROM entries WHERE parameter_id = 'cedarkit.v';
INSERT INTO entry_external_elements(entry_id, namespace, code)
SELECT id, 'cmadaas', 'PRE' FROM entries WHERE parameter_id = 'cedarkit.rain.any';
