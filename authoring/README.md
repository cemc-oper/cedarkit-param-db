# Current parameter authoring

`state/manifest.json` and the 18 stable, primary-key-ordered JSONL tables in
`state/` are the maintained authoring source. Each line is one database row.
SQL JSON columns stay strings, preserving their original bytes and legacy audit
payloads. The manifest records table layouts, row counts and SHA256; schema4
DDL, generated columns, constraints and identity-protection triggers come from
the packaged schema, whose fingerprint must match.

The current state is 243 mappings/233 active parameters. Legacy definitions are
138 resolved/83 needs_evidence, with 416 unresolved legacy obligations. The
separate `definition-reviews.json` retains twelve authored variants and twenty-four backend
obligations, giving 440 combined obligations. The GFS parameter slice is v6 and
mapping v11; the other five slices remain parameter v2/mapping v5. Review decisions
and old/new values are in [`reviews/surface-radiation.json`](reviews/surface-radiation.json).
The recorded radiation leads are verification samples, not runtime limits.
The previous 235 mappings and their evidence remain intact. The earlier
lead extension and its remaining conflicts are recorded in
[`reviews/gfs-clear-sky-energy-leads.json`](reviews/gfs-clear-sky-energy-leads.json).
The earlier [`GSWC/GULWC review`](reviews/gswc-gulwc.json) corrects six legacy
definitions and reassesses their dependent GRIB obligations. GSWC is net
shortwave, distinct from downward GDSWC. The GULWC decoder's `unknown` unit and
numeric `parameterUnits=224` are retained; the exact mapping declares J/m2 from
original package, model and business evidence. Four new mappings use two
explicit since-initialization variants. That review did not add top bindings.
Output retains the original signed J/m2 values without duration scaling or
accumulation differencing. This subset does not establish a complete domain.
The latest [GSW/GLW review](reviews/gsw-glw.json) corrects the case111 GSW
energy unit to J/m2 and reassesses TSW inheritance plus both GRIB dependencies.
The explicit surface since-initialization variant preserves the broad GSW
conditions; its original six sampled leads do not define a support whitelist. This is
unqualified net shortwave, separate from clear-sky GSWC and case113 GNSW flux.
GLW remains unbound: original case112 says net longwave, but business table0
row38 Chinese says downward longwave while its element is NLWRF. Its stable
old definition and unresolved obligations are preserved pending producer
clarification; no derived-unit lookup or native code alone resolves that link.
The `consolidation_baseline` in current.json remains the historical223 origin.

The latest [CEMC step correction](reviews/cemc-step-sampling.json) follows the
user-confirmed lead invariance of CEMC GRIB2 fields. All208 mappings in the six
current slices retain their IDs and native/physical constraints but omit
`when.step`. Catalog product scopes and provision rows likewise omit sampled
steps. Public Query step/valid_time and explicit caller bounds remain valid;
actual message time/statistical intervals are still checked. Historical leads
remain evidence of tests performed, without restricting other valid leads or
claiming complete product availability. No GSW3h/9h tests were added.

The latest [generic pressure review](reviews/cemc-pressure-sampling.json) removes
sampled numeric level lists and their accompanying level_unit from66 pressure
mappings for existing t/u/v/q/rh identities. Native first surface100/second255,
pressure decoding/scaling and Pa/hPa coordinate interpretation remain in the
translation rules. All parameter definitions and nonpressure conditions,
including t2m/u10m/v10m heights and soil-layer boundaries, retain their bytes.
Catalog/current profile pressure rows likewise omit sampled numeric levels;
explicit caller level filters and scope bounds remain valid. Representative
rule-group checks do not claim every layer/lead has been tested, and no GSW3h/9h
tests are added. No new elements or complete product-domain claims are implied.

The latest [GFS TOA review](reviews/gfs-toa-energy.json) confirms the existing
TSW, TSWC, TUSWC and TULWC definitions and their inherited J/m2 units without
changing their stable identities. Four explicit since-initialization variants
and eight initial/forecast mappings bind the actual top-of-atmosphere fields.
Mapping conditions retain the real atmosphere_top constraint and exact native
contexts, with no sampled step or numeric level whitelist. TUSWC is 0/4/53;
TULWC is the separately reviewed master4/local1/PDT8 0/5/224 top encoding.
Decoder absence placeholders do not supply a unit: producer declarations and
business evidence establish the finite mapping's J/m2 declaration. Known unit
conflicts still fail. Existing definitions, fixed height and soil layer variants,
and other five system resources retain their bytes. Complete product/backend
coverage and independent physical acceptance remain open; GLW is unchanged.

From the repository root, always use fresh output paths:

```bash
uv run python tools/authoring.py build --db /tmp/cedarkit-review.db
uv run python -m cedarkit_param_db --db /tmp/cedarkit-review.db migration-report
# Apply checked transaction/review API changes to the explicit candidate.
uv run python tools/authoring.py capture --db /tmp/cedarkit-review.db
uv run python tools/authoring.py export --out-dir /tmp/cedarkit-current-export
```

`build` creates a new database exclusively. It verifies the entire source, all
18 table values, schema, generated references, foreign keys and full resource
semantics; failed builds leave no candidate database. `capture` validates one
WAL-aware SQLite backup and publishes a complete text generation, restoring the
old source on publication failure. `capture --out-dir <new-directory>` keeps the
maintained source unchanged. Review the text diff together with resource version
changes and small evidence-bearing decisions before committing.

Default `export` rebuilds once from text and reads every selected slice from that
same temporary database. It does not read `review-schema4.db`, even if that file
exists with different contents. The generated local database is ignored by Git;
the original227-state bytes were preserved in workspace maintenance evidence.
The root `cedarkit_param.db` remains the unchanged historical schema3 input.
An explicit `export --db /tmp/candidate.db` still uses one WAL-aware backup for
the group. Source/candidate failures never publish partial outputs, and all
temporary state is cleaned. Runtime export contracts and closure gates are
unchanged; no versions or resources are automatically installed into reki.

Do not hand-edit a JSONL table without its manifest or drop authoring/audit
rows. Prefer the checked candidate workflow; capture updates hashes/counts and
stable ordering together. Keep the source at this fixed path, and keep full
reports, temporary candidates and execution logs under workspace doc or/tmp.
A conversation boundary does not create a migration or a full database commit.
New schema semantics require an explicit schema migration rather than silently
accepting extra tables, columns, indexes or triggers.

For historical locators, `tools/authoring.py resolve <old-workspace-path>` checks
both the pinned archive index and payload SHA. The13 compatibility links and
252 archived files retain their bytes. Neither the archive nor predecessor
checkpoints are required by current text-based build/export.
