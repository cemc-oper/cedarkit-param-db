# Schema-4 authoring and export contract

`schema_meta.schema_version=4` is authoritative. `PRAGMA user_version` is not used as a second version source. All connections enable foreign keys. Read-only inspection uses SQLite URI `mode=ro` and `query_only=ON`; reads do not create absent databases. `init_db` exclusively creates a new file.

The parameter database owns one effective parameter resource and any explicitly identified mapping resources. `parameter_resources` and `mapping_resources` store independent IDs/revisions; mappings also store backend. Parameters are flat, with stable primary IDs, ordinary parent foreign keys, optional units/descriptions and local fixed-condition JSON. Aliases reference the unified parameter table. SQL NULL means an optional column was undeclared; input JSON null is rejected before insertion, and export omits SQL NULL.

Mapping identity is `(resource_id, id)`. Translation tables are `(resource_id, id)` and rows `(resource_id, table_id, id)`. Evidence references have owner foreign keys and local uniqueness. No GRIB triple, service code, short name, or native table key has a global uniqueness constraint. Shared semantic validation detects actual contradictions, while different proven product scopes can reuse native codes.

The statistical object reference and mapping table references are automatically generated SQLite columns derived from JSON; users never maintain duplicate references. Parent, object, mapping and table references prevent deletion of active targets. Imports may list children before parents. The final transaction view is checked for deferred foreign keys and with the shared resource validator, including combined parent/object cycles and inherited constraints.

Retiring an unreferenced parameter removes its active row and aliases/notes, then records an ID tombstone in the same transaction. Reuse, removal or renaming of tombstone occupancy is rejected. Stable active IDs cannot be renamed; an incompatible new meaning requires a new identity and explicit retirement. Quarantined legacy IDs are separately reserved until an evidence-bearing definition review restores them. Historical raw records survive those operations.

`migration_sources`, `migration_records`, `migration_issues` and `parameter_reservations` are authoring/audit data, not runtime definitions. Full legacy payloads preserve all original fields and auxiliary tables. Pending facts use existing G17 IDs and task ownership. No catalog, populations, connection endpoint, credentials or service client is stored as an operational resource.

`transaction(db_path)` exposes SQL within `BEGIN IMMEDIATE`, validates the final full resource set, then commits. It rolls back on validation, SQL or caller failures. A partially reviewed migration copy may be internally consistent but is prohibited from full export. Removing an issue by unsupported manual SQL is not an evidenced migration decision.

Export uses a read transaction for the whole resource group and browser annotations. It sorts parameters by stable ID, resources/tables/mappings/rows by their scoped IDs, and alias/evidence sets lexically. Declared arrays inside conditions are retained unless the shared canonical fixed-condition normalization already specifies their semantics; no generic array sorting can alter paired or ordered data. JSON object keys are sorted, Unicode is retained, indentation is two spaces, and files end with a newline. YAML is a separate deterministic serialization of the same document. Actual file bytes are hashed; formats can have different hashes. Editorial notes occur only in browser data, never in runtime parameter/mapping files.

Exports stage all files privately, parse/validate them and compare them to the consistent source documents, verify their actual byte hashes, then rename the new directory as one group. A failure removes staging and leaves existing output untouched. Paths in manifests are relative bundle filenames. Resource content revisions must be deliberately updated when semantic content changes; the exporter neither chooses latest nor changes versions automatically. The I10 publication process must enforce immutability of distributed resource revisions across releases.

## Browser params.json contract 4

The generated browser envelope has:

- `meta`: `schema_version: 4`, `generated_by: cedarkit-param-db`, explicit `scope`, exact `parameter_resource` format/ID/version and counts for parameters, aliases and mappings.
- `parameters`: the flat local definitions from the same validated parameter resource, including parent IDs; no manually duplicated effective definition tree.
- `mapping_resources`: full new mapping resources, each with backend, scope, translation configuration, shared tables and evidence; empty for an explicitly definition-only slice.
- `retired_ids`: sorted records with `parameter_id` and `retired_reason`.
- `notes`: sorted editorial `parameter_id`, optional `remark` and original `updated_at`, only for displayed parameters.

For a full database export, `scope.kind=database_resources` and `parameter_ids` is the exact exported list. A definition slice has `kind=parameter_definitions`, requested IDs, the dependency-closed parameter IDs, and `runtime_mappings=false`. Neither scope is a product coverage denominator. Old `entries/variants/key` structure is absent. I07 must adapt its TypeScript types and pages to these generated files; this task does not overwrite `public/params.json` or claim that the old UI already consumes contract 4.

The separate manifest records scope, internal-validation limits, per-file actual size and SHA256, and runtime resource format/ID/version or browser schema version. A catalog is never generated here. Product-dependent references, populations/methods, interface capability and actual values remain I04/I06/I09 responsibilities.
