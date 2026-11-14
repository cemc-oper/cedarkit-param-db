# cedarkit-param-db

The task 03 GFS authoring slice lives in [authoring](authoring). It contains the reviewed `cedarkit.t` and `cedarkit.t2m` definitions and the two applicable GRIB2 mappings. The input records come from the version-controlled authoring state at `e0aba5374e00ce88656760f05d6bd2c1ba79dca2`. The GFS scope and vertical conditions follow the reviewed GFS projection at reki `5023d7e15f231ade263e34ca98728be1b8b9840a` and the frozen GFS report headers.

With the corresponding `cedarkit-query` installed, export to a new staging directory from this repository:

```sh
python tools/export_gfs_task03.py \
  --catalog ../../repo/reki/src/reki/catalog/builtin/catalog-v1.json \
  --output /tmp/gfs-task03-snapshot
```

reki owns the catalog, including layout and the two finite expected-domain sample cells. The exporter validates the combination and pins the parameter and mapping versions and byte digests in the staged catalog. Compare all three staged files with the deployment copy before replacing a complete snapshot. Changes to a published resource require a new content revision. The historical browser export and the remaining authoring records are available in the stage 1.1 archive.

## Reviewed browser snapshot set (N03A and subsequent candidates)

[authoring/browser-current.json](authoring/browser-current.json) selects browser
revision 16. The exporter applies the stage 1.4 ORIG bindings and the reviewed
K-index, snowfall and vertical diagnostics refinements, then verifies the catalog v56 resources against the sealed
wheel. It also includes the reviewed CMADaaS resources from T05. Extract the
wheel and export the schema-4 bundle with `cedarkit-query` 0.2.1 from this repository.

```sh
python -m zipfile -e ../../doc/2026-11-14-stage1.5-query-reki/evidence/1.5-04C/supplement/artifacts/reki-2026.9.1.dev121+g111cb2a.orig56-py3-none-any.whl /tmp/reki-orig56
python tools/export_browser_snapshot.py \
  --catalog /tmp/reki-orig56/reki/catalog/builtin/catalog-v1.json \
  --legacy-snapshot ../cedarkit-param-web/public/params.json \
  --output /tmp/reviewed-browser-schema4
```

The bundle manifest indexes seven independent schema-4 browser documents and
pins the unchanged runtime files and reki-owned input catalog. Each document
retains one parameter resource, its flat definitions and parent IDs, complete
mapping restrictions, and evidence references. A stable ID can have different
local constraints in different resources; neither parameter IDs nor GRIB
triplets are used to overwrite another resource's definitions. Mapping IDs are
scoped by their mapping resource. The legacy index is navigation-only and does
not import historical units, definitions or support claims.

Exports validate authored bytes against runtime resources and catalog pins,
stage privately, verify the staged group, and publish only to a new directory.
The browser bundle has its own explicit content revision; parameter, mapping
and catalog revisions remain unchanged. Supply `--previous /path/to/bundle`
to check an earlier bundle before publication; changed bytes at the same
browser revision and revision rollback are rejected.

This export covers reviewed authoring resources, with incomplete product
coverage and remaining obligations recorded explicitly. It does not mark all
times or members available, retire old IDs outside the slice, or promote the
archived authoring collection into current support. It does not replace
`cedarkit-param-web/public/params.json`: the existing site consumes schema 3,
and schema-4 loading, display and old-link behavior belong to N03B. See the
[schema-4 bundle contract](docs/browser-schema4.md) for file layout, identity,
scope and consumer checks.

The remaining-obligation counters describe one global ledger. They repeat in
each resource view for context and must not be added across the seven views.

Run exporter regression tests with a Python 3.11+ environment containing
`cedarkit-query` 0.2.1 and pytest:

```sh
python -m pytest tests/test_export_browser_snapshot.py -q
```

The historical revision 2 policy records the N04B-01 resource candidate
(catalog v41, MESO-1KM parameters v9 and mappings v12). That revision 2 group
was accepted by N10I-01 with its frozen runtime cohort. The T03 group used
revision 9 and is described below. Revision 1's policy is retained
byte-for-byte in
[authoring/browser-reviewed-v1.json](authoring/browser-reviewed-v1.json). To
reconstruct that historical group, select this policy together with its original
catalog v40 and runtime resource bytes, rather than the newer current files:

