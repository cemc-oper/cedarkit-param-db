"""Export bytes, scope, consistency, and failure atomicity."""

import hashlib
import json

import pytest
from cedarkit_query import load_value

from cedarkit_param_db import (
    connect,
    export_bundle,
    import_resources,
    init_db,
    transaction,
)
from cedarkit_param_db import exporter


def contents(path):
    return {p.name: p.read_bytes() for p in path.iterdir()}


def test_bundle_determinism_hashes_new_browser_contract_and_no_machine_paths(
    db, tmp_path
):
    one, two = tmp_path / "one", tmp_path / "two"
    manifest = export_bundle(db, one)
    export_bundle(db, two)
    assert contents(one) == contents(two)
    assert len(manifest["files"]) == 7
    for f in manifest["files"]:
        data = (one / f["path"]).read_bytes()
        assert f["sha256"] == hashlib.sha256(data).hexdigest()
        assert f["size"] == len(data)
    for f in one.glob("*.yaml"):
        same = load_value(
            (one / (f.stem + ".json")).read_text(),
            "parameters" if f.stem == "parameters" else "mappings",
        )
        assert (
            load_value(
                f.read_text(), "parameters" if f.stem == "parameters" else "mappings"
            )
            == same
        )
    browser = json.loads((one / "params.json").read_text())
    assert browser["meta"]["schema_version"] == 4
    assert browser["meta"]["stats"] == {"parameters": 2, "aliases": 2, "mappings": 2}
    assert all("key" not in p and "variants" not in p for p in browser["parameters"])
    assert "entries" not in browser
    for data in contents(one).values():
        assert str(tmp_path).encode() not in data
        assert b"exported_at" not in data


def test_order_of_unordered_records_aliases_and_evidence_does_not_change_export(
    db, tmp_path, parameters, mappings
):
    other = tmp_path / "other.db"
    init_db(other)
    parameters["parameters"].reverse()
    for m in mappings:
        m["mappings"].reverse()
        m["tables"].reverse()
        for row in m["mappings"]:
            row["evidence"].reverse()
    mappings.reverse()
    import_resources(other, parameters, mappings)
    export_bundle(db, tmp_path / "one")
    export_bundle(other, tmp_path / "two")
    assert contents(tmp_path / "one") == contents(tmp_path / "two")


def test_unordered_evidence_dedup_is_rejected_before_writing(
    db, tmp_path, parameters, mappings
):
    path = tmp_path / "bad.db"
    init_db(path)
    mappings[0]["mappings"][0]["evidence"] *= 2
    # Duplicate input references are schema-invalid, never silently collapsed.
    with pytest.raises(ValueError):
        import_resources(path, parameters, mappings)


def test_stage_write_failure_never_publishes_partial_group(db, tmp_path, monkeypatch):
    original = exporter._write_file
    count = 0

    def fail(path, data):
        nonlocal count
        count += 1
        if count == 3:
            raise OSError("injected staging failure")
        original(path, data)

    monkeypatch.setattr(exporter, "_write_file", fail)
    with pytest.raises(OSError, match="injected"):
        export_bundle(db, tmp_path / "output")
    assert not (tmp_path / "output").exists()
    assert not list(tmp_path.glob(".cedarkit-export-*"))


def test_existing_bundle_is_not_replaced(db, tmp_path):
    out = tmp_path / "bundle"
    export_bundle(db, out)
    before = contents(out)
    with pytest.raises(FileExistsError):
        export_bundle(db, out)
    assert contents(out) == before


def test_snapshot_remains_consistent_during_concurrent_writer(
    db, tmp_path, monkeypatch
):
    c = connect(db)
    c.execute("PRAGMA journal_mode=WAL")
    c.close()
    original = exporter._browser

    def interleave(conn, p, ms, scope):
        with transaction(db) as writer:
            writer.execute("UPDATE parameter_resources SET version=?", ("2",))
            writer.execute("UPDATE parameter_notes SET remark=?", ("changed",))
        return original(conn, p, ms, scope)

    monkeypatch.setattr(exporter, "_browser", interleave)
    export_bundle(db, tmp_path / "old-view")
    p = json.loads((tmp_path / "old-view/parameters.json").read_text())
    browser = json.loads((tmp_path / "old-view/params.json").read_text())
    assert p["version"] == "1"
    assert browser["meta"]["parameter_resource"]["version"] == "1"
    c = connect(db, readonly=True)
    try:
        assert c.execute("SELECT version FROM parameter_resources").fetchone()[0] == "2"
    finally:
        c.close()


def test_edited_annotations_only_appear_in_browser(db, tmp_path):
    with transaction(db) as c:
        c.execute(
            "INSERT INTO parameter_notes VALUES (?,?,?)",
            ("example.t", "review note", "2026-10-27 00:00:00"),
        )
    export_bundle(db, tmp_path / "bundle")
    p = json.loads((tmp_path / "bundle/parameters.json").read_text())
    browser = json.loads((tmp_path / "bundle/params.json").read_text())
    assert all("remark" not in r and "updated_at" not in r for r in p["parameters"])
    assert browser["notes"] == [
        {
            "parameter_id": "example.t",
            "remark": "review note",
            "updated_at": "2026-10-27 00:00:00",
        }
    ]


def test_staged_corruption_prevents_group_publication(db, tmp_path, monkeypatch):
    original = exporter._write_file

    def corrupt(path, data):
        original(path, b"{}\n" if path.name == "parameters.json" else data)

    monkeypatch.setattr(exporter, "_write_file", corrupt)
    with pytest.raises(ValueError):
        export_bundle(db, tmp_path / "corrupt")
    assert not (tmp_path / "corrupt").exists()
    assert not list(tmp_path.glob(".cedarkit-export-*"))
