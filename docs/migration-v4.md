# Explicit legacy migration and review

Supported offline inputs are a checkpointed schema-3 SQLite database or an explicitly versioned `reki.parameter-registry/v3` JSON/YAML snapshot. The source remains at its original path, opened read-only. The tool records and rechecks its actual SHA256. A distinct, nonexistent destination is required. Unknown versions fail; the current exporter never converts legacy resources at runtime.

Database migration retains all source tables as audit JSON, plus a per-identity raw record, original aliases, parent association, native key, service codes, predicate classifications and metadata. Snapshot migration retains its complete source document; it cannot invent omitted vocabulary, tombstones or timestamps. Native triple and inherited external code information is not a runtime binding.

The finite migration vocabulary translates explicit old predicates only: known boundary types, explicit numeric levels and complete physical intervals, and known time operations. Old pressure values already represent hPa in the old shared metadata adapter, while declared heights/depths are meters. The source meanings and applicable conversion boundary are recorded in the I03 handoff. Canonical depth bottom is the deeper endpoint. Informational `typeOfLevel/level` values never add a business restriction. Unknown types/keys remain open facts. `time_range_hours` stays pending because a duration does not prove anchoring. No new GRIB decoder or CMADaaS rule executes during migration.

Every migrated definition initially requires factual review, even if its draft passes structural validation. The tool also records per-identity GRIB scope/translation needs and service mapping needs when old parent codes exist. These rows are migration bookkeeping, not business product counts. Conflicting definitions are quarantined and their IDs reserved. The report explicitly distinguishes raw identity preservation, internally consistent active drafts, quarantined definitions and unverified mappings.

Review input is a local JSON/YAML object with exactly `source_sha256` and nonempty `decisions`. Every decision has `parameter_id`, `aspect`, factual `explanation` and a nonempty `evidence` reference list. Decisions are transactional, duplicate-safe, source-bound and cannot close already resolved or nonexistent issues.

For a definition decision, supply the entire local `definition` and preserve its stable ID, name and registered aliases. Parent changes require an explicit evidenced definition and remain visible in the migration diff. A reviewer must establish whether the definition is intentionally broad, which fixed semantics are present, and whether a concrete statistical period/method is required. Copying a structurally valid draft without that review is not evidence. Example shape, with placeholder digest and references that must be replaced by actual inputs:

```json
{
  "source_sha256": "<actual source file SHA256>",
  "decisions": [
    {
      "parameter_id": "example.t",
      "aspect": "definition",
      "explanation": "The cited definition establishes this intentionally broad temperature identity and unit; it introduces no fixed time statistic.",
      "evidence": ["<independent definition reference>"],
      "definition": {"parameter_id": "example.t", "name": "t", "unit": "K"}
    }
  ]
}
```

For a GRIB2 or CMADaaS decision, `aspect` is the backend name and `mapping_ids` lists exact `{resource_id, id}` references to existing mappings for that same parameter/backend. Definitions cannot appear in such a decision. A note about a future mapping does not resolve the issue. Actual mappings/tables can be added using `insert_mappings(conn, resource)` inside `transaction(db_path)` after obtaining their independent scope and interpretation facts; use a new resource ID, or edit an existing resource deliberately with SQL and its explicit revision. The final complete resource set is shared-validated before commit. Missing product versions must never be represented as unrestricted applicability.

Full export is allowed only after all pending migration facts are resolved. A reviewed definition-only slice is a different, explicit contract: exact requested IDs plus parent/object closure, a distinct resource identity/revision, no runtime mappings, and a manifest stating that boundary. It cannot skip a pending selected definition, substitute a broader parent, or manufacture a valid native binding. Supplying its JSON to I04 gives usable parameter structure; it does not close mapping or coverage work.

For recovery, keep the original database, old YAML/browser snapshots and old package combination intact. The review copy is disposable only after its reports/decisions are preserved. Reproduce it by creating a fresh path from the fixed source and replaying source-bound reviewed decisions, then compare reports and exported bytes. Do not overwrite the unique legacy input or mix a new parameter slice with old runtime mappings as a deployment. I04/I07/I10 own their later integration and release steps.
