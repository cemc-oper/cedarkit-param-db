# Reviewed browser snapshots, schema 4

`tools/export_browser_snapshot.py` exports the current reviewed text authoring
state for a future schema-4 browser consumer. It does not restore the archived
database application, edit runtime resources, or update the browser site's
generated `public/params.json`.

The reviewed selection and the independent browser content revision are in
`authoring/browser-current.json`. The six ORIG resource groups are reconstructed
from the reviewed base and its ordered authoring increments; the service group
comes from the selected complete CMADaaS authoring slice. Runtime files provide
byte comparison, rather than becoming a second authoring authority.

## Export a new group

With the matching `cedarkit-query` installed, run from this repository:

```sh
python tools/export_browser_snapshot.py \
  --catalog ../../repo/reki/src/reki/catalog/builtin/catalog-v1.json \
  --legacy-snapshot ../cedarkit-param-web/public/params.json \
  --output /tmp/browser-reviewed-current
```

`--catalog` is required and remains owned by reki. `--runtime-dir` defaults to
the catalog's directory. `--author` defaults to this repository's authoring
directory, and `--policy` defaults to `authoring/browser-current.json`.
`--legacy-snapshot` is optional; without it the export does not claim to carry
historical link navigation. All inputs are read only. The output directory must
not already exist, including an empty directory.

The exporter verifies the policy's catalog format, ID, revision and exact byte
digest. It reconstructs and validates each authoring resource with the shared
resource validators, checks each selected dataset combination, compares the
resulting resource bytes with the deployment copy, and checks catalog pins.
Unknown bindings, stale author increments, missing evidence or mismatched
identities/versions/digests fail before publication.

## Group format and content versions

The group manifest/index has `schema_version: 1`, the policy's explicit `id`
and `version`, and the following fields:

| Field | Meaning |
|---|---|
| `scope` | Selected browser group, bounded review/availability status, remaining obligations, and whether legacy navigation is included |
| `catalog` | The original copied catalog's relative path, format/ID/revision, byte size and SHA256; `owner: reki`, `copied_unchanged: true` |
| `sources` | Logical relative source paths with exact input sizes/digests, including authoring, policy, catalog and optional old browser input |
| `snapshots` | Key, relative browser document path, schema version, exact parameter/mapping resource pins and dataset IDs for each group |
| `dataset_bindings` | Each selected dataset's snapshot and parameter/mapping references, retaining its product IDs/revisions |
| `files` | Every other emitted file's relative path, actual byte size and SHA256; the manifest itself is excluded from this list |

The current selection produces seven documents in `browser/{key}/params.json`,
fourteen original runtime files in `resources/`, the original `catalog-v1.json`,
and the manifest. With the optional navigation projection it also produces
`legacy-links.json`. Machine paths, export timestamps and worktree state do not
enter the generated group.

The browser content revision is separate from browser schema 4, catalog content
v40, and each runtime resource's format/ID/revision. Runtime bytes and content
versions are copied unchanged. Edit the browser policy's revision deliberately
when changing a distributed browser group; the exporter never chooses a newer
revision automatically.

Use `--previous /path/to/previous/group` to enforce immutability against a prior
group. The exporter first validates all previous files and their manifest
checksums. The content ID must match, revisions cannot decrease, and the same
revision is allowed only if every file is byte-identical. An explicit newer
revision allows changed browser bytes. This comparison does not overwrite or
modify the previous directory.

## Individual browser document, schema 4

Each document retains the established schema-4 shape:

```text
meta
parameters
mapping_resources
retired_ids
notes
```

`meta` contains `schema_version: 4`, `generated_by: cedarkit-param-db`, the
explicit scope, a single effective `parameter_resource`, and counts for
parameters, aliases and mappings. Its parameter reference includes
`api_version`, `id`, `version` and the SHA256 of the unchanged resource file in
`resources/`. Mapping byte digests are recorded in the group manifest's pins.
These are digests of the original runtime files, not hashes of the inline
browser projection.

`parameters` contains the flat local definitions. Stable IDs, parents,
aliases, units, descriptions and fixed conditions are preserved. A variant
remains a parameter with its own ID, parent and local conditions; it is not
flattened into a duplicate effective definition tree. `mapping_resources`
retains the complete selected mapping resource, including scoped mapping IDs,
backend, applicability, conditions, native translation configuration, shared
tables and evidence references.

Identity-indexed records and alias/evidence sets are sorted for the browser
projection. Arrays inside conditions and translation configuration keep their
declared order. The copied runtime files preserve their exact original bytes
and ordering.

There is no old `entries`, `variants` or `key` structure. The seven parameter
resources remain separate because the same stable ID can have different local
definitions in different resources. Consumers must retain resource context;
they must not resolve these differences with last-write-wins deduplication.

`meta.scope.kind` is `parameter_mappings`. It records the whole reviewed
registry's parameter IDs, the IDs directly referenced by selected mappings,
the mapping resource ID, selected dataset IDs, `runtime_mappings: true` and
`complete_product_coverage: false`. Review status means reviewed authoring and
reviewed mappings with the cited references, rather than guaranteed availability
or independent physical acceptance for every product/time/member combination.
The existing service-history, quality-cell, native-gap, deferred modelvar and
unreaudited-archive obligations remain explicit.

`retired_ids` and `notes` are empty for this slice. It contains no newly reviewed
tombstones or editorial notes, and does not silently import them from the old
database. Absence from this reviewed slice does not retire a historical ID.

## Historical navigation

When a schema-3 browser file is explicitly supplied, `legacy-links.json` keeps
only GRIB triplets and stable IDs from its entries/variants, plus targets in the
current scoped snapshots. Each triplet retains every candidate ID; an ID absent
from the current selection is marked `historical_only: true`. Current targets
carry a snapshot key/path and parameter resource ID, so code reuse and
cross-resource definition differences remain visible.

The index is historical navigation only. It does not copy old units,
descriptions, native conditions or support status into current authoring.
Schema-3 page routing, schema-4 loading/types, search/details and the UI handling
of ambiguous or historical-only links belong to N03B. Generating this group does
not establish that the current site consumes schema 4.

## Publication and verification

All documents are built and shared-validated before writing. Publication uses a
private sibling staging directory, re-reads staged files, checks their content
and byte digests, then renames the new group into place. Failed staging or
validation removes the private directory and leaves existing groups intact.
This is a local new-directory publication step, not a concurrent release service.

Programmatic acceptance tools can call:

```python
files = build_bundle(author=author_dir, policy=policy_file,
                     catalog=catalog_file, runtime_dir=runtime_dir,
                     legacy_snapshot=old_browser_file)
manifest = write_bundle(files, new_output_dir, previous=old_group_dir)
```

`build_bundle` returns a mapping of relative paths to immutable bytes and does
not create output files. `write_bundle` validates that mapping and the optional
previous group before creating private staging. The site's prior generated
snapshot and earlier groups remain available for rollback; N03B and N10G still
own consumer and combined-candidate acceptance.
