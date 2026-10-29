# Current-business CMA-GFS binding resource

2026-10-29. This new review copy continues the preserved
`../stage1.1-i03-grib-util-batch-2/review-schema4.db`.
The user's current-only policy authorizes `product.version=current`; this is a
business selection label, with no asserted official producer V-number.

No definitions changed: 125 resolved / 96 needs_evidence, all 221 old identities
preserved. The new resource `cedarkit.grib2.cma-gfs.current@1` has 14 exact
dataset/product-scoped mappings, derived from the reviewed second-batch resources.
Authoring count is now 41 mapping rows (27 previous opt-in rows plus 14 scoped
current GFS rows); these are not 41 independent physical quantities.

Supported pairs are f24 pressure T/U/V/Q/RH at 1000 hPa, T2M, instantaneous
U10M/V10M, PS/PSL and the four soil-temperature intervals. Business material and
original encoding evidence stay attached to the source rows. Complete current
product coverage remains false; SW and other first-batch local quantities are
not silently registered as this product's supported domain.

`runtime/` is the deterministic mapping slice, with 16 dependency-closed
definitions in `cedarkit.parameters.cma-gfs.current@1`. The JSON bytes for the
parameters and mapping are packaged verbatim in reki. No definitions/mappings
are reconstructed at query time, implicitly merged or taken from an old format.

`backend-assessments.json` reassesses the 14 GRIB identities against the current
binding while preserving their remaining mandatory obligations. The complete
`migration-report.json` still records 429 unresolved identity-wide obligations;
a limited current-product binding does not close the whole migration.

Replay from this project into a new directory:

```bash
uv run --offline --no-sync python ../../doc/2026-10-13-stage1.1-query-reki/evidence/I03/round-5/build_current_gfs.py --output /tmp/current-gfs-review
```

The script also performs a second temporary replay and compares export bytes.
`--install-resources` is an explicit authoring step for the generated reki assets;
future semantic changes need new resource versions and evidence, not a replay
that changes published version-1 bytes.

See [I04 round-6](../../../../doc/2026-10-13-stage1.1-query-reki/evidence/I04/round-6/README.md)
and [I06 round-9](../../../../doc/2026-10-13-stage1.1-query-reki/evidence/I06/round-9/README.md).
