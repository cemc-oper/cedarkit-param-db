# cedarkit-param-db

Schema-4 SQLite authoring for CedarKit parameter definitions, aliases, backend mappings, shared translation tables and evidence references. Python 3.11+ is required. Business validation is shared with `cedarkit-query`; this package does not depend on reki, ecCodes, xarray or a service client.

Stage 1.1 separates `cedarkit.parameters/v1` and `cedarkit.mappings/v1` resources. Product catalogs and populations remain independently maintained by I04. The root `cedarkit_param.db` is the preserved **schema-3 migration input**, not a schema-4 working database. Every CLI operation requires an explicit `--db`; nothing upgrades the root file automatically.

## Current authoring entry

The maintained state now contains 227 mappings and 226 active parameters after
the first directional clear-sky radiation energy review. Legacy definitions are
130 resolved / 91 needs_evidence; 424 legacy obligations and 10 additional
variant backend obligations remain open. GFS adds only surface energy integrals
at leads 0/6h. TUSWC is restored as an authoring definition without a runtime
product binding. See the [current review](authoring/reviews/surface-radiation.json).

The maintained authoring source is the complete, stable text checkpoint in
[`authoring/state/`](authoring/state/manifest.json), configured by
[`authoring/current.json`](authoring/current.json). Its 18 JSONL tables retain
all stored database values, including legacy payloads, review history, unresolved
issues, reservations, tombstones and evidence. Generated columns and all schema
constraints/triggers are rebuilt from the packaged schema. Additional variant
reviews remain in [`definition-reviews.json`](authoring/definition-reviews.json).
The local `authoring/review-schema4.db` is ignored generated state, not the source
for default exports. The schema-3 root input remains unchanged.

```bash
uv sync --extra test
uv run python tools/authoring.py build --db /tmp/cedarkit-review.db
uv run python -m cedarkit_param_db --db /tmp/cedarkit-review.db migration-report
uv run python tools/authoring.py export --out-dir /tmp/cedarkit-current-export
uv run python tools/authoring.py export --system geps --out-dir /tmp/cedarkit-geps-export
```

Default export validates the complete text checkpoint and builds one temporary
SQLite database for the entire selected group. It ignores an absent or stale
local database. Every table file must match its manifest SHA256 and row count;
full resource validation, foreign keys, schema identity and exact cell roundtrip
are checked. Bad text fails without falling back to an older database. All
selected slices must pass before output publication; existing output directories
are refused and temporary databases are removed on success or failure.

Make reviewed changes to a new temporary candidate through `transaction` and
source-bound review APIs, then save the complete reviewed state back to text:

```bash
uv run python tools/authoring.py capture --db /tmp/cedarkit-review.db
uv run python tools/authoring.py export --out-dir /tmp/cedarkit-reviewed-export
```

`capture` publishes a complete replacement text directory after validating the
candidate; it restores the previous source if publication fails. Use
`capture --db <candidate> --out-dir <new-directory>` for a separate text candidate.
An explicit `export --db <candidate>` retains the single SQLite backup path,
including committed WAL data. Record stable IDs, old/new values, applicability,
evidence positions and hashes, and intentional resource revisions in the small
review records. Commit text and review changes together. Do not commit generated
SQLite files or create per-session migration trees. See the
[authoring workflow](authoring/README.md).

## Historical evidence and migration tools

The former 13 complete migration directories have been relocated byte-for-byte
to the workspace [archive and SHA index](../../doc/archives/cedarkit-param-db/stage1.1-migrations/README.md).
The small relative links under `migrations/` retain historical evidence locators
and replay inputs. They are compatibility paths, not current authoring inputs.
Historical scripts remain unchanged evidence; new exports use `tools/authoring.py`.

```bash
uv run python tools/authoring.py check-archive
uv run python tools/authoring.py resolve data/cedarkit-param-db/migrations/stage1.1-i03-grib-util-v12.6/review-schema4.db
```

Archive resolution verifies both the index and payload SHA256, including a
`#sha256=<digest>` locator when supplied. The workspace archive is required only
for historical lookup/replay; current exports require just the authoring
text/configuration and package dependencies. Full reports and temporary
exports belong in workspace evidence, not the repository. `migrations/` is
reserved for actual upgrade sources and the existing compatibility links.

## Start a migration from the preserved legacy input

Run from this project directory. All example output paths must be new; the tools refuse replacement.

```bash
uv sync --extra test
uv run python -m cedarkit_param_db --db /tmp/cedarkit-review.db migrate-v3 --source-db cedarkit_param.db --report /tmp/cedarkit-migration-report.json
uv run python -m cedarkit_param_db --db /tmp/cedarkit-review.db migration-report
```

`migrate-v3 --source-snapshot <file>` explicitly accepts identified `reki.parameter-registry/v3` JSON/YAML snapshots. Unknown versions, duplicate keys, unsafe YAML and nonfinite values fail. Snapshot migration cannot recover tombstones or editorial data absent from the snapshot; a full database source preserves all legacy tables, including vocabulary and retired identities. A database with a journal must first be supplied as a stable checkpointed copy.

