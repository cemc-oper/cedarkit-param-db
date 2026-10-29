# Current-business GFS extension and MESO 3 km review

Derived from the previous `stage1.1-i04-current-gfs/review-schema4.db`; the
source and all prior resources remain intact. No parameter definition or ID
changed. Current GFS mappings move to content version 2 (14 rows); current
MESO 3 km mappings start at version 1 (12 rows, with distinct soil intervals).
Authoring total: 53 rows, 125 resolved definitions / 96 concrete gaps and 429
identity-wide unresolved obligations. These counts do not imply full products.

`gfs/` and `meso3/` are deterministic exports, copied verbatim into reki.
`mapping-diff.json` records old/new GFS applicability and the MESO rows with
conditions, source locations and SHA evidence. `backend-assessments.json`
records scoped reassessment; `migration-report.json` retains precise gaps.

The source derivation, replay command and current shared-validator requirement
are documented in workspace `doc/2026-10-13-stage1.1-query-reki/evidence/I03/round-6/`.
Latest original-file and clean installation checks are in I06 round-10;
I04 round-7 owns the finite business binding. For further edits, copy this
review DB into a new batch. Do not reuse the fixed-input generator to overwrite
this review or previously pinned resources.