```sh
python tools/export_browser_snapshot.py \
  --policy authoring/browser-reviewed-v1.json \
  --catalog ../../doc/2026-11-04-stage1.2-query-reki/evidence/task-n10i-01/previous-browser/catalog-v1.json \
  --runtime-dir ../../doc/2026-11-04-stage1.2-query-reki/evidence/task-n10i-01/previous-browser/resources \
  --legacy-snapshot ../cedarkit-param-web/public/params.json \
  --output /tmp/reviewed-browser-revision1
```

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

## MESO-1KM native PWAT task N04B-01

[The reviewed increment](authoring/cemc-orig-task-n04b-01.json) adds the existing
stable `cedarkit.pwat`/`cedarkit.pwat.any` identities to the MESO-1KM parameter
resource, with `kg/m2` and entire-atmosphere fixed conditions. Two GRIB2 mappings
separate the original initialization from forecast phases. Applicability is
explicitly limited to the frozen 2026-11-02 12 UTC reference and 0/6/48-hour
leads, including minute time units, centre/table/surface and production keys.

The native data retains its decoded values. The reviewed same-field service
unit and native mass-per-area declarations resolve this batch's unit binding;
no `kg/kg`, factor 1000 or unreviewed physical conversion is inferred. The 0h
instantaneous original is an initialization zero, not independently verified
physical zero atmospheric water. No expected-domain cells are added.

To reconstruct current catalog v41 from the reviewed inputs:

```sh
python tools/export_cemc_orig.py \
  --catalog ../../repo/reki/src/reki/catalog/builtin/catalog-v1.json \
  --additions authoring/cemc-orig-task06b.json \
  --additions authoring/cemc-orig-task06c.json \
  --additions authoring/cemc-orig-task06i.json \
  --additions authoring/cemc-orig-task-n04b-01.json \
  --output /tmp/cemc-orig-n04b-01
```

The parameter and mapping content revisions are 9 and 12. Changed pins require a
newer catalog revision; unchanged current inputs reproduce v41 without an
additional catalog bump. Other native and service resource files retain their
previous bytes. Browser policy revision 2 selects this group, whose web and
runtime combination was accepted by N10I-01. The original revision 1 policy and its complete prior
browser/runtime group remain frozen and recoverable in that acceptance evidence.

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


## REPS precipitation and snowfall review (task 07E6)

[The task 07E6 input](authoring/cmadaas-task07e6.json) publishes all 36 control and perturbation TPE/CPE/TOSN rows, covering since-initialization accumulation and 1/3/6/12/24-hour windows. It preserves parameter v6 byte for byte, all 101 parameter definitions, all 492 existing mappings, and all five joint vertical tables. Catalog v40 pins mapping v8 and contains 528 mappings covering 529 historical service rows.

The 163 finite expected cells are verified against real service responses and matching originals, including all 15 members for all three accumulation families at +48h. Rainfall retains native kg/m2 water-equivalent values as mm, and snowfall retains m. The four TPE/CPE mappings also include the explicitly verified zero-hour initialization cells omitted from the old metadata. Member bounds remain control 0 and perturbations 1–14, independent of the native ensemble-count value zero. The existing REPS member interface contract and surface table remain unchanged.

All 36 rows have nonzero original-window evidence. Independent task 07E18 tracks 419 unavailable sample cells; those cells are excluded from verified expected domains and are not counted as unaccepted historical rows. Existing TYM and GEPS cell follow-ups remain separate. No new parameter identities or protocol schemas are introduced.

```sh
python tools/export_cmadaas_task07b.py --author authoring/cmadaas-task07e6.json --catalog ../../doc/2026-11-04-stage1.2-query-reki/evidence/task-07e6/inputs/catalog-v39.json --catalog-version 40 --output /tmp/cmadaas-task07e6-export
```

Re-export against catalog v40 reproduces the snapshots deterministically. Parameter, mapping and catalog revisions retain their independent version guards. The frozen task 07E5 input and v39 catalog remain independently recoverable.

