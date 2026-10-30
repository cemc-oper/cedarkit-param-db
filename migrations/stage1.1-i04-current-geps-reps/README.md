# Current GEPS/REPS original-member review slice

Derived from the immutable 97-mapping `stage1.1-i04-current-meso1-tym` review. This copy adds 40 GEPS and 32 REPS contextual mappings (169 total), with no definition, stable-ID or parent changes. Definition review remains 125 resolved / 96 needs evidence; 429 identity-wide obligations remain open.

Each parameter has separate initial/forecast and control/perturbation native contexts. These are individual instantaneous PDT-1 members, not ensemble statistical products. GEPS uses members 0–30 and REPS 0–14, supported hours 0/6/24, and finite reviewed parameter/level pairs. Both new parameter/mapping bundles use content version 1. REPS's raw ensemble-size value 0 is preserved and is not a population declaration.

The workspace generator is `doc/2026-10-13-stage1.1-query-reki/evidence/I03/round-8/build_current.py`; its fixed input is this copy's 97-row predecessor. Subsequent incremental work must copy this latest 169-row state and adjust generator inputs/outputs. Review differences, dependency reassessment and source SHA references are retained beside the database; deterministic exports live in `geps/` and `reps/`.

Current member-range/role decisions and real-file validation are in workspace I04 round-9 / I06 round-12, outside the code repository. Complete product provision and independent physical acceptance remain open. No CMADaaS service, formal ensemble statistics, probability or quantile support is implied.
