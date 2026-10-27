-- Schema 4: business identities and scoped mappings; no product catalog.
-- cedarkit-query validates business semantics before transaction commit/export.
PRAGMA foreign_keys = ON;
CREATE TABLE schema_meta (key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL);
INSERT INTO schema_meta VALUES ('schema_version', '4');
CREATE TABLE parameter_resources (
 id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(id)) > 0),
 version TEXT NOT NULL CHECK (version NOT GLOB '*[^0-9]*' AND version GLOB '[1-9]*')
);
CREATE TABLE mapping_resources (
 id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(id)) > 0),
 version TEXT NOT NULL CHECK (version NOT GLOB '*[^0-9]*' AND version GLOB '[1-9]*'),
 backend TEXT NOT NULL CHECK (backend IN ('grib2','cmadaas')), UNIQUE(id,backend)
);
CREATE TABLE parameters (
 parameter_id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(parameter_id)) > 0),
 resource_id TEXT NOT NULL REFERENCES parameter_resources(id) ON DELETE RESTRICT,
 name TEXT NOT NULL CHECK (length(trim(name)) > 0),
 parent TEXT REFERENCES parameters(parameter_id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
 unit TEXT CHECK (unit IS NULL OR length(trim(unit)) > 0),
 description TEXT, description_cn TEXT,
 fixed_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(fixed_json) AND json_type(fixed_json)='object'),
 -- Derived from JSON, never separately maintained.
 object_id TEXT GENERATED ALWAYS AS (json_extract(fixed_json,'$.statistics.of.parameter_id')) STORED
   REFERENCES parameters(parameter_id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
 CHECK (parent IS NULL OR parent <> parameter_id)
);
CREATE TABLE aliases (
 parameter_id TEXT NOT NULL REFERENCES parameters(parameter_id) ON DELETE RESTRICT,
 alias TEXT NOT NULL CHECK (length(trim(alias)) > 0), PRIMARY KEY(parameter_id,alias)
);
CREATE TABLE parameter_notes (
 parameter_id TEXT PRIMARY KEY NOT NULL REFERENCES parameters(parameter_id) ON DELETE RESTRICT,
 remark TEXT, updated_at TEXT
);
CREATE TABLE parameter_id_tombstones (
 parameter_id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(parameter_id)) > 0),
 retired_reason TEXT NOT NULL CHECK (length(trim(retired_reason)) > 0)
);
CREATE TRIGGER reject_retired_insert BEFORE INSERT ON parameters
WHEN EXISTS(SELECT 1 FROM parameter_id_tombstones WHERE parameter_id=NEW.parameter_id)
BEGIN SELECT RAISE(ABORT,'retired parameter ID cannot be reused'); END;
CREATE TRIGGER reject_retired_update BEFORE UPDATE OF parameter_id ON parameters
WHEN EXISTS(SELECT 1 FROM parameter_id_tombstones WHERE parameter_id=NEW.parameter_id)
BEGIN SELECT RAISE(ABORT,'retired parameter ID cannot be reused'); END;
CREATE TRIGGER reject_live_retirement BEFORE INSERT ON parameter_id_tombstones
WHEN EXISTS(SELECT 1 FROM parameters WHERE parameter_id=NEW.parameter_id)
BEGIN SELECT RAISE(ABORT,'remove active references before retirement'); END;
CREATE TRIGGER reject_live_tombstone_update BEFORE UPDATE OF parameter_id ON parameter_id_tombstones
WHEN EXISTS(SELECT 1 FROM parameters WHERE parameter_id=NEW.parameter_id)
BEGIN SELECT RAISE(ABORT,'active parameter ID cannot be retired'); END;
CREATE TABLE translation_tables (
 resource_id TEXT NOT NULL REFERENCES mapping_resources(id) ON DELETE RESTRICT,
 id TEXT NOT NULL CHECK (length(trim(id)) > 0),
 key_kind TEXT NOT NULL CHECK (key_kind IN ('code','level_type_and_level')),
 applies_json TEXT NOT NULL CHECK (json_valid(applies_json) AND json_type(applies_json)='object'),
 PRIMARY KEY(resource_id,id)
);
CREATE TABLE table_rows (
 resource_id TEXT NOT NULL, table_id TEXT NOT NULL,
 id TEXT NOT NULL CHECK (length(trim(id)) > 0),
 native_json TEXT NOT NULL CHECK (json_valid(native_json) AND json_type(native_json)='object'),
 canonical_json TEXT NOT NULL CHECK (json_valid(canonical_json) AND json_type(canonical_json)='object'),
 PRIMARY KEY(resource_id,table_id,id),
 FOREIGN KEY(resource_id,table_id) REFERENCES translation_tables(resource_id,id) ON DELETE RESTRICT
);
CREATE TABLE mappings (
 resource_id TEXT NOT NULL,
 id TEXT NOT NULL CHECK (length(trim(id)) > 0),
 parameter_id TEXT NOT NULL REFERENCES parameters(parameter_id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
 backend TEXT NOT NULL,
 applies_json TEXT NOT NULL CHECK (json_valid(applies_json) AND json_type(applies_json)='object'),
 when_json TEXT NOT NULL CHECK (json_valid(when_json) AND json_type(when_json)='object'),
 native_json TEXT NOT NULL CHECK (json_valid(native_json) AND json_type(native_json)='object'),
 vertical_table TEXT GENERATED ALWAYS AS (json_extract(native_json,'$.translate.vertical.config.table')) STORED,
 member_table TEXT GENERATED ALWAYS AS (json_extract(native_json,'$.translate.member.config.table')) STORED,
 PRIMARY KEY(resource_id,id),
 FOREIGN KEY(resource_id,backend) REFERENCES mapping_resources(id,backend) ON DELETE RESTRICT,
 FOREIGN KEY(resource_id,vertical_table) REFERENCES translation_tables(resource_id,id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(resource_id,member_table) REFERENCES translation_tables(resource_id,id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE mapping_evidence (
 resource_id TEXT NOT NULL, mapping_id TEXT NOT NULL,
 ref TEXT NOT NULL CHECK (length(trim(ref)) > 0), PRIMARY KEY(resource_id,mapping_id,ref),
 FOREIGN KEY(resource_id,mapping_id) REFERENCES mappings(resource_id,id) ON DELETE RESTRICT
);
CREATE TABLE table_evidence (
 resource_id TEXT NOT NULL, table_id TEXT NOT NULL,
 ref TEXT NOT NULL CHECK (length(trim(ref)) > 0), PRIMARY KEY(resource_id,table_id,ref),
 FOREIGN KEY(resource_id,table_id) REFERENCES translation_tables(resource_id,id) ON DELETE RESTRICT
);
CREATE TABLE row_evidence (
 resource_id TEXT NOT NULL, table_id TEXT NOT NULL, row_id TEXT NOT NULL,
 ref TEXT NOT NULL CHECK (length(trim(ref)) > 0), PRIMARY KEY(resource_id,table_id,row_id,ref),
 FOREIGN KEY(resource_id,table_id,row_id) REFERENCES table_rows(resource_id,table_id,id) ON DELETE RESTRICT
);
-- Audit data is never interpreted as runtime mappings. Historical IDs survive retirement.
CREATE TABLE migration_sources (
 sha256 TEXT PRIMARY KEY NOT NULL CHECK(length(sha256)=64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
 format TEXT NOT NULL,
 payload_json TEXT NOT NULL CHECK(json_valid(payload_json) AND json_type(payload_json)='object')
);
CREATE TABLE migration_records (
 parameter_id TEXT PRIMARY KEY NOT NULL,
 source_sha256 TEXT NOT NULL REFERENCES migration_sources(sha256) ON DELETE RESTRICT,
 legacy_json TEXT NOT NULL CHECK(json_valid(legacy_json) AND json_type(legacy_json)='object')
);
CREATE TABLE migration_issues (
 parameter_id TEXT NOT NULL REFERENCES migration_records(parameter_id) ON DELETE RESTRICT,
 aspect TEXT NOT NULL CHECK(aspect IN ('definition','grib2','cmadaas')),
 gap TEXT NOT NULL CHECK(gap IN ('G17-02','G17-03','G17-05','G17-06')),
 missing_input TEXT NOT NULL CHECK(length(trim(missing_input))>0),
 owner_tasks TEXT NOT NULL CHECK(length(trim(owner_tasks))>0),
 resolution_json TEXT CHECK(resolution_json IS NULL OR (json_valid(resolution_json) AND json_type(resolution_json)='object')),
 PRIMARY KEY(parameter_id,aspect)
);
-- IDs quarantined by shared validation remain occupied, with the complete draft in the audit.
CREATE TABLE parameter_reservations (
 parameter_id TEXT PRIMARY KEY NOT NULL REFERENCES migration_records(parameter_id) ON DELETE RESTRICT,
 reason_json TEXT NOT NULL CHECK(json_valid(reason_json) AND json_type(reason_json)='object')
);
CREATE TRIGGER reject_reserved_insert BEFORE INSERT ON parameters
WHEN EXISTS(SELECT 1 FROM parameter_reservations WHERE parameter_id=NEW.parameter_id)
BEGIN SELECT RAISE(ABORT,'quarantined identity requires explicit definition review'); END;
CREATE TRIGGER reject_reserved_update BEFORE UPDATE OF parameter_id ON parameters
WHEN EXISTS(SELECT 1 FROM parameter_reservations WHERE parameter_id=NEW.parameter_id)
BEGIN SELECT RAISE(ABORT,'quarantined identity requires explicit definition review'); END;
CREATE TRIGGER immutable_parameter_id BEFORE UPDATE OF parameter_id ON parameters
WHEN NEW.parameter_id <> OLD.parameter_id
BEGIN SELECT RAISE(ABORT,'stable identity cannot be renamed; retire and create explicitly'); END;
CREATE TRIGGER keep_retired_identity BEFORE DELETE ON parameter_id_tombstones
BEGIN SELECT RAISE(ABORT,'retired identity occupancy is permanent'); END;
CREATE TRIGGER keep_retired_identity_key BEFORE UPDATE OF parameter_id ON parameter_id_tombstones
WHEN NEW.parameter_id <> OLD.parameter_id
BEGIN SELECT RAISE(ABORT,'retired identity occupancy is permanent'); END;