## GFS NLHF service energy batch N06-01

[The N06-01 authoring input](authoring/cmadaas-task-n06-01.json) adds the existing `cedarkit.slhf` identity to two GFS service mappings. Service parameters v7 contain 102 definitions; service mappings v9 contain 530 mappings. Catalog v42 retains the other 21 runtime resources unchanged. The reviewed NLHF cells are restricted to 2026-11-02 12 UTC, analysis 0h and forecast 3/6/48h. Raw response `W.m-2` is retained as evidence while original GRIB/producer and whole-grid comparisons establish accumulated `J/m2` values; no duration division, sign conversion or fitted scale is introduced.

```bash
python tools/export_cmadaas_task07b.py --author authoring/cmadaas-task-n06-01.json --catalog ../../repo/reki/src/reki/catalog/builtin/catalog-v1.json --output /tmp/cmadaas-n06-01-export
```

`browser-current.json` advances the author candidate to revision 3 with these exact resource pins and service-history counts 531 accepted / 482 remaining. Native 95 / ensemble 48 groups, 485 quality cells and deferred N27 remain unchanged. The published browser revision 2 stays intact until the independent N10I-02 combination acceptance; regenerate and hand off the revision-3 group through the existing exporter rather than editing `public/params.json`. N06 retains 114 separately tracked rows (32 extremes, 28 changes and 54 other fluxes); this batch does not close the parent task or certify other NLHF cycles/leads.


## GFS NSRF energy batch N06-02

`authoring/cmadaas-task-n06-02.json` extends the accepted N06-01 authoring with four GFS NSRF surface/top mappings and the existing `cedarkit.gsw`/`cedarkit.tsw` identities. Parameters v8 contain104 definitions, mappings v10 contain534 mappings, and catalog v43 pins the exact new group. Existing102 definitions,530 mappings and existing table rows are preserved; `cmadaas.levels` gains only the reviewed atmosphere-top8/0 row. The other21 runtime resources are unchanged.

The finite cycle, rectangle and analysis0/forecast3,6,48h cells retain original `J/m2` net short-wave integrated energy and raw `W.m-2` evidence. No duration division, sign conversion or positivity rule is added. Actual MXT/MNT data falsify a proposed since-initialization extrema clock, so those four rows remain pending rather than being aliased to a guessed three-hour window. Native95 groups and the485 independent service quality cells are not reduced.

`browser-current.json` advances the author candidate to revision4 with535 accepted historical rows and478 remaining. Browser revision3 remains the accepted page checkout until N10I-03 validates the full combination; use the existing exporter, preserve the frozen previous group and do not hand-edit generated public snapshots. N06 remains split with110 pending rows (32 extrema,28 changes,50 fluxes).

## GFS NWFS clear-sky energy batch N06-03

`authoring/cmadaas-task-n06-03.json` extends the cumulative N06-02 input with the independently reviewed GFS NWFS surface/top mappings. Parameters v9 contain107 definitions, mappings v11 contain538 mappings, and catalog v44 pins this group. The new `cedarkit.gswc`/`cedarkit.tswc` identities inherit `J/m2` from `cedarkit.gswc.any` and fix accumulation since initialization. The prior104 definitions,534 mappings, all five translation tables and other21 runtime resources remain unchanged.

```sh
python tools/export_cmadaas_task07b.py --author authoring/cmadaas-task-n06-03.json --catalog ../../repo/reki/src/reki/catalog/builtin/catalog-v1.json --output /tmp/cmadaas-n06-03-export
```

Producer GSWC/TSWC and case109 `[ws/m2]`, original0/4/11 PDT8 energy, and actual eight-cell responses independently establish clear-sky net short-wave energy at surface1/0 and top8/0. The reviewed scope remains2026110212, analysis0/forecast3,6,48h,39–41N/115–117E. Raw `W.m-2` and the original919 top negative6-to48h differences are retained; no division by seconds, sign adjustment or monotonicity rule is introduced. NSRF and NLHF remain separately reviewed profiles, and the four MXT/MNT clock counterexamples remain pending.

