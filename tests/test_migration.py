"""Offline migration must preserve facts and reject guessed/partial publication."""

from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import pytest
import yaml
from cedarkit_query import load_value

from cedarkit_param_db import (
    apply_review,
    connect,
    export_bundle,
    export_definitions,
    migrate_v3,
    migration_report,
    transaction,
)
from cedarkit_param_db.__main__ import main


def reviewed_definitions(path, ids=None):
    report = migration_report(path)
    selected = ids or [r["parameter_id"] for r in report["records"]]
    return {
        "source_sha256": report["sources"][0]["sha256"],
        "decisions": [
            {
                "parameter_id": r["parameter_id"],
                "aspect": "definition",
                "explanation": "Independent fixture definition confirms the declared broad or fixed meaning.",
                "evidence": ["fixture:business-definition"],
                "definition": deepcopy(
                    r["current"] or r["legacy"]["canonical_definition"]
                ),
            }
            for r in report["records"]
            if r["parameter_id"] in selected
        ],
    }


def test_source_preserved_flattened_draft_and_no_unproven_mapping(legacy, tmp_path):
    original = legacy.read_bytes()
    out = tmp_path / "review.db"
    report = migrate_v3(legacy, out, source_kind="snapshot")
    assert legacy.read_bytes() == original
    assert report["counts"] == {
        "parameters": 2,
        "preserved_identities": 2,
        "quarantined": 0,
        "aliases": 2,
        "mappings": 0,
        "retired_ids": 0,
        "unresolved": 6,
    }
    assert not report["full_migration_complete"]
    assert all(
        r["identity_preserved"] and r["parent_preserved"] for r in report["records"]
    )
    base = next(r for r in report["records"] if r["parameter_id"] == "example.t")
    assert (
        "fixed_conditions" not in base["current"]
    )  # typeOfLevel was information only.
    assert base["legacy"]["metadata_normalization"] == {
        "description": {"before": "Temperature ", "after": "Temperature"}
    }
    child = next(r for r in report["records"] if r["parameter_id"] == "example.t2m")
    assert child["current"]["fixed_conditions"] == {
        "level_type": "height_above_ground",
        "level": 2,
        "level_unit": "m",
    }
    assert not {"TEM", "TEMPERATURE"} & set(base["current"].get("aliases", []))
    with pytest.raises(ValueError, match="unresolved"):
        export_bundle(out, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


def test_definition_slice_requires_review_and_dependency_closure(legacy, tmp_path):
    out = tmp_path / "review.db"
    migrate_v3(legacy, out, source_kind="snapshot")

    def export(target):
        return export_definitions(
            out, target, ["example.t2m"], resource_id="example.slice", version="1"
        )

    with pytest.raises(ValueError, match="unresolved"):
        export(tmp_path / "unreviewed")
    review = reviewed_definitions(out)
    apply_review(out, review)
    manifest = export(tmp_path / "definitions")
    assert manifest["scope"] == {
        "kind": "parameter_definitions",
        "requested_parameter_ids": ["example.t2m"],
        "parameter_ids": ["example.t", "example.t2m"],
        "runtime_mappings": False,
    }
    assert {p.name for p in (tmp_path / "definitions").iterdir()} == {
        "manifest.json",
        "parameters.json",
        "parameters.yaml",
        "params.json",
    }
    assert (
        load_value(
            (tmp_path / "definitions/parameters.json").read_text(), "parameters"
        ).id
        == "example.slice"
    )
    assert migration_report(out)["counts"]["unresolved"] == 4
    with pytest.raises(ValueError, match="unresolved"):
        export_bundle(out, tmp_path / "still-incomplete")
    with pytest.raises(ValueError, match="distinct"):
        export_definitions(
            out,
            tmp_path / "same",
            ["example.t"],
            resource_id="cedarkit.parameters",
            version="1",
        )
    with pytest.raises(ValueError, match="unknown"):
        export_definitions(
            out, tmp_path / "unknown", ["unknown"], resource_id="x", version="1"
        )


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r.update(source_sha256="0" * 64),
        lambda r: r["decisions"][0].update(evidence=[]),
        lambda r: r["decisions"][0].update(explanation=""),
        lambda r: r["decisions"][0]["definition"].update(name="renamed"),
        lambda r: r["decisions"][0]["definition"].update(aliases=["discarded"]),
        lambda r: r["decisions"].append(deepcopy(r["decisions"][0])),
        lambda r: r["decisions"][0].update(unknown=True),
    ],
)
def test_invalid_review_is_atomic(legacy, tmp_path, change):
    path = tmp_path / "review.db"
    migrate_v3(legacy, path, source_kind="snapshot")
    before = migration_report(path)
    review = reviewed_definitions(path)
    change(review)
    with pytest.raises((ValueError, sqlite3.Error)):
        apply_review(path, review)
    assert migration_report(path) == before


