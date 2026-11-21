"""Keep the full-library registration traceable to the frozen scoped definitions."""

import csv
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from cedarkit_query import QueryError, prepare_queries
from cedarkit_query.resources import effective_parameters

DB = Path(__file__).resolve().parents[1]
WORKSPACE = DB.parents[1]
EVIDENCE = WORKSPACE / "doc/2026-11-16-stage1.6-query-reki/evidence/1.6-07"
V57 = (
    WORKSPACE / "doc/2026-11-14-stage1.5-query-reki/evidence/1.5-04D/supplement/artifacts"
    / "reki-2026.9.1.dev122+g1a95894.orig57-py3-none-any.whl"
)


@pytest.fixture(scope="module")
def registry():
    return json.loads((DB / "authoring/stage1.6-identity-registry.json").read_bytes())


@pytest.fixture(scope="module")
def unified(registry):
    return effective_parameters({
        "api_version": "cedarkit.parameters/v1",
        "id": "cedarkit.parameters.stage1.6-registry-test",
        "version": "1",
        "parameters": registry["unified_parameters"],
    })


def test_registration_covers_all_scoped_definitions_and_mappings(registry):
    with (EVIDENCE / "branch-index.tsv").open(encoding="utf-8", newline="") as stream:
        branches = list(csv.DictReader(stream, delimiter="\t"))
    branch_targets = {(row["resource"], row["mapping_id"]): row["unified_id"] for row in branches}
    assert len(branch_targets) == len(branches) == 2609

    entries = {(row["resource"], row["source"]["parameter_id"]): row for row in registry["source_entries"]}
    assert len(entries) == len(registry["source_entries"]) == 702
    assert len({pid for _, pid in entries}) == 215
    assert len({carrier for row in entries.values() for carrier in row["carrier_ids"]}) == 463
    assert sum(len(row["carrier_ids"]) for row in entries.values() if row["origin"] == "product_definition") == 94
    with ZipFile(V57) as wheel:
        for key, pins in registry["source_resources"].items():
            parameter_bytes = wheel.read("reki/catalog/builtin/" + pins["parameters"]["file"])
            mapping_bytes = wheel.read("reki/catalog/builtin/" + pins["mappings"]["file"])
            assert sha256(parameter_bytes).hexdigest() == pins["parameters"]["sha256"]
            assert sha256(mapping_bytes).hexdigest() == pins["mappings"]["sha256"]
            parameters = effective_parameters(json.loads(parameter_bytes))
            assert {pid: row["source"] for (scope, pid), row in entries.items() if scope == key} == parameters
            scoped_mappings = {row["id"]: row["parameter_id"] for row in json.loads(mapping_bytes)["mappings"]}
            declared_mappings = {
                mid: pid for (scope, pid), row in entries.items() if scope == key for mid in row["source_mapping_ids"]
            }
            assert declared_mappings == scoped_mappings
            for mid, pid in scoped_mappings.items():
                row = entries[key, pid]
                assert branch_targets[key, mid] == row.get("branch_targets", {}).get(mid, row["unified_parameter_id"])


def test_radiation_aliases_and_snowfall_variants_keep_distinct_identities(registry, unified):
    def resolve(token):
        query, = prepare_queries([{"parameter": token}], unified)
        return query.to_dict()["parameter"]

    for quantity in ("gsw", "glw", "hfx"):
        assert resolve(quantity + "-flux") == "cedarkit." + quantity
        assert resolve(quantity + "-since-initialization") == "cedarkit." + quantity + ".since-initialization"
        assert unified["cedarkit." + quantity]["unit"] == "W/m2"
        assert unified["cedarkit." + quantity + ".since-initialization"]["unit"] == "J/m2"
    assert unified["cedarkit.tsw"]["parent"] == "cedarkit.gsw.energy"
    assert registry["same_id_differences"]["cedarkit.hfx"]["split_identity"]
    for ambiguous in ("gsw", "ssr", "glw", "hfx", "sf"):
        with pytest.raises(QueryError, match="unknown parameter"):
            resolve(ambiguous)
    for snowfall in ("since-initialization", "large-scale.since-initialization", "with-convective-diagnostic"):
        pid = "cedarkit.sf." + snowfall
        assert resolve(pid) == resolve(unified[pid]["name"]) == pid
    assert resolve("2t") == resolve("t2m") == "cedarkit.t2m"


def test_service_variants_reuse_concrete_fields_and_keep_endpoint_differences(registry, unified):
    entries = {
        row["source"]["parameter_id"]: row for row in registry["source_entries"] if row["resource"] == "cmadaas"
    }
    assert set(entries["cedarkit.h.any"]["branch_targets"].values()) == {"cedarkit.zs"}
    assert set(entries["cedarkit.q"]["branch_targets"].values()) == {"cedarkit.q2m"}
    assert entries["cedarkit.rainc.any"]["branch_targets"] == {"S-gfs-fcst.frozen.CPE": "cedarkit.rainc.24h"}
    assert registry["unified_uses"]["cedarkit.sf.diagnostic-change.1h"]["direct_branches"] == {
        "service_endpoint_difference": 2
    }
    assert registry["unified_uses"]["cedarkit.st-10-30"]["direct_branches"] == {
        "service_original_comparison": 4
    }
    assert unified["cedarkit.st-10-30"]["fixed_conditions"]["layer"]["bottom"]["value"] == 0.3
    assert unified["cedarkit.st-10-40"]["fixed_conditions"]["layer"]["bottom"]["value"] == 0.4
    assert registry["unified_uses"]["cedarkit.h.any"]["field_variants"] == [
        {"parameter_id": "cedarkit.h",
         "parent_query": {"parameter": "cedarkit.h.any", "level_type": "pressure", "level_unit": "hPa"}},
        {"parameter_id": "cedarkit.zs",
         "parent_query": {"parameter": "cedarkit.h.any", "level_type": "surface"}},
    ]