The author candidate advances to browser revision5 with539 accepted historical rows and474 remaining. The published web checkout stays at the jointly accepted N10I-03 revision4; the exact seven-package/extra/browser5 candidate must pass N10I-04 before page adoption. N06 retains106 rows (32 extrema,28 changes,46 fluxes); quality485, native95, ensemble48 groups/96 messages and N27 deferral remain unchanged. Use the existing exporter for the complete candidate and retain the accepted revision4 recovery group.

## GFS USRF signed upward energy batch N06-04

`authoring/cmadaas-task-n06-04.json` adds four independently reviewed GFS USRF service mappings and the `cedarkit.gusw.any`/`cedarkit.gusw`/`cedarkit.tusw` hierarchy. Parameters v10 contain110 definitions, mappings v12 contain542 mappings, and catalog v45 pins this group. The prior107 definitions,538 mappings, five translation tables and other21 runtime resources are preserved. Existing historical stable IDs are reused for this reviewed service resource; archived `w/m2` claims and aliases are not promoted into current unit semantics.

```sh
python tools/export_cmadaas_task07b.py --author authoring/cmadaas-task-n06-04.json --catalog ../../repo/reki/src/reki/catalog/builtin/catalog-v1.json --output /tmp/cmadaas-n06-04-export
```

The reviewed cells are2026110212, analysis0h and forecast3/6/48h,39–41N/115–117E, surface1/0 and top8/0. Producer GUSW/TUSW, element211 `[ws/m2]`, original0/4/8 PDT8 accumulation and paired actual responses support signed energy inJ/m2. Native decoder `W m**-2`/`unknown` and service `W.m-2` labels remain in the evidence. Large negative and small positive original values are preserved; no sign reversal, clipping, division by seconds, fitted scale or positive-up convention is imposed. Other products and flux families require their own review.

The author candidate advances to browser revision6 with543 accepted historical rows and470 remaining. The published web checkout remains the jointly accepted N10I-04 revision5; N10I-05 receives the exact new seven-package/extra/browser6 candidate for full combination and page acceptance. N06 retains102 rows (32 extrema,28 changes,42 fluxes), including the four MXT/MNT clock counterexamples; quality485, native95, ensemble48 groups/96 messages and N27 deferral remain unchanged.

### N06-05：GFS ULRF 有限范围交付

`authoring/cmadaas-task-n06-05.json` 在 N06-04 的 110 定义／542 映射基础上独立审核 GFS ULRF 地表与大气顶的分析／预报四行，形成 113 定义／546 映射、参数资源 11／映射资源 13／catalog46。公开 `cedarkit.gulw.any`、`cedarkit.gulw`、`cedarkit.tulw` 使用 `J/m2` 与起报至有效时刻累计区间。生产 case212 `ws/m2` 与原始 0/5/4 累计载体、八个真实成对样本共同支持有限范围解释；原始地表 `W m**-2`、大气顶 `unknown` 及服务 `W.m-2` 标签原样留存。

八场 33,177,600 原始点／2,176 服务点逐点核验；分析为零，六个预报全场为负，不取反、裁零、除时长或拟合，不作正值向上或物理成因推断。历史 GULW 的 `w/m2`、`gslu` 别名不导入当前语义。该批作者策略为 revision7：551 作用域定义、169 稳定 ID、1315 作用域映射、127 直接映射 ID；该批交接时已联合验收的前端为 browser6，完整新组合由 N10I-06 独立验收。历史行累计 547/1013，剩余 466；N06 剩余 98（32 极值、28 变差、38 通量），四条 MXT/MNT 时钟反证保持。质量 485、原生 95、集合 48 组／96 消息和 N27 暂缓状态不变。

### T02：瞬时水汽输送与地表质量通量

T02 的 `authoring/cmadaas-task-t02.json` 延续原113定义／546映射，新增 `cedarkit.qflx`、`cedarkit.qfxsfc.any`、`cedarkit.qfxsfc` 三份服务定义和10条映射，形成参数12／116定义、映射14／556条及catalog47。`browser-current.json` 选择revision8，包含554作用域定义、169稳定ID和1325作用域映射。

