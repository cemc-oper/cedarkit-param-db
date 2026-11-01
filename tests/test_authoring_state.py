"""Complete authoring state survives text storage, including non-runtime data."""

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest
from cedarkit_query import QueryError

from cedarkit_param_db import (
    apply_review,
    build_authoring_database,
    migrate_v3,
    migration_report,
    transaction,
    write_authoring_source,
)
from cedarkit_param_db import authoring
from cedarkit_param_db.exporter import compact


def contents(folder):
    return {p.name: p.read_bytes() for p in folder.iterdir()}


def tables(path):
    with closing(sqlite3.connect(path)) as conn:
        return {
            name: sorted(conn.execute('SELECT * FROM "' + name + '"'), key=repr)
            for (name,) in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }


def rewrite_table(source, name, transform):
    path = source / (name + ".jsonl")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    transform(rows)
    data = "".join(compact(r) + "\n" for r in rows).encode()
    path.write_bytes(data)
    manifest = json.loads((source / "manifest.json").read_text())
    table = next(t for t in manifest["tables"] if t["name"] == name)
    table.update(rows=len(rows), sha256=hashlib.sha256(data).hexdigest())
    (source / "manifest.json").write_text(json.dumps(manifest))


def test_complete_tables_generated_references_tombstones_and_literal_notes(
    db, tmp_path
):
    with transaction(db) as conn:
        conn.execute(
            "INSERT INTO parameter_notes VALUES (?,?,?)",
            ("example.t", '中文 " \\ \0\n', None),
        )
        conn.execute(
            "INSERT INTO parameter_id_tombstones VALUES (?,?)",
            ("example.retired", "retained"),
        )
        conn.execute(
            "INSERT INTO parameters(parameter_id,resource_id,name,unit,fixed_json) VALUES (?,?,?,?,?)",
            (
                "example.ensemble",
                "example.parameters",
                "ensemble",
                "K",
                json.dumps(
                    {
                        "statistics": {
                            "over": "ensemble",
                            "operation": "mean",
                            "of": {"parameter_id": "example.t2m"},
                        }
                    }
                ),
            ),
        )
    source = write_authoring_source(db, tmp_path / "state")
    target = build_authoring_database(source, tmp_path / "rebuilt.db")
    assert tables(db) == tables(target)
    assert len(tables(target)) == 18
    with closing(sqlite3.connect(target)) as conn:
        assert conn.execute(
            "SELECT object_id FROM parameters WHERE parameter_id='example.ensemble'"
        ).fetchone() == ("example.t2m",)
    with pytest.raises(sqlite3.IntegrityError, match="permanent"):
        with transaction(target) as conn:
            conn.execute("DELETE FROM parameter_id_tombstones")
    assert contents(
        write_authoring_source(target, tmp_path / "recaptured")
    ) == contents(source)


def test_migration_history_unresolved_assessment_and_quarantine_survive(
    legacy, tmp_path
):
    database = tmp_path / "review.db"
    report = migrate_v3(legacy, database, source_kind="snapshot")
    apply_review(
        database,
        {
            "source_sha256": report["sources"][0]["sha256"],
            "decisions": [
                {
                    "parameter_id": "example.t",
                    "aspect": "definition",
                    "outcome": "needs_evidence",
                    "explanation": "Inspected the retained source without assuming a unit.",
                    "evidence": ["fixture:source"],
                    "missing_input": "Verified unit and exact product meaning",
                    "owner_tasks": "I03/I04/I06",
                }
            ],
        },
    )
    with transaction(database) as conn:
        conn.execute("DELETE FROM aliases WHERE parameter_id='example.t2m'")
        conn.execute("DELETE FROM parameters WHERE parameter_id='example.t2m'")
        conn.execute(
            "INSERT INTO parameter_reservations VALUES (?,?)",
            ("example.t2m", '{"reason":"needs evidence"}'),
        )
    before = migration_report(database)
    state = write_authoring_source(database, tmp_path / "state")
    restored = build_authoring_database(state, tmp_path / "restored.db")
    assert tables(restored) == tables(database)
    assert migration_report(restored) == before
    with pytest.raises(sqlite3.IntegrityError, match="quarantined"):
        with transaction(restored) as conn:
            conn.execute(
                "INSERT INTO parameters(parameter_id,resource_id,name) VALUES (?,?,?)",
                ("example.t2m", "cedarkit.parameters", "t2m"),
            )


