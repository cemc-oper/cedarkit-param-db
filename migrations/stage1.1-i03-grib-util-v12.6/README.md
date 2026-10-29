# grib_util v12.6 first reviewed batch

Created 2026-10-29 from the preserved `../stage1.1-i03-review-2/review-schema4.db`.
The original `cedarkit_param.db` and earlier review databases are unchanged.

Seven source-bound definition decisions correct SRC/HTDN units and restore SW
with its four depth variants as volumetric soil water, separate from specific
humidity. Existing IDs/names/aliases and the original audit records are retained.
There are 121 resolved and 100 evidence-dependent definitions, 220 active rows,
one quarantined definition, and all 221 original identities. All 221 GRIB and
112 service-wide obligations remain open: a finite encoding slice cannot prove
every required product's availability or semantics.

`reviewed-definitions/` contains 121 reviewed definitions. `initial-mappings/`
contains 14 GRIB mappings and 19 definitions including dependencies. Its manifest
declares the limited scope and pending obligations. These are opt-in explicit-file
resources, not default product catalog bindings or a replacement deployment.

The first mapping resource covers CDBZ, pressure DBZ, DCAPE, FOGH, HT0, HT2, ZNT,
DBZMAXH, broad SW, four SW layers and ST(10–40). Native conditions restrict centre
38/subcentre 0/master 4/local 1/production status 0/template 0 and exact surfaces.
ST(10–40) also accepts observed local table 0. Other statuses, templates, models,
statistics, units and product-version domains require separate review.

`review-decisions.json` and `backend-assessments.json` retain evidence and reasons.
`migration-report.json` records remaining facts; `verification.json` records
source/review SHA, refusal of full export and identical report/export replay.

Reproduction and detailed handoff:
[I03 round-3](../../../../doc/2026-10-13-stage1.1-query-reki/evidence/I03/round-3/README.md).
Validation and four original GRIB message comparisons:
[I06 round-7](../../../../doc/2026-10-13-stage1.1-query-reki/evidence/I06/round-7/README.md).
