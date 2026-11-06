"""Export reviewed authoring resources as an atomic schema-4 browser group."""

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile

from cedarkit_query import load_value, validate_resource_set


AUTHOR = Path(__file__).resolve().parents[1] / "authoring"
JSON_SCHEMA_VERSION = 4


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def _read(path):
    raw = Path(path).read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {Path(path).name}")
    return value, raw


def _name(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("bundle and author paths must be relative POSIX paths")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise ValueError("bundle and author paths must remain within their group")
    return value


def _revision(value):
    if not isinstance(value, str) or not value.isdigit() or str(int(value)) != value or int(value) < 1:
        raise ValueError("browser content version must be a positive integer string")
    return int(value)


def _info(path, raw, resource=None):
    result = {"path": path, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    if resource is not None:
        result.update({key: resource[key] for key in ("api_version", "id", "version")})
        if "backend" in resource:
            result["backend"] = resource["backend"]
    return result


def _canonical_resource(resource, kind):
    """Sort identity-indexed records and reference sets, never condition arrays."""
    resource = deepcopy(resource)
    if kind == "parameters":
        resource["parameters"].sort(key=lambda row: row["parameter_id"])
        for row in resource["parameters"]:
            if "aliases" in row:
                row["aliases"].sort()
    else:
        resource["mappings"].sort(key=lambda row: row["id"])
        resource["tables"].sort(key=lambda row: row["id"])
        for row in resource["mappings"]:
            row["evidence"].sort()
        for table in resource["tables"]:
            table["evidence"].sort()
            table["rows"].sort(key=lambda row: row["id"])
            for row in table["rows"]:
                if "evidence" in row:
                    row["evidence"].sort()
    return resource


def _browser(parameters, mappings, parameter_pin, dataset_ids, policy):
    p = _canonical_resource(parameters, "parameters")
    m = _canonical_resource(mappings, "mappings")
    scope = {
        "kind": "parameter_mappings",
        "parameter_ids": [row["parameter_id"] for row in p["parameters"]],
        "requested_parameter_ids": sorted({row["parameter_id"] for row in m["mappings"]}),
        "mapping_resource_ids": [m["id"]],
        "dataset_ids": sorted(dataset_ids),
        "definition_selection": "whole_reviewed_parameter_resource",
        "runtime_mappings": True,
        "complete_product_coverage": False,
        "evidence_status": deepcopy(policy["review_status"]),
        "remaining_migration_obligations": deepcopy(policy["remaining_migration_obligations"]),
        "editorial_and_retirement_scope": "No reviewed tombstones or editorial notes in this slice; archived records are not imported.",
    }
    return {
        "meta": {
            "schema_version": JSON_SCHEMA_VERSION,
            "generated_by": "cedarkit-param-db",
            "scope": scope,
            "parameter_resource": {key: parameter_pin[key] for key in ("api_version", "id", "version", "sha256")},
            "stats": {"parameters": len(p["parameters"]),
                      "aliases": sum(len(row.get("aliases", [])) for row in p["parameters"]),
                      "mappings": len(m["mappings"])},
        },
        "parameters": p["parameters"],
        "mapping_resources": [m],
        "retired_ids": [],
        "notes": [],
    }


def _binding(dataset, key, parameter_pin, mapping_pin):
    backend = mapping_pin["backend"]
    for pin, reference in ((parameter_pin, dataset.get("parameter_registry", {})),
                           (mapping_pin, dataset.get("mappings", {}).get(backend, {}))):
        if reference.get("version") != pin["version"] or reference.get("sha256") != pin["sha256"]:
            raise ValueError("catalog resource pin differs from authored bytes")
    return {"dataset_id": dataset["id"], "snapshot": key,
            "parameter_registry": parameter_pin, "mappings": {backend: mapping_pin},
            "products": [{"id": product["id"], "version": product["version"]}
                         for product in dataset["products"]]}


def _legacy_links(document, raw, snapshots, files):
    if document.get("meta", {}).get("schema_version") != 3 or not isinstance(document.get("entries"), list):
        raise ValueError("legacy navigation requires an explicit schema-3 browser snapshot")
    current = {}
    for snapshot in snapshots:
        browser = json.loads(files[snapshot["path"]])
        for parameter in browser["parameters"]:
            current.setdefault(parameter["parameter_id"], []).append(
                {"snapshot": snapshot["key"], "path": snapshot["path"],
                 "parameter_resource_id": snapshot["parameter_resource"]["id"]})
    grouped = {}
    for entry in document["entries"]:
        key = entry.get("key", {})
        values = [key.get(name) for name in ("discipline", "category", "number")]
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError("legacy entry requires a numeric GRIB triplet")
        ids = grouped.setdefault(".".join(map(str, values)), set())
        for row in [entry, *entry.get("variants", [])]:
            parameter_id = row.get("parameter_id")
            if not isinstance(parameter_id, str) or not parameter_id:
                raise ValueError("legacy navigation requires stable parameter IDs")
            ids.add(parameter_id)
    return {
        "schema_version": 1,
        "scope": {"purpose": "historical_navigation_only", "current_support": False},
        "source": _info("legacy/params-schema3.json", raw),
        "links": [{"triplet": triplet,
                   "candidates": [{"parameter_id": parameter_id,
                                   "historical_only": parameter_id not in current,
                                   "current_targets": current.get(parameter_id, [])}
                                  for parameter_id in sorted(grouped[triplet])]}
                  for triplet in sorted(grouped, key=lambda value: tuple(map(int, value.split("."))))],
    }


def build_bundle(*, author, policy, catalog, runtime_dir=None, legacy_snapshot=None):
    """Read authoritative text inputs and return validated relative file bytes."""
    author, policy, catalog = Path(author), Path(policy), Path(catalog)
    runtime_dir = Path(runtime_dir) if runtime_dir is not None else catalog.parent
    policy_doc, policy_raw = _read(policy)
    if policy_doc.get("schema_version") != 1 or not isinstance(policy_doc.get("id"), str) or not policy_doc["id"]:
        raise ValueError("unsupported browser policy")
    _revision(policy_doc.get("version"))
    catalog_doc, catalog_raw = _read(catalog)
    catalog_doc = load_value(catalog_raw.decode("utf-8"), "catalog").to_dict()
    wanted_catalog = policy_doc["catalog"]
    for key in ("api_version", "id", "version"):
        if wanted_catalog[key] != catalog_doc[key]:
            raise ValueError("catalog identity differs from the reviewed policy")
    if wanted_catalog["sha256"] != hashlib.sha256(catalog_raw).hexdigest():
        raise ValueError("catalog bytes differ from the reviewed policy")
    sources = [_info("authoring/browser-current.json", policy_raw), _info("catalog-v1.json", catalog_raw)]

    def read_author(name):
        name = _name(name)
        document, raw = _read(author / name)
        sources.append(_info("authoring/" + name, raw))
        return document

    selected = policy_doc["resources"]
    if not isinstance(selected, list) or not selected:
        raise ValueError("browser policy must select reviewed resource groups")
    native = {}
    if any(row["mappings"]["backend"] == "grib2" for row in selected):
        native = read_author(policy_doc["authoring"]["native_base"])["products"]
        for name in policy_doc["authoring"]["native_additions"]:
            additions = read_author(name)
            for key, product in additions["products"].items():
                if key not in native:
                    raise ValueError("authoring increment references an unknown native product")
                for kind in ("parameters", "mappings"):
                    resource, extra = native[key][kind], product[kind]
                    if int(extra["version"]) <= int(resource["version"]):
                        raise ValueError("authoring increments require newer resource revisions")
                    resource["version"] = extra["version"]
                    resource[kind].extend(extra[kind])
    service = read_author(policy_doc["authoring"]["service"]) if any(
        row["mappings"]["backend"] == "cmadaas" for row in selected) else None
    datasets = {row["id"]: row for row in catalog_doc["datasets"]}
    files = {"catalog-v1.json": catalog_raw}
    snapshots, bindings, seen_keys, seen_datasets = [], [], set(), set()
    for row in sorted(selected, key=lambda item: item["key"]):
        key = row["key"]
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", key) or key in seen_keys:
            raise ValueError("browser snapshot keys must be unique portable names")
        seen_keys.add(key)
        backend = row["mappings"]["backend"]
        if backend not in {"grib2", "cmadaas"}:
            raise ValueError("unreviewed browser backend")
        authored = service if backend == "cmadaas" else native[key]
        if backend == "grib2" and row["dataset_ids"] != [authored["dataset"]]:
            raise ValueError("native dataset selection differs from its reviewed authoring")
        resources, pins = {}, {}
        for kind in ("parameters", "mappings"):
            resource = load_value(encode(authored[kind]).decode("utf-8"), kind).to_dict()
            expected = row[kind]
            if resource["id"] != expected["id"] or resource["version"] != expected["version"]:
                raise ValueError("authoring resource identity differs from policy")
            filename = _name(expected["file"])
            raw = (runtime_dir / filename).read_bytes()
            if encode(resource) != raw or hashlib.sha256(raw).hexdigest() != expected["sha256"]:
                raise ValueError("authoring export differs from the pinned runtime resource bytes")
            path = "resources/" + filename
            if path in files:
                raise ValueError("duplicate runtime resource output path")
            files[path] = raw
            resources[kind] = resource
            pins[kind] = _info(path, raw, resource)
        if resources["mappings"]["backend"] != backend or any(
                not mapping["evidence"] for mapping in resources["mappings"]["mappings"]):
            raise ValueError("reviewed mappings require matching backend and evidence")
        dataset_ids = row["dataset_ids"]
        if not isinstance(dataset_ids, list) or not dataset_ids or len(set(dataset_ids)) != len(dataset_ids):
            raise ValueError("explicit unique dataset bindings are required")
        for dataset_id in sorted(dataset_ids):
            if dataset_id in seen_datasets or dataset_id not in datasets:
                raise ValueError("duplicate or unknown dataset binding")
            seen_datasets.add(dataset_id)
            dataset = datasets[dataset_id]
            validate_resource_set(resources["parameters"], [resources["mappings"]], catalog_doc, dataset_id)
            bindings.append(_binding(dataset, key, pins["parameters"], pins["mappings"]))
        path = f"browser/{key}/params.json"
        files[path] = encode(_browser(resources["parameters"], resources["mappings"],
                                      pins["parameters"], dataset_ids, policy_doc))
        snapshots.append({"key": key, "path": path, "schema_version": JSON_SCHEMA_VERSION,
                          "dataset_ids": sorted(dataset_ids), "parameter_resource": pins["parameters"],
                          "mapping_resources": [pins["mappings"]]})
    if service is not None and {row["id"] for row in service["services"]} != {
            dataset_id for row in selected if row["mappings"]["backend"] == "cmadaas" for dataset_id in row["dataset_ids"]}:
        raise ValueError("service dataset selection differs from reviewed service bindings")
    if legacy_snapshot is not None:
        legacy_doc, raw = _read(legacy_snapshot)
        files["legacy-links.json"] = encode(_legacy_links(legacy_doc, raw, snapshots, files))
        sources.append(_info("legacy/params-schema3.json", raw))
    manifest = {
        "schema_version": 1, "id": policy_doc["id"], "version": policy_doc["version"],
        "scope": {"kind": "parameter_browser_snapshots", "complete_product_coverage": False,
                  "evidence_status": policy_doc["review_status"],
                  "remaining_migration_obligations": policy_doc["remaining_migration_obligations"],
                  "legacy_navigation": legacy_snapshot is not None},
        "catalog": {**_info("catalog-v1.json", catalog_raw, catalog_doc), "owner": "reki", "copied_unchanged": True},
        "sources": sorted(sources, key=lambda item: item["path"]),
        "snapshots": snapshots,
        "dataset_bindings": sorted(bindings, key=lambda item: item["dataset_id"]),
        "files": [_info(name, files[name]) for name in sorted(files)],
    }
    files["manifest.json"] = encode(manifest)
    _validate_files(files)
    return files


def _validate_contents(files):
    if "manifest.json" not in files:
        raise ValueError("browser bundle requires a manifest")
    manifest = json.loads(files["manifest.json"])
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("id"), str) or not manifest["id"]:
        raise ValueError("unsupported browser group manifest")
    _revision(manifest.get("version"))
    entries = manifest["files"]
    if len({item["path"] for item in entries}) != len(entries):
        raise ValueError("duplicate bundle manifest path")
    if set(files) != {item["path"] for item in entries} | {"manifest.json"}:
        raise ValueError("bundle files do not match the manifest")
    for item in entries:
        path = _name(item["path"])
        if item != _info(path, files[path]):
            raise ValueError("bundle content differs from its manifest checksum")
    source_paths = set()
    for source in manifest["sources"]:
        path = _name(source["path"])
        if (set(source) != {"path", "size", "sha256"} or path in source_paths
                or type(source["size"]) is not int or source["size"] < 0
                or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"])):
            raise ValueError("invalid or duplicate relative source byte reference")
        source_paths.add(path)
    catalog = load_value(files[manifest["catalog"]["path"]].decode("utf-8"), "catalog").to_dict()
    if manifest["catalog"] != {**_info("catalog-v1.json", files["catalog-v1.json"], catalog), "owner": "reki", "copied_unchanged": True}:
        raise ValueError("copied catalog identity differs from manifest")
    scope = manifest["scope"]
    if scope["kind"] != "parameter_browser_snapshots" or scope["complete_product_coverage"] is not False:
        raise ValueError("browser group must retain bounded authoring scope")
    if type(scope["legacy_navigation"]) is not bool or scope["legacy_navigation"] != ("legacy-links.json" in files):
        raise ValueError("legacy navigation declaration differs from emitted files")
    datasets = {row["id"]: row for row in catalog["datasets"]}
    expected_bindings, seen_keys, seen_datasets = [], set(), set()
    current_targets = {}
    for snapshot in manifest["snapshots"]:
        key = snapshot["key"]
        if (not isinstance(key, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", key)
                or key in seen_keys or snapshot["path"] != f"browser/{key}/params.json"
                or snapshot["schema_version"] != JSON_SCHEMA_VERSION):
            raise ValueError("invalid or duplicate schema-4 snapshot index")
        seen_keys.add(key)
        dataset_ids = snapshot["dataset_ids"]
        if not isinstance(dataset_ids, list) or not dataset_ids or len(set(dataset_ids)) != len(dataset_ids):
            raise ValueError("snapshot requires explicit unique dataset bindings")
        browser = json.loads(files[snapshot["path"]])
        p_pin, m_pins = snapshot["parameter_resource"], snapshot["mapping_resources"]
        parameters = load_value(files[p_pin["path"]].decode("utf-8"), "parameters").to_dict()
        mappings = [load_value(files[pin["path"]].decode("utf-8"), "mappings").to_dict() for pin in m_pins]
        if p_pin != _info(p_pin["path"], files[p_pin["path"]], parameters) or len(mappings) != 1:
            raise ValueError("invalid snapshot runtime resource pin")
        if m_pins[0] != _info(m_pins[0]["path"], files[m_pins[0]["path"]], mappings[0]):
            raise ValueError("invalid snapshot mapping resource pin")
        for dataset_id in dataset_ids:
            if dataset_id not in datasets or dataset_id in seen_datasets:
                raise ValueError("duplicate or unknown snapshot dataset binding")
            seen_datasets.add(dataset_id)
            validate_resource_set(parameters, mappings, catalog, dataset_id)
            expected_bindings.append(_binding(datasets[dataset_id], key, p_pin, m_pins[0]))
        expected = _browser(parameters, mappings[0], p_pin, dataset_ids, {
            "review_status": manifest["scope"]["evidence_status"],
            "remaining_migration_obligations": manifest["scope"]["remaining_migration_obligations"],
        })
        if browser != expected:
            raise ValueError("schema-4 browser snapshot differs from its pinned reviewed resources")
        for parameter in browser["parameters"]:
            current_targets.setdefault(parameter["parameter_id"], []).append(
                {"snapshot": key, "path": snapshot["path"], "parameter_resource_id": p_pin["id"]})
    if not seen_keys or manifest["dataset_bindings"] != sorted(expected_bindings, key=lambda row: row["dataset_id"]):
        raise ValueError("dataset binding index differs from catalog and snapshot resource pins")
    if scope["legacy_navigation"]:
        legacy = json.loads(files["legacy-links.json"])
        if (set(legacy) != {"schema_version", "scope", "source", "links"}
                or legacy["schema_version"] != 1
                or legacy["scope"] != {"purpose": "historical_navigation_only", "current_support": False}):
            raise ValueError("legacy links must remain historical navigation only")
        source = legacy["source"]
        if (source["path"] != "legacy/params-schema3.json" or type(source["size"]) is not int
                or source["size"] < 0 or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"])):
            raise ValueError("invalid legacy source byte reference")
        seen_triplets = set()
        for link in legacy["links"]:
            triplet = link["triplet"]
            if (set(link) != {"triplet", "candidates"} or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", triplet)
                    or triplet in seen_triplets):
                raise ValueError("invalid or duplicate legacy navigation triplet")
            seen_triplets.add(triplet)
            seen_ids = set()
            for candidate in link["candidates"]:
                parameter_id = candidate["parameter_id"]
                if (set(candidate) != {"parameter_id", "historical_only", "current_targets"}
                        or not isinstance(parameter_id, str) or not parameter_id or parameter_id in seen_ids
                        or candidate["current_targets"] != current_targets.get(parameter_id, [])
                        or candidate["historical_only"] is not (parameter_id not in current_targets)):
                    raise ValueError("legacy candidate differs from current scoped definitions")
                seen_ids.add(parameter_id)
    return manifest


def _validate_files(files):
    try:
        return _validate_contents(files)
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        raise ValueError(f"malformed browser bundle: {exc}") from exc


def _previous_files(path):
    path = Path(path)
    files = {str(item.relative_to(path).as_posix()): item.read_bytes()
             for item in path.rglob("*") if item.is_file()}
    _validate_files(files)
    return files


def _write_file(path, raw):
    path.write_bytes(raw)


def write_bundle(files, output, previous=None):
    """Verify immutable content revisions, then publish a new directory atomically."""
    manifest = _validate_files(files)
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    if previous is not None:
        old_files = _previous_files(previous)
        old = json.loads(old_files["manifest.json"])
        if old["id"] != manifest["id"]:
            raise ValueError("previous browser group has another content identity")
        if _revision(manifest["version"]) < _revision(old["version"]):
            raise ValueError("browser content revision cannot move backwards")
        if manifest["version"] == old["version"] and files != old_files:
            raise ValueError("changed browser bytes require a newer content version")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".cedarkit-browser-", dir=output.parent))
    try:
        for name, raw in files.items():
            path = stage / _name(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_file(path, raw)
        staged = _previous_files(stage)
        if staged != files:
            raise ValueError("staged browser bytes differ from the validated source view")
        if output.exists():
            raise FileExistsError(output)
        os.rename(stage, output)
        return manifest
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--author", type=Path, default=AUTHOR)
    parser.add_argument("--policy", type=Path, default=AUTHOR / "browser-current.json")
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path)
    parser.add_argument("--legacy-snapshot", type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        files = build_bundle(author=args.author, policy=args.policy, catalog=args.catalog,
                             runtime_dir=args.runtime_dir, legacy_snapshot=args.legacy_snapshot)
        manifest = write_bundle(files, args.output, previous=args.previous)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps({"id": manifest["id"], "version": manifest["version"],
                      "snapshots": len(manifest["snapshots"]), "files": len(files)}, sort_keys=True))


if __name__ == "__main__":
    main()