def test_review_cannot_close_missing_mapping_with_a_note(legacy, tmp_path):
    path = tmp_path / "review.db"
    migrate_v3(legacy, path, source_kind="snapshot")
    review = reviewed_definitions(path)
    d = review["decisions"][0]
    d.pop("definition")
    d.update(
        aspect="cmadaas",
        mapping_ids=[{"resource_id": "cedarkit.cmadaas", "id": "absent"}],
    )
    with pytest.raises(ValueError, match="actual backend"):
        apply_review(path, review)


def test_unknown_legacy_version_and_duplicate_keys_fail_without_destination(
    legacy, tmp_path
):
    doc = json.loads(legacy.read_text())
    doc["api_version"] = "reki.parameter-registry/v999"
    legacy.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="identified"):
        migrate_v3(legacy, tmp_path / "no", source_kind="snapshot")
    legacy.write_text(
        '{"api_version":"reki.parameter-registry/v3","entries":[],"entries":[]}'
    )
    with pytest.raises(ValueError, match="duplicate"):
        migrate_v3(legacy, tmp_path / "no", source_kind="snapshot")
    assert not (tmp_path / "no").exists()


@pytest.mark.parametrize(
    "text",
    [
        "api_version: reki.parameter-registry/v3\nentries: []\nentries: []\n",
        "!!python/object/apply:os.system [false]",
        '{"api_version":"reki.parameter-registry/v3","entries":[],"x":NaN}',
    ],
)
def test_unsafe_or_nonfinite_snapshot_rejected(tmp_path, text):
    path = tmp_path / "bad.yaml"
    path.write_text(text)
    with pytest.raises((ValueError, yaml.YAMLError)):
        migrate_v3(path, tmp_path / "out.db", source_kind="snapshot")
    assert not (tmp_path / "out.db").exists()


def test_time_window_does_not_guess_period_anchor(legacy, tmp_path):
    doc = json.loads(legacy.read_text())
    doc["entries"][0]["params"][0]["when"].update(stepType="accum", time_range_hours=24)
    legacy.write_text(json.dumps(doc))
    r = migrate_v3(legacy, tmp_path / "review.db", source_kind="snapshot")
    child = next(r for r in r["records"] if r["parameter_id"] == "example.t2m")
    assert child["current"]["fixed_conditions"]["statistics"] == {
        "over": "time",
        "operation": "accumulation",
    }
    assert (
        child["legacy"]["predicate_classification"]["time_range_hours"]
        == "pending_period_definition"
    )
    assert any("anchoring" in r["missing_input"] for r in r["unresolved"])


def test_depth_layer_direction_and_unknown_native_type_are_recorded(legacy, tmp_path):
    doc = json.loads(legacy.read_text())
    variants = doc["entries"][0]["params"]
    variants[0]["when"] = {
        "first_level_type": 106,
        "first_level": 0.1,
        "second_level_type": 106,
        "second_level": 0.4,
    }
    variants.append(
        {
            "parameter_id": "example.unknown",
            "name": "unknown",
            "when": {"first_level_type": 166},
        }
    )
    legacy.write_text(json.dumps(doc))
    r = migrate_v3(legacy, tmp_path / "review.db", source_kind="snapshot")
    child = next(r for r in r["records"] if r["parameter_id"] == "example.t2m")
    assert child["current"]["fixed_conditions"] == {
        "layer": {
            "bottom": {"type": "depth_below_land", "unit": "m", "value": 0.4},
            "top": {"type": "depth_below_land", "unit": "m", "value": 0.1},
        },
    }
    assert any(
        i["parameter_id"] == "example.unknown"
        and "native vertical type" in i["missing_input"]
        for i in r["unresolved"]
    )


def test_invalid_parent_unit_is_quarantined_not_rewritten(legacy, tmp_path):
    doc = json.loads(legacy.read_text())
    doc["entries"][0]["params"][0]["unit"] = "m/s"
    legacy.write_text(json.dumps(doc))
    path = tmp_path / "review.db"
    r = migrate_v3(legacy, path, source_kind="snapshot")
    assert r["counts"]["quarantined"] == 1 and r["counts"]["preserved_identities"] == 2
    child = next(r for r in r["records"] if r["parameter_id"] == "example.t2m")
    assert child["state"] == "quarantined" and child["current"] is None
    assert child["legacy"]["record"]["unit"] == "m/s"
    assert child["legacy"]["canonical_definition"]["parent"] == "example.t"
    with pytest.raises(sqlite3.IntegrityError, match="quarantined"):
        with transaction(path) as c:
            c.execute(
                "INSERT INTO parameters(parameter_id,resource_id,name) VALUES (?,?,?)",
                ("example.t2m", "cedarkit.parameters", "reuse"),
            )
    review = reviewed_definitions(path, ["example.t2m"])
    review["decisions"][0]["definition"].pop("parent")
    apply_review(path, review)
    assert migration_report(path)["counts"]["quarantined"] == 0
    assert (
        next(
            r
            for r in migration_report(path)["records"]
            if r["parameter_id"] == "example.t2m"
        )["parent_preserved"]
        is False
    )


