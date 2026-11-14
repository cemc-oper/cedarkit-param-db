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
from zipfile import ZipFile

import pytest


REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO.parents[1]
REKI = WORKSPACE / "repo/reki"
RUNTIME = REKI / "src/reki/catalog/builtin"
V50_WHEEL = (
    WORKSPACE / "doc/2026-11-11-stage1.3-query-reki/evidence/orig-09/artifacts/"
    "reki-2026.9.1.dev115+g03b0f4f.orig09-py3-none-any.whl"
)
V52_WHEEL = (
    WORKSPACE / "doc/2026-11-13-stage1.4-query-reki/evidence/1.4-07/artifacts/"
    "reki-2026.9.1.dev117+g8d80735.orig52-py3-none-any.whl"
)


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


@pytest.mark.parametrize(("wheel_path", "policy_name", "counts"), [
    (V50_WHEEL, "browser-reviewed-v11.json", (582, 173, 1398, 998, 130, 53)),
    (V52_WHEEL, "browser-reviewed-v12.json", (702, 215, 2581, 2181, 158, 72)),
    (None, "browser-current.json", (702, 215, 2605, 2193, 158, 75)),
], ids=["v50-recovery", "v52-recovery", "v56-current"])
def test_snapshot_preserves_scoped_definitions_and_mapping_identities(exporter, tmp_path, wheel_path, policy_name, counts):
    runtime = RUNTIME
    if wheel_path:
        runtime = tmp_path / "runtime"
        runtime.mkdir()
        with ZipFile(wheel_path) as wheel:
            for name in wheel.namelist():
                if name.startswith("reki/catalog/builtin/") and name.endswith(".json"):
                    (runtime / Path(name).name).write_bytes(wheel.read(name))
    files = exporter.build_bundle(author=REPO / "authoring", policy=REPO / "authoring" / policy_name,
                                  catalog=runtime / "catalog-v1.json", runtime_dir=runtime)
    manifest, browsers = browser_documents(files)
    assert len(manifest["dataset_bindings"]) == 18
    assert set(browsers) == {"gfs", "meso1", "meso3", "tym", "geps", "reps", "cmadaas"}
    definitions = [row for document in browsers.values() for row in document["parameters"]]
    mappings = [(resource["id"], row)
                for document in browsers.values() for resource in document["mapping_resources"]
                for row in resource["mappings"]]
    definitions_count, stable_ids, scoped_mappings, mapping_ids, mapped_ids, differing_definitions = counts
    assert len(definitions) == definitions_count
    assert len({row["parameter_id"] for row in definitions}) == stable_ids
    assert len(mappings) == scoped_mappings
    assert len({row["id"] for _, row in mappings}) == mapping_ids
    assert len({(resource_id, row["id"]) for resource_id, row in mappings}) == scoped_mappings
    assert len({row["parameter_id"] for _, row in mappings}) == mapped_ids
    native_sf = next(row for row in browsers["geps"]["parameters"] if row["parameter_id"] == "cedarkit.sf")
    service_sf = next(row for row in browsers["cmadaas"]["parameters"] if row["parameter_id"] == "cedarkit.sf")
    assert native_sf["fixed_conditions"]["statistics"]["period"] == {"kind": "since_initialization"}
    assert native_sf["name"] == "sf" and set(native_sf["aliases"]) == {"asnow", "snow"}
    native_sf_parent = next(row for row in browsers["geps"]["parameters"] if row["parameter_id"] == native_sf["parent"])
    assert native_sf_parent["name"] == "cedarkit.sf.any"
    assert "period" not in service_sf["fixed_conditions"]["statistics"]
    raw_scoped = defaultdict(list)
    for key, browser in browsers.items():
        source = read(runtime / f"current-{key}-parameters.json")
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
            expected = read(runtime / f"current-{key}-mappings.json")
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
    assert sum(len({json.dumps(row, sort_keys=True) for row in values}) > 1
               for values in raw_scoped.values()) == differing_definitions
    assert not any("task07a" in item["path"] for item in manifest["files"])
    assert not any("modelvar" in item["dataset_id"] for item in manifest["dataset_bindings"])
    if wheel_path != V50_WHEEL:
        binding_path = "authoring/cemc-orig-stage1.4-bindings.json"
        binding_source = next(row for row in manifest["sources"] if row["path"] == binding_path)
        assert binding_source["sha256"] == sha256((REPO / binding_path).read_bytes())
        orig = [row for _, row in mappings if row["applies_to"]["product"] == "orig"]
        assert len(orig) == (1997 if wheel_path is None else 1973)
        assert sum("unit" not in row["native"].get("translate", {}) for row in orig) == 1171
    if wheel_path is None:
        author_path = "authoring/cemc-orig-stage1.5-kindex-units.json"
        source = next(row for row in manifest["sources"] if row["path"] == author_path)
        assert source["sha256"] == sha256((REPO / author_path).read_bytes())
        snowfall = [row for row in orig if row["id"].startswith("sf.since-initialization.")]
        snowfall_datasets = {"cma_gfs_gmf", "cma_meso_1km", "cma_meso_3km", "cma_tym"}
        assert {row["applies_to"]["dataset"] for row in snowfall} == snowfall_datasets
        for dataset in snowfall_datasets:
            rows = [row for row in snowfall if row["applies_to"]["dataset"] == dataset]
            assert all(row["applies_to"]["time"] == "2026-11-02T12:00:00Z" for row in rows)
            lengths = (360, 2880) if dataset == "cma_meso_1km" else (6, 48)
            assert {tuple(row["native"]["match"]["lengthOfTimeRange"]) for row in rows} == {(0,), lengths}
            assert all(row["native"]["translate"]["unit"]["config"]["source_unit"] == "m" for row in rows)
        reps = next(row for row in browsers["reps"]["parameters"] if row["parameter_id"] == "cedarkit.sf")
        assert reps["unit"] == "m" and "period" not in reps["fixed_conditions"]["statistics"]
        diagnostic = [row for row in orig if row["id"].startswith("sf.diagnostic.")]
        assert len(diagnostic) == 6
        assert {(tuple(row["when"]["step"]), tuple(row["when"]["member"])) for row in diagnostic} == {
            (steps, members) for steps in [("PT0H",), ("PT6H", "PT48H")] for members in [(0,), (1,), (2, 14)]
        }
        for row in diagnostic:
            assert row["applies_to"]["dataset"] == "cma_reps"
            assert row["applies_to"]["time"] == "2026-11-02T06:00:00Z"
            native = row["native"]
            assert native["match"]["perturbationNumber"] == row["when"]["member"]
            assert native["match"]["forecastTime"] == 0
            assert native["match"]["lengthOfTimeRange"] == [int(step[2:-1]) for step in row["when"]["step"]]
            assert native["translate"]["unit"]["config"]["source_unit"] == "m"
        radar = [row for row in orig if row["id"].startswith("dbzmaxh.height.")]
        assert {row["applies_to"]["dataset"] for row in radar} == {"cma_meso_3km"}
        assert {row["applies_to"]["time"] for row in radar} == {"2026-11-02T12:00:00Z"}
        assert {tuple(row["native"]["match"]["forecastTime"]) for row in radar} == {(0,), (6, 48)}
        assert all(row["native"]["translate"]["unit"]["config"]["source_unit"] == "m" for row in radar)
        for system in ("gfs", "meso3"):
            clouds = [row for row in browsers[system]["parameters"]
                      if row["parameter_id"] in {"cedarkit.cldb", "cedarkit.cldt"}]
            assert len(clouds) == 2 and all("above model terrain" in row["description"] for row in clouds)
            assert all(row["fixed_conditions"] == {"level_type": "surface"} for row in clouds)
        for system in ("gfs", "meso1", "meso3", "tym"):
            rows = [r for r in browsers[system]["mapping_resources"][0]["mappings"] if r["parameter_id"] == "cedarkit.kidx"]
            assert len(rows) == 4
            reviewed = [r for r in rows if "unit" in r["native"]["translate"]]
            assert len(reviewed) == 2
            assert all(r["applies_to"]["time"] == "2026-11-02T12:00:00Z" for r in reviewed)
            assert {step for r in reviewed for step in r["when"]["step"]} == {"PT0H", "PT6H", "PT48H"}


