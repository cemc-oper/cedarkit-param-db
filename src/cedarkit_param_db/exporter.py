"""Consistent schema-4 snapshots and atomic, deterministic resource bundles."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from cedarkit_query import load_value, validate_resource_set
import yaml

from .db import connect, require_schema

JSON_SCHEMA_VERSION = 4


def json_text(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    )


def compact(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _refs(conn, table, columns, values):
    where = " AND ".join(k + "=?" for k in columns)
    return [
        r[0]
        for r in conn.execute(
            f"SELECT ref FROM {table} WHERE {where} ORDER BY ref", values
        )
    ]


def read_resources(conn):
    """Read and fully validate one existing transaction view, including derived FKs."""
    require_schema(conn)
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("database contains broken foreign key references")
    roots = conn.execute("SELECT * FROM parameter_resources ORDER BY id").fetchall()
    if len(roots) != 1:
        raise ValueError("exactly one effective parameter resource is required")
    resource = {
        "api_version": "cedarkit.parameters/v1",
        "id": roots[0]["id"],
        "version": roots[0]["version"],
        "parameters": [],
    }
    for r in conn.execute("SELECT * FROM parameters ORDER BY parameter_id"):
        p = {"parameter_id": r["parameter_id"], "name": r["name"]}
        for key in ("parent", "unit", "description", "description_cn"):
            if r[key] is not None:
                p[key] = r[key]
        aliases = [
            a[0]
            for a in conn.execute(
                "SELECT alias FROM aliases WHERE parameter_id=? ORDER BY alias",
                (r["parameter_id"],),
            )
        ]
        if aliases:
            p["aliases"] = aliases
        fixed = json.loads(r["fixed_json"])
        if fixed:
            p["fixed_conditions"] = fixed
        resource["parameters"].append(p)
    mappings = []
    for root in conn.execute("SELECT * FROM mapping_resources ORDER BY id"):
        rid, backend = root["id"], root["backend"]
        m = {
            "api_version": "cedarkit.mappings/v1",
            "id": rid,
            "version": root["version"],
            "backend": backend,
            "mappings": [],
            "tables": [],
        }
        for r in conn.execute(
            "SELECT * FROM mappings WHERE resource_id=? ORDER BY id", (rid,)
        ):
            m["mappings"].append(
                {
                    "id": r["id"],
                    "parameter_id": r["parameter_id"],
                    "backend": r["backend"],
                    "applies_to": json.loads(r["applies_json"]),
                    "when": json.loads(r["when_json"]),
                    "native": json.loads(r["native_json"]),
                    "evidence": _refs(
                        conn,
                        "mapping_evidence",
                        ("resource_id", "mapping_id"),
                        (rid, r["id"]),
                    ),
                }
            )
        for t in conn.execute(
            "SELECT * FROM translation_tables WHERE resource_id=? ORDER BY id", (rid,)
        ):
            table = {
                "id": t["id"],
                "key_kind": t["key_kind"],
                "applies_to": json.loads(t["applies_json"]),
                "evidence": _refs(
                    conn, "table_evidence", ("resource_id", "table_id"), (rid, t["id"])
                ),
                "rows": [],
            }
            for r in conn.execute(
                "SELECT * FROM table_rows WHERE resource_id=? AND table_id=? ORDER BY id",
                (rid, t["id"]),
            ):
                row = {
                    "id": r["id"],
                    "native": json.loads(r["native_json"]),
                    "canonical": json.loads(r["canonical_json"]),
                }
                refs = _refs(
                    conn,
                    "row_evidence",
                    ("resource_id", "table_id", "row_id"),
                    (rid, t["id"], r["id"]),
                )
                if refs:
                    row["evidence"] = refs
                table["rows"].append(row)
            m["tables"].append(table)
        mappings.append(m)
    retired = [
        r[0]
        for r in conn.execute(
            "SELECT parameter_id FROM parameter_id_tombstones ORDER BY parameter_id"
        )
    ]
    validate_resource_set(resource, mappings, retired_ids=retired)
    return resource, mappings


def pending_issues(conn, *, definitions=None):
    from .review import review_states

    rows = [
        r
        for r in review_states(conn)
        if r["review_status"] not in {"resolved", "not_applicable"}
    ]
    if definitions is not None:
        rows = [
            r
            for r in rows
            if r["aspect"] == "definition" and r["parameter_id"] in definitions
        ]
    return rows


def snapshot(db_path):
    conn = connect(db_path, readonly=True)
    try:
        conn.execute("BEGIN")
        p, ms = read_resources(conn)
        return p, ms, pending_issues(conn)
    finally:
        conn.close()


def _browser(conn, parameters, mappings, scope):
    ids = {p["parameter_id"] for p in parameters["parameters"]}
    notes = [
        {k: r[k] for k in ("parameter_id", "remark", "updated_at") if r[k] is not None}
        for r in conn.execute("SELECT * FROM parameter_notes ORDER BY parameter_id")
        if r["parameter_id"] in ids
    ]
    return {
        "meta": {
            "schema_version": JSON_SCHEMA_VERSION,
            "generated_by": "cedarkit-param-db",
            "scope": scope,
            "parameter_resource": {
                k: parameters[k] for k in ("api_version", "id", "version")
            },
            "stats": {
                "parameters": len(ids),
                "aliases": sum(
                    len(p.get("aliases", [])) for p in parameters["parameters"]
                ),
                "mappings": sum(len(m["mappings"]) for m in mappings),
            },
        },
        "parameters": parameters["parameters"],
        "mapping_resources": mappings,
        "retired_ids": [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM parameter_id_tombstones ORDER BY parameter_id"
            )
        ],
        "notes": notes,
    }


def _write_file(path, data):
    path.write_bytes(data)


def _publish(out_dir, parameters, mappings, browser, scope):
    """Stage the whole group, then rename a new directory; never replace a live bundle."""
    out_dir = Path(out_dir).absolute()
    if out_dir.exists():
        raise FileExistsError(out_dir)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".cedarkit-export-", dir=out_dir.parent))
    try:
        outputs = {"parameters": parameters}
        outputs.update(
            {f"mappings-{i:02d}-{m['backend']}": m for i, m in enumerate(mappings)}
        )
        manifest = {
            "schema_version": 1,
            "scope": scope,
            "validation": "internal shared validation only; external product context and backend evidence remain required",
            "files": [],
        }
        for stem, document in outputs.items():
            for suffix, text in (
                ("json", json_text(document)),
                (
                    "yaml",
                    yaml.safe_dump(
                        document, allow_unicode=True, sort_keys=True, width=120
                    ),
                ),
            ):
                name = stem + "." + suffix
                data = text.encode("utf-8")
                _write_file(stage / name, data)
                manifest["files"].append(
                    {
                        "path": name,
                        "id": document["id"],
                        "version": document["version"],
                        "api_version": document["api_version"],
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "size": len(data),
                    }
                )
        data = json_text(browser).encode("utf-8")
        _write_file(stage / "params.json", data)
        manifest["files"].append(
            {
                "path": "params.json",
                "schema_version": 4,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            }
        )
        # Validate staged bytes, not merely the in-memory source. A failed group stays private.
        for stem, expected in outputs.items():
            kind = "parameters" if stem == "parameters" else "mappings"
            for suffix in ("json", "yaml"):
                path = stage / (stem + "." + suffix)
                if (
                    load_value(path.read_text(encoding="utf-8"), kind).to_dict()
                    != expected
                ):
                    raise ValueError(
                        "staged resource differs from the validated source"
                    )
        if json.loads((stage / "params.json").read_text(encoding="utf-8")) != browser:
            raise ValueError(
                "staged browser data differs from the consistent source view"
            )
        for item in manifest["files"]:
            actual = (stage / item["path"]).read_bytes()
            if item["sha256"] != hashlib.sha256(actual).hexdigest():
                raise ValueError("staged bytes changed before publication")
        _write_file(stage / "manifest.json", json_text(manifest).encode("utf-8"))
        if out_dir.exists():
            raise FileExistsError(out_dir)
        os.rename(stage, out_dir)
        return manifest
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def export_bundle(db_path, out_dir):
    conn = connect(db_path, readonly=True)
    try:
        conn.execute("BEGIN")
        p, ms = read_resources(conn)
        missing = conn.execute(
            "SELECT r.parameter_id FROM migration_records r LEFT JOIN parameters p USING(parameter_id) LEFT JOIN parameter_id_tombstones t USING(parameter_id) WHERE p.parameter_id IS NULL AND t.parameter_id IS NULL ORDER BY r.parameter_id"
        ).fetchall()
        if (
            missing
            or conn.execute("SELECT 1 FROM parameter_reservations LIMIT 1").fetchone()
        ):
            raise ValueError("unresolved quarantined identities prevent full export")
        unresolved = pending_issues(conn)
        if unresolved:
            raise ValueError(
                f"unresolved migration facts prevent full export: {len(unresolved)}; inspect migration-report"
            )
        from .review import disposition_summary

        scope = {
            "kind": "database_resources",
            "parameter_ids": [p["parameter_id"] for p in p["parameters"]],
        }
        dispositions = disposition_summary(conn, p, ms)
        if dispositions:
            scope["non_applicable"] = dispositions
        return _publish(out_dir, p, ms, _browser(conn, p, ms, scope), scope)
    finally:
        conn.close()


def export_definitions(db_path, out_dir, parameter_ids, *, resource_id, version):
    """Explicit definition-only slice with dependency closure; never export unresolved definitions."""
    if (
        not isinstance(parameter_ids, (list, tuple))
        or not parameter_ids
        or any(not isinstance(pid, str) or not pid.strip() for pid in parameter_ids)
    ):
        raise ValueError("a nonempty explicit parameter ID selection is required")
    conn = connect(db_path, readonly=True)
    try:
        conn.execute("BEGIN")
        p, _ = read_resources(conn)
        index = {r["parameter_id"]: r for r in p["parameters"]}
        selected = set(parameter_ids)
        if selected - index.keys():
            raise ValueError(f"unknown selected IDs: {sorted(selected - index.keys())}")
        remaining = list(selected)
        while remaining:
            row = index[remaining.pop()]
            for dep in (
                row.get("parent"),
                row.get("fixed_conditions", {})
                .get("statistics", {})
                .get("of", {})
                .get("parameter_id"),
            ):
                if dep is not None and dep not in selected:
                    selected.add(dep)
                    remaining.append(dep)
        unresolved = pending_issues(conn, definitions=selected)
        if unresolved:
            raise ValueError(
                f"selected definitions have unresolved migration facts: {unresolved}"
            )
        if resource_id == p["id"]:
            raise ValueError(
                "a definition slice needs its own resource ID, distinct from the full resource"
            )
        p.update(
            id=resource_id,
            version=version,
            parameters=[index[k] for k in sorted(selected)],
        )
        validate_resource_set(p)
        scope = {
            "kind": "parameter_definitions",
            "requested_parameter_ids": sorted(set(parameter_ids)),
            "parameter_ids": sorted(selected),
            "runtime_mappings": False,
        }
        return _publish(out_dir, p, [], _browser(conn, p, [], scope), scope)
    finally:
        conn.close()


def export_mapping_slice(
    db_path, out_dir, mapping_resource_ids, *, parameter_resource_id, version
):
    """Export explicitly selected complete mapping resources and reviewed definitions.

    This bounded authoring handoff does not close identity-wide migration issues
    or certify product coverage. Resource IDs/revisions and native conditions are
    preserved; the dependency-closed parameter slice gets its own identity.
    """
    if (
        not isinstance(mapping_resource_ids, (list, tuple))
        or not mapping_resource_ids
        or any(
            not isinstance(rid, str) or not rid.strip() for rid in mapping_resource_ids
        )
    ):
        raise ValueError("explicit mapping resource IDs are required")
    conn = connect(db_path, readonly=True)
    try:
        conn.execute("BEGIN")
        p, resources = read_resources(conn)
        wanted = set(mapping_resource_ids)
        mappings = [m for m in resources if m["id"] in wanted]
        if wanted != {m["id"] for m in mappings}:
            raise ValueError("unknown selected mapping resource")
        if any(not m["mappings"] for m in mappings) or any(
            not row["evidence"] for m in mappings for row in m["mappings"]
        ):
            raise ValueError("mapping slice needs nonempty mappings and evidence")
        index = {row["parameter_id"]: row for row in p["parameters"]}
        selected = {row["parameter_id"] for m in mappings for row in m["mappings"]}
        requested = sorted(selected)
        remaining = list(selected)
        while remaining:
            row = index[remaining.pop()]
            for dep in (
                row.get("parent"),
                row.get("fixed_conditions", {})
                .get("statistics", {})
                .get("of", {})
                .get("parameter_id"),
            ):
                if dep is not None and dep not in selected:
                    selected.add(dep)
                    remaining.append(dep)
        if pending_issues(conn, definitions=selected):
            raise ValueError("selected definitions have unresolved migration facts")
        if parameter_resource_id == p["id"]:
            raise ValueError("a mapping slice needs a distinct parameter resource ID")
        p.update(
            id=parameter_resource_id,
            version=version,
            parameters=[index[pid] for pid in sorted(selected)],
        )
        validate_resource_set(p, mappings)
        # Retain pending source-wide obligations explicitly. A usable finite
        # mapping is not evidence that every required product is covered.
        obligations = [
            {
                k: row[k]
                for k in ("parameter_id", "aspect", "review_status", "missing_input")
            }
            for row in pending_issues(conn)
            if row["parameter_id"] in selected and row["aspect"] != "definition"
        ]
        scope = {
            "kind": "parameter_mappings",
            "mapping_resource_ids": sorted(wanted),
            "requested_parameter_ids": requested,
            "parameter_ids": sorted(selected),
            "runtime_mappings": True,
            "complete_product_coverage": False,
            "remaining_migration_obligations": obligations,
        }
        return _publish(out_dir, p, mappings, _browser(conn, p, mappings, scope), scope)
    finally:
        conn.close()