def test_sqlite_source_tombstone_and_auxiliary_tables_retained(tmp_path):
    source = tmp_path / "old.db"
    c = sqlite3.connect(source)
    c.executescript((Path(__file__).parent / "fixtures/schema-v3.sql").read_text())
    c.execute(
        "INSERT INTO entries(id,parameter_id,discipline,category,number,name,unit) VALUES (?,?,?,?,?,?,?)",
        (1, "cedarkit.t", 0, 0, 0, "t", "K"),
    )
    c.execute(
        "INSERT INTO variants(id,entry_id,parameter_id,name,when_json,sort_order) VALUES (?,?,?,?,?,?)",
        (1, 1, "cedarkit.t2m", "t2m", '{"first_level_type":103,"first_level":2}', 0),
    )
    c.execute(
        "INSERT INTO parameter_id_tombstones VALUES (?,?)", ("cedarkit.old", "retired")
    )
    c.execute(
        "INSERT INTO external_elements VALUES (?,?,?,?)",
        ("cmadaas", "TEM", "温度", "fixture:source"),
    )
    c.execute(
        "INSERT INTO entry_external_elements VALUES (?,?,?)", (1, "cmadaas", "TEM")
    )
    c.commit()
    c.close()
    original = source.read_bytes()
    out = tmp_path / "new.db"
    r = migrate_v3(source, out)
    assert source.read_bytes() == original
    assert r["counts"]["retired_ids"] == 1
    c = connect(out, readonly=True)
    try:
        payload = json.loads(
            c.execute("SELECT payload_json FROM migration_sources").fetchone()[0]
        )
        assert payload["tables"]["external_elements"] == [
            {
                "namespace": "cmadaas",
                "code": "TEM",
                "description_cn": "温度",
                "source_ref": "fixture:source",
            }
        ]
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        c.close()
    with pytest.raises(sqlite3.IntegrityError, match="retired"):
        with transaction(out) as c:
            c.execute(
                "INSERT INTO parameters(parameter_id,resource_id,name) VALUES (?,?,?)",
                ("cedarkit.old", "cedarkit.parameters", "reuse"),
            )
    with pytest.raises(FileExistsError):
        migrate_v3(source, source)
    assert source.read_bytes() == original


def test_cli_explicit_paths_migration_report_review_and_slice(legacy, tmp_path, capsys):
    out = tmp_path / "copy.db"
    report = tmp_path / "report.json"
    assert (
        main(
            [
                "--db",
                str(out),
                "migrate-v3",
                "--source-snapshot",
                str(legacy),
                "--report",
                str(report),
            ]
        )
        == 0
    )
    assert not json.loads(report.read_text())["full_migration_complete"]
    assert main(["--db", str(out), "export", "--out-dir", str(tmp_path / "full")]) == 2
    assert "unresolved" in capsys.readouterr().err
    path = tmp_path / "review.json"
    path.write_text(json.dumps(reviewed_definitions(out)))
    assert main(["--db", str(out), "review", "--decisions", str(path)]) == 0
    assert (
        main(
            [
                "--db",
                str(out),
                "export-definitions",
                "--parameter-id",
                "example.t2m",
                "--resource-id",
                "example.slice",
                "--version",
                "1",
                "--out-dir",
                str(tmp_path / "slice"),
            ]
        )
        == 0
    )
    assert main(["--db", str(out), "migration-report", "--out", str(report)]) == 2
    assert main(["--db", str(out), "migrate-v3", "--source-snapshot", str(legacy)]) == 2
    with pytest.raises(SystemExit):
        main(["init"])


def test_manual_issue_flags_cannot_publish_quarantined_identity(legacy, tmp_path):
    doc = json.loads(legacy.read_text())
    doc["entries"][0]["params"][0]["unit"] = "m/s"
    legacy.write_text(json.dumps(doc))
    path = tmp_path / "review.db"
    migrate_v3(legacy, path, source_kind="snapshot")
    c = connect(path)
    try:
        c.execute("UPDATE migration_issues SET resolution_json='{}'")
        c.commit()
    finally:
        c.close()
    with pytest.raises(ValueError, match="quarantined"):
        export_bundle(path, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()
