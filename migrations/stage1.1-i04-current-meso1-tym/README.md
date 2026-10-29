# Current MESO1 analysis/forecast and TYM review

Copied from `stage1.1-i04-current-gfs-meso3/review-schema4.db` without modifying
its bytes or historical bundles. No definitions, stable IDs or parent relations
changed. Definition state remains 125 resolved / 96 concrete gaps, with 429
identity-wide unresolved obligations.

The new database contains 97 mappings: previous 53 + MESO1 20 + TYM 24.
Analysis and forecast have separate exact native rows inside each existing
ORIG/current product. Only selected hours 0/6/24 and pressure levels 850/500 hPa
are supported. MESO1 exports 12 dependency definitions, TYM 14; both new mapping
and parameter resources have content version 1. TYM soil intervals are explicit;
MESO1 soil coverage remains pending.

`mapping-diff.json` preserves new rows, conditions, evidence locations and SHA;
`backend-assessments.json` records reassessment without closing global duties.
The fixed-input generator and deterministic replay are documented in workspace
I03 round-7; latest originals, numeric and installation evidence are in I06
round-11, with product context in I04 round-8. Further development must copy this
review into a new batch rather than overwrite a pinned bundle.
