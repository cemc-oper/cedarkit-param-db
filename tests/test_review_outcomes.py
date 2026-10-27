"""Assessment state, non-applicability and full-export closure tests."""

import hashlib
import json
from pathlib import Path

import pytest

from cedarkit_param_db import (
    apply_review,
    connect,
    copy_review,
    export_bundle,
    export_definitions,
    migrate_v3,
    migration_report,
    transaction,
)


def setup_review(legacy, tmp_path, *, resolve_definitions=True):
    path = tmp_path / "review.db"
    migrate_v3(legacy, path, source_kind="snapshot")
    report = migration_report(path)
    if resolve_definitions:
        apply_review(
            path,
            {
                "source_sha256": report["sources"][0]["sha256"],
                "decisions": [
                    {
                        "parameter_id": r["parameter_id"],
                        "aspect": "definition",
                        "definition": r["current"],
                        "explanation": "Fixture authority establishes broad temperature and the explicit height variant.",
                        "evidence": ["fixture:definition"],
                    }
                    for r in report["records"]
                ],
            },
        )
    return path


def proof_document(tmp_path, reason="outside_stage_scope"):
    path = tmp_path / "applicability.md"
    facts = {
        "outside_stage_scope": "Independent fixture scope authority: these fixture identities are exclusive GDA fields and excluded across all mandatory stage 1.1 products.",
        "not_provided": "Independent fixture scope authority: the complete mandatory scope is fixture/only-required-product/v1; neither fixture identity is provided by that scope.",
        "definition_only": "Independent fixture authority: these two identities are only internal statistical objects used by example.ensemble.root and example.ensemble.child; neither is published as a field in any mandatory product.",
    }
    path.write_text(
        facts[reason] + " No conclusion is inferred from missing samples.\n"
    )
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def non_applicable(pid, aspect, document, reason="outside_stage_scope"):
    applicability = {
        "reason": reason,
        "scope": {"stage": "1.1", "backend": aspect, "extent": "all_required_products"},
        "documents": [document],
    }
    if reason == "outside_stage_scope":
        applicability["excluded_scope"] = "gfs_gda"
    if reason == "not_provided":
        applicability["products"] = [
            {
                "dataset": "fixture",
                "product": "only-required-product",
                "product_version": "v1",
            }
        ]
    if reason == "definition_only":
        applicability["used_by"] = ["example.ensemble"]
    return {
        "parameter_id": pid,
        "aspect": aspect,
        "outcome": "not_applicable",
        "explanation": "The independently cited fixture authority establishes the stated disposition for the complete mandatory scope.",
        "evidence": ["fixture:scope-authority"],
        "applicability": applicability,
    }


def review_input(path, decisions):
    return {
        "source_sha256": migration_report(path)["sources"][0]["sha256"],
        "decisions": decisions,
    }


def test_unreviewed_and_real_evidence_gap_are_distinct_and_both_block_export(
    legacy, tmp_path
):
    path = setup_review(legacy, tmp_path, resolve_definitions=False)
    assert migration_report(path)["review_summary"]["definition"] == {"unreviewed": 2}
    decision = {
        "parameter_id": "example.t",
        "aspect": "definition",
        "outcome": "needs_evidence",
        "explanation": "The inspected fixture source lacks a verified business unit.",
        "evidence": ["fixture:inspected-source"],
        "missing_input": "Authoritative business unit and interpretation are required.",
        "owner_tasks": "I03 with I04/I06 facts",
    }
    apply_review(path, review_input(path, [decision]))
    r = migration_report(path)
    assert r["review_summary"]["definition"] == {"needs_evidence": 1, "unreviewed": 1}
    assert r["counts"]["unresolved"] == 6
    with pytest.raises(ValueError, match="unresolved"):
        export_definitions(
            path,
            tmp_path / "blocked",
            ["example.t2m"],
            resource_id="fixture.slice",
            version="1",
        )
    decision["missing_input"] = "Follow-up inspection still needs a product definition."
    apply_review(path, review_input(path, [decision]))
    c = connect(path, readonly=True)
    try:
        assert (
            c.execute("SELECT count(*) FROM migration_assessments").fetchone()[0] == 2
        )
    finally:
        c.close()


