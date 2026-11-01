# Current parameter authoring

`state/manifest.json` and the 18 stable, primary-key-ordered JSONL tables in
`state/` are the maintained authoring source. Each line is one database row.
SQL JSON columns stay strings, preserving their original bytes and legacy audit
payloads. The manifest records table layouts, row counts and SHA256; schema4
DDL, generated columns, constraints and identity-protection triggers come from
the packaged schema, whose fingerprint must match.

The current state is 233 mappings/228 active parameters. Legacy definitions are
136 resolved/85 needs_evidence, with 418 unresolved legacy obligations. The
separate `definition-reviews.json` retains seven authored variants and fourteen backend
obligations, giving 432 combined obligations. The GFS parameter slice is v4 and
mapping v7; the other five slices remain parameter v2/mapping v3. TUSWC has an
active authoring definition without a runtime product binding. Review decisions
and old/new values are in [`reviews/surface-radiation.json`](reviews/surface-radiation.json).
Four GFS surface clear-sky energy integrals have finite 0/6/12/24/48/72h pairs.
The previous 229 mappings and their evidence remain intact. The earlier
lead extension and its remaining conflicts are recorded in
[`reviews/gfs-clear-sky-energy-leads.json`](reviews/gfs-clear-sky-energy-leads.json).
The latest [`GSWC/GULWC review`](reviews/gswc-gulwc.json) corrects six legacy
definitions and reassesses their dependent GRIB obligations. GSWC is net
shortwave, distinct from downward GDSWC. The GULWC decoder's `unknown` unit and
numeric `parameterUnits=224` are retained; the exact mapping declares J/m2 from
original package, model and business evidence. Four new mappings use two
explicit since-initialization variants. Top definitions do not add top bindings.
Output retains the original signed J/m2 values without duration scaling or
accumulation differencing. This subset does not establish a complete domain.
The `consolidation_baseline` in current.json remains the historical223 origin.

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
