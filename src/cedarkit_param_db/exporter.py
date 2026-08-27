"""SQLite → param_registry.yaml 确定性导出。

导出结果逐字节确定：条目按 (discipline, category, number) 排序（F3），
变体按 sort_order（spec §5 并列裁决依赖），字段顺序固定，浮点层次值
为整数时写回整数形式（与历史快照格式一致）。
"""

import json
from pathlib import Path

import yaml

#: YAML 快照头部注释（导出时写入）
HEADER = (
    "# GRIB2 要素注册表。约束规范见同目录 param_registry_spec.md，请勿违反编号规则。\n"
    "# 本文件由 cedarkit-param-db 从要素数据库导出（python -m cedarkit_param_db export），请勿手工编辑。\n"
)

#: when 键在 YAML 中的书写顺序（spec §3.4 白名单顺序；when_json 按键名排序存储，
#: 导出时恢复为本语义顺序以保证 diff 可读）
WHEN_KEY_ORDER = (
    "first_level_type",
    "first_level",
    "second_level_type",
    "second_level",
    "stepType",
    "time_range_hours",
)

_ENTRY_FIELDS = (
    "parameter_id", "key", "name", "aliases", "wgrib2_name", "unit", "description",
    "description_cn", "typeOfLevel", "level", "params",
)

_VARIANT_FIELDS = (
    "parameter_id", "name", "aliases", "when", "typeOfLevel", "level",
    "unit", "description", "description_cn",
)

#: params.json 的 schema 版本（cedarkit-param-web 构建时校验兼容性）
JSON_SCHEMA_VERSION = 2
PARAMETER_REGISTRY_API_VERSION = "reki.parameter-registry/v2"

#: params.json 的字段顺序（规范化契约的一部分，保证 diff 可读）
_JSON_ENTRY_FIELDS = (
    "parameter_id", "key", "name", "aliases", "wgrib2_name", "unit", "description",
    "description_cn", "typeOfLevel", "level", "remark", "updated_at", "variants",
)


def _norm_number(value):
    """REAL 列读回的整数值写回 int（level: 2 而非 2.0）。"""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _order_fields(data: dict, order: tuple) -> dict:
    return {field: data[field] for field in order if field in data}


def export_entries(db_path: Path | str) -> list:
    """从数据库读出条目列表（结构等同 param_registry.yaml 的 safe_load 结果）。"""
    from cedarkit_param_db.db import connect

    conn = connect(db_path)
    try:
        entries = []
        entry_rows = conn.execute(
            "SELECT * FROM entries ORDER BY discipline, category, number"
        ).fetchall()
        for row in entry_rows:
            entry = {
                "parameter_id": row["parameter_id"],
                "key": {
                    "discipline": row["discipline"],
                    "category": row["category"],
                    "number": row["number"],
                },
                "name": row["name"],
            }
            aliases = _aliases_of(conn, "entry", row["id"])
            if aliases:
                entry["aliases"] = aliases
            for col, field in (
                ("wgrib2_name", "wgrib2_name"),
                ("unit", "unit"),
                ("description", "description"),
                ("description_cn", "description_cn"),
                ("type_of_level", "typeOfLevel"),
            ):
                if row[col] is not None:
                    entry[field] = row[col]
            if row["level"] is not None:
                entry["level"] = _norm_number(row["level"])

            variants = []
            variant_rows = conn.execute(
                "SELECT * FROM variants WHERE entry_id = ? ORDER BY sort_order",
                (row["id"],),
            ).fetchall()
            for v in variant_rows:
                variant = {"parameter_id": v["parameter_id"], "name": v["name"]}
                v_aliases = _aliases_of(conn, "variant", v["id"])
                if v_aliases:
                    variant["aliases"] = v_aliases
                variant["when"] = _decode_when(v["when_json"])
                if v["type_of_level"] is not None:
                    variant["typeOfLevel"] = v["type_of_level"]
                if v["level"] is not None:
                    variant["level"] = _norm_number(v["level"])
                # 变体级元数据：NULL 表示继承条目级，导出时省略
                for col in ("unit", "description", "description_cn"):
                    if v[col] is not None:
                        variant[col] = v[col]
                variants.append(_order_fields(variant, _VARIANT_FIELDS))

            if variants:
                entry["params"] = variants
            entries.append(_order_fields(entry, _ENTRY_FIELDS))
        return entries
    finally:
        conn.close()


def _aliases_of(conn, owner_type: str, owner_id: int) -> list:
    rows = conn.execute(
        "SELECT alias FROM aliases WHERE owner_type = ? AND owner_id = ? ORDER BY id",
        (owner_type, owner_id),
    ).fetchall()
    return [r["alias"] for r in rows]