def test_frozen_browser_policies_are_retained():
    for version, digest in {
        "1": "3143397eecf0802db66c93074eda65bdc6a026931c384bdcef1e0450553aca96",
        "11": "c512841ee038a4f026165396d8b7ce916eb35e9223d3c880f267cdff7289bf22",
        "12": "aae8f0f67c40b312812e6be0b7f9126791577e51825d3f54ca6697fa9fa97fb0",
        "13": "90f6c1765129a5472c1b4460cc2cb791cf404455586475f8c2e925dcb41cab08",
        "14": "ebca0bf9652c7a1b6967bc057b797c1ae075ef619102dfba27e4a8df1d2f9aae",
        "15": "0578ad6a5e302b8954cf2c4f410dd85e6c8359c8bb7feaf5e43d11e4328088fa",
    }.items():
        assert sha256((REPO / f"authoring/browser-reviewed-v{version}.json").read_bytes()) == digest
    current = read(REPO / "authoring/browser-current.json")
    assert current["version"] == "16"
    assert current["catalog"]["version"] == "56"
    assert current["authoring"]["native_release"] == "cemc-orig-task-orig09.json"
    assert current["authoring"]["native_binding"] == "cemc-orig-stage1.4-bindings.json"
    assert current["authoring"]["native_mapping_refinement"] == [
        "cemc-orig-stage1.5-kindex-units.json", "cemc-orig-stage1.5-snowfall.json",
        "cemc-orig-stage1.5-vertical-diagnostics.json", "cemc-orig-stage1.5-snowfall-supplement.json",
    ]
    assert "cemc-orig-task-n04b-01.json" in current["authoring"]["native_additions"]


