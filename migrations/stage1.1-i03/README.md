# Stage 1.1 I03 migration working artifacts

Date: 2026-10-27. **Partial migration: I03 remains in progress.** These are authoring/review artifacts and a narrowly reviewed parameter-definition export, not a production resource replacement.

| File | Purpose |
|---|---|
| [legacy-schema3.db](legacy-schema3.db) | Exact preserved copy of the I01 input; SHA256 `7bedee8c204bfe2b6b1c096dc55d2b7297298f9f70faa134def05a7b4456deae` |
| [review-schema4.db](review-schema4.db) | Schema-4 review copy: 219 active drafts, 2 quarantined/reserved definitions, all 221 original identities retained in the audit, 27 aliases, no verified native mappings |
| [migration-report.json](migration-report.json) | Per-identity source, old fields, predicate classification, metadata differences, current definition or quarantine, source-bound review decisions and unresolved responsibilities |
| [review-decisions-temperature.json](review-decisions-temperature.json) | Eight evidence-bearing definition reviews; no source applicability or mapping decision |
| [temperature-definitions/manifest.json](temperature-definitions/manifest.json) | Explicit scope and actual byte hashes for the generated definition slice |
| [temperature-definitions/parameters.json](temperature-definitions/parameters.json) / [YAML](temperature-definitions/parameters.yaml) | `cedarkit.parameters/v1`, resource `cedarkit.i03.temperature-definitions`, content version `1` |
| [temperature-definitions/params.json](temperature-definitions/params.json) | Automatically generated browser contract 4, eight definitions and one alias, no runtime mappings |

The reviewed identities are `cedarkit.t`, `cedarkit.t2m`, `cedarkit.ts`, `cedarkit.st` and four soil intervals (`st-0-10`, `st-10-40`, `st-40-100`, `st-100-200`). All preserve the existing names, aliases and parent association. Fixed soil boundaries come from explicit old normalized predicates and the confirmed physical definitions, never from a service layer code or sample filename. This does not establish which actual product/version provides them.

There are 546 remaining migration facts: 213 definition reviews, 221 GRIB applicability/translation records and 112 service applicability/translation records. These are authoring bookkeeping counts, not product coverage denominators. Two definitions are explicitly quarantined: `cedarkit.sw` (`m3/m3`, old parent `cedarkit.q` with `kg/kg`) and `cedarkit.tuswc` (`w/m2`, old parent `cedarkit.guswc.any` with `w/m2 S`). Their complete original definitions remain intact and their IDs cannot be reused.

The review database contains empty mapping-resource containers to retain authoring identities; it has **no verified GRIB2 or CMADaaS runtime bindings**. Full export is refused. Do not mix this definition slice with the old runtime registry as a deployment or overwrite the original database/browser snapshot.

See [stage I03 evidence and handoff](../../../../doc/2026-10-13-stage1.1-query-reki/evidence/I03/README.md), [migration tool documentation](../../docs/migration-v4.md) and [schema/export/browser contract](../../docs/schema-v4.md). Recovery replays the fixed source and exact reviewed decisions to a fresh path; reports and exported bytes are verified to match. Original project-root database and downstream runtime resources remain unchanged.
