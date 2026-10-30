# Current GEPS/REPS original-member precipitation accumulations

Derived from the immutable 169-mapping current GEPS/REPS review. This copy adds 20 mappings (12 GEPS, 8 REPS), bringing the total to 189, and three explicit since-initialization precipitation variants under the unchanged rain/rainc/rainnc identities. Existing definitions, stable IDs, parents and all 169 predecessor mapping rows are preserved.

Combined GEPS and REPS parameter/mapping resources use content version 2, with 52/40 mapping rows and 21/15 dependency definitions. Support remains at members 0–30/0–14 and hours 0/6/24. Zero-hour accumulations have zero-length intervals; positive-lead output steps come from encoded interval ends, never raw forecastTime=0. Water-equivalent precipitation converts the original kg/m2 values to the reviewed mm target with an explicitly scoped 1:1 convention; it is not a generic unit alias.

The legacy migration review denominator remains 221 identities, with 125 resolved / 96 pending definitions and 429 unresolved obligations. The three new authored definitions are reviewed separately in new-definitions-review.json and parameter_notes, with six additional backend applicability/coverage obligations. They are not fabricated legacy migration records. Complete product coverage, independent physical acceptance, CMADaaS and formal ensemble products remain open.

The workspace generator is doc/2026-10-13-stage1.1-query-reki/evidence/I03/round-9/build_current.py; its fixed input is this copy's 169-row predecessor. Subsequent work must copy the current 189-row state and update generator paths. Workspace I04 round-10 and I06 round-13 contain business/native/unit decisions, exact SHA references, full-field public-entry checks, error-boundary regressions and clean-install evidence.
