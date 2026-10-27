# I03 continued review of existing parameter definitions

Date: 2026-10-27. I03 remains in progress. This directory preserves a new schema-4 copy of the first-round review database and the results of reviewing every remaining definition against existing materials. The previous review database and eight-definition export are unchanged.

| File | Content |
|---|---|
| [review-schema4.db](review-schema4.db) | New copy with append-only assessment storage; 221 original identities retained, 219 active drafts and 2 quarantined identities |
| [review-decisions.json](review-decisions.json) | Source-bound decisions: 106 additional resolved definitions, 107 precise definition evidence gaps and 333 backend evidence-gap assessments |
| [definition-audit.json](definition-audit.json) | Per-identity outcome, independent expected vertical/statistical restrictions or concrete missing fact, source references and task ownership |
| [migration-report.json](migration-report.json) | Current declarations, original records, assessment history, resolutions and status counts |
| [verification.json](verification.json) | Source-copy digest, replay/report/export-byte equality, definition-only scope and full-export refusal |
| [reviewed-definitions/manifest.json](reviewed-definitions/manifest.json) | Actual-byte hashes and exact 114-definition scope |
| [JSON](reviewed-definitions/parameters.json) / [YAML](reviewed-definitions/parameters.yaml) | `cedarkit.parameters/v1`, distinct resource `cedarkit.i03.reviewed-definitions`, revision `1`; no runtime mappings |
| [Browser data](reviewed-definitions/params.json) | Automatically generated contract 4 from the same reviewed definitions |

The definition state is now **114 resolved, 107 needs_evidence, 0 unreviewed**. This resolves 106 additional definitions beyond the first-round eight. The remaining 440 migration obligations are 107 definition facts, 221 GRIB facts and 112 service facts; those are bookkeeping counts, not product coverage totals.

Explicit old wildcard predicates and the confirmed broad-definition contract support retaining broad quantities and unrestricted statistical periods where intentionally undeclared. A fixed old time_range_hours is never discarded or widened. Missing units, ambiguous temporal/quantity semantics, scaling, soil-water inheritance, channel context and source-description contradictions remain evidence gaps. One display-only correction changes the u10m English V-component typo to U, corroborated by existing DOCX UGRD/10m U rows, the U-component parent and original Chinese description; IDs, aliases, units, parents and fixed conditions are unchanged.

No actual non-applicability decision was made: the inspected materials do not prove identity-wide definition-only use, an exclusive confirmed exclusion or complete non-provision across all required products. Tests exercise the supported closure paths with independent synthetic evidence. Unknown scope stays unresolved; no runtime mapping was fabricated. Full export still refuses unresolved/quarantined inputs.

See [continued-stage evidence](../../../../doc/2026-10-13-stage1.1-query-reki/evidence/I03/round-2/README.md) and [authoring review contract](../../docs/migration-v4.md). These are parameter-definition and migration-review results, not real-product, backend or business acceptance. I04–I10 have not been executed.
