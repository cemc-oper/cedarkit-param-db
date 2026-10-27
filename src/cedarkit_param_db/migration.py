"""Explicit offline v3 migration to a new schema-4 review copy.

Native facts without a proven product/version and translation remain audit data.
They are never converted to unrestricted runtime mappings.
"""

import hashlib
import json
from pathlib import Path
import sqlite3

import yaml
from cedarkit_query import QueryError, normalize_fixed

from .db import connect, init_db, transaction
from .exporter import compact, json_text, pending_issues, read_resources
from .importer import insert_mappings, insert_parameters

SURFACES = {
    1: "surface",
    8: "atmosphere_top",
    10: "entire_atmosphere",
    100: "pressure",
    101: "mean_sea_level",
    103: "height_above_ground",
    106: "depth_below_land",
}
OPERATIONS = {
    "instant": "instantaneous",
    "accum": "accumulation",
    "max": "maximum",
    "min": "minimum",
    "avg": "mean",
}
WHEN_KEYS = {
    "first_level_type",
    "first_level",
    "second_level_type",
    "second_level",
    "stepType",
    "time_range_hours",
}


def _pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise ValueError(f"duplicate legacy key: {key}")
        result[key] = value
    return result


class _LegacyLoader(yaml.SafeLoader):
    pass


