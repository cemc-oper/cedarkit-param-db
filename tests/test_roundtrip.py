"""Self-contained schema-4 authoring/transaction regression tests; no workspace skips."""

import json
import sqlite3

import pytest
from cedarkit_query import QueryError, load_value, validate_resource_set

from cedarkit_param_db import (
    connect,
    export_bundle,
    import_resources,
    init_db,
    retire_parameter,
    schema_version,
    snapshot,
    transaction,
)


def state(db):
    return snapshot(db)[:2]


def test_flat_identity_parent_alias_and_all_rule_slots_roundtrip(db):
    assert schema_version(db) == 4
    p, ms = state(db)
    index = {r["parameter_id"]: r for r in p["parameters"]}
    assert sorted(index) == ["example.t", "example.t2m"]
    assert index["example.t2m"]["parent"] == "example.t"
    assert "unit" not in index["example.t2m"]
    assert index["example.t2m"]["fixed_conditions"] == {
        "level_type": "height_above_ground",
        "level_unit": "m",
        "level": 2,
    }
    assert index["example.t"]["aliases"] == ["temperature"]
    names = {
        r["rule"]
        for m in ms
        for row in m["mappings"]
        for r in row["native"]["translate"].values()
    }
    assert names == {
        "grib.fixed_surfaces",
        "grib.time",
        "grib.member",
        "grib.statistics",
        "cmadaas.vertical_table",
        "cmadaas.time_fields",
        "cmadaas.member_field",
        "cmadaas.statistics_fields",
        "common.value_unit",
    }
    assert all(m["tables"] == [] for m in ms if m["backend"] == "grib2")
    cms = next(m for m in ms if m["backend"] == "cmadaas")
    assert cms["tables"][0]["rows"][0]["native"] == {"level_type": "103", "level": "2"}
    assert cms["tables"][0]["rows"][0]["evidence"] == ["fixture:row"]


def test_new_resources_reimport_and_same_bytes(db, tmp_path):
    export_bundle(db, tmp_path / "one")
    other = tmp_path / "other.db"
    init_db(other)
    p = load_value((tmp_path / "one/parameters.yaml").read_text(), "parameters")
    ms = [
        load_value(f.read_text(), "mappings")
        for f in sorted((tmp_path / "one").glob("mappings-*.json"))
    ]
    import_resources(other, p, ms)
    export_bundle(other, tmp_path / "two")
    assert {f.name: f.read_bytes() for f in (tmp_path / "one").iterdir()} == {
        f.name: f.read_bytes() for f in (tmp_path / "two").iterdir()
    }


@pytest.mark.parametrize("bad", [None, True, 1.0, "", "0", "01"])
def test_content_versions_are_strict(db, parameters, tmp_path, bad):
    p = tmp_path / "bad.db"
    init_db(p)
    parameters["version"] = bad
    with pytest.raises(QueryError):
        import_resources(p, parameters)
    with connect(p, readonly=True) as c:
        assert c.execute("SELECT count(*) FROM parameters").fetchone()[0] == 0


def test_failed_import_leaves_no_partial_roots(tmp_path, parameters, mappings):
    path = tmp_path / "bad.db"
    init_db(path)
    mappings[1]["mappings"][0]["parameter_id"] = "absent"
    with pytest.raises(QueryError):
        import_resources(path, parameters, mappings)
    c = connect(path, readonly=True)
    try:
        assert c.execute("SELECT count(*) FROM parameter_resources").fetchone()[0] == 0
    finally:
        c.close()


def test_import_rejects_existing_resources_without_replacement(db, parameters):
    before = state(db)
    with pytest.raises(ValueError, match="empty"):
        import_resources(db, parameters)
    assert state(db) == before


