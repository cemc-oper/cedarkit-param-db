-- Additive authoring audit storage within schema 4; no runtime resource change.
CREATE TABLE IF NOT EXISTS migration_assessments (
 id INTEGER PRIMARY KEY,
 parameter_id TEXT NOT NULL,
 aspect TEXT NOT NULL,
 source_sha256 TEXT NOT NULL REFERENCES migration_sources(sha256) ON DELETE RESTRICT,
 review_json TEXT NOT NULL CHECK(json_valid(review_json) AND json_type(review_json)='object'),
 definition_sha256 TEXT NOT NULL CHECK(length(definition_sha256)=64),
 FOREIGN KEY(parameter_id,aspect) REFERENCES migration_issues(parameter_id,aspect) ON DELETE RESTRICT
);
