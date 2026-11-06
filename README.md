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

## CMADaaS live bindings task 07B

[The online authoring slice](authoring/cmadaas-task07b.json) promotes the sixteen verified cases into the default catalog v33. It retains five stable parameter identities and sixteen service mappings. The product version `service-20261105` records this reviewed binding revision. The authoring record preserves the user's decision to use actual response grids and matching original fields while leaving the official producer release unspecified.

```sh
python tools/export_cmadaas_task07b.py \
  --catalog /path/to/task-07b/inputs/catalog-v32.json \
  --catalog-version 33 \
  --output /tmp/cmadaas-task07b
```

To reproduce v33, use the archived `../../doc/2026-11-04-stage1.2-query-reki/evidence/task-07c/inputs/catalog-v33.json` input and omit `--catalog-version`. The exporter writes the complete catalog and the `current-cmadaas-parameters.json` and `current-cmadaas-mappings.json` resources. Their content versions and byte digests are pinned in each service registration. The eighteen native resources, native dataset registrations and three task 07A snapshots retain their original bytes.

GFS and TYM analysis bind the forecast-style interface at lead zero. REPS expected cells use the verified 2026-11-04 06 UTC cycle. Its explicit member contract retains missing response names and units and obtains K from the pinned mapping verified against original GRIB fields. The other services validate their actual nonempty unit and exact element/level-type names. GFS CPE and LPE retain distinct complete 24-hour accumulation windows. Member requests verify GEPS 1–30 and REPS 1–14, with control member zero and boundary failures recorded separately.

Task 07A export remains reproducible from the current catalog. Content version checks apply to references to the same resource, so promoting a distinct resource identity cannot create a false same-version conflict when reconstructing the older offline candidate.

## CMADaaS instantaneous batch (task 07C)

[The reviewed authoring input](authoring/cmadaas-task07c.json) retains the sixteen task 07B mappings and adds 374 instantaneous service rows verified against real responses and matching original GRIB messages. It contains 64 definitions, 390 mappings and three joint vertical tables. Public service parameters and mappings advance to content version 2; the default reki catalog advances to version 34. The generic geopotential-height parent preserves its native identity; surface restrictions remain in their product mappings. Reviewed pressure, scalar-surface and cloud-column identities stay distinct.

Export against the frozen task 07B catalog or reproduce the installed version 34 resources into a new empty directory:

```sh
python tools/export_cmadaas_task07b.py \
  --author authoring/cmadaas-task07c.json \
  --catalog ../../doc/2026-11-04-stage1.2-query-reki/evidence/task-07c/inputs/catalog-v33.json \
  --catalog-version 34 \
  --output /tmp/cmadaas-task07c
```

The optional `--author` argument preserves the original task 07B default. Reproducing version 34 from its own catalog omits `--catalog-version`. Changed parameter or mapping content needs a newer content version, and changed catalog pins need a newer catalog version. Restore task 07B with its original authoring input and archived version 33 catalog; the older snapshot does not acquire task 07C coverage.

Published level and forecast-hour domains use the reviewed historical product inventory. Finite expected domains retain only the independently verified sample cells. Empty units require an explicitly reviewed contract and preserve mapping provenance; they are not inferred from element spelling. The service and original-message receipts, complete 997-row reconciliation, and 623 deferred rows are archived in the workspace task 07C evidence. The unaccepted rows remain outside the published mapping set.


## GFS accumulation and identity review (task 07E1)

[The task 07E1 input](authoring/cmadaas-task07e1.json) adds 26 GFS mappings, bringing the shared service registry to 93 definitions and 416 mappings. It distinguishes since-initialization accumulation, trailing 3/6/12/24-hour fields, precipitable water PRE, and pressure-level radar reflectivity RAR. PC remains deferred pending Pa/hPa evidence. The legacy CPE/LPE generic IDs retain their 24-hour mapping behavior, with the operation and window declared in mapping configuration so their parameter families can host reviewed variants.

Use cedarkit-query 0.2.1 or newer in the 0.2 series:

```sh
python tools/export_cmadaas_task07b.py \
  --author authoring/cmadaas-task07e1.json \
  --catalog ../../doc/2026-11-04-stage1.2-query-reki/evidence/task-07e1/inputs/catalog-v34.json \
  --catalog-version 35 \
  --output /tmp/cmadaas-task07e1
```