def _decode_when(when_json: str) -> dict:
    when = json.loads(when_json)
    ordered = {k: when[k] for k in WHEN_KEY_ORDER if k in when}
    for k in when:  # 白名单外的键（规范升级后）排在最后，不丢失
        if k not in ordered:
            ordered[k] = when[k]
    return ordered


def export_document(db_path: Path | str) -> dict:
    """Export the versioned reki parameter-registry v2 document."""
    return {"api_version": PARAMETER_REGISTRY_API_VERSION, "entries": export_entries(db_path)}


def export_text(db_path: Path | str) -> str:
    """导出完整的 YAML 文本（含头部注释）。"""
    entries = export_document(db_path)
    body = yaml.safe_dump(
        entries,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=120,
    )
    return HEADER + body


def export_file(db_path: Path | str, out_path: Path | str) -> Path:
    out_path = Path(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(export_text(db_path))
    return out_path


def export_full_entries(db_path: Path | str) -> list:
    """导出完整要素列表（params.json 契约的数据段）。

    与 export_entries()（YAML 快照）的差异：包含数据库独有字段
    remark/updated_at，变体列表键名为 variants（与数据库表名一致）。
    只含规范化原始数据，不含任何展示层预加工字段。
    """
    from cedarkit_param_db.db import connect

    conn = connect(db_path)
    try:
        entries = []
        entry_rows = conn.execute(
            "SELECT * FROM entries ORDER BY discipline, category, number"
        ).fetchall()
        for row in entry_rows:
            entry = {
                "parameter_id": row["parameter_id"],
                "key": {
                    "discipline": row["discipline"],
                    "category": row["category"],
                    "number": row["number"],
                },
                "name": row["name"],
            }
            aliases = _aliases_of(conn, "entry", row["id"])
            if aliases:
                entry["aliases"] = aliases
            for col, field in (
                ("wgrib2_name", "wgrib2_name"),
                ("unit", "unit"),
                ("description", "description"),
                ("description_cn", "description_cn"),
                ("type_of_level", "typeOfLevel"),
            ):
                if row[col] is not None:
                    entry[field] = row[col]
            if row["level"] is not None:
                entry["level"] = _norm_number(row["level"])
            # 数据库独有字段（不进 YAML 快照）
            if row["remark"] is not None:
                entry["remark"] = row["remark"]
            entry["updated_at"] = row["updated_at"]

            variants = []
            variant_rows = conn.execute(
                "SELECT * FROM variants WHERE entry_id = ? ORDER BY sort_order",
                (row["id"],),
            ).fetchall()
            for v in variant_rows:
                variant = {"parameter_id": v["parameter_id"], "name": v["name"]}
                v_aliases = _aliases_of(conn, "variant", v["id"])
                if v_aliases:
                    variant["aliases"] = v_aliases
                variant["when"] = _decode_when(v["when_json"])
                if v["type_of_level"] is not None:
                    variant["typeOfLevel"] = v["type_of_level"]
                if v["level"] is not None:
                    variant["level"] = _norm_number(v["level"])
                for col in ("unit", "description", "description_cn"):
                    if v[col] is not None:
                        variant[col] = v[col]
                variants.append(_order_fields(variant, _VARIANT_FIELDS))

            if variants:
                entry["variants"] = variants
            entries.append(_order_fields(entry, _JSON_ENTRY_FIELDS))
        return entries
    finally:
        conn.close()


def export_json(db_path: Path | str) -> str:
    """导出 params.json 文本（确定性：字段顺序、缩进、末尾换行固定）。

    这是 cedarkit-param-db 与 cedarkit-param-web 之间的契约文件：
    结构变更必须递增 meta.schema_version。
    """
    entries = export_full_entries(db_path)
    doc = {
        "meta": {
            "schema_version": JSON_SCHEMA_VERSION,
            "generated_by": "cedarkit-param-db",
            "stats": {
                "entries": len(entries),
                "variants": sum(len(e.get("variants", [])) for e in entries),
                "aliases": sum(
                    len(e.get("aliases", []))
                    + sum(len(v.get("aliases", [])) for v in e.get("variants", []))
                    for e in entries
                ),
                "parameter_ids": len(entries) + sum(len(e.get("variants", [])) for e in entries),
            },
        },
        "entries": entries,
    }
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def export_json_file(db_path: Path | str, out_path: Path | str) -> Path:
    out_path = Path(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(export_json(db_path))
    return out_path
