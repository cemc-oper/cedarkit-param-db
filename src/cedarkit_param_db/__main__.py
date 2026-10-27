"""Explicit offline migration, schema-4 authoring and atomic bundle exports."""

import argparse
from pathlib import Path
import sqlite3
import sys

from cedarkit_query import load_value

from .db import init_db
from .exporter import export_bundle, export_definitions, json_text
from .importer import import_resources
from .migration import _LegacyLoader, _pairs, apply_review, migrate_v3, migration_report
import json
import yaml


def _write_report(value, path):
    if path is None:
        sys.stdout.write(json_text(value))
    else:
        # Reports also refuse accidental replacement of previous evidence.
        with path.open("x", encoding="utf-8") as stream:
            stream.write(json_text(value))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cedarkit_param_db", description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        required=True,
        help="explicit schema-4 destination or authoring copy; never auto-upgrades the old database",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="create an empty schema-4 database at a new path")
    migrate = commands.add_parser(
        "migrate-v3", help="migrate a fixed legacy source to a new review copy"
    )
    source = migrate.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-db", type=Path)
    source.add_argument("--source-snapshot", type=Path)
    migrate.add_argument("--report", type=Path)
    load = commands.add_parser(
        "import", help="initialize an empty v4 database from new-format resources"
    )
    load.add_argument("--parameters", type=Path, required=True)
    load.add_argument("--mappings", type=Path, action="append", default=[])
    report = commands.add_parser("migration-report")
    report.add_argument("--out", type=Path)
    review = commands.add_parser(
        "review", help="apply explicit source-bound factual resolutions"
    )
    review.add_argument("--decisions", type=Path, required=True)
    export = commands.add_parser(
        "export", help="export a fully resolved resource group to a new directory"
    )
    export.add_argument("--out-dir", type=Path, required=True)
    definitions = commands.add_parser(
        "export-definitions",
        help="export a reviewed definition-only slice; never runtime mappings",
    )
    definitions.add_argument("--out-dir", type=Path, required=True)
    definitions.add_argument("--parameter-id", action="append", required=True)
    definitions.add_argument("--resource-id", required=True)
    definitions.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            init_db(args.db)
        elif args.command == "migrate-v3":
            if args.report and args.report.exists():
                raise FileExistsError(args.report)
            result = migrate_v3(
                args.source_db or args.source_snapshot,
                args.db,
                source_kind="database" if args.source_db else "snapshot",
            )
            _write_report(result, args.report)
        elif args.command == "import":
            import_resources(
                args.db,
                load_value(args.parameters.read_text(encoding="utf-8"), "parameters"),
                [
                    load_value(p.read_text(encoding="utf-8"), "mappings")
                    for p in args.mappings
                ],
            )
        elif args.command == "migration-report":
            _write_report(migration_report(args.db), args.out)
        elif args.command == "review":
            text = args.decisions.read_text(encoding="utf-8")
            document = (
                json.loads(text, object_pairs_hook=_pairs)
                if text.lstrip().startswith("{")
                else yaml.load(text, Loader=_LegacyLoader)
            )
            apply_review(args.db, document)
        elif args.command == "export":
            export_bundle(args.db, args.out_dir)
        elif args.command == "export-definitions":
            export_definitions(
                args.db,
                args.out_dir,
                args.parameter_id,
                resource_id=args.resource_id,
                version=args.version,
            )
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
