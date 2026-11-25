"""Export short names from the pinned wgrib2 source for its NCEP convention."""

import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re

POLICY = Path(__file__).resolve().parents[1] / "authoring/wgrib2-names.json"
FORMAT = "cedarkit.wgrib2-names/v1"
COLUMNS = (
    "discipline",
    "parameterCategory",
    "parameterNumber",
    "masterTableMinimum",
    "masterTableMaximum",
    "centre",
    "localTablesVersion",
    "shortName",
)
QUOTED = r'"(?:[^"\\]|\\.)*"'
ROW = re.compile(
    rf'\s*\{{\s*((?:-?\d+\s*,\s*){{8}})"([^"\\]+)"'
    rf'\s*,\s*{QUOTED}\s*,\s*{QUOTED}\s*\}}\s*,?\s*(?://.*)?'
)


def read_rows(content, filename):
    # Preserve line numbers when removing block comments, including disabled rows.
    text = re.sub(
        r"/\*.*?\*/", lambda match: "\n" * match[0].count("\n"), content, flags=re.S
    )
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("//"):
            continue
        match = ROW.fullmatch(line)
        if match is None:
            raise ValueError(f"{filename}:{line_number}: invalid GRIB table row")
        discipline, _, low, high, centre, local, category, number = map(
            int, match[1].split(",")[:-1]
        )
        yield (discipline, category, number, low, high, centre, local, match[2])


def _master_versions(row):
    # A message with master table 255 takes the local lookup path.
    return range(row[3], min(row[4], 254) + 1)


def _unshadowed_tigge(ncep, tigge):
    # The default invocation consults TIGGE only after a failed NCEP lookup
    # and only for TIGGE production statuses. Normally these rows are covered
    # by the NCEP table. A shadowed name must not claim an ecCodes shortName.
    covered = defaultdict(set)
    for row in ncep:
        covered[row[:3]].update(_master_versions(row))
    return [
        row for row in tigge
        if not covered[row[:3]].issuperset(_master_versions(row))
    ]


def build_snapshot(source, policy=POLICY):
    authoring = json.loads(policy.read_text(encoding="utf-8"))
    upstream = authoring["upstream"]
    files = {}
    for filename, expected in upstream["sha256"].items():
        content = (source / filename).read_bytes()
        if sha256(content).hexdigest() != expected:
            raise ValueError(f"{filename} differs from pinned wgrib2 {upstream['tag']}")
        files[filename] = content

    tables = {
        name: [
            row
            for filename in filenames
            for row in read_rows(files[filename].decode("utf-8"), filename)
        ]
        for name, filenames in authoring["tables"].items()
    }
    # For the NCEP convention, these arrays are only searched for messages
    # belonging to their centres in the local lookup path.
    tables["ecmwf_local"] = [row for row in tables["ecmwf_local"] if row[5] == 98]
    tables["dwd_local"] = [row for row in tables["dwd_local"] if row[5] in (78, 79)]
    tables["tigge"] = _unshadowed_tigge(tables["ncep"], tables["tigge"])
    return {
        "api_version": FORMAT,
        "version": authoring["version"],
        "upstream": upstream,
        "short_name_case": "upper",
        "columns": COLUMNS,
        "tables": {
            name: [(*row[:-1], row[-1].upper()) for row in rows]
            for name, rows in tables.items()
        },
    }


def encode_snapshot(snapshot):
    # Put each C initializer's numeric keys and short name on one line.
    header = {key: value for key, value in snapshot.items() if key != "tables"}
    groups = []
    for name, rows in snapshot["tables"].items():
        lines = ",\n".join(f"      {json.dumps(row, ensure_ascii=False)}" for row in rows)
        group = f"[\n{lines}\n    ]" if rows else "[]"
        groups.append(f"    {json.dumps(name)}: {group}")
    return (
        json.dumps(header, indent=2, ensure_ascii=False).removesuffix("\n}")
        + ',\n  "tables": {\n'
        + ",\n".join(groups)
        + "\n  }\n}\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="wgrib2 source root")
    parser.add_argument("--output", type=Path, required=True, help="new JSON file")
    args = parser.parse_args()
    try:
        snapshot = encode_snapshot(build_snapshot(args.source))
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(snapshot)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
