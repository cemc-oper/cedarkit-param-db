"""Authoring-only assessment states and evidenced non-applicability dispositions."""

import hashlib
from importlib.resources import files
import json
from pathlib import Path

from cedarkit_query import effective_parameters, normalize_fixed

from .db import connect, require_schema


def _compact(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def local_definition(value):
    result = dict(value)
    result["aliases"] = sorted(result.get("aliases", []))
    result["fixed_conditions"] = normalize_fixed(result.get("fixed_conditions", {}))
    return result


def definition_digests(parameters):
    return {
        pid: hashlib.sha256(_compact(p).encode()).hexdigest()
        for pid, p in effective_parameters(parameters).items()
    }


def definition_digest(parameters, pid):
    return definition_digests(parameters).get(
        pid, hashlib.sha256(b"quarantined").hexdigest()
    )


def copy_review(source, destination):
    """Explicitly extend a NEW schema-4 copy; never alter an archived audit database."""
    from .exporter import read_resources

    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise FileExistsError("review copy must use a distinct new path")
    reader = connect(source, readonly=True)
    try:
        require_schema(reader)
        read_resources(reader)
        with destination.open("xb"):
            pass
        writer = connect(destination)
        try:
            reader.backup(writer)
            writer.executescript(
                files("cedarkit_param_db")
                .joinpath("review.sql")
                .read_text(encoding="utf-8")
            )
            read_resources(writer)
            writer.commit()
        except BaseException:
            writer.close()
            destination.unlink()
            raise
        finally:
            writer.close()
    finally:
        reader.close()
    return destination


def _documents(value, *, verify):
    if not isinstance(value, list) or not value:
        raise ValueError(
            "non-applicability needs independently referenced local evidence documents"
        )
    for document in value:
        if not isinstance(document, dict) or set(document) != {"path", "sha256"}:
            raise ValueError("evidence document requires exactly path and sha256")
        if (
            not isinstance(document["path"], str)
            or not Path(document["path"]).is_absolute()
        ):
            raise ValueError(
                "authoring evidence document paths must be absolute; they are excluded from runtime resources"
            )
        digest = document["sha256"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise ValueError("evidence document sha256 must describe actual bytes")
        if verify:
            path = Path(document["path"])
            if (
                not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest
            ):
                raise ValueError("non-applicability evidence is missing or has changed")


def validate_non_applicability(decision, parameters, *, verify=True):
    aspect = decision["aspect"]
    if aspect not in {"grib2", "cmadaas"}:
        raise ValueError(
            "non-applicability cannot close an unknown parameter definition"
        )
    proof = decision.get("applicability")
    if (
        not isinstance(proof, dict)
        or not {"reason", "scope", "documents"} <= proof.keys()
        or proof.keys()
        - {"reason", "scope", "documents", "used_by", "excluded_scope", "products"}
    ):
        raise ValueError(
            "non-applicability requires a finite reason, complete scope and document evidence"
        )
    if proof["scope"] != {
        "stage": "1.1",
        "backend": aspect,
        "extent": "all_required_products",
    }:
        raise ValueError(
            "a narrow or unknown product scope cannot close a whole-backend obligation"
        )
    _documents(proof["documents"], verify=verify)
    reason = proof["reason"]
    optional = set(proof) - {"reason", "scope", "documents"}
    pid = decision["parameter_id"]
    if reason == "definition_only":
        if (
            optional != {"used_by"}
            or not isinstance(proof["used_by"], list)
            or not proof["used_by"]
        ):
            raise ValueError(
                "definition-only needs exact statistical-object reference users and independent non-publication evidence"
            )
        actual = {
            p["parameter_id"]
            for p in effective_parameters(parameters).values()
            if p.get("fixed_conditions", {})
            .get("statistics", {})
            .get("of", {})
            .get("parameter_id")
            == pid
        }
        if (
            len(proof["used_by"]) != len(set(proof["used_by"]))
            or not set(proof["used_by"]) <= actual
        ):
            raise ValueError(
                "definition-only references must actually use this statistical object"
            )
    elif reason == "outside_stage_scope":
        if optional != {"excluded_scope"} or proof["excluded_scope"] not in {
            "gfs_gda",
            "odb_observation",
        }:
            raise ValueError(
                "only confirmed stage exclusions are accepted; absent samples are not exclusions"
            )
    elif reason == "not_provided":
        products = proof.get("products")
        if optional != {"products"} or not isinstance(products, list) or not products:
            raise ValueError(
                "not-provided needs a complete independently evidenced product/version coverage list"
            )
        seen = set()
        for product in products:
            if (
                not isinstance(product, dict)
                or set(product) != {"dataset", "product", "product_version"}
                or any(
                    not isinstance(v, str) or not v.strip() for v in product.values()
                )
            ):
                raise ValueError(
                    "not-provided products require exact dataset/product/product_version"
                )
            key = tuple(product[k] for k in ("dataset", "product", "product_version"))
            if key in seen:
                raise ValueError("duplicate product coverage identity")
            seen.add(key)
    else:
        raise ValueError(
            "unknown, unsupported or missing evidence is not a non-applicability reason"
        )


def review_states(conn, parameters=None, mappings=None):
    """Recheck stored proof and current definitions; SQL flags alone never establish closure."""
    from .exporter import read_resources

    if parameters is None:
        parameters, mappings = read_resources(conn)
    index = {p["parameter_id"]: p for p in parameters["parameters"]}
    effective = effective_parameters(parameters)
    fingerprints = {
        pid: hashlib.sha256(_compact(p).encode()).hexdigest()
        for pid, p in effective.items()
    }
    fingerprints_default = hashlib.sha256(b"quarantined").hexdigest()

    def fingerprint(pid):
        return fingerprints.get(pid, fingerprints_default)

    tables = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assessments = {}
    if "migration_assessments" in tables:
        for r in conn.execute("SELECT * FROM migration_assessments ORDER BY id"):
            assessments[(r["parameter_id"], r["aspect"])] = dict(r)
    existing_mappings = {
        (m["id"], row["id"]): (m["backend"], row["parameter_id"])
        for m in mappings or ()
        for row in m["mappings"]
    }
    rows = []
    for r in conn.execute(
        "SELECT i.*,r.source_sha256 FROM migration_issues i JOIN migration_records r USING(parameter_id) ORDER BY i.parameter_id,i.aspect"
    ):
        row = {
            k: r[k]
            for k in ("parameter_id", "aspect", "gap", "missing_input", "owner_tasks")
        }
        pid, aspect = r["parameter_id"], r["aspect"]
        row["review_status"] = "unreviewed"
        latest = assessments.get((pid, aspect))
        decision = None
        try:
            if r["resolution_json"] is not None:
                decision = json.loads(r["resolution_json"])
                if (
                    not isinstance(decision, dict)
                    or decision.get("parameter_id") != pid
                    or decision.get("aspect") != aspect
                    or not isinstance(decision.get("explanation"), str)
                    or not decision["explanation"].strip()
                    or not isinstance(decision.get("evidence"), list)
                    or not decision["evidence"]
                    or any(
                        not isinstance(e, str) or not e.strip()
                        for e in decision["evidence"]
                    )
                ):
                    raise ValueError(
                        "malformed resolution does not close an obligation"
                    )
                if decision.get("_definition_sha256", fingerprint(pid)) != fingerprint(
                    pid
                ):
                    raise ValueError("reviewed effective definition has changed")
                outcome = decision.get("outcome", "resolved")
                if outcome == "not_applicable":
                    if (
                        decision.get("_definition_sha256") != fingerprint(pid)
                        or decision.get("_source_sha256") != r["source_sha256"]
                    ):
                        raise ValueError(
                            "non-applicability needs an explicit source and current definition fingerprint"
                        )
                    if "definition" in decision or "mapping_ids" in decision:
                        raise ValueError(
                            "non-applicability cannot contain a synthetic mapping or definition"
                        )
                    validate_non_applicability(decision, parameters)
                    row["review_status"] = "not_applicable"
                elif outcome == "resolved":
                    if aspect == "definition":
                        if (
                            pid not in index
                            or not isinstance(decision.get("definition"), dict)
                            or local_definition(decision["definition"])
                            != local_definition(index[pid])
                        ):
                            raise ValueError(
                                "reviewed local definition has changed or is quarantined"
                            )
                    else:
                        refs = decision.get("mapping_ids")
                        if (
                            not isinstance(refs, list)
                            or not refs
                            or any(
                                not isinstance(ref, dict)
                                or set(ref) != {"resource_id", "id"}
                                or existing_mappings.get(
                                    (ref["resource_id"], ref["id"])
                                )
                                != (aspect, pid)
                                for ref in refs
                            )
                        ):
                            raise ValueError(
                                "reviewed mapping no longer exists for this identity/backend"
                            )
                    row["review_status"] = "resolved"
                else:
                    raise ValueError(
                        "non-final assessment cannot be stored as a resolution"
                    )
            elif latest is not None:
                decision = json.loads(latest["review_json"])
                if latest["source_sha256"] != r["source_sha256"] or latest[
                    "definition_sha256"
                ] != fingerprint(pid):
                    raise ValueError("assessment predates a definition change")
                row["review_status"] = "needs_evidence"
                row["missing_input"] = decision["missing_input"]
                row["owner_tasks"] = decision["owner_tasks"]
            if decision is not None:
                row["assessment"] = decision
        except (ValueError, KeyError, TypeError, OSError) as error:
            row["review_status"] = "needs_reassessment"
            row["review_error"] = str(error)
        rows.append(row)
    # A disposition requires a reviewed definition and all inherited/object definitions.
    definitions = {r["parameter_id"]: r for r in rows if r["aspect"] == "definition"}
    for row in rows:
        if row["review_status"] not in {"resolved", "not_applicable"}:
            continue
        todo = [row["parameter_id"]]
        seen = set()
        while todo:
            pid = todo.pop()
            if pid in seen:
                continue
            seen.add(pid)
            status = definitions.get(pid)
            if status and status["review_status"] != "resolved":
                row["review_status"] = "needs_reassessment"
                row["review_error"] = (
                    "definition or inherited/object dependency has not been reviewed"
                )
                break
            if pid in index:
                p = index[pid]
                todo.extend(
                    d
                    for d in (
                        p.get("parent"),
                        p.get("fixed_conditions", {})
                        .get("statistics", {})
                        .get("of", {})
                        .get("parameter_id"),
                    )
                    if d is not None
                )
    return rows


def disposition_summary(conn, parameters, mappings):
    rows = review_states(conn, parameters, mappings)
    return [
        {
            "parameter_id": r["parameter_id"],
            "backend": r["aspect"],
            "outcome": "not_applicable",
            "reason": r["assessment"]["applicability"]["reason"],
            "scope": r["assessment"]["applicability"]["scope"],
            "evidence_sha256": sorted(
                d["sha256"] for d in r["assessment"]["applicability"]["documents"]
            ),
        }
        for r in rows
        if r["review_status"] == "not_applicable"
    ]
