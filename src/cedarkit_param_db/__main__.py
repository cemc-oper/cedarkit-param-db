"""命令行入口：python -m cedarkit_param_db <init|import|export|export-json|check>"""

import argparse
import difflib
import sys
from pathlib import Path

from cedarkit_param_db.db import DEFAULT_DB_PATH, init_db
from cedarkit_param_db.exporter import export_file, export_json, export_json_file, export_text
from cedarkit_param_db.importer import import_registry


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="cedarkit_param_db",
        description="GRIB2 要素数据库（param_registry.yaml 的编辑真源）",
    )
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB_PATH,
        help=f"数据库文件路径（默认 {DEFAULT_DB_PATH}）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="按 schema.sql 建库")

    p_import = sub.add_parser("import", help="从注册表 YAML 全量导入（替换现有内容）")
    p_import.add_argument("--yaml", type=Path, required=True, help="param_registry.yaml 路径")

    p_export = sub.add_parser("export", help="从数据库导出注册表 YAML")
    p_export.add_argument("-o", "--out", type=Path, help="输出文件（缺省打印到 stdout）")

    p_export_json = sub.add_parser(
        "export-json", help="从数据库导出 params.json（cedarkit-param-web 的契约文件）"
    )
    p_export_json.add_argument("-o", "--out", type=Path, help="输出文件（缺省打印到 stdout）")

    p_check = sub.add_parser("check", help="drift 检查：数据库导出结果与快照逐字节对比")
    p_check.add_argument("--yaml", type=Path, help="待对比的 param_registry.yaml 路径")
    p_check.add_argument("--json", type=Path, help="待对比的 params.json 路径")

    args = parser.parse_args(argv)

    if args.command == "init":
        path = init_db(args.db)
        print(f"initialized {path}")
        return 0

    if args.command == "import":
        stats = import_registry(args.yaml, args.db)
        print(f"imported from {args.yaml}: "
              f"{stats['entries']} entries, {stats['variants']} variants, {stats['aliases']} aliases")
        return 0

    if args.command == "export":
        if args.out:
            export_file(args.db, args.out)
            print(f"exported {args.db} -> {args.out}")
        else:
            sys.stdout.write(export_text(args.db))
        return 0

    if args.command == "export-json":
        if args.out:
            export_json_file(args.db, args.out)
            print(f"exported {args.db} -> {args.out}")
        else:
            sys.stdout.write(export_json(args.db))
        return 0

    if args.command == "check":
        if not args.yaml and not args.json:
            print("check 需要 --yaml 和/或 --json 参数", file=sys.stderr)
            return 2
        failed = False
        for label, expected, actual_path in (
            ("YAML", export_text(args.db) if args.yaml else None, args.yaml),
            ("JSON", export_json(args.db) if args.json else None, args.json),
        ):
            if actual_path is None:
                continue
            actual = Path(actual_path).read_text(encoding="utf-8")
            if expected == actual:
                print(f"OK: {actual_path} 与数据库导出结果一致")
                continue
            diff = difflib.unified_diff(
                actual.splitlines(keepends=True),
                expected.splitlines(keepends=True),
                fromfile=str(actual_path),
                tofile=f"{args.db} (export)",
            )
            sys.stdout.writelines(diff)
            print(f"\nDRIFT: {actual_path} 与数据库不一致。"
                  f"请从数据库重新导出，或将快照变更导入数据库（import）。")
            failed = True
        return 1 if failed else 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
