# grib_util second review batch

Created 2026-10-29 by copying the preserved first-batch review database at
`../stage1.1-i03-grib-util-v12.6/review-schema4.db`. The source, schema-3 original
and earlier review copies retain their previous bytes.

Four existing standard-code identities now have evidenced units: SKINT and TSOIL
use K, SOIL_M uses kg/m3, and TSRWE uses kg/m2/s. Exact legacy triples and explicit
wgrib2 names are checked against the archived ecCodes 2.48.0 table-version-4
declarations. These definitions retain their IDs, names, aliases and broad scope.
SOIL_M remains separate from CEMC volumetric SW; a shared word such as “soil” does
not establish inheritance. No new parent, vertical or statistical meaning is
invented. The remaining unit/inheritance cases retain precise evidence gaps.

There are 125 resolved and 96 evidence-dependent definitions, 220 active rows,
one quarantined definition, and all 221 original identities. All 221 GRIB and
112 CMADaaS identity-wide obligations remain open, for 429 remaining obligations.
`reviewed-definitions/` is `cedarkit.i03.reviewed-definitions@3`.

`file-mappings/` contains 27 bounded mappings in two resources:

- `cedarkit.grib2.cemc-grib-util-v12.6.initial@2` retains the 14 first-batch rows
  and adds the evidenced local-0 soil-water profile to SW and its four layers.
- `cedarkit.grib2.cemc-grib-util-v12.6.common@1` adds 13 rows: pressure T/U/V/Q/RH,
  T2M, instantaneous U10M/V10M, PS/PSL and the three other soil-temperature layers.
  ST(10–40) remains in the first resource. Exact producer, status, template and
  surface conditions remain attached to each mapping.

Both resources share the exported dependency-closed parameter registry
`cedarkit.i03.grib-util-v12.6.second@1`. A context chooses one GRIB mapping
resource; it does not implicitly merge these files. The manifest records all
actual resource hashes and `complete_product_coverage: false`.

The complete migration export is still refused. `definition-diff.json` records
old/new values and source locations/SHA; `candidate-field-review.json` retains
all 221 identity/candidate links and conditional original declarations without
turning candidates into accepted mappings. `backend-assessments.json` records
reassessment against the new effective definitions. `verification.json` records
the source copy hash, counts, export refusal and deterministic report/export replay.

Reproduce from this project, choosing a new output path:

```bash
uv run --offline --no-sync python ../../doc/2026-10-13-stage1.1-query-reki/evidence/I03/round-4/build_review.py --output /tmp/i03-second-review
```

Source/clean-wheel validation and full-field original-message checks are indexed
by [I06 round-8](../../../../doc/2026-10-13-stage1.1-query-reki/evidence/I06/round-8/README.md).
Business product versions and complete provision remain subject to
[I04 round-4](../../../../doc/2026-10-13-stage1.1-query-reki/evidence/I04/round-4/README.md).
