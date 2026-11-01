"""Current-state export and archival lookups must not depend on a batch chain."""

from copy import deepcopy
from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

from cedarkit_param_db import init_db, import_resources, write_authoring_source

SPEC = importlib.util.spec_from_file_location(
    "authoring_tool", Path(__file__).resolve().parents[1] / "tools/authoring.py"
)
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


@pytest.fixture
def authoring(tmp_path, parameters, mappings):
    path = tmp_path / "current"
    path.mkdir()
    database = path / "review-schema4.db"
    init_db(database)
    import_resources(database, parameters, mappings)
    config = {
        "format": "cedarkit.authoring/v1",
        "database": database.name,
        "exports": {
            "sample": {
                "mapping_resource_ids": [mappings[0]["id"]],
                "parameter_resource_id": "fixture.slice",
                "parameter_version": "1",
            }
        },
    }
    target = path / "current.json"
    target.write_text(json.dumps(config))
    return target, config


def test_export_uses_current_database_and_repeats_exactly(tmp_path, authoring):
    config, _ = authoring
    before = TOOL.digest(config.parent / "review-schema4.db")
    one, two = tmp_path / "one", tmp_path / "two"
    TOOL.export_current(config, one)
    TOOL.export_current(config, two, systems=["sample"])
    assert {p.name: p.read_bytes() for p in (one / "sample").iterdir()} == {
        p.name: p.read_bytes() for p in (two / "sample").iterdir()
    }
    manifest = json.loads((one / "sample/manifest.json").read_text())
    assert manifest["scope"]["complete_product_coverage"] is False
    assert TOOL.digest(config.parent / "review-schema4.db") == before
    with pytest.raises(FileExistsError):
        TOOL.export_current(config, one)


def test_unknown_system_fails_without_an_output(tmp_path, authoring):
    config, _ = authoring
    with pytest.raises(ValueError, match="unknown export systems"):
        TOOL.export_current(config, tmp_path / "out", systems=["missing"])
    assert not (tmp_path / "out").exists()


def test_failed_second_slice_does_not_publish_partial_group(tmp_path, authoring):
    path, config = authoring
    bad = deepcopy(config["exports"]["sample"])
    bad["mapping_resource_ids"] = ["missing.mapping"]
    config["exports"]["bad"] = bad
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        TOOL.export_current(path, tmp_path / "out")
    assert not (tmp_path / "out").exists()
    assert not list(tmp_path.glob(".cedarkit-export-*"))


@pytest.mark.parametrize("journal_mode", ["DELETE", "WAL"])
def test_group_keeps_one_snapshot_when_authoring_changes_between_slices(
    tmp_path, authoring, monkeypatch, journal_mode
):
    path, config = authoring
    database = path.parent / config["database"]
    resource = config["exports"]["sample"]["mapping_resource_ids"][0]
    config["exports"]["second"] = deepcopy(config["exports"]["sample"])
    path.write_text(json.dumps(config))
    original_export = TOOL.export_mapping_slice
    calls = []
    with closing(sqlite3.connect(database)) as writer:
        writer.execute(f"PRAGMA journal_mode={journal_mode}")
        writer.execute(
            "UPDATE mapping_resources SET version='7' WHERE id=?", (resource,)
        )
        writer.commit()

        # Keep the WAL writer open so committed state need not be in the main file.
        def change_after_first_slice(*args, **kwargs):
            manifest = original_export(*args, **kwargs)
            calls.append(manifest)
            if len(calls) == 1:
                writer.execute(
                    "UPDATE mapping_resources SET version='8' WHERE id=?", (resource,)
                )
                writer.commit()
            return manifest

        monkeypatch.setattr(TOOL, "export_mapping_slice", change_after_first_slice)
        destination = tmp_path / "out"
        TOOL.export_current(path, destination)
        assert len(calls) == 2
        assert [
            json.loads((destination / system / "mappings-00-grib2.json").read_text())[
                "version"
            ]
            for system in ["sample", "second"]
        ] == ["7", "7"]
        assert writer.execute(
            "SELECT version FROM mapping_resources WHERE id=?", (resource,)
        ).fetchone() == ("8",)
    assert not list(tmp_path.glob(".cedarkit-export-*"))


def test_candidate_database_is_explicit_and_configuration_is_not_rewritten(
    tmp_path, authoring
):
    path, config = authoring
    candidate = tmp_path / "candidate.db"
    candidate.write_bytes((path.parent / config["database"]).read_bytes())
    # The default database is deliberately absent: no fallback to another batch.
    (path.parent / config["database"]).unlink()
    before = path.read_bytes()
    TOOL.export_current(path, tmp_path / "out", database=candidate)
    assert path.read_bytes() == before
    with pytest.raises(sqlite3.OperationalError, match="unable to open"):
        TOOL.export_current(path, tmp_path / "missing-default")


