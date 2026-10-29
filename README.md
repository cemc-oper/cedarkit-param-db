# cedarkit-param-db

Schema-4 SQLite authoring for CedarKit parameter definitions, aliases, backend mappings, shared translation tables and evidence references. Python 3.11+ is required. Business validation is shared with `cedarkit-query`; this package does not depend on reki, ecCodes, xarray or a service client.

Stage 1.1 separates `cedarkit.parameters/v1` and `cedarkit.mappings/v1` resources. Product catalogs and populations remain independently maintained by I04. The root `cedarkit_param.db` is the preserved **schema-3 migration input**, not a schema-4 working database. Every CLI operation requires an explicit `--db`; nothing upgrades the root file automatically.

## Start from the preserved legacy input

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

The new copy supports distinct unreviewed, evidence-gap, resolved and evidenced non-applicable outcomes. Unknowns remain unresolved; changed proof or definitions require reassessment. See [review outcomes and non-applicability](docs/migration-v4.md#evidence-bearing-non-applicability).

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

Tests use self-contained fixtures and a frozen legacy schema; they do not skip because another workspace repository is absent. I03 records the first-round baseline under `migrations/stage1.1-i03/` and the continued parameter review under `migrations/stage1.1-i03-review-2/`, with stage evidence indexed in `doc/2026-10-13-stage1.1-query-reki/evidence/I03/` at workspace level. These results do not exercise backend decoding, online services, frontend adaptation or I10 cross-package acceptance.
