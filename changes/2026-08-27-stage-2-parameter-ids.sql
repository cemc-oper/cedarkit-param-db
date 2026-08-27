-- Stage 2 schema migration.  The accompanying accepted T2-01 inventory is
-- the audited, explicit source of the 221 UPDATE values applied to the
-- released SQLite artifact.  SQLite cannot add a NOT NULL UNIQUE column to
-- a populated table, so those constraints are enforced by the v2 init schema
-- and by the migration checker after this structural step.
CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO schema_meta (key, value) VALUES ('schema_version', '2');
ALTER TABLE entries ADD COLUMN parameter_id TEXT;
ALTER TABLE variants ADD COLUMN parameter_id TEXT;
CREATE UNIQUE INDEX idx_entries_parameter_id ON entries(parameter_id);
CREATE UNIQUE INDEX idx_variants_parameter_id ON variants(parameter_id);
CREATE TABLE parameter_id_tombstones (
    parameter_id TEXT PRIMARY KEY,
    retired_reason TEXT NOT NULL
);
