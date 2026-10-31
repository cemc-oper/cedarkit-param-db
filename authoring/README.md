# Current parameter authoring

`review-schema4.db` is the maintained schema-4 authoring entry. It was copied
byte-for-byte from the final 223-mapping review on 2026-10-31. The root
`cedarkit_param.db` remains the unchanged schema-3 input. Do not interchange them.

`current.json` selects six whole mapping resources and the explicit identities
and versions of their parameter slices. Mapping versions remain GFS4 and the
other five3; parameter versions remain2. Its consolidation baseline documents
the origin checkpoint, not a lock on future reviewed edits.

From the repository root:

```bash
uv run python tools/authoring.py export --out-dir /tmp/cedarkit-current-export
uv run python tools/authoring.py export --db /tmp/review-candidate.db --out-dir /tmp/cedarkit-candidate-export
uv run python -m cedarkit_param_db --db authoring/review-schema4.db migration-report
```

Use a fresh output directory. The utility checks the complete selected resource
groups through the existing finite-slice exporter. It neither adds definitions
or mappings nor installs exports into reki. Current exports do not need the
historical archive, producer samples, or predecessor databases.

Each export group reads one temporary SQLite backup, including committed WAL
pages. Authoring changes made after that snapshot do not affect later slices
in the group. The source connection closes before slice export; the temporary
snapshot and staging directory are cleaned on success or failure.

Make source-bound edits in a checked `transaction`, optionally first in a
temporary `copy-review` candidate. Promote the reviewed state to this fixed
path and record the actual incremental decision; Git retains previous states.
A change record should identify the stable ID, old/new values, applicability,
evidence position and SHA256, dependent reassessment, and resource revisions.
The existing `definition-reviews.json` retains the three reviewed variants and
their six still-open backend obligations. Legacy migration-report has 429 open
obligations; together these remain435. Do not drop the extra six from reporting.

Keep small review decisions and authoring tools in this repository. Store full
reports, candidate database checkpoints, temporary exports and execution logs
under workspace `doc/`. A conversation boundary does not create a migration.
Create real migration sources only when schema/data-upgrade semantics need one.

For historical locators use `tools/authoring.py resolve <old-workspace-path>`.
`current.json` pins the archive index SHA. The index maps original paths to
archived bytes; the 13 relative compatibility links keep original evidence and
historical replay scripts usable without modifying their recorded hashes.