@pytest.mark.parametrize(
    "sql,args",
    [
        (
            "UPDATE parameters SET parent=parameter_id WHERE parameter_id=?",
            ("example.t",),
        ),
        (
            "UPDATE parameters SET parent=? WHERE parameter_id=?",
            ("example.t2m", "example.t"),
        ),
        (
            "UPDATE parameters SET fixed_json=? WHERE parameter_id=?",
            ('{"level_type":"pressure","level":500}', "example.t"),
        ),
        (
            "UPDATE parameters SET fixed_json=? WHERE parameter_id=?",
            (
                '{"statistics":{"over":"time","operation":"instantaneous","period":{"kind":"trailing","duration":"PT24H"}}}',
                "example.t",
            ),
        ),
        ("INSERT INTO aliases VALUES (?,?)", ("example.t2m", "example.t")),
        (
            "UPDATE mappings SET native_json=? WHERE resource_id=?",
            (
                '{"match":{"x":1},"translate":{"vertical":{"rule":"unknown"}}}',
                "example.grib2",
            ),
        ),
        (
            "UPDATE table_rows SET canonical_json=? WHERE table_id=?",
            ('{"level_type":"pressure","level":850}', "levels"),
        ),
    ],
)
def test_failed_transaction_restores_every_change(db, sql, args):
    before = state(db)
    with pytest.raises((ValueError, sqlite3.Error)):
        with transaction(db) as c:
            c.execute("UPDATE parameter_resources SET version=?", ("99",))
            c.execute(sql, args)
    assert state(db) == before


def test_arbitrary_failure_rolls_back_even_before_validation(db):
    before = state(db)
    with pytest.raises(RuntimeError):
        with transaction(db) as c:
            c.execute("UPDATE parameters SET description=?", ("changed",))
            raise RuntimeError("injected failure")
    assert state(db) == before


def test_direct_sql_is_revalidated_at_export(db, tmp_path):
    c = connect(db)
    try:
        c.execute(
            "UPDATE parameters SET fixed_json=? WHERE parameter_id=?",
            ('{"unknown":true}', "example.t"),
        )
        c.commit()
    finally:
        c.close()
    with pytest.raises(QueryError):
        export_bundle(db, tmp_path / "must-not-exist")
    assert not (tmp_path / "must-not-exist").exists()