_LegacyLoader.yaml_implicit_resolvers = {
    k: [(tag, pattern) for tag, pattern in v if tag != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _yaml_pairs(loader, node):
    pairs = [
        (loader.construct_object(k, deep=True), loader.construct_object(v, deep=True))
        for k, v in node.value
    ]
    if any(not isinstance(k, str) for k, _ in pairs):
        raise ValueError("legacy keys must be strings")
    return _pairs(pairs)


_LegacyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _yaml_pairs
)


def _load_snapshot(path):
    text = path.read_text(encoding="utf-8")
    doc = (
        json.loads(text, object_pairs_hook=_pairs)
        if text.lstrip().startswith(("{", "["))
        else yaml.load(text, Loader=_LegacyLoader)
    )
    if (
        not isinstance(doc, dict)
        or doc.get("api_version") != "reki.parameter-registry/v3"
        or not isinstance(doc.get("entries"), list)
    ):
        raise ValueError(
            "only explicitly identified reki.parameter-registry/v3 snapshots are supported"
        )
    compact(doc)  # Reject nonfinite numbers and non-JSON values, including cyclic YAML.
    records = []
    for entry in doc["entries"]:
        base = {
            "kind": "entry",
            "record": entry,
            "key": entry["key"],
            "aliases": entry.get("aliases", []),
            "external_names": entry.get("external_names", {}),
        }
        records.append(base)
        for variant in entry.get("params", []):
            records.append(
                {
                    "kind": "variant",
                    "record": variant,
                    "parent_id": entry["parameter_id"],
                    "key": entry["key"],
                    "aliases": variant.get("aliases", []),
                    "external_names": entry.get("external_names", {}),
                }
            )
    return doc, records, []


def _load_database(path):
    for suffix in ("-wal", "-journal"):
        if Path(str(path) + suffix).exists():
            raise ValueError(
                "legacy source has a journal; supply a stable checkpointed copy"
            )
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        version = conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()
        if version is None or version[0] != "3":
            raise ValueError("only schema-3 legacy databases are supported")
        # All legacy tables are retained verbatim for review and recovery, including vocabulary.
        names = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        tables = {
            n: [
                dict(r)
                for r in conn.execute('SELECT * FROM "' + n.replace('"', '""') + '"')
            ]
            for n in names
        }
    finally:
        conn.close()
    entries = {r["id"]: r for r in tables["entries"]}
    records = []
    for kind, rows in (("entry", tables["entries"]), ("variant", tables["variants"])):
        for row in rows:
            entry = row if kind == "entry" else entries[row["entry_id"]]
            codes = {
                r["namespace"]: r["code"]
                for r in tables["entry_external_elements"]
                if r["entry_id"] == entry["id"]
            }
            records.append(
                {
                    "kind": kind,
                    "record": row,
                    "key": {k: entry[k] for k in ("discipline", "category", "number")},
                    "aliases": [
                        r["alias"]
                        for r in tables["aliases"]
                        if r["owner_type"] == kind and r["owner_id"] == row["id"]
                    ],
                    "external_names": codes,
                    **(
                        {"parent_id": entry["parameter_id"]}
                        if kind == "variant"
                        else {}
                    ),
                }
            )
    return {"tables": tables}, records, tables["parameter_id_tombstones"]


def _fixed_conditions(record):
    """Only explicit old predicates; never promote informational level fields."""
    old = record["record"]
    when = (
        json.loads(old["when_json"], object_pairs_hook=_pairs)
        if "when_json" in old
        else old.get("when", {})
    )
    fixed, reasons, classification = {}, [], {}
    unknown = when.keys() - WHEN_KEYS
    if unknown:
        reasons.append("unrecognized old predicates: " + ", ".join(sorted(unknown)))
    vertical = {
        k: v
        for k, v in when.items()
        if k in WHEN_KEYS and k not in {"stepType", "time_range_hours"}
    }
    if vertical:
        first = vertical.get("first_level_type")
        second = vertical.get("second_level_type")
        if type(first) is not int or first not in SURFACES:
            reasons.append(
                "native vertical type needs an evidenced canonical interpretation"
            )
        elif second is not None:
            if (
                second != first
                or not {"first_level", "second_level"} <= vertical.keys()
                or first not in (100, 103, 106)
            ):
                reasons.append("native layer endpoints require explicit interpretation")
            else:
                a, b = vertical["first_level"], vertical["second_level"]
                if (
                    isinstance(a, bool)
                    or isinstance(b, bool)
                    or not isinstance(a, (float, int))
                    or not isinstance(b, (float, int))
                ):
                    raise ValueError("legacy layer values must be finite numbers")
                bottom, top = (
                    (max(a, b), min(a, b))
                    if first in (100, 106)
                    else (min(a, b), max(a, b))
                )
                fixed.update(
                    level_type=SURFACES[first],
                    level_unit="hPa" if first == 100 else "m",
                    layer={"bottom": bottom, "top": top},
                )
        else:
            fixed["level_type"] = SURFACES[first]
            if first in (100, 103, 106):
                fixed["level_unit"] = "hPa" if first == 100 else "m"
                if "first_level" in vertical:
                    fixed["level"] = vertical["first_level"]
            elif "first_level" in vertical:
                reasons.append(
                    "numeric value attached to a named boundary needs review"
                )
        for key in vertical:
            classification[key] = (
                "canonical_vertical" if not reasons else "pending_vertical_review"
            )
    if "stepType" in when:
        step = when["stepType"]
        if step not in OPERATIONS:
            reasons.append("unknown statistical operation")
        else:
            fixed["statistics"] = {"over": "time", "operation": OPERATIONS[step]}
            if step != "instant":
                reasons.append(
                    "statistical period anchoring requires definition; window length alone does not establish trailing or since_initialization"
                )
        classification["stepType"] = "canonical_operation"
    if "time_range_hours" in when:
        reasons.append(
            "time_range_hours retained for review, not converted to an assumed period"
        )
        classification["time_range_hours"] = "pending_period_definition"
    for key in unknown:
        classification[key] = "pending_unknown_predicate"
    return normalize_fixed(fixed), reasons, classification


def migrate_v3(source, destination, *, source_kind="database"):
    """Preserve the source and produce a new review DB. Incomplete facts stay unresolved."""
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve() or destination.exists():
        raise FileExistsError(
            "migration requires a new destination distinct from the source"
        )
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    if source_kind == "database":
        payload, records, retired = _load_database(source)
    elif source_kind == "snapshot":
        payload, records, retired = _load_snapshot(source)
    else:
        raise ValueError("unknown legacy input kind")
    if hashlib.sha256(source.read_bytes()).hexdigest() != before:
        raise ValueError("legacy source changed during inspection")
    parameters, audit, issues, notes = [], [], [], []
    for record in records:
        raw = record["record"]
        p = {"parameter_id": raw["parameter_id"], "name": raw["name"]}
        for key in ("unit", "description", "description_cn"):
            if raw.get(key) is not None:
                # Descriptions are display-only; trim boundary whitespace explicitly in the audit.
                p[key] = raw[key].strip() if key.startswith("description") else raw[key]
        if record["kind"] == "variant":
            p["parent"] = record["parent_id"]
        if record["aliases"]:
            p["aliases"] = record["aliases"]
        fixed, reasons, classification = _fixed_conditions(record)
        if fixed:
            p["fixed_conditions"] = fixed
        if raw.get("unit") is None and record["kind"] == "entry":
            reasons.append(
                "business output unit is undeclared; do not infer a unit from names or samples"
            )
        # Structural translation is a draft, not a review of the full business meaning.
        reasons.append(
            "review the preserved identity, broad versus fixed semantics and informational fields against definition evidence"
        )
        issues.append(
            (
                p["parameter_id"],
                "definition",
                "G17-02",
                "; ".join(reasons),
                "I03; I04 product definition; I06 native facts",
            )
        )
        issues.append(
            (
                p["parameter_id"],
                "grib2",
                "G17-03",
                "exact applicable product/version, native table/producer context and complete translation evidence; legacy triple alone is insufficient",
                "I03 mapping; I04 scope/version; I06 native facts",
            )
        )
        if record["external_names"]:
            issues.append(
                (
                    p["parameter_id"],
                    "cmadaas",
                    "G17-05",
                    "product/version applicability, joint vertical/member keys and original unit facts; parent external code does not prove variant support"
                    + (
                        "; preserve PRE conflict (G17-02/04/06), do not rebind"
                        if record["external_names"].get("cmadaas") == "PRE"
                        else ""
                    ),
                    "I03 mapping/table; I04 product binding; I06 protocol/native facts",
                )
            )
        audit.append(
            (
                p["parameter_id"],
                {
                    **record,
                    "predicate_classification": classification,
                    "informational_fields": [
                        k
                        for k in (
                            "type_of_level",
                            "typeOfLevel",
                            "level",
                            "wgrib2_name",
                            "sort_order",
                            "remark",
                            "updated_at",
                        )
                        if k in raw
                    ],
                    "metadata_normalization": {
                        key: {"before": raw[key], "after": p[key]}
                        for key in ("description", "description_cn")
                        if key in p and raw.get(key) != p[key]
                    },
                    "canonical_definition": p,
                },
            )
        )
        parameters.append(p)
        if record["kind"] == "entry" and (
            raw.get("remark") is not None or raw.get("updated_at") is not None
        ):
            notes.append((p["parameter_id"], raw.get("remark"), raw.get("updated_at")))
    resource = {
        "api_version": "cedarkit.parameters/v1",
        "id": "cedarkit.parameters",
        "version": "1",
        "parameters": parameters,
    }
    # Validate before creating any destination; failed semantics do not leave a partial database.
    from cedarkit_query import validate_resource_set

    quarantined = {}
    while True:
        try:
            validate_resource_set(
                resource, retired_ids=[r["parameter_id"] for r in retired]
            )
            break
        except QueryError as error:
            # Retain failed definitions in the review audit; never export them as valid.
            parts = error.path.split("/")
            if len(parts) < 3 or parts[1] != "parameters":
                raise
            token = parts[2].replace("~1", "/").replace("~0", "~")
            current = {r["parameter_id"]: r for r in resource["parameters"]}
            pid = (
                resource["parameters"][int(token)]["parameter_id"]
                if token.isdigit()
                else token
            )
            if pid not in current:
                raise
            quarantine_now = {pid}
            while True:
                dependents = {
                    key
                    for key, row in current.items()
                    if row.get("parent") in quarantine_now
                    or row.get("fixed_conditions", {})
                    .get("statistics", {})
                    .get("of", {})
                    .get("parameter_id")
                    in quarantine_now
                }
                if dependents <= quarantine_now:
                    break
                quarantine_now |= dependents
            for key in quarantine_now:
                quarantined[key] = {
                    "code": error.code,
                    "path": error.path,
                    "message": error.message,
                    "failed_parameter_id": pid,
                }
            resource["parameters"] = [
                r
                for r in resource["parameters"]
                if r["parameter_id"] not in quarantine_now
            ]
    init_db(destination)
    try:
        with transaction(destination) as conn:
            insert_parameters(conn, resource)
            for backend in ("grib2", "cmadaas"):
                insert_mappings(
                    conn,
                    {
                        "api_version": "cedarkit.mappings/v1",
                        "id": "cedarkit." + backend,
                        "version": "1",
                        "backend": backend,
                        "mappings": [],
                        "tables": [],
                    },
                )
            conn.executemany(
                "INSERT INTO parameter_id_tombstones VALUES (?,?)",
                [(r["parameter_id"], r["retired_reason"]) for r in retired],
            )
            conn.executemany(
                "INSERT INTO parameter_notes VALUES (?,?,?)",
                [r for r in notes if r[0] not in quarantined],
            )
            conn.execute(
                "INSERT INTO migration_sources VALUES (?,?,?)",
                (
                    before,
                    "schema-3"
                    if source_kind == "database"
                    else "reki.parameter-registry/v3",
                    compact(payload),
                ),
            )
            conn.executemany(
                "INSERT INTO migration_records VALUES (?,?,?)",
                [(pid, before, compact(record)) for pid, record in audit],
            )
            conn.executemany(
                "INSERT INTO migration_issues(parameter_id,aspect,gap,missing_input,owner_tasks) VALUES (?,?,?,?,?)",
                issues,
            )
            for pid, reason in quarantined.items():
                conn.execute(
                    "INSERT INTO parameter_reservations VALUES (?,?)",
                    (pid, compact(reason)),
                )
                conn.execute(
                    "UPDATE migration_issues SET missing_input=missing_input || ? WHERE parameter_id=? AND aspect='definition'",
                    (
                        "; shared validation rejected the preserved definition: "
                        + compact(reason),
                        pid,
                    ),
                )
    except BaseException:
        destination.unlink()
        raise
    return migration_report(destination)


def migration_report(db_path):
    conn = connect(db_path, readonly=True)
    try:
        conn.execute("BEGIN")
        p, ms = read_resources(conn)
        index = {r["parameter_id"]: r for r in p["parameters"]}
        rows = []
        for r in conn.execute("SELECT * FROM migration_records ORDER BY parameter_id"):
            old = json.loads(r["legacy_json"])
            rows.append(
                {
                    "parameter_id": r["parameter_id"],
                    "source_sha256": r["source_sha256"],
                    "legacy": old,
                    "current": index.get(r["parameter_id"]),
                    "state": "active_review"
                    if r["parameter_id"] in index
                    else "quarantined",
                    "identity_preserved": (
                        index.get(r["parameter_id"], old["canonical_definition"])[
                            "name"
                        ]
                        == old["record"]["name"]
                        and sorted(
                            index.get(
                                r["parameter_id"], old["canonical_definition"]
                            ).get("aliases", [])
                        )
                        == sorted(old["aliases"])
                    ),
                    "parent_preserved": index.get(
                        r["parameter_id"], old["canonical_definition"]
                    ).get("parent")
                    == old.get("parent_id"),
                }
            )
        pending = pending_issues(conn)
        return {
            "schema_version": 4,
            "scope": "offline parameter authoring migration; not product/backend acceptance",
            "sources": [
                {"sha256": r["sha256"], "format": r["format"]}
                for r in conn.execute(
                    "SELECT sha256,format FROM migration_sources ORDER BY sha256"
                )
            ],
            "counts": {
                "parameters": len(p["parameters"]),
                "preserved_identities": len(rows),
                "quarantined": conn.execute(
                    "SELECT count(*) FROM parameter_reservations"
                ).fetchone()[0],
                "aliases": sum(len(r.get("aliases", [])) for r in p["parameters"]),
                "mappings": sum(len(m["mappings"]) for m in ms),
                "retired_ids": conn.execute(
                    "SELECT count(*) FROM parameter_id_tombstones"
                ).fetchone()[0],
                "unresolved": len(pending),
            },
            "full_migration_complete": not pending,
            "records": rows,
            "unresolved": pending,
            "resolutions": [
                dict(r)
                for r in conn.execute(
                    "SELECT parameter_id,aspect,resolution_json FROM migration_issues WHERE resolution_json IS NOT NULL ORDER BY parameter_id,aspect"
                )
            ],
        }
    finally:
        conn.close()


def report_text(db_path):
    return json_text(migration_report(db_path))


def apply_review(db_path, review):
    """Apply explicit source-bound, evidence-bearing decisions in one transaction.

    This records the reviewer's factual basis; it cannot establish its truth or replace
    independent product acceptance. There is no blanket ignore/accept-all switch.
    """
    if (
        not isinstance(review, dict)
        or set(review) != {"source_sha256", "decisions"}
        or not isinstance(review["source_sha256"], str)
        or not isinstance(review["decisions"], list)
        or not review["decisions"]
    ):
        raise ValueError("review requires source_sha256 and a nonempty decisions list")
    from cedarkit_query import Parameters

    seen = set()
    with transaction(db_path) as conn:
        source = conn.execute(
            "SELECT 1 FROM migration_sources WHERE sha256=?", (review["source_sha256"],)
        ).fetchone()
        if not source:
            raise ValueError("review source digest does not match this migration")
        for decision in review["decisions"]:
            required = {"parameter_id", "aspect", "explanation", "evidence"}
            if (
                not isinstance(decision, dict)
                or not required <= decision.keys()
                or decision.keys() - (required | {"definition", "mapping_ids"})
            ):
                raise ValueError("unknown or missing review decision fields")
            pid, aspect = decision["parameter_id"], decision["aspect"]
            if not isinstance(pid, str) or not isinstance(aspect, str):
                raise ValueError("review identity and aspect must be strings")
            if (pid, aspect) in seen:
                raise ValueError("duplicate review decision")
            seen.add((pid, aspect))
            if (
                not isinstance(decision["explanation"], str)
                or not decision["explanation"].strip()
                or not isinstance(decision["evidence"], list)
                or not decision["evidence"]
                or any(
                    not isinstance(e, str) or not e.strip()
                    for e in decision["evidence"]
                )
            ):
                raise ValueError(
                    "each resolution needs a factual explanation and nonempty evidence references"
                )
            issue = conn.execute(
                "SELECT r.legacy_json FROM migration_issues i JOIN migration_records r USING(parameter_id) WHERE i.parameter_id=? AND i.aspect=? AND i.resolution_json IS NULL AND r.source_sha256=?",
                (pid, aspect, review["source_sha256"]),
            ).fetchone()
            if not issue:
                raise ValueError(
                    "no matching unresolved issue for this source/identity/aspect"
                )
            if aspect == "definition":
                if "definition" not in decision or "mapping_ids" in decision:
                    raise ValueError(
                        "definition review needs a complete local definition, without mapping_ids"
                    )
                definition = decision["definition"]
                if not isinstance(definition, dict):
                    raise ValueError("review definition must be an object")
                p, _ = read_resources(conn)
                old = next(
                    (r for r in p["parameters"] if r["parameter_id"] == pid),
                    json.loads(issue["legacy_json"])["canonical_definition"],
                )
                for key in ("parameter_id", "name"):
                    if definition.get(key) != old.get(key):
                        raise ValueError(
                            "review cannot silently change a stable identity or name"
                        )
                if sorted(definition.get("aliases", [])) != sorted(
                    old.get("aliases", [])
                ):
                    raise ValueError("review must preserve registered aliases")
                exists = any(r["parameter_id"] == pid for r in p["parameters"])
                candidate = {
                    **p,
                    "parameters": [
                        definition if r["parameter_id"] == pid else r
                        for r in p["parameters"]
                    ]
                    + ([] if exists else [definition]),
                }
                Parameters(candidate)
                if exists:
                    conn.execute(
                        "UPDATE parameters SET parent=?,unit=?,description=?,description_cn=?,fixed_json=? WHERE parameter_id=?",
                        (
                            definition.get("parent"),
                            definition.get("unit"),
                            definition.get("description"),
                            definition.get("description_cn"),
                            compact(
                                normalize_fixed(definition.get("fixed_conditions", {}))
                            ),
                            pid,
                        ),
                    )
                else:
                    conn.execute(
                        "DELETE FROM parameter_reservations WHERE parameter_id=?",
                        (pid,),
                    )
                    conn.execute(
                        "INSERT INTO parameters(parameter_id,resource_id,name,parent,unit,description,description_cn,fixed_json) VALUES (?,?,?,?,?,?,?,?)",
                        (
                            pid,
                            p["id"],
                            definition["name"],
                            definition.get("parent"),
                            definition.get("unit"),
                            definition.get("description"),
                            definition.get("description_cn"),
                            compact(
                                normalize_fixed(definition.get("fixed_conditions", {}))
                            ),
                        ),
                    )
                    conn.executemany(
                        "INSERT INTO aliases VALUES (?,?)",
                        [(pid, a) for a in definition.get("aliases", [])],
                    )
            elif aspect in {"grib2", "cmadaas"}:
                if (
                    "definition" in decision
                    or not isinstance(decision.get("mapping_ids"), list)
                    or not decision["mapping_ids"]
                ):
                    raise ValueError(
                        "mapping review needs explicit existing resource/id references"
                    )
                for ref in decision["mapping_ids"]:
                    if not isinstance(ref, dict) or set(ref) != {"resource_id", "id"}:
                        raise ValueError(
                            "mapping reference needs exactly resource_id and id"
                        )
                    row = conn.execute(
                        "SELECT backend,parameter_id FROM mappings WHERE resource_id=? AND id=?",
                        (ref["resource_id"], ref["id"]),
                    ).fetchone()
                    if (
                        row is None
                        or row["backend"] != aspect
                        or row["parameter_id"] != pid
                    ):
                        raise ValueError(
                            "resolution must reference this parameter's actual backend mapping"
                        )
            else:
                raise ValueError("unknown review aspect")
            conn.execute(
                "UPDATE migration_issues SET resolution_json=? WHERE parameter_id=? AND aspect=?",
                (compact(decision), pid, aspect),
            )
    return migration_report(db_path)