QFLX覆盖GFS／MESO‑3KM／TYM分析及预报六行，使用各自同文件Q／U／V独立复算和打包误差传播支持 `g/(cm.hPa.s)`。地表QFX覆盖MESO‑3KM／TYM四行，单位 `kg/(m2.s)`；两类都是瞬时量。实际空响应单位通过明确审核映射保留来源，原值不套用旧十倍字面、不乘服务metadata尺度、不转潜热、不当累计能量。

范围仅为2026-11-02 12UTC、39–41N／115–117E，分析0h、预报6／48h及各产品审核层域；33组实际服务／原场边界样本独立登记为expected cells。历史服务557行已验、456行未验，另67条本次缺证／失败行逐行保留；质量485、本地95／集合48组及模式层用户暂缓均独立跟踪。使用原导出器生成运行和浏览器快照，不手改生成文件。[核查与组合验收](../../doc/2026-11-04-stage1.2-query-reki/evidence/task-t02/README.md)

### T03：产品专属土温层表

当前`authoring/cmadaas-task-t03.json`保留原116定义、556映射与五张翻译表，新增六个K单位土温层定义、20条服务映射及六张产品专属联合层表，形成参数13／122定义、映射15／576条、catalog48及browser9。浏览器560作用域定义／171稳定ID／1345映射。

规范身份为明确上下边界：GFS的0–10／10–40／40–100／100–200cm，MESO‑3KM／TYM已核0–10／10–30／60–100cm。服务中点只作为本产品联合键，不进行通用106单位改写。实际范围限2026-11-02 12UTC、39–41N／115–117E、分析0h／预报6h。六行历史土温按明确有限层域交付，30–60cm层45四个失败单元独立保留；GFS分析与TYM预报旧错误层标保留原值并记录实测更正。

土壤湿度kg/kg与产品m3/m3的冲突不靠相似数值换算，六行待证；1KM四条土壤行缺自身载体与可读服务。历史563已验／450未验，原485质量单元、T02两个控制观察及T03四个土温单元独立计数，本地95／集合48组不变。[逐项核查](../../doc/2026-11-04-stage1.2-query-reki/evidence/task-t03/README.md)

## ORIG-09 native release

[The ORIG-09 release](authoring/cemc-orig-task-orig09.json) applies the ORIG-06 naming decisions to the published native definitions and binds the ORIG-07 and ORIG-08 additions to their reviewed cycles, forecast hours, and ensemble members. Catalog v50 pins six ORIG resource pairs. Rebuild browser revision 11 using `--policy authoring/browser-reviewed-v11.json` and the [ORIG-09 wheel](../../doc/2026-11-11-stage1.3-query-reki/evidence/orig-09/README.md).

Run the native export from this repository with `cedarkit-query` 0.2.1. A catalog v49 input produces the release, and the v50 catalog extracted from the ORIG-09 wheel reproduces it byte for byte.

```sh
python tools/export_cemc_orig.py \
  --catalog /tmp/reki-orig09/reki/catalog/builtin/catalog-v1.json \
  --additions authoring/cemc-orig-task06b.json \
  --additions authoring/cemc-orig-task06c.json \
  --additions authoring/cemc-orig-task06i.json \
  --additions authoring/cemc-orig-task-n04b-01.json \
  --additions authoring/cemc-orig-task-orig07.json \
  --additions authoring/cemc-orig-task-orig08.json \
  --release authoring/cemc-orig-task-orig09.json \
  --output /tmp/cemc-orig-v50
```

## Stage 1.4 ORIG naming decisions

The [stage 1.4 naming review](authoring/cemc-orig-stage1.4-name-review.json) records the 1.4-03 decisions for 455 of the 463 frozen ORIG carrier groups. `groups_by_product` links each decision to the carrier IDs in the stage evidence. `definition_source_by_product` identifies the v50 ORIG definition or archived definition that supplies the stable ID for each product. The review also lists inherited definitions that need a scoped name change and existing aliases that move to the mapped definition.

