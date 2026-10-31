# Migration sources and historical compatibility

Actual schema/data upgrade sources belong here. Full database copies, generated
reports and per-conversation exports do not. Continue ordinary development at
[`authoring/current.json`](../authoring/current.json) using
[`tools/authoring.py`](../tools/authoring.py).

The 13 `stage1.1-*` entries are relative symbolic links into the workspace
[archive](../../../doc/archives/cedarkit-param-db/stage1.1-migrations/README.md),
not additional stored copies. They preserve old evidence/replay locators.
Never write a new batch through a historical link or add more session snapshots.
The archived files are immutable; SHA256 verification is available with:

```bash
uv run python tools/authoring.py check-archive
```

The old directory removals/link replacements are normal working-tree changes.
Existing staged blobs were preserved during consolidation; review and stage the
whole intended consolidation before committing. Git history was not rewritten.
