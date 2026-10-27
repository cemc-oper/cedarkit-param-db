"""Validated schema-4 initialization. Legacy formats require the explicit offline migrator."""

from cedarkit_query import Mappings, Parameters, normalize_fixed, validate_resource_set

from .db import transaction
from .exporter import compact


def insert_parameters(conn, resource):
    resource = Parameters(resource).to_dict()
    conn.execute(
        "INSERT INTO parameter_resources VALUES (?,?)",
        (resource["id"], resource["version"]),
    )
    for p in resource["parameters"]:
        conn.execute(
            "INSERT INTO parameters(parameter_id,resource_id,name,parent,unit,description,description_cn,fixed_json) VALUES (?,?,?,?,?,?,?,?)",
            (
                p["parameter_id"],
                resource["id"],
                p["name"],
                p.get("parent"),
                p.get("unit"),
                p.get("description"),
                p.get("description_cn"),
                compact(normalize_fixed(p.get("fixed_conditions", {}))),
            ),
        )
        conn.executemany(
            "INSERT INTO aliases VALUES (?,?)",
            [(p["parameter_id"], a) for a in p.get("aliases", [])],
        )


def insert_mappings(conn, resource):
    resource = Mappings(resource).to_dict()
    rid, backend = resource["id"], resource["backend"]
    conn.execute(
        "INSERT INTO mapping_resources VALUES (?,?,?)",
        (rid, resource["version"], backend),
    )
    for t in resource["tables"]:
        conn.execute(
            "INSERT INTO translation_tables VALUES (?,?,?,?)",
            (rid, t["id"], t["key_kind"], compact(t["applies_to"])),
        )
        conn.executemany(
            "INSERT INTO table_evidence VALUES (?,?,?)",
            [(rid, t["id"], e) for e in t["evidence"]],
        )
        for r in t["rows"]:
            conn.execute(
                "INSERT INTO table_rows VALUES (?,?,?,?,?)",
                (rid, t["id"], r["id"], compact(r["native"]), compact(r["canonical"])),
            )
            conn.executemany(
                "INSERT INTO row_evidence VALUES (?,?,?,?)",
                [(rid, t["id"], r["id"], e) for e in r.get("evidence", [])],
            )
    for m in resource["mappings"]:
        conn.execute(
            "INSERT INTO mappings(resource_id,id,parameter_id,backend,applies_json,when_json,native_json) VALUES (?,?,?,?,?,?,?)",
            (
                rid,
                m["id"],
                m["parameter_id"],
                m["backend"],
                compact(m["applies_to"]),
                compact(m["when"]),
                compact(m["native"]),
            ),
        )
        conn.executemany(
            "INSERT INTO mapping_evidence VALUES (?,?,?)",
            [(rid, m["id"], e) for e in m["evidence"]],
        )


def import_resources(db_path, parameters, mappings=(), *, retired=()):
    """Initialize an empty v4 authoring database in one validated transaction."""
    p = Parameters(parameters).to_dict()
    ms = [Mappings(m).to_dict() for m in mappings]
    retired = list(retired)
    validate_resource_set(p, ms, retired_ids=[r["parameter_id"] for r in retired])
    with transaction(db_path) as conn:
        if conn.execute("SELECT count(*) FROM parameter_resources").fetchone()[0]:
            raise ValueError(
                "import requires an empty schema-4 database; use validated transaction edits for existing resources"
            )
        conn.executemany(
            "INSERT INTO parameter_id_tombstones VALUES (?,?)",
            [(r["parameter_id"], r["retired_reason"]) for r in retired],
        )
        insert_parameters(conn, p)
        for m in ms:
            insert_mappings(conn, m)
    return {"parameters": len(p["parameters"]), "mapping_resources": len(ms)}
