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

## Explicit finite mapping slices

`export_mapping_slice(db_path, out_dir, mapping_resource_ids, *, parameter_resource_id, version)` exports explicitly selected **whole** mapping resources with reviewed parameter/parent/statistical-object closure. Selection must be nonempty, known and evidence-bearing; definitions must have current resolved reviews. The parameter resource identity must differ from the full database resource. Mapping resource IDs, revisions, native restrictions and tables are retained. This is a Python authoring API; the full-export CLI gate is unchanged.

The manifest/browser scope uses `kind: parameter_mappings`, lists requested IDs and dependencies, and records `runtime_mappings: true`, `complete_product_coverage: false` and all remaining selected backend obligations. A finite, independently established encoding interpretation can therefore be handed to an explicit-file reader while whole-backend product coverage remains open. This does not resolve those obligations or turn missing product versions into universal product applicability. Do not attach the slice to an I04 product without its exact product/source evidence.

The 2026-10-29 example is [the grib_util v12.6 review](../migrations/stage1.1-i03-grib-util-v12.6/README.md): 7 definition corrections, 14 native-profile mappings, 19 dependency-closed exported definitions, and continued full-export refusal. Original producer include/binary evidence supersedes conflicting legacy GRIB facts only where the quantity, unit and conditions are established; contradictory producer descriptions and service meanings stay under review.

For recovery, keep the original database, old YAML/browser snapshots and old package combination intact. The review copy is disposable only after its reports/decisions are preserved. Reproduce it by creating a fresh path from the fixed source and replaying source-bound reviewed decisions, then compare reports and exported bytes. Do not overwrite the unique legacy input or mix a new parameter slice with old runtime mappings as a deployment. I04/I07/I10 own their later integration and release steps.

## Continued reviews and explicit assessment states

`copy_review(source, destination)` / CLI `--db <new-path> copy-review --source-db <previous-schema4-copy>` creates a separate review copy and installs the additive `review.sql` assessment table. It preserves the previous database and its decisions. The database version stays 4; no runtime parameter, mapping or browser format changes. Old review databases remain readable, while new non-final assessments should be written only to an explicitly prepared copy.

Reports distinguish `unreviewed`, `needs_evidence`, `resolved`, `not_applicable` and `needs_reassessment`. `needs_evidence` is an actual inspection conclusion with a precise missing fact and owner, not a synonym for a queue of unaudited records. Use a decision with `outcome: needs_evidence`, `missing_input` and `owner_tasks`, plus the usual identity/aspect/explanation/evidence. It remains unresolved and blocks the affected export. Assessments are append-only authoring history. A later factual resolution can close the same issue without erasing the preceding inspection.

A normal definition/mapping decision may explicitly use `outcome: resolved`, or retain the first-round spelling without outcome. The tool records source and effective-definition fingerprints. Current exports recheck stored resolutions, definition/object dependencies and actual mapping references; an arbitrary non-null SQL flag is insufficient. Edited definitions, changed inherited meaning or invalid proof cause `needs_reassessment`. Full export still checks quarantined and missing identities independently.

## Evidence-bearing non-applicability

Only backend obligations can use `outcome: not_applicable`. It cannot close an unknown definition or contain a fabricated mapping. It requires the usual explanation/nonempty evidence and an `applicability` object:

- `reason`: exactly `definition_only`, `outside_stage_scope` or `not_provided`.
- `scope`: exactly `{stage: "1.1", backend: "grib2" | "cmadaas", extent: "all_required_products"}`, matching the obligation. A single-product, partial or unknown scope cannot close a whole-backend obligation.
- `documents`: nonempty `{path, sha256}` references to actual locally available supporting material. Paths are absolute authoring locators; SHA256 checks actual bytes. They are not runtime dependencies or copied into runtime resources.
- For `definition_only`, `used_by` lists exact existing parameters whose effective statistics actually reference this object. The cited material must independently establish that the object is not separately published; the mere existence of an `of` reference is insufficient factual justification.
- For `outside_stage_scope`, `excluded_scope` is `gfs_gda` or `odb_observation`, the already confirmed exclusions. Evidence must establish that this identity/backend obligation lies exclusively in that exclusion; a shared parameter also used in required products cannot be excluded merely because GDA uses it.
- For `not_provided`, `products` lists exact dataset/product/product_version objects for the independently established complete mandatory scope. The evidence must establish both completeness and non-provision, not simply fail to list a parameter.

Only current reviewed definitions and dependencies permit such closure. Missing/changed evidence bytes or effective definitions invalidate the disposition and block full export again. `unknown`, `unsupported`, missing samples and absence of a service code are not accepted reasons. These mechanical checks validate the decision structure, retained dependencies and evidence bytes; they cannot establish that a cited document actually supports the claim. Factual adequacy remains the reviewer's explicit responsibility under Q17/Q20.

Accepted non-applicability appears separately in the full export's manifest/browser scope as parameter/backend/reason, complete scope and evidence hashes. No runtime mapping is synthesized and no absolute evidence path leaks into the runtime bundle. This is closure of an audited migration obligation, not proof of backend support or business acceptance. In the actual second-round I03 review, no candidate had sufficient full-scope evidence for non-applicability, so no such actual disposition was created.