@pytest.mark.parametrize(
    "reason", ["outside_stage_scope", "not_provided", "definition_only"]
)
def test_evidenced_non_applicability_can_close_all_obligations_without_fake_mappings(
    legacy, tmp_path, reason
):
    path = setup_review(legacy, tmp_path)
    if reason == "definition_only":
        with transaction(path) as c:
            for suffix, target in (("root", "example.t"), ("child", "example.t2m")):
                c.execute(
                    "INSERT INTO parameters(parameter_id,resource_id,name,unit,fixed_json) VALUES (?,?,?,?,?)",
                    (
                        "example.ensemble." + suffix,
                        "cedarkit.parameters",
                        "ensemble." + suffix,
                        "K",
                        json.dumps(
                            {
                                "statistics": {
                                    "over": "ensemble",
                                    "operation": "mean",
                                    "of": {"parameter_id": target},
                                }
                            }
                        ),
                    ),
                )
        # Each object has its own genuine reference user.
    doc = proof_document(tmp_path, reason)
    decisions = [
        non_applicable(pid, aspect, doc, reason)
        for pid in ("example.t", "example.t2m")
        for aspect in ("grib2", "cmadaas")
    ]
    if reason == "definition_only":
        for d in decisions:
            d["applicability"]["used_by"] = [
                "example.ensemble."
                + ("root" if d["parameter_id"] == "example.t" else "child")
            ]
    apply_review(path, review_input(path, decisions))
    r = migration_report(path)
    assert (
        r["full_migration_complete"]
        and r["counts"]["unresolved"] == 0
        and r["counts"]["mappings"] == 0
    )
    assert r["review_summary"]["grib2"] == {"not_applicable": 2}
    manifest = export_bundle(path, tmp_path / "complete-internal-bundle")
    assert len(manifest["scope"]["non_applicable"]) == 4
    assert all(d["reason"] == reason for d in manifest["scope"]["non_applicable"])
    assert str(tmp_path) not in json.dumps(manifest)
    browser = json.loads(
        (tmp_path / "complete-internal-bundle/params.json").read_text()
    )
    assert len(browser["meta"]["scope"]["non_applicable"]) == 4


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["applicability"]["scope"].update(extent="one_product"),
        lambda d: d["applicability"]["scope"].update(stage="future"),
        lambda d: d["applicability"].update(reason="unknown"),
        lambda d: d["applicability"].update(reason="unsupported"),
        lambda d: d["applicability"].update(documents=[]),
        lambda d: d["applicability"]["documents"][0].update(sha256="0" * 64),
        lambda d: d.update(mapping_ids=[{"resource_id": "invented", "id": "fake"}]),
        lambda d: d.update(aspect="definition"),
        lambda d: d["applicability"].update(excluded_scope="new_exclusion"),
    ],
)
def test_unknown_narrow_or_unsupported_dispositions_cannot_close_pending_items(
    legacy, tmp_path, change
):
    path = setup_review(legacy, tmp_path)
    before = migration_report(path)
    d = non_applicable("example.t", "grib2", proof_document(tmp_path))
    change(d)
    with pytest.raises(ValueError):
        apply_review(path, review_input(path, [d]))
    assert migration_report(path) == before


def test_non_applicability_cannot_mask_an_unreviewed_definition(legacy, tmp_path):
    path = setup_review(legacy, tmp_path, resolve_definitions=False)
    d = non_applicable("example.t", "grib2", proof_document(tmp_path))
    with pytest.raises(ValueError, match="reviewed"):
        apply_review(path, review_input(path, [d]))
    assert migration_report(path)["counts"]["unresolved"] == 6


def test_changed_evidence_invalidates_non_applicability_and_reblocks_export(
    legacy, tmp_path
):
    path = setup_review(legacy, tmp_path)
    doc = proof_document(tmp_path)
    decisions = [
        non_applicable(pid, aspect, doc)
        for pid in ("example.t", "example.t2m")
        for aspect in ("grib2", "cmadaas")
    ]
    apply_review(path, review_input(path, decisions))
    Path(doc["path"]).write_text("Changed evidence: current scope is unknown.\n")
    report = migration_report(path)
    assert report["review_summary"]["grib2"] == {"needs_reassessment": 2}
    assert not report["full_migration_complete"]
    with pytest.raises(ValueError, match="unresolved"):
        export_bundle(path, tmp_path / "blocked")
    assert not (tmp_path / "blocked").exists()


def test_changed_effective_definition_invalidates_prior_review_and_disposition(
    legacy, tmp_path
):
    path = setup_review(legacy, tmp_path)
    doc = proof_document(tmp_path)
    apply_review(
        path, review_input(path, [non_applicable("example.t2m", "grib2", doc)])
    )
    with transaction(path) as c:
        c.execute("UPDATE parameters SET unit='degC' WHERE parameter_id='example.t'")
    report = migration_report(path)
    assert any(
        r["aspect"] == "grib2"
        and r["parameter_id"] == "example.t2m"
        and r["review_status"] == "needs_reassessment"
        for r in report["unresolved"]
    )
    with pytest.raises(ValueError, match="unresolved"):
        export_definitions(
            path,
            tmp_path / "blocked",
            ["example.t2m"],
            resource_id="fixture.slice",
            version="1",
        )


def test_manual_sql_resolution_flags_are_not_sufficient_even_without_quarantine(
    legacy, tmp_path
):
    path = setup_review(legacy, tmp_path, resolve_definitions=False)
    c = connect(path)
    try:
        c.execute("UPDATE migration_issues SET resolution_json='{}'")
        c.commit()
    finally:
        c.close()
    assert migration_report(path)["review_summary"]["definition"] == {
        "needs_reassessment": 2
    }
    with pytest.raises(ValueError, match="unresolved"):
        export_bundle(path, tmp_path / "blocked")


def test_definition_only_disposition_requires_real_object_reference_users(
    legacy, tmp_path
):
    path = setup_review(legacy, tmp_path)
    d = non_applicable(
        "example.t", "grib2", proof_document(tmp_path), "definition_only"
    )
    with pytest.raises(ValueError, match="actually use"):
        apply_review(path, review_input(path, [d]))


def test_copy_review_extends_a_new_copy_and_preserves_legacy_audit(legacy, tmp_path):
    source = setup_review(legacy, tmp_path)
    before = source.read_bytes()
    # Model the first-round schema-4 database, which predates assessment storage.
    c = connect(source)
    try:
        c.execute("DROP TABLE migration_assessments")
        c.commit()
    finally:
        c.close()
    before = source.read_bytes()
    target = tmp_path / "continued.db"
    copy_review(source, target)
    assert source.read_bytes() == before
    assert (
        migration_report(target)["review_summary"]
        == migration_report(source)["review_summary"]
    )
    c = connect(target, readonly=True)
    try:
        assert c.execute(
            "SELECT name FROM sqlite_master WHERE name='migration_assessments'"
        ).fetchone()
    finally:
        c.close()
    with pytest.raises(FileExistsError):
        copy_review(source, target)
    with pytest.raises(FileExistsError):
        copy_review(source, source)
