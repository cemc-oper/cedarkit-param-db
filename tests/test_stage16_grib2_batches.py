"""Independent snapshots keep batch scope and preserve the reviewed identities."""

import copy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from cedarkit_query import QueryError

DB = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def snapshots():
    import cedarkit_query

    if not hasattr(cedarkit_query, "validate_standalone_grib2"):
        pytest.skip("the independent GRIB2 export requires cedarkit-query 0.2.3")
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(DB / "tools"))
        from export_stage16_grib2 import BATCHES, build_snapshot

        return {name: build_snapshot(name) for name in BATCHES}


def test_batches_add_rules_and_pin_the_same_parameter_resource(snapshots):
    previous = {}
    for files, count in zip(snapshots.values(), (10, 29, 344), strict=True):
        manifest = json.loads(files["manifest.json"])
        assert manifest["counts"] == {"parameters": 226, "mappings": count}
        registry = manifest["standalone"]["parameter_registry"]
        mapping = manifest["standalone"]["mappings"]["grib2"]
        assert registry["version"] == "2"
        for pin in (registry, mapping):
            assert sha256(files[pin["path"]]).hexdigest() == pin["sha256"]
        resource = json.loads(files[mapping["path"]])
        assert not resource["tables"]
        rules = {row["id"]: row for row in resource["mappings"]}
        assert all(not row["applies_to"] for row in rules.values())
        assert all(rules[mid] == old for mid, old in previous.items())
        previous = rules
    assert len({files["public-parameters.json"] for files in snapshots.values()}) == 1


def test_pilot_height_and_local_table_constraints_reject_overlap(snapshots):
    from cedarkit_query import validate_standalone_grib2

    files = snapshots["q2m-znt"]
    definitions = json.loads(files["public-parameters.json"])
    resource = json.loads(files["generic-grib2-mappings.json"])
    rules = {row["parameter_id"]: row for row in resource["mappings"]}
    q2m = rules["cedarkit.q2m"]
    znt = rules["cedarkit.znt"]
    assert q2m["when"] == {"level_type": "height_above_ground", "level_unit": "m", "level": 2}
    assert q2m["native"]["match"]["localTablesVersion"] == 0
    assert {key: znt["native"]["match"][key] for key in ("centre", "subCentre", "tablesVersion", "localTablesVersion")} == {
        "centre": 38, "subCentre": 0, "tablesVersion": 4, "localTablesVersion": 1,
    }
    duplicate = copy.deepcopy(znt)
    duplicate["id"] = "widened-znt"
    del duplicate["native"]["match"]["localTablesVersion"]
    resource["mappings"].append(duplicate)
    with pytest.raises(QueryError, match="overlapping standalone mapping"):
        validate_standalone_grib2(definitions, resource)


def test_full_batch_retains_native_member_and_statistic_boundaries(snapshots):
    mapping = json.loads(snapshots["full-library"]["generic-grib2-mappings.json"])
    by_id = {}
    for row in mapping["mappings"]:
        by_id.setdefault(row["parameter_id"], []).append(row)

    for pid, expected_size in (
        ("cedarkit.sf.since-initialization", 31), ("cedarkit.sf.with-convective-diagnostic", 0),
    ):
        assert {
            row["native"]["match"]["numberOfForecastsInEnsemble"]
            for row in by_id[pid] if row["native"]["match"]["productDefinitionTemplateNumber"] == 11
        } == {expected_size}
    for pid, operation in (("cedarkit.mx2t", 2), ("cedarkit.mn2t", 3), ("cedarkit.rhmax2m", 2), ("cedarkit.rhmin2m", 3)):
        rule, = by_id[pid]
        assert rule["native"]["match"]["forecastTime"] == 0
        assert rule["native"]["match"]["typeOfStatisticalProcessing"] == operation
        assert "unit" not in rule["native"]["translate"]
    assert set(by_id).isdisjoint({
        "cedarkit.gsw", "cedarkit.gsw.since-initialization",
        "cedarkit.glw", "cedarkit.glw.since-initialization",
        "cedarkit.hfx", "cedarkit.hfx.since-initialization",
    })


def test_original_fields_extend_full_batch_with_raw_surface_selectors(snapshots, monkeypatch):
    monkeypatch.syspath_prepend(str(DB / "tools"))
    from export_stage16_grib2 import ORIGINAL_FIELDS_BATCH, build_snapshot

    files = build_snapshot(ORIGINAL_FIELDS_BATCH)
    baseline = snapshots["full-library"]
    parameters = json.loads(files["public-parameters.json"])
    base_parameters = json.loads(baseline["public-parameters.json"])["parameters"]
    mappings = json.loads(files["generic-grib2-mappings.json"])
    base_mappings = json.loads(baseline["generic-grib2-mappings.json"])["mappings"]
    assert (parameters["version"], mappings["version"]) == ("3", "5")
    assert parameters["parameters"][:len(base_parameters)] == base_parameters
    assert mappings["mappings"][:len(base_mappings)] == base_mappings
    new_definitions = parameters["parameters"][len(base_parameters):]
    new_mappings = mappings["mappings"][len(base_mappings):]
    assert {row["name"]: row["parameter_id"] for row in new_definitions} == {
        name: f"cedarkit.{name}.raw" for name in ("glw", "gsw", "hfx")
    }
    assert {row["parameter_id"] for row in new_mappings} == {r["parameter_id"] for r in new_definitions}
    for rule in new_mappings:
        assert rule["native"]["match"]["typeOfFirstFixedSurface"] == 1
        assert "unit" not in rule["native"]["translate"]
