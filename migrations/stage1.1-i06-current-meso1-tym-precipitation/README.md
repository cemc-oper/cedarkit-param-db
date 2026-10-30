# Current MESO 1 km and TYM precipitation review

This schema-4 review continues the 197-row `stage1.1-i06-current-deterministic-precipitation` database without changing its existing definitions, stable IDs, aliases, parents, notes or mapping/evidence cells. It adds eight finite mapping rows, bringing the total to 205 with 223 active parameters.

- MESO 1 km: total precipitation at surface and 0/6/12 hours; two initial/forecast mapping rows; parameter and mapping content version 2, 15 dependency definitions and 22 mapping rows.
- TYM: total, convective and large-scale precipitation at surface and 0/6/24 hours; six initial/forecast mapping rows; parameter and mapping content version 2, 23 dependency definitions and 30 mapping rows.
- Reuse the three reviewed `*.since-initialization` definitions unchanged. Native kg/m2 and target mm remain separate under the reviewed narrow water-equivalent convention.
- PDT 4.8 single-range accumulations retain the coded reference/start/end/duration. MESO 1 km uses raw minutes and TYM hours. Zero-length initial accumulation remains distinct from an instantaneous analysis field.

The latest cycles frozen at discovery are MESO 1 km 2026103009Z and TYM 2026103006Z. No 24 h MESO 1 km file was available in that cycle, so the new finite precipitation scope uses 12 h without falling back to an older cycle. Catalog v8 adds 12 h to the MESO 1 km product scope while preserving every old instantaneous provides entry; it does not add 12 h instantaneous support.

The old 125 resolved/96 needs-evidence migration definitions and 435 combined obligations remain. `new-definitions-review.json` and `formal-product-review.json` preserve earlier reviews; this batch adds no definitions or formal ensemble products. Current MESO 1 km component gaps are in `deferred-candidates.json`; earlier MESO3 gaps remain in `inherited-deferred-candidates.json` and the predecessor database.

`mapping-diff.json`, `definition-reuse-review.json`, `derivation.json` and `migration-report.json` retain decisions and source SHA. JSON/YAML resources are deterministically exported by workspace I03 round-12/build_precipitation.py with fixed 197-row input; adjust its input/output and content versions before continuing another batch. The old database and previous evidence remain immutable. No windows are computed by subtracting accumulations. Complete product coverage, independent physical acceptance, CMADaaS/modelvar bindings and formal ensemble statistics/probability/quantile products remain outside this finite delivery.