def test_shared_table_and_json_object_references_block_deletion(db):
    with pytest.raises(sqlite3.IntegrityError):
        with transaction(db) as c:
            c.execute("DELETE FROM translation_tables WHERE id=?", ("members",))
    with pytest.raises(sqlite3.IntegrityError):
        retire_parameter(db, "example.t", "old")
    with transaction(db) as c:
        c.execute(
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
    with pytest.raises(sqlite3.IntegrityError):
        with transaction(db) as c:
            c.execute("DELETE FROM mapping_evidence WHERE mapping_id=?", ("t2m",))
            c.execute("DELETE FROM mappings WHERE id=?", ("t2m",))
            c.execute("DELETE FROM aliases WHERE parameter_id=?", ("example.t2m",))
            c.execute("DELETE FROM parameters WHERE parameter_id=?", ("example.t2m",))


def test_of_parent_joint_cycle_is_shared_validation_failure(db):
    before = state(db)
    with pytest.raises(QueryError):
        with transaction(db) as c:
            c.execute(
                "UPDATE parameters SET fixed_json=? WHERE parameter_id=?",
                (
                    json.dumps(
                        {
                            "statistics": {
                                "over": "ensemble",
                                "operation": "mean",
                                "of": {"parameter_id": "example.t2m"},
                            }
                        }
                    ),
                    "example.t",
                ),
            )
    assert state(db) == before


def test_unreferenced_identity_retirement_and_reuse_protection(db):
    with transaction(db) as c:
        c.execute(
            "INSERT INTO parameters(parameter_id,resource_id,name) VALUES (?,?,?)",
            ("example.old", "example.parameters", "old"),
        )
    retire_parameter(db, "example.old", "incompatible meaning retired")
    with pytest.raises(sqlite3.IntegrityError, match="retir"):
        with transaction(db) as c:
            c.execute(
                "INSERT INTO parameters(parameter_id,resource_id,name) VALUES (?,?,?)",
                ("example.old", "example.parameters", "new"),
            )
    with pytest.raises(sqlite3.IntegrityError, match="retir"):
        with transaction(db) as c:
            c.execute(
                "UPDATE parameters SET parameter_id=? WHERE parameter_id=?",
                ("example.old", "example.t2m"),
            )


def test_scoped_native_key_reuse_is_not_globally_unique(db):
    with transaction(db) as c:
        row = c.execute("SELECT * FROM mappings WHERE backend=?", ("grib2",)).fetchone()
        c.execute(
            "INSERT INTO parameters(parameter_id,resource_id,name,unit) VALUES (?,?,?,?)",
            ("example.other", "example.parameters", "other", "K"),
        )
        c.execute(
            "INSERT INTO mappings(resource_id,id,parameter_id,backend,applies_json,when_json,native_json) VALUES (?,?,?,?,?,?,?)",
            (
                row["resource_id"],
                "other",
                "example.other",
                "grib2",
                '{"dataset":"example","product":"orig","product_version":"v2"}',
                row["when_json"],
                row["native_json"],
            ),
        )
    p, ms = state(db)
    validate_resource_set(p, ms)
    assert sum(len(m["mappings"]) for m in ms) == 3


def test_conflicting_joint_table_rows_fail_and_rollback(db):
    before = state(db)
    with pytest.raises(QueryError):
        with transaction(db) as c:
            c.execute(
                "INSERT INTO table_rows VALUES (?,?,?,?,?)",
                (
                    "example.cmadaas",
                    "levels",
                    "conflict",
                    '{"level_type":"103","level":"2"}',
                    '{"level_type":"height_above_ground","level":10}',
                ),
            )
    assert state(db) == before


def test_equivalent_joint_table_rows_remain_legal(db):
    with transaction(db) as c:
        c.execute(
            "INSERT INTO table_rows VALUES (?,?,?,?,?)",
            (
                "example.cmadaas",
                "levels",
                "equivalent",
                '{"level_type":"103","level":"2"}',
                '{"level_type":"height_above_ground","level":200,"level_unit":"cm"}',
            ),
        )
    assert (
        len(
            next(m for m in state(db)[1] if m["backend"] == "cmadaas")["tables"][0][
                "rows"
            ]
        )
        == 2
    )


def test_init_and_connect_never_overwrite_or_create_implicitly(db, tmp_path):
    before = db.read_bytes()
    with pytest.raises(FileExistsError):
        init_db(db)
    with pytest.raises(sqlite3.OperationalError):
        connect(tmp_path / "absent.db")
    assert db.read_bytes() == before
    assert not (tmp_path / "absent.db").exists()


def test_tombstone_occupancy_cannot_be_deleted_or_renamed(db):
    with transaction(db) as c:
        c.execute(
            "INSERT INTO parameter_id_tombstones VALUES (?,?)",
            ("example.retired", "old meaning"),
        )
    for sql in (
        "DELETE FROM parameter_id_tombstones",
        "UPDATE parameter_id_tombstones SET parameter_id='example.new'",
    ):
        with pytest.raises(sqlite3.IntegrityError, match="permanent"):
            with transaction(db) as c:
                c.execute(sql)


def test_stable_active_id_cannot_be_renamed(db):
    with pytest.raises(sqlite3.IntegrityError, match="stable identity"):
        with transaction(db) as c:
            c.execute(
                "UPDATE parameters SET parameter_id='different' WHERE parameter_id='example.t'"
            )


@pytest.mark.parametrize("kind", ["parameters", "mappings"])
def test_low_level_resource_insertion_checks_input_before_discarding_fields(
    db, parameters, mappings, kind
):
    from cedarkit_param_db.importer import insert_parameters, insert_mappings

    before = state(db)
    value = parameters if kind == "parameters" else mappings[0]
    value["unknown_input_field"] = "must not disappear during SQL projection"
    with pytest.raises(QueryError, match="unknown_input_field"):
        with transaction(db) as c:
            c.execute("UPDATE parameter_resources SET version=?", ("99",))
            (insert_parameters if kind == "parameters" else insert_mappings)(c, value)
    assert state(db) == before