Catalog v35 pins content-v3 service resources. The explicit version 3 forecast contract is used only with reviewed derived-grid profiles for suffix fields; empty return headers remain visible and units are labelled as mapping evidence. Snowfall retains m without guessing a snow-depth or water-equivalent conversion. Original-message endpoint differences, nonzero convective-window checks, real responses and all 162 row dispositions are archived in the workspace task 07E1 evidence. Tasks 07E2–07E6 own the other 134 rows; 07E7 owns the two GFS PC unit conflicts. Restore the preceding resource set with the task 07C authoring input and archived catalog v34.

## MESO-1KM accumulation and identity review (task 07E2)

[The task 07E2 input](authoring/cmadaas-task07e2.json) preserves all 93 existing definitions and 416 mappings, adds one-hour rain and snowfall variants plus precipitation-type codes, and publishes 20 MESO-1KM mappings. Catalog v36 pins content-v4 service resources with 96 definitions and 436 mappings. All 28 intake rows have a disposition: four Richardson rows move to 07E8, two five-minute dual-window rows to 07E9, and two PC unit conflicts to 07E10. The published mappings are independent of these follow-ups.

```sh
python tools/export_cmadaas_task07b.py \
  --author authoring/cmadaas-task07e2.json \
  --catalog ../../doc/2026-11-04-stage1.2-query-reki/evidence/task-07e2/inputs/catalog-v35.json \
  --catalog-version 36 \
  --output /tmp/cmadaas-task07e2
```

TPE and TOSN use since-initialization identities, while the 01/03/06/12/24 suffixes use trailing windows checked against both original cumulative endpoints. PRE is entire-atmosphere precipitable water, RAR is pressure-level reflectivity, and PRTY is `cedarkit.precitype` with unit `1` and WMO GRIB2 code table 4.201. Codes remain unchanged; snowfall retains its verified m values. Forty finite sample cells have real-response and original-message evidence, including nonzero precipitation-type codes.

The explicit MESO-1KM forecast contract v4 permits the reviewed `derived_grid` mapping profile for instantaneous, since-initialization and trailing-accumulation fields, retaining empty processed-response headers and recording mapped units. The retained profile name describes reviewed response behavior rather than asserting that all such fields are differences. GFS contract v3 remains restricted to trailing accumulation. Query/Request v1 and the existing query 0.2.1 mapping schema are unchanged.

The native PRE_5MIN candidate is a maximum over an outer one-hour window, described as maximum five-minute rainfall within that hour; no simple five-minute accumulation is published. Richardson carriers were absent from 18 scanned originals and the tested service aliases failed. PC values match the native condensation-level pressure carrier, but its Pa/hPa production evidence remains unresolved. All failed requests and per-row material requirements are archived in the workspace task 07E2 evidence. Reproduce v36 from its own catalog without `--catalog-version`; restore v35 using the task 07E1 authoring input and archived v35 catalog. Deterministic exports, content/catalog version refusals and byte-identical rollback have been verified.

## MESO-3KM accumulation and Richardson review (task 07E3)

[The task 07E3 input](authoring/cmadaas-task07e3.json) preserves the existing 96 definitions and 436 mappings, adds the dimensionless Richardson family with surface and PBL variants, and publishes 24 mappings covering 25 accepted MESO-3KM historical rows. One analysis RCSN/166 row is merged into the verified RCSN_166/166 mapping. Catalog v37 pins parameter and mapping content v5, with 99 definitions and 460 mappings covering 461 historical service rows. Forty-eight finite samples have original-message and real-response evidence.

```sh
python tools/export_cmadaas_task07b.py \
  --author authoring/cmadaas-task07e3.json \
  --catalog ../../doc/2026-11-04-stage1.2-query-reki/evidence/task-07e3/inputs/catalog-v36.json \
  --catalog-version 37 \
  --output /tmp/cmadaas-task07e3
```