@pytest.mark.parametrize(("issue", "message"), [
    ("base", "needs its base release"),
    ("version", "pinned newer catalog version"),
    ("scope", "must match its ORIG product"),
    ("provides", "provisions differ from the pinned catalog"),
])
def test_rejects_binding_that_disagrees_with_release_or_catalog(exporter, tmp_path, issue, message):
    author = REPO / "authoring"
    policy_path = author / "browser-reviewed-v12.json"
    policy = read(policy_path)
    for filename in [
        policy["authoring"]["native_base"],
        *policy["authoring"]["native_additions"],
        policy["authoring"]["native_release"],
        read(author / policy["authoring"]["native_release"])["name_review"],
    ]:
        shutil.copyfile(author / filename, tmp_path / filename)
    binding_path = policy["authoring"]["native_binding"]
    candidate = read(author / binding_path)
    gfs = candidate["products"]["gfs"]
    if issue == "base":
        candidate["base_release"] = "unexpected-release"
    elif issue == "version":
        candidate["catalog_version"] = "51"
    elif issue == "scope":
        gfs["mappings"]["mappings"][0]["applies_to"]["dataset"] = "cma_meso_1km"
    elif issue == "provides":
        pid = "cedarkit.glw"
        gfs["provides"].remove(pid)
        gfs["mappings"]["mappings"] = [
            row for row in gfs["mappings"]["mappings"] if row["parameter_id"] != pid
        ]
    (tmp_path / binding_path).write_bytes(encode(candidate))
    with ZipFile(V52_WHEEL) as wheel:
        catalog = tmp_path / "catalog-v1.json"
        catalog.write_bytes(wheel.read("reki/catalog/builtin/catalog-v1.json"))
    with pytest.raises(ValueError, match=message):
        exporter.build_bundle(author=tmp_path, policy=policy_path, catalog=catalog)