@pytest.mark.parametrize("journal", ["DELETE", "WAL"])
def test_capture_uses_one_snapshot_even_when_live_tables_change(
    db, tmp_path, monkeypatch, journal
):
    original = authoring._table_bytes
    changed = False
    with closing(sqlite3.connect(db)) as writer:
        writer.execute("PRAGMA journal_mode=" + journal)
        writer.execute("UPDATE mapping_resources SET version='7'")
        writer.commit()

        def interleave(conn, table):
            nonlocal changed
            result = original(conn, table)
            if not changed:
                writer.execute("UPDATE mapping_resources SET version='8'")
                writer.commit()
                changed = True
            return result

        monkeypatch.setattr(authoring, "_table_bytes", interleave)
        source = write_authoring_source(db, tmp_path / "source")
        target = build_authoring_database(source, tmp_path / "rebuilt.db")
        with closing(sqlite3.connect(target)) as reader:
            assert {
                r[0] for r in reader.execute("SELECT version FROM mapping_resources")
            } == {"7"}
        assert {
            r[0] for r in writer.execute("SELECT version FROM mapping_resources")
        } == {"8"}


@pytest.mark.parametrize("damage", ["table", "missing", "schema", "extra"])
def test_source_integrity_errors_leave_no_database(db, tmp_path, damage):
    source = write_authoring_source(db, tmp_path / "source")
    if damage == "table":
        (source / "parameters.jsonl").write_text("{}\n")
    elif damage == "missing":
        (source / "migration_assessments.jsonl").unlink()
    elif damage == "extra":
        (source / "untracked.jsonl").write_text("{}\n")
    else:
        manifest = json.loads((source / "manifest.json").read_text())
        manifest["schema_sha256"] = "0" * 64
        (source / "manifest.json").write_text(json.dumps(manifest))
    destination = tmp_path / "rejected.db"
    with pytest.raises(ValueError):
        build_authoring_database(source, destination)
    assert not destination.exists()


def test_valid_checksums_do_not_bypass_semantic_validation(db, tmp_path):
    source = write_authoring_source(db, tmp_path / "source")

    def wrong_quantity(rows):
        next(r for r in rows if r["parameter_id"] == "example.t2m")["unit"] = "m"

    rewrite_table(source, "parameters", wrong_quantity)
    with pytest.raises(QueryError):
        build_authoring_database(source, tmp_path / "rejected.db")
    assert not (tmp_path / "rejected.db").exists()


def test_existing_database_and_source_are_never_overwritten_implicitly(db, tmp_path):
    source = write_authoring_source(db, tmp_path / "source")
    before_db, before_source = db.read_bytes(), contents(source)
    with pytest.raises(FileExistsError):
        build_authoring_database(source, db)
    with pytest.raises(FileExistsError):
        write_authoring_source(db, source)
    assert db.read_bytes() == before_db and contents(source) == before_source


def test_capture_publication_failure_restores_previous_source(
    db, tmp_path, monkeypatch
):
    source = write_authoring_source(db, tmp_path / "source")
    before = contents(source)
    rename = Path.rename

    def fail_new_group(path, target):
        if path.name == "source" and path.parent.name.startswith(".cedarkit-source-"):
            raise OSError("fixture publication failure")
        return rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_new_group)
    with pytest.raises(OSError, match="publication"):
        write_authoring_source(db, source, replace=True)
    assert contents(source) == before
    assert not list(tmp_path.glob(".cedarkit-source-*"))


@pytest.mark.parametrize(
    "extension",
    [
        "CREATE INDEX author_local_index ON parameters(name)",
        "CREATE TABLE sqlitex_payload(value TEXT)",
    ],
)
def test_schema_extensions_cannot_be_silently_lost(db, tmp_path, extension):
    with closing(sqlite3.connect(db)) as conn:
        conn.execute(extension)
    with pytest.raises(ValueError, match="schema differs"):
        write_authoring_source(db, tmp_path / "source")
    assert not (tmp_path / "source").exists()