The [stage 1.4 conflict review](authoring/cemc-orig-stage1.4-conflict-review.json) adds `cldb` and `cldt` for six cloud-height carrier groups in GFS, MESO‑1KM, and MESO‑3KM. It records the reproduced `UHMAX` encoding for three products and carries two unresolved identities and the TYM physical layer into follow-up. Apply its approved decisions alongside the 1.4-03 review. [Evidence and handoff](../../doc/2026-11-13-stage1.4-query-reki/evidence/1.4-04/README.md)

The [stage 1.4 bindings](authoring/cemc-orig-stage1.4-bindings.json) add product-scoped parameter definitions and GRIB2 mappings for the 463 frozen carrier groups. Catalog v52 adds GFS `glw` and REPS `sf` under their existing stable IDs. These two bindings expose the original decoded values and retain the encoded metadata. Their physical meanings and stored units are pending product evidence. [Original-value bindings](../../doc/2026-11-13-stage1.4-query-reki/evidence/1.4-06-original-values/README.md)

Append `--binding-candidate authoring/cemc-orig-stage1.4-bindings.json` to the ORIG-09 export command and use a new output directory. The formal v52 catalog refers to the exported resource files by relative path. Mappings with a unit rule retain reviewed value semantics. The v51 candidate for the first 461 carrier groups can be reproduced from commit `f40d0e7`. [v52 formal export and installation](../../doc/2026-11-13-stage1.4-query-reki/evidence/1.4-07/README.md) · [v51 validation and replay](../../doc/2026-11-13-stage1.4-query-reki/evidence/1.4-05/README.md)

## Stage 1.5 ORIG K-index units

Add `--mapping-refinement authoring/cemc-orig-stage1.5-kindex-units.json` to the native export command that selects the v52 binding. The eight derived mapping branches publish the stored K-index values in K for GFS, MESO-1KM, MESO-3KM, and TYM at 2026-11-02 12 UTC and leads 0, 6, and 48 hours. The scale is the numeric temperature-index scale with zero offset. Browser revision 12 can be rebuilt with `--policy authoring/browser-reviewed-v12.json` and the v52 wheel. [Stage 1.5-04 evidence](../../doc/2026-11-14-stage1.5-query-reki/evidence/1.5-04/README.md)

## Stage 1.5 ORIG snowfall units

For catalog v54, append `--mapping-refinement authoring/cemc-orig-stage1.5-snowfall.json` after the K-index refinement. The six snowfall branches match the reference time and the native accumulation length. They expose the unchanged GFS, MESO-3KM, and TYM surface `cedarkit.sf` values in meters of liquid-water equivalent at 2026-11-02 12 UTC and leads 0, 6, and 48 hours. Browser revision 13 can be rebuilt with `--policy authoring/browser-reviewed-v13.json` and the v53 wheel. [Stage 1.5-04C evidence](../../doc/2026-11-14-stage1.5-query-reki/evidence/1.5-04C/README.md)

## Stage 1.5 ORIG vertical diagnostics

For catalog v55, append `--mapping-refinement authoring/cemc-orig-stage1.5-vertical-diagnostics.json` after the snowfall refinement. It records the terrain-relative cloud base and cloud top reference for GFS and MESO-3KM and applies a unit rule in meters to the absolute geopotential height of maximum radar reflectivity for MESO-3KM. The reviewed cycle is 2026-11-02 12 UTC at 0, 6 and 48 hours. Browser revision 14 can be rebuilt with `--policy authoring/browser-reviewed-v14.json` and the v54 wheel. [Stage 1.5-04D evidence](../../doc/2026-11-14-stage1.5-query-reki/evidence/1.5-04D/README.md)

For catalog v56, append `--mapping-refinement authoring/cemc-orig-stage1.5-snowfall-supplement.json` after the vertical diagnostics refinement. The new unit rules preserve the stored liquid-water-equivalent depth in meters for MESO-1KM at 2026-11-02 12 UTC and for REPS members 0, 1, 2 and 14 at 2026-11-02 06 UTC, both at leads 0, 6 and 48 hours. The REPS rule preserves the encoded interval and records the convective snow term recomputed at each output. Browser revision 15 can be rebuilt with `--policy authoring/browser-reviewed-v15.json` and the v55 wheel. [Snowfall supplement](../../doc/2026-11-14-stage1.5-query-reki/evidence/1.5-04C/supplement/README.md)
