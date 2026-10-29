"""A bounded mapping handoff must preserve full-migration refusal and evidence."""

import json

import pytest

from cedarkit_param_db import (
    apply_review,
    export_bundle,
    export_mapping_slice,
    init_db,
    import_resources,
    migrate_v3,
    migration_report,
    transaction,
)
from cedarkit_param_db.importer import insert_mappings


def test_mapping_slice_closes_dependencies_and_is_deterministic(
    tmp_path, parameters, mappings
):
    mappings[0]["mappings"][0]["parameter_id"] = "example.t2m"
    path = tmp_path / "author.db"
    init_db(path)
    import_resources(path, parameters, mappings)
    selected = mappings[0]["id"]
    outputs = [tmp_path / "one", tmp_path / "two"]
    for out in outputs:
        manifest = export_mapping_slice(
            path, out, [selected], parameter_resource_id="example.slice", version="1"
        )
        assert manifest["scope"]["complete_product_coverage"] is False
        assert manifest["scope"]["mapping_resource_ids"] == [selected]
        assert manifest["scope"]["parameter_ids"] == ["example.t", "example.t2m"]
        assert (
            len(json.loads((out / "params.json").read_text())["mapping_resources"]) == 1
        )
    assert {p.name: p.read_bytes() for p in outputs[0].iterdir()} == {
        p.name: p.read_bytes() for p in outputs[1].iterdir()
    }


@pytest.mark.parametrize("selected", [[], ["missing"], "not-a-list"])
def test_mapping_slice_rejects_invalid_selection(
    tmp_path, parameters, mappings, selected
):
    path = tmp_path / "author.db"
    init_db(path)
    import_resources(path, parameters, mappings)
    with pytest.raises(ValueError):
        export_mapping_slice(
            path,
            tmp_path / "out",
            selected,
            parameter_resource_id="example.slice",
            version="1",
        )
    assert not (tmp_path / "out").exists()


def test_pending_backend_obligations_remain_visible_and_full_export_blocked(
    legacy, tmp_path
):
    path = tmp_path / "review.db"
    migrate_v3(legacy, path, source_kind="snapshot")
    report = migration_report(path)
    resource = {
        "api_version": "cedarkit.mappings/v1",
        "id": "fixture.limited",
        "version": "1",
        "backend": "grib2",
        "tables": [],
        "mappings": [
            {
                "id": "t",
                "parameter_id": "example.t",
                "backend": "grib2",
                "applies_to": {},
                "when": {},
                "native": {
                    "match": {
                        "discipline": 0,
                        "parameterCategory": 0,
                        "parameterNumber": 0,
                    }
                },
                "evidence": ["fixture:limited-encoding"],
            }
        ],
    }
    with transaction(path) as conn:
        insert_mappings(conn, resource)
    with pytest.raises(ValueError, match="unresolved"):
        export_mapping_slice(
            path,
            tmp_path / "blocked",
            [resource["id"]],
            parameter_resource_id="fixture.slice",
            version="1",
        )
    row = next(r for r in report["records"] if r["parameter_id"] == "example.t")
    apply_review(
        path,
        {
            "source_sha256": report["sources"][0]["sha256"],
            "decisions": [
                {
                    "parameter_id": "example.t",
                    "aspect": "definition",
                    "definition": row["current"],
                    "explanation": "Independent fixture authority confirms broad temperature.",
                    "evidence": ["fixture:definition"],
                }
            ],
        },
    )
    manifest = export_mapping_slice(
        path,
        tmp_path / "limited",
        [resource["id"]],
        parameter_resource_id="fixture.slice",
        version="1",
    )
    assert manifest["scope"]["remaining_migration_obligations"]
    assert migration_report(path)["counts"]["unresolved"] > 0
    with pytest.raises(ValueError, match="unresolved"):
        export_bundle(path, tmp_path / "full")


def test_mapping_slice_cannot_reuse_full_identity_or_omit_evidence(
    tmp_path, parameters, mappings
):
    path = tmp_path / "author.db"
    init_db(path)
    import_resources(path, parameters, mappings)
    with pytest.raises(ValueError, match="distinct"):
        export_mapping_slice(
            path,
            tmp_path / "same-id",
            [mappings[0]["id"]],
            parameter_resource_id=parameters["id"],
            version="1",
        )
    with transaction(path) as conn:
        conn.execute("DELETE FROM mapping_evidence")
    with pytest.raises(ValueError, match="evidence"):
        export_mapping_slice(
            path,
            tmp_path / "no-proof",
            [mappings[0]["id"]],
            parameter_resource_id="fixture.slice",
            version="1",
        )
