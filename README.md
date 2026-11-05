# cedarkit-param-db

The task 03 GFS authoring slice lives in [authoring](authoring). It contains the reviewed `cedarkit.t` and `cedarkit.t2m` definitions and the two applicable GRIB2 mappings. The input records come from the version-controlled authoring state at `e0aba5374e00ce88656760f05d6bd2c1ba79dca2`. The GFS scope and vertical conditions follow the reviewed GFS projection at reki `5023d7e15f231ade263e34ca98728be1b8b9840a` and the frozen GFS report headers.

With the corresponding `cedarkit-query` installed, export to a new staging directory from this repository:

```sh
python tools/export_gfs_task03.py \
  --catalog ../../repo/reki/src/reki/catalog/builtin/catalog-v1.json \
  --output /tmp/gfs-task03-snapshot
```

reki owns the catalog, including layout and the two finite expected-domain sample cells. The exporter validates the combination and pins the parameter and mapping versions and byte digests in the staged catalog. Compare all three staged files with the deployment copy before replacing a complete snapshot. Changes to a published resource require a new content revision. The historical browser export and the remaining authoring records are available in the stage 1.1 archive.

## CEMC ORIG batch 1

[The reviewed batch](authoring/cemc-orig-batch1.json) preserves the stable definitions from the archived authoring state and the applicable mapping rows from the archived reki product projection. Each mapping cites the current original-header evidence used to select it. Coverage is recorded separately in the workspace task 06 ledger.

Stage the six product resource pairs against the task 06A version 28 reki catalog from this repository:

```sh
python tools/export_cemc_orig.py \
  --catalog /path/to/task-06a/catalog-v1.json \
  --output /tmp/cemc-orig-batch1
```

The output directory must be new or empty. The exporter validates each product combination and pins resource versions and byte digests in the staged catalog. Revise the resource and catalog content versions when publishing changed bytes.

## CEMC deterministic ORIG task 06B

[The reviewed additions](authoring/cemc-orig-task06b.json) extend the 06A definitions and mappings for GFS, MESO-1KM, MESO-3KM, and TYM. They retain the archive revision and the original-header references for each new mapping. Export the combined resource set against the current catalog:

```sh
python tools/export_cemc_orig.py \
  --catalog ../../repo/reki/src/reki/catalog/builtin/catalog-v1.json \
  --additions authoring/cemc-orig-task06b.json \
  --output /tmp/cemc-orig-task06b
```

When changing pins with `--additions`, pass the updated product provisions in the input catalog and set `--catalog-version` to a newer revision.

The catalog v30 additions use `g/(cm.hPa.s)` for pressure-level QFLX in GFS, MESO-3KM, and TYM. The stored unit was verified by reconstructing the diagnostic from the original humidity and wind fields on the same pressure levels and grids.

## CEMC ensemble ORIG task 06C

[The member additions](authoring/cemc-orig-task06c.json) cover reviewed GEPS and REPS member fields. They include the GEPS zero-hour snowfall branch verified against original records for all 31 members. Apply both authoring increments to reproduce catalog v31:

```sh
python tools/export_cemc_orig.py \
  --catalog ../../repo/reki/src/reki/catalog/builtin/catalog-v1.json \
  --additions authoring/cemc-orig-task06b.json \
  --additions authoring/cemc-orig-task06c.json \
  --output /tmp/cemc-orig-task06c
```

## CEMC GFS accumulated latent heat task 06I

[The SLHF additions](authoring/cemc-orig-task06i.json) define `cedarkit.slhf` as surface latent heat accumulated since initialization in `J/m2`. The initial and forecast mappings retain the reviewed GFS `0/0/10`, PDT 8 and producer phase fields. Evidence includes the product table, writer declaration and SHA256 of the zero-, six- and 48-hour original records.

Apply the three increments to reproduce catalog v32:

```sh
python tools/export_cemc_orig.py \
  --catalog ../../repo/reki/src/reki/catalog/builtin/catalog-v1.json \
  --additions authoring/cemc-orig-task06b.json \
  --additions authoring/cemc-orig-task06c.json \
  --additions authoring/cemc-orig-task06i.json \
  --output /tmp/cemc-orig-task06i
```

The preceding 06B and 06C commands use the archived v30 and v31 catalogs respectively.

## CMADaaS offline candidates task 07A

[The service authoring slice](authoring/cmadaas-task07a.json) provides twelve service candidates and sixteen mappings. Each service has a reviewed historical TEM row for the 2 m temperature contract. The GFS forecast candidate also includes the frozen surface TEM, GPH, CPE and LPE cases. The joint vertical table preserves the native level-type and level pair. CPE and LPE retain their separate identities and complete 24-hour accumulation windows.

Export the dedicated candidate catalog and its two resources from this repository:

```sh
python tools/export_cmadaas_task07a.py \
  --catalog ../../repo/reki/src/reki/catalog/builtin/catalog-v1.json \
  --output /tmp/cmadaas-task07a
```

To reproduce a published candidate, supply `cmadaas-task07a-catalog.json` as the input catalog. Changed parameter or mapping bytes require newer content versions. A changed candidate catalog requires a newer `--catalog-version`. The exporter uses the shared resource validators and writes only to a new or empty directory.

The resulting catalog is explicitly selected with `context={"catalog": {"builtin": "reki.catalog.cmadaas.task07a"}}`. Its `candidate-07a` product version, UTC request clock, Beijing rectangle and member ranges are controlled offline contracts. Actual service versions, time zones, authorization, member availability and numeric values require task 07B evidence before promotion. The default v32 catalog retains its existing production bindings. The 997 remaining historical service rows, including PRE conflicts and accumulation suffixes, remain separately tracked in the workspace coverage ledger.
