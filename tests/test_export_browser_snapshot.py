"""Browser publication must preserve reviewed scope and fail before publication."""

from __future__ import annotations

import copy
from collections import defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest


REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO.parents[1]
RUNTIME = WORKSPACE / "repo/reki/src/reki/catalog/builtin"


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


@pytest.fixture(scope="session")
def exporter():
    path = REPO / "tools/export_browser_snapshot.py"
    spec = importlib.util.spec_from_file_location("export_browser_snapshot_tests", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Inputs:
    def __init__(self, root):
        self.root = root
        self.author = root / "authoring"
        self.policy = self.author / "browser-policy.json"
        self.catalog = root / "catalog-v1.json"
        self.runtime = root / "runtime"

    def build(self, exporter, **kwargs):
        return exporter.build_bundle(author=self.author, policy=self.policy,
                                     catalog=self.catalog, runtime_dir=self.runtime, **kwargs)

    def repin(self):
        """Keep bytes/pins consistent so a test reaches semantic validation."""
        source = read(self.author / "native.json")["products"]["gfs"]
        policy = read(self.policy)
        catalog = read(self.catalog)
        resource = policy["resources"][0]
        dataset = catalog["datasets"][0]
        for kind in ("parameters", "mappings"):
            raw = encode(source[kind])
            reference = resource[kind]
            reference.update(id=source[kind]["id"], version=source[kind]["version"], sha256=sha256(raw))
            self.runtime.joinpath(reference["file"]).write_bytes(raw)
            pin = dataset["parameter_registry"] if kind == "parameters" else dataset["mappings"]["grib2"]
            pin.update(version=source[kind]["version"], sha256=sha256(raw))
        raw = encode(catalog)
        self.catalog.write_bytes(raw)
        policy["catalog"].update(version=catalog["version"], sha256=sha256(raw))
        self.policy.write_bytes(encode(policy))


@pytest.fixture
def inputs(tmp_path):
    fixture = Inputs(tmp_path / "inputs")
    fixture.author.mkdir(parents=True)
    fixture.runtime.mkdir()
    parameters = read(REPO / "authoring/gfs-task03-parameters.json")
    mappings = read(REPO / "authoring/gfs-task03-mappings.json")
    fixture.author.joinpath("native.json").write_bytes(encode({
        "authoring_revision": "reviewed-fixture",
        "products": {"gfs": {"dataset": "cma_gfs_gmf", "parameters": parameters, "mappings": mappings}},
    }))
    catalog = read(RUNTIME / "catalog-v1.json")
    dataset = next(row for row in catalog["datasets"] if row["id"] == "cma_gfs_gmf")
    product = dataset["products"][0]
    product["provides"] = [row for row in product["provides"] if row["parameter"] in {"cedarkit.t", "cedarkit.t2m"}]
    catalog.update(version="1", datasets=[dataset])
    fixture.catalog.write_bytes(encode(catalog))
    policy = read(REPO / "authoring/browser-current.json")
    policy["version"] = "1"  # Controlled revision tests are independent of the current release.
    policy["authoring"] = {"native_base": "native.json", "native_additions": [], "service": "not-selected.json"}
    policy["resources"] = [next(row for row in policy["resources"] if row["key"] == "gfs")]
    policy["remaining_migration_obligations"] = [{"id": "fixture-unreviewed", "note": "not current support"}]
    fixture.policy.write_bytes(encode(policy))
    fixture.repin()
    return fixture


def browser_documents(files):
    manifest = json.loads(files["manifest.json"])
    return manifest, {row["key"]: json.loads(files[row["path"]]) for row in manifest["snapshots"]}


def legacy_file(inputs):
    path = inputs.root / "old-params.json"
    path.write_bytes(encode({
        "meta": {"schema_version": 3},
        "entries": [{"parameter_id": "cedarkit.t", "key": {"discipline": 0, "category": 0, "number": 0},
                     "variants": [{"parameter_id": "cedarkit.t2m"}, {"parameter_id": "cedarkit.archived"}]}],
    }))
    return path


def test_export_is_byte_identical_across_input_and_output_directories(exporter, inputs, tmp_path):
    first = inputs.build(exporter)
    alternate = tmp_path / "unrelated-absolute-location"
    shutil.copytree(inputs.root, alternate)
    second = Inputs(alternate).build(exporter)
    assert first == second
    assert not any(str(inputs.root).encode() in raw or str(alternate).encode() in raw for raw in first.values())
    exporter.write_bundle(first, tmp_path / "publication-a")
    exporter.write_bundle(second, tmp_path / "publication-b")
    assert {str(p.relative_to(tmp_path / "publication-a")): p.read_bytes()
            for p in (tmp_path / "publication-a").rglob("*") if p.is_file()} == first
    assert {str(p.relative_to(tmp_path / "publication-b")): p.read_bytes()
            for p in (tmp_path / "publication-b").rglob("*") if p.is_file()} == second


@pytest.mark.parametrize("change", ["author", "runtime", "catalog_pin", "policy_pin"])
def test_resource_or_pin_mismatch_is_rejected(exporter, inputs, change):
    if change == "author":
        path = inputs.author / "native.json"
        value = read(path)
        value["products"]["gfs"]["parameters"]["parameters"][0]["description"] = "different reviewed bytes"
    elif change == "runtime":
        path = inputs.runtime / "current-gfs-parameters.json"
        value = read(path)
        value["parameters"][0]["description"] = "runtime drift"
    elif change == "catalog_pin":
        path = inputs.catalog
        value = read(path)
        value["datasets"][0]["parameter_registry"]["sha256"] = "0" * 64
        raw = encode(value)
        path.write_bytes(raw)
        policy = read(inputs.policy)
        policy["catalog"]["sha256"] = sha256(raw)
        inputs.policy.write_bytes(encode(policy))
        with pytest.raises(ValueError):
            inputs.build(exporter)
        return
    else:
        path = inputs.policy
        value = read(path)
        value["resources"][0]["parameters"]["sha256"] = "0" * 64
    path.write_bytes(encode(value))
    with pytest.raises(ValueError):
        inputs.build(exporter)


@pytest.mark.parametrize("change", ["missing_parent", "parent_cycle", "unmapped_provision"])
def test_shared_resource_semantics_are_validated_after_matching_pins(exporter, inputs, change):
    path = inputs.author / "native.json"
    value = read(path)
    definitions = value["products"]["gfs"]["parameters"]["parameters"]
    if change == "missing_parent":
        definitions[1]["parent"] = "cedarkit.unreviewed"
    elif change == "parent_cycle":
        definitions[0]["parent"] = "cedarkit.t2m"
    else:
        value["products"]["gfs"]["mappings"]["mappings"] = value["products"]["gfs"]["mappings"]["mappings"][:1]
    path.write_bytes(encode(value))
    inputs.repin()
    with pytest.raises(ValueError):
        inputs.build(exporter)


def test_condition_lists_keep_author_order(exporter, inputs):
    path = inputs.author / "native.json"
    value = read(path)
    value["products"]["gfs"]["mappings"]["mappings"][0]["when"]["level"] = [1000, 850]
    path.write_bytes(encode(value))
    inputs.repin()
    files = inputs.build(exporter)
    _, browsers = browser_documents(files)
    mapping = browsers["gfs"]["mapping_resources"][0]["mappings"][0]
    assert mapping["when"]["level"] == [1000, 850]


def test_existing_output_is_not_overwritten(exporter, inputs, tmp_path):
    files = inputs.build(exporter)
    output = tmp_path / "published"
    output.mkdir()
    output.joinpath("keep.txt").write_bytes(b"existing publication")
    with pytest.raises(FileExistsError):
        exporter.write_bundle(files, output)
    assert {p.name: p.read_bytes() for p in output.iterdir()} == {"keep.txt": b"existing publication"}


@pytest.mark.parametrize("failure", ["write_error", "corrupt_staged_bytes"])
def test_failed_staging_never_publishes_and_cleans_temporary_directory(exporter, inputs, tmp_path, monkeypatch, failure):
    files = inputs.build(exporter)
    output = tmp_path / "publication"
    previous_children = set(tmp_path.iterdir())
    original = Path.write_bytes
    injected = []

    def write(path, raw):
        if path.name == "params.json":
            injected.append(path)
            if failure == "write_error":
                raise OSError("injected staging write failure")
            return original(path, b"{}\n")
        return original(path, raw)

    monkeypatch.setattr(Path, "write_bytes", write)
    with pytest.raises((OSError, ValueError)):
        exporter.write_bundle(files, output)
    assert injected, "the staging fault was not exercised"
    assert not output.exists()
    assert set(tmp_path.iterdir()) == previous_children


def test_previous_snapshot_requires_content_revision_and_disallows_rollback(exporter, inputs, tmp_path):
    original_files = inputs.build(exporter)
    previous = tmp_path / "previous"
    exporter.write_bundle(original_files, previous)
    exporter.write_bundle(original_files, tmp_path / "identical", previous=previous)
    policy = read(inputs.policy)
    policy["remaining_migration_obligations"][0]["note"] = "updated disclosure, same runtime resources"
    inputs.policy.write_bytes(encode(policy))
    changed_files = inputs.build(exporter)
    assert changed_files != original_files
    with pytest.raises(ValueError):
        exporter.write_bundle(changed_files, tmp_path / "same-version", previous=previous)
    assert not (tmp_path / "same-version").exists()
    policy["version"] = "2"
    inputs.policy.write_bytes(encode(policy))
    upgraded_files = inputs.build(exporter)
    upgraded = tmp_path / "upgraded"
    manifest = exporter.write_bundle(upgraded_files, upgraded, previous=previous)
    assert str(manifest["version"]) == "2"
    with pytest.raises(ValueError):
        exporter.write_bundle(original_files, tmp_path / "downgraded", previous=upgraded)
    assert not (tmp_path / "downgraded").exists()
    assert {str(p.relative_to(previous)): p.read_bytes() for p in previous.rglob("*") if p.is_file()} == original_files


def test_corrupt_previous_snapshot_is_rejected_before_new_publication(exporter, inputs, tmp_path):
    files = inputs.build(exporter)
    previous = tmp_path / "previous"
    exporter.write_bundle(files, previous)
    manifest = read(previous / "manifest.json")
    browser = previous / manifest["snapshots"][0]["path"]
    browser.write_bytes(b"{}\n")
    policy = read(inputs.policy)
    policy["version"] = "2"
    inputs.policy.write_bytes(encode(policy))
    with pytest.raises(ValueError):
        exporter.write_bundle(inputs.build(exporter), tmp_path / "next", previous=previous)
    assert not (tmp_path / "next").exists()


@pytest.mark.parametrize("change", ["missing_snapshot", "binding_pin", "duplicate_binding",
                                   "snapshot_schema", "snapshot_key", "snapshot_datasets", "legacy_presence"])
def test_manifest_index_tampering_is_rejected_before_publication(exporter, inputs, tmp_path, change):
    files = inputs.build(exporter)
    manifest = json.loads(files["manifest.json"])
    if change == "missing_snapshot":
        manifest["dataset_bindings"][0]["snapshot"] = "unknown"
    elif change == "binding_pin":
        manifest["dataset_bindings"][0]["parameter_registry"]["sha256"] = "0" * 64
    elif change == "duplicate_binding":
        manifest["dataset_bindings"].append(copy.deepcopy(manifest["dataset_bindings"][0]))
    elif change == "snapshot_schema":
        manifest["snapshots"][0]["schema_version"] = 3
    elif change == "snapshot_key":
        manifest["snapshots"][0]["key"] = "different"
    elif change == "snapshot_datasets":
        manifest["snapshots"][0]["dataset_ids"] = []
    else:
        manifest["scope"]["legacy_navigation"] = True
    files["manifest.json"] = encode(manifest)
    with pytest.raises(ValueError):
        exporter.write_bundle(files, tmp_path / "corrupt-publication")
    assert not (tmp_path / "corrupt-publication").exists()


def test_legacy_triplet_keeps_multiple_candidates_without_promoting_archive(exporter, inputs):
    files = inputs.build(exporter, legacy_snapshot=legacy_file(inputs))
    manifest, browsers = browser_documents(files)
    assert manifest["scope"]["legacy_navigation"] is True
    links = json.loads(files["legacy-links.json"])
    assert links["scope"] == {"purpose": "historical_navigation_only", "current_support": False}
    assert len(links["links"]) == 1
    route = links["links"][0]
    assert route["triplet"] == "0.0.0"
    candidates = {row["parameter_id"]: row for row in route["candidates"]}
    assert set(candidates) == {"cedarkit.t", "cedarkit.t2m", "cedarkit.archived"}
    assert candidates["cedarkit.archived"]["historical_only"] is True
    assert candidates["cedarkit.archived"]["current_targets"] == []
    for current in ["cedarkit.t", "cedarkit.t2m"]:
        assert candidates[current]["historical_only"] is False
        assert candidates[current]["current_targets"][0]["snapshot"] == "gfs"
    assert {row["parameter_id"] for row in browsers["gfs"]["parameters"]} == {"cedarkit.t", "cedarkit.t2m"}


def test_legacy_attachment_cannot_claim_current_support(exporter, inputs, tmp_path):
    files = inputs.build(exporter, legacy_snapshot=legacy_file(inputs))
    links = json.loads(files["legacy-links.json"])
    links["scope"]["current_support"] = True
    files["legacy-links.json"] = encode(links)
    manifest = json.loads(files["manifest.json"])
    entry = next(row for row in manifest["files"] if row["path"] == "legacy-links.json")
    entry.update(size=len(files["legacy-links.json"]), sha256=sha256(files["legacy-links.json"]))
    files["manifest.json"] = encode(manifest)
    with pytest.raises(ValueError):
        exporter.write_bundle(files, tmp_path / "promoted-history")
    assert not (tmp_path / "promoted-history").exists()


def test_current_snapshot_preserves_scoped_definitions_and_mapping_identities(exporter):
    files = exporter.build_bundle(author=REPO / "authoring", policy=REPO / "authoring/browser-current.json",
                                  catalog=RUNTIME / "catalog-v1.json", runtime_dir=RUNTIME)
    manifest, browsers = browser_documents(files)
    assert len(manifest["dataset_bindings"]) == 18
    assert set(browsers) == {"gfs", "meso1", "meso3", "tym", "geps", "reps", "cmadaas"}
    definitions = [row for document in browsers.values() for row in document["parameters"]]
    mappings = [(resource["id"], row)
                for document in browsers.values() for resource in document["mapping_resources"]
                for row in resource["mappings"]]
    assert len(definitions) == 548
    assert len({row["parameter_id"] for row in definitions}) == 166
    assert len(mappings) == 1311
    assert len({row["id"] for _, row in mappings}) == 911
    assert len({(resource_id, row["id"]) for resource_id, row in mappings}) == 1311
    assert len({row["parameter_id"] for _, row in mappings}) == 125
    native_sf = next(row for row in browsers["geps"]["parameters"] if row["parameter_id"] == "cedarkit.sf")
    service_sf = next(row for row in browsers["cmadaas"]["parameters"] if row["parameter_id"] == "cedarkit.sf")
    assert native_sf["fixed_conditions"]["statistics"]["period"] == {"kind": "since_initialization"}
    assert "period" not in service_sf["fixed_conditions"]["statistics"]
    raw_scoped = defaultdict(list)
    for key, browser in browsers.items():
        source = read(RUNTIME / f"current-{key}-parameters.json")
        assert browser["meta"]["schema_version"] == 4
        assert browser["retired_ids"] == []
        assert browser["notes"] == []
        actual = {row["parameter_id"]: row for row in browser["parameters"]}
        for raw in source["parameters"]:
            raw_scoped[raw["parameter_id"]].append(raw)
            for field, value in raw.items():
                if field == "aliases":
                    assert sorted(actual[raw["parameter_id"]][field]) == sorted(value)
                else:
                    assert actual[raw["parameter_id"]][field] == value
        for resource in browser["mapping_resources"]:
            expected = read(RUNTIME / f"current-{key}-mappings.json")
            assert {field: resource[field] for field in ["api_version", "id", "version", "backend"]} == {
                field: expected[field] for field in ["api_version", "id", "version", "backend"]}
            actual_mappings = {row["id"]: row for row in resource["mappings"]}
            assert set(actual_mappings) == {row["id"] for row in expected["mappings"]}
            for raw in expected["mappings"]:
                for field, value in raw.items():
                    if field == "evidence":
                        assert set(actual_mappings[raw["id"]][field]) == set(value)
                    else:
                        assert actual_mappings[raw["id"]][field] == value
            assert {row["id"] for row in resource["tables"]} == {row["id"] for row in expected["tables"]}
        parameter_pin = next(row for row in manifest["snapshots"] if row["key"] == key)["parameter_resource"]
        assert json.loads(files[parameter_pin["path"]]) == source
    assert sum(len({json.dumps(row, sort_keys=True) for row in values}) > 1 for values in raw_scoped.values()) == 51
    assert not any("task07a" in item["path"] for item in manifest["files"])
    assert not any("modelvar" in item["dataset_id"] for item in manifest["dataset_bindings"])


def test_frozen_revision_one_policy_is_retained():
    raw = (REPO / "authoring/browser-reviewed-v1.json").read_bytes()
    assert sha256(raw) == "3143397eecf0802db66c93074eda65bdc6a026931c384bdcef1e0450553aca96"
    current = read(REPO / "authoring/browser-current.json")
    assert current["version"] == "6"
    assert current["catalog"]["version"] == "45"
    assert "cemc-orig-task-n04b-01.json" in current["authoring"]["native_additions"]
