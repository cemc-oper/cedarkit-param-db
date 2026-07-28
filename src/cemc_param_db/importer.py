"""param_registry.yaml → SQLite 全量导入。

导入是**全量替换**：清空 entries/variants/aliases 三张表后按 YAML 内容重建。
partial 编辑请直接操作数据库（SQL），再以 export 重新生成快照。
"""

import json
from pathlib import Path

import yaml


def canonicalize_when(when: dict) -> str:
    """把 when 条件规范化为 JSON 文本：键排序 + 紧凑分隔符。

    C4 的唯一索引 (entry_id, when_json) 依赖本函数消除键序与空白差异；
    int/float/str 的原生类型由 JSON 保留，导出时经 json.loads 还原。
    """
    if not isinstance(when, dict) or not when:
        raise ValueError(f"when 必须是非空 map（V2），得到: {when!r}")
    return json.dumps(when, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def import_registry(yaml_path: Path | str, db_path: Path | str) -> dict:
    """把注册表 YAML 全量灌入数据库，返回统计信息。"""
    from cemc_param_db.db import connect

    yaml_path = Path(yaml_path)
    with open(yaml_path, encoding="utf-8") as f:
        # 跳过文件头注释，safe_load 天然忽略注释行
        entries = yaml.safe_load(f)
    if not isinstance(entries, list):
        raise ValueError(f"{yaml_path}: 顶层结构必须是条目列表（F2）")

    conn = connect(db_path)
    stats = {"entries": 0, "variants": 0, "aliases": 0}
    try:
        with conn:
            conn.execute("DELETE FROM aliases")
            conn.execute("DELETE FROM variants")
            conn.execute("DELETE FROM entries")

            for entry in entries:
                key = entry["key"]
                cur = conn.execute(
                    """
                    INSERT INTO entries
                        (discipline, category, number, name, wgrib2_name,
                         unit, description, description_cn, type_of_level, level)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        key["discipline"], key["category"], key["number"],
                        entry["name"], entry.get("wgrib2_name"),
                        entry.get("unit"), entry.get("description"),
                        entry.get("description_cn"), entry.get("typeOfLevel"),
                        entry.get("level"),
                    ),
                )
                entry_id = cur.lastrowid
                stats["entries"] += 1

                for alias in entry.get("aliases", []):
                    conn.execute(
                        "INSERT INTO aliases (owner_type, owner_id, alias) VALUES ('entry', ?, ?)",
                        (entry_id, alias),
                    )
                    stats["aliases"] += 1

                for sort_order, variant in enumerate(entry.get("params", [])):
                    cur = conn.execute(
                        """
                        INSERT INTO variants
                            (entry_id, name, when_json, type_of_level, level,
                             unit, description, description_cn, sort_order)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            entry_id, variant["name"], canonicalize_when(variant["when"]),
                            variant.get("typeOfLevel"), variant.get("level"),
                            variant.get("unit"), variant.get("description"),
                            variant.get("description_cn"), sort_order,
                        ),
                    )
                    variant_id = cur.lastrowid
                    stats["variants"] += 1

                    for alias in variant.get("aliases", []):
                        conn.execute(
                            "INSERT INTO aliases (owner_type, owner_id, alias) VALUES ('variant', ?, ?)",
                            (variant_id, alias),
                        )
                        stats["aliases"] += 1
    finally:
        conn.close()
    return stats