Migration preserves IDs, names, aliases and old parent associations. Explicit old predicates produce draft canonical conditions. Informational type/level fields are retained in the audit and never promoted to fixed business conditions. Description boundary whitespace is trimmed with an exact before/after audit; identity and unit strings are not silently repaired. A statistical window length does not establish trailing versus since-initialization semantics. Native triples and service codes remain audit facts until their product applicability and interpretation have evidence; missing applicability never becomes `{}`.

The review database reserves IDs for definitions rejected by shared validation, retaining the complete failed draft and diagnostic. It does not rewrite parent or units to make a conflict pass. Other draft definitions also require evidence-bearing review before export. **A successful migration command creates a review copy; it does not mean the full migration or product coverage is complete.**

## Continue an existing review

```bash
uv run python -m cedarkit_param_db --db /tmp/cedarkit-review-next.db copy-review --source-db /path/to/previous-schema4-review.db
```

The new copy supports distinct unreviewed, evidence-gap, resolved and evidenced non-applicable outcomes. Unknowns remain unresolved; changed proof or definitions require reassessment. A new destination protects the source during the operation; it does not require retaining a new full snapshot in Git after every conversation. See [review outcomes and non-applicability](docs/migration-v4.md#evidence-bearing-non-applicability).

## Review and export

See [review decisions](docs/migration-v4.md) for source-bound resolutions. There is no blanket ignore-errors or accept-all switch. Definition review preserves stable ID, name and aliases; an explicitly evidenced parent correction is recorded as a difference. Mapping review must reference actual mappings for that identity/backend.

```bash
uv run python -m cedarkit_param_db --db /tmp/cedarkit-review.db review --decisions /path/to/reviewed-decisions.json
uv run python -m cedarkit_param_db --db /tmp/cedarkit-review.db export --out-dir /tmp/cedarkit-reviewed-bundle
```

Full export fails while any migration issue is unresolved. A fully evidenced, current backend non-applicability decision can close an obligation without inventing a mapping; unsupported or unknown scope cannot. For a reviewed **definition-only** slice, specify its exact IDs and a distinct resource identity:

```bash
uv run python -m cedarkit_param_db --db /tmp/cedarkit-review.db export-definitions --parameter-id cedarkit.t2m --resource-id cedarkit.temperature-definitions --version 1 --out-dir /tmp/cedarkit-definition-slice
```

The slice includes parent/statistical-object dependencies, checks their definition reviews, and explicitly declares `runtime_mappings: false`. It contains parameter JSON/YAML, browser `params.json` contract 4, and a byte-hash manifest. It never silently drops unresolved selected definitions or publishes unverified native bindings. This narrow export does not satisfy full migration or business acceptance.

For an independently evidenced finite encoding slice, the Python
`export_mapping_slice` API exports whole selected mapping resources and reviewed
parameter dependency closure. Its manifest keeps remaining backend obligations
and explicitly states `complete_product_coverage: false`; full export remains
blocked. See [the scope contract](docs/migration-v4.md#explicit-finite-mapping-slices)
and [the grib_util v12.6 first review](migrations/stage1.1-i03-grib-util-v12.6/README.md).

A fully resolved bundle contains parameter JSON/YAML, independent mapping JSON/YAML for each stored resource, browser contract 4, and the manifest. Exports use one consistent database view, validate the complete resource combination through `cedarkit-query`, validate staged bytes, and atomically rename the entire new output directory. Existing bundles are not overwritten. No export time, machine path or database row number enters runtime resources. Explicit content revisions are stored per resource; repeated export does not increment them. Publishing an already distributed identity/version with changed content remains forbidden.

## Initialize and edit new resources

```bash
uv run python -m cedarkit_param_db --db /tmp/new-authoring.db init
uv run python -m cedarkit_param_db --db /tmp/new-authoring.db import --parameters /path/to/parameters.json --mappings /path/to/grib2.json --mappings /path/to/cmadaas.json
```

Import initializes an empty schema-4 database atomically and accepts only new resource formats. Edits use `transaction(db_path)` with ordinary SQL; it validates the final resource set and derived references before committing. Failures roll back the entire transaction. Direct SQL maintenance is still fully checked on export. `retire_parameter` refuses referenced identities and preserves permanent retired-ID occupancy.

See [storage and export contract](docs/schema-v4.md) for tables, reference constraints, deterministic ordering, browser data and downstream responsibilities. Legacy YAML exports, vocabulary-to-entry inventory and automatic parent-code inheritance are removed; old formats are read only by the explicit offline migrator.

## Verification

```bash
uv run pytest -q
uv build
```

Tests use self-contained fixtures and a frozen legacy schema; they do not skip because another workspace repository is absent. Historical I03 baselines live in the workspace archive and remain reachable through compatibility links. Current-state export and archive-integrity tests use isolated fixtures. Stage evidence is indexed in `doc/2026-10-13-stage1.1-query-reki/evidence/I03/` at workspace level. These results do not exercise backend decoding, online services, frontend adaptation or I10 cross-package acceptance.