def text_configuration(authoring):
    path, config = authoring
    write_authoring_source(path.parent / config["database"], path.parent / "state")
    config["source"] = "state"
    path.write_text(json.dumps(config))
    return path, config


def test_text_export_ignores_stale_or_missing_local_database(tmp_path, authoring):
    path, config = text_configuration(authoring)
    database = path.parent / config["database"]
    with closing(sqlite3.connect(database)) as conn:
        conn.execute("UPDATE mapping_resources SET version='99'")
        conn.commit()
    TOOL.export_current(path, tmp_path / "stale-cache")
    database.unlink()
    TOOL.export_current(path, tmp_path / "missing-cache")
    for folder in ["stale-cache", "missing-cache"]:
        assert (
            json.loads(
                (tmp_path / folder / "sample/mappings-00-grib2.json").read_text()
            )["version"]
            == "1"
        )
    (path.parent / "state/parameters.jsonl").write_text("{}\n")
    with pytest.raises(ValueError, match="SHA256"):
        TOOL.export_current(path, tmp_path / "invalid-source")
    assert not (tmp_path / "invalid-source").exists()


def test_text_source_replacement_between_slices_cannot_mix_generations(
    tmp_path, authoring, monkeypatch
):
    path, config = text_configuration(authoring)
    config["exports"]["second"] = deepcopy(config["exports"]["sample"])
    path.write_text(json.dumps(config))
    original, calls = TOOL.export_mapping_slice, []

    def replace_after_first_slice(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(result)
        if len(calls) == 1:
            with closing(sqlite3.connect(path.parent / config["database"])) as conn:
                conn.execute("UPDATE mapping_resources SET version='8'")
                conn.commit()
            write_authoring_source(
                path.parent / config["database"], path.parent / "state", replace=True
            )
        return result

    monkeypatch.setattr(TOOL, "export_mapping_slice", replace_after_first_slice)
    TOOL.export_current(path, tmp_path / "out")
    assert [
        json.loads((tmp_path / "out" / system / "mappings-00-grib2.json").read_text())[
            "version"
        ]
        for system in ["sample", "second"]
    ] == ["1", "1"]


def test_build_and_capture_commands_use_explicit_candidates(tmp_path, authoring):
    path, config = text_configuration(authoring)
    candidate = tmp_path / "candidate.db"
    assert TOOL.main(["--config", str(path), "build", "--db", str(candidate)]) == 0
    with closing(sqlite3.connect(candidate)) as conn:
        conn.execute("UPDATE mapping_resources SET version='7'")
        conn.commit()
    assert TOOL.main(["--config", str(path), "capture", "--db", str(candidate)]) == 0
    TOOL.export_current(path, tmp_path / "new")
    assert (
        json.loads((tmp_path / "new/sample/mappings-00-grib2.json").read_text())[
            "version"
        ]
        == "7"
    )
    assert TOOL.main(["--config", str(path), "build", "--db", str(candidate)]) == 2


@pytest.fixture
def archived(tmp_path, authoring):
    config_path, config = authoring
    folder = tmp_path / "archive"
    folder.mkdir()
    payload = folder / "snapshot.json"
    payload.write_text('{"immutable":true}\n')
    sha = hashlib.sha256(payload.read_bytes()).hexdigest()
    original = "data/cedarkit-param-db/migrations/old/snapshot.json"
    index = folder / "index.json"
    index.write_text(
        json.dumps(
            {
                "format": "cedarkit.authoring-archive/v1",
                "workspace_root": "..",
                "files": [
                    {
                        "original_path": original,
                        "archive_path": "archive/snapshot.json",
                        "sha256": sha,
                    }
                ],
            }
        )
    )
    config["archive"] = {
        "index": "../archive/index.json",
        "sha256": TOOL.digest(index),
    }
    config_path.write_text(json.dumps(config))
    return config_path, original, payload, index, sha


def test_archive_resolution_checks_old_absolute_relative_and_hashed_locators(archived):
    config, original, payload, _, sha = archived
    for locator in [
        original,
        str(payload.parent.parent / original),
        original + "#sha256=" + sha,
    ]:
        assert TOOL.resolve_archived(config, locator) == payload
    assert TOOL.check_archive(config) == 1
    with pytest.raises(ValueError, match="unknown archived evidence"):
        TOOL.resolve_archived(config, "missing")
    with pytest.raises(ValueError, match="reference SHA256"):
        TOOL.resolve_archived(config, original + "#sha256=" + "0" * 64)


def test_archived_payload_change_is_detected(archived):
    config, original, payload, _, _ = archived
    payload.write_text("changed")
    with pytest.raises(ValueError, match="archived evidence SHA256"):
        TOOL.resolve_archived(config, original)


def test_archive_index_change_is_detected_before_lookup(archived):
    config, original, _, index, _ = archived
    index.write_text("{}")
    with pytest.raises(ValueError, match="archive index SHA256"):
        TOOL.resolve_archived(config, original)
