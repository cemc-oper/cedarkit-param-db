"""Build/capture complete text authoring state, export it, or locate archives."""

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

from cedarkit_param_db import connect, export_mapping_slice
from cedarkit_param_db.authoring import build_authoring_database, write_authoring_source

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "authoring/current.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configuration(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("format") != "cedarkit.authoring/v1":
        raise ValueError("unsupported authoring configuration")
    return value


def export_current(config_path, destination, *, database=None, systems=None):
    """Export one SQLite snapshot; publish the group only if every slice passes."""
    config_path, destination = Path(config_path).resolve(), Path(destination).resolve()
    config = configuration(config_path)
    selected = list(dict.fromkeys(systems or config["exports"]))
    unknown = set(selected) - config["exports"].keys()
    if unknown:
        raise ValueError("unknown export systems: " + ", ".join(sorted(unknown)))
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".cedarkit-export-", dir=destination.parent
    ) as temporary:
        snapshot = Path(temporary) / "authoring.db"
        # SQLite backup includes committed WAL pages and gives every slice the
        # same state without holding the author's database open during export.
        if database is None and "source" in config:
            build_authoring_database(config_path.parent / config["source"], snapshot)
        else:
            # Explicit candidate DBs and historical v1 configurations keep the
            # existing consistent-snapshot path. Never fall back from bad text.
            source = (
                Path(database).resolve()
                if database is not None
                else config_path.parent / config["database"]
            )
            with closing(connect(source, readonly=True)) as reader:
                with closing(sqlite3.connect(snapshot)) as writer:
                    reader.backup(writer)
        group = Path(temporary) / "group"
        group.mkdir()
        for system in selected:
            spec = config["exports"][system]
            export_mapping_slice(
                snapshot,
                group / system,
                spec["mapping_resource_ids"],
                parameter_resource_id=spec["parameter_resource_id"],
                version=spec["parameter_version"],
            )
        group.rename(destination)
    return destination


def archive_index(config_path):
    config_path = Path(config_path).resolve()
    reference = configuration(config_path)["archive"]
    path = (config_path.parent / reference["index"]).resolve()
    if digest(path) != reference["sha256"]:
        raise ValueError("archive index SHA256 mismatch")
    index = json.loads(path.read_text(encoding="utf-8"))
    if index.get("format") != "cedarkit.authoring-archive/v1":
        raise ValueError("unsupported archive index")
    return path, index


def resolve_archived(config_path, reference):
    """Resolve an old workspace path, optionally followed by #sha256=<digest>."""
    index_path, index = archive_index(config_path)
    root = (index_path.parent / index["workspace_root"]).resolve()
    original, _, fragment = reference.partition("#")
    if Path(original).is_absolute():
        original = str(Path(original).relative_to(root))
    for row in index["files"]:
        if row["original_path"] != original:
            continue
        if (
            fragment.startswith("sha256=")
            and fragment[7:].split(";", 1)[0] != row["sha256"]
        ):
            raise ValueError("reference SHA256 does not match archive index")
        destination = root / row["archive_path"]
        if digest(destination) != row["sha256"]:
            raise ValueError("archived evidence SHA256 mismatch: " + original)
        return destination
    raise ValueError("unknown archived evidence: " + original)


def check_archive(config_path):
    _, index = archive_index(config_path)
    for row in index["files"]:
        resolve_archived(config_path, row["original_path"])
    return len(index["files"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="export current finite resources")
    export.add_argument("--out-dir", type=Path, required=True)
    export.add_argument("--db", type=Path, help="explicit temporary candidate database")
    export.add_argument(
        "--system", action="append", help="default: all configured systems"
    )
    build = commands.add_parser("build", help="rebuild a new candidate DB from text")
    build.add_argument("--db", type=Path, required=True)
    capture = commands.add_parser("capture", help="capture a reviewed DB as text")
    capture.add_argument("--db", type=Path, required=True)
    capture.add_argument(
        "--out-dir", type=Path, help="default: replace configured text source"
    )
    resolve = commands.add_parser(
        "resolve", help="verify and locate historical evidence"
    )
    resolve.add_argument("reference")
    commands.add_parser(
        "check-archive", help="verify the immutable archive and its index"
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            print(
                export_current(
                    args.config,
                    args.out_dir,
                    database=args.db,
                    systems=args.system,
                )
            )
        elif args.command == "build":
            config = configuration(args.config)
            print(
                build_authoring_database(args.config.parent / config["source"], args.db)
            )
        elif args.command == "capture":
            config = configuration(args.config)
            destination = args.out_dir or args.config.parent / config["source"]
            print(
                write_authoring_source(
                    args.db, destination, replace=args.out_dir is None
                )
            )
        elif args.command == "resolve":
            print(resolve_archived(args.config, args.reference))
        else:
            print(f"Verified {check_archive(args.config)} archived files")
    except (ValueError, OSError, sqlite3.Error) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