MESO-3KM's TPE/TOSN accumulation and 1/3/6/12/24-hour windows, PRE, RAR and PRTY retain product-specific values and units. The PBL Richardson parameter encodes its reviewed vertical meaning; a scoped singleton table maps it to native 166/0 without inventing a generic level type or height. Its executor rejects additional vertical selectors. Analysis RCSN and RCSN_166 aliases share one mapping to avoid ambiguity. The inspected Richardson originals are zero, so the evidence does not claim nonzero diagnostic-value validation.

All 30 intake rows have a disposition. The unresolved level-type-0 RCSN row belongs to 07E11, the two five-minute dual-window/unit rows to 07E12, and the two PC stored-unit conflicts to 07E13. These follow-ups do not gate the published mappings. Query/Request v1 and query 0.2.1 remain unchanged. Restore v36 using the task 07E2 input and archived v36 catalog; content/catalog version checks, deterministic export and byte-identical recovery are verified independently.

## TYM accumulation and precipitable-water review (task 07E4)

[The task 07E4 input](authoring/cmadaas-task07e4.json) preserves all 99 existing definitions and 460 mappings, adds one-hour convective and large-scale precipitation variants, and publishes all 30 TYM historical rows. Catalog v38 pins parameter and mapping content v6 with 101 definitions and 490 mappings, covering 491 historical service records after the earlier MESO-3KM alias merge. Sixty finite sample cells have real-response and original-message evidence.

```sh
python tools/export_cmadaas_task07b.py \
  --author authoring/cmadaas-task07e4.json \
  --catalog ../../doc/2026-11-04-stage1.2-query-reki/evidence/task-07e4/inputs/catalog-v37.json \
  --catalog-version 38 \
  --output /tmp/cmadaas-task07e4
```

The snapshot distinguishes total, convective and large-scale precipitation and snowfall since initialization and over trailing 1/3/6/12/24-hour windows. Original cumulative endpoint differences include independent nonzero regions for all twenty trailing-window families. PRE is instantaneous entire-atmosphere precipitable water in kg/m2; precipitation uses the reviewed kg/m2-to-mm convention, while snowfall retains m. TYM analysis keeps its verified forecast-style interface with validTime=0, and reviewed processed forecast mappings use the existing v4 response contract.

No historical mapping row remains unaccepted in this batch. The two LPE01/LPE12 cells at 2026-11-04 12 UTC +36h return service code -1 and are separately numbered 07E14, without duplicating historical-row counts or expanding verified expected domains. Alternative +24h samples pass, and all public input formats preserve the unavailable-cell error. Restore v37 using the task 07E3 snapshot and archived v37 catalog; deterministic export, content/catalog version refusals and recovery are independently verified. Query/Request v1 and query 0.2.1 remain unchanged.


## GEPS precipitable-water review (task 07E5)

[The task 07E5 input](authoring/cmadaas-task07e5.json) preserves the entire parameter v6 resource byte for byte and all 490 existing mappings. Catalog v39 pins parameter v6 and mapping v7, with 101 definitions and 492 mappings covering 493 historical service rows. The two new PRE mappings publish instantaneous entire-atmosphere precipitable water in kg/m2, restricted to the verified 2026-11-02 12 UTC cycle. Forty-three finite cells cover the control and all 30 perturbation members, including four leads for members 0, 1, 2 and 30. Perturbation PRE uses a dataset-scoped joint vertical table for native service selector `10/1`; this alias does not introduce a physical level axis.

Six cumulative-precipitation rows transfer to 07E15 for working service bindings and matching real-response evidence; two CSWE rows transfer to 07E16 for carrier, rate-unit and window evidence. Recent wrong-stride responses are rejected and tracked as 64 reference/lead/member cells in 07E17, separately from the historical-row ledger. Existing TYM 07E14 availability cells remain unchanged. Query/Request schemas, native resource registrations and member interface contracts are unchanged.

```sh
python tools/export_cmadaas_task07b.py --author authoring/cmadaas-task07e5.json --catalog ../../doc/2026-11-04-stage1.2-query-reki/evidence/task-07e5/inputs/catalog-v38.json --catalog-version 39 --output /tmp/cmadaas-task07e5-export
```

Re-export against catalog v39 reproduces the installed snapshots deterministically. Content changes require their own newer parameter or mapping version; catalog changes require a newer catalog version. Task 07E4 remains independently recoverable from its frozen authoring input and v38 catalog.
