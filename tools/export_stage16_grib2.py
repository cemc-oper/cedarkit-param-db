"""Export a reviewed Stage 1.6-08 standalone GRIB2 batch."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from cedarkit_query import Mappings, Parameters, validate_standalone_grib2

from export_browser_snapshot import AUTHOR, encode
from export_cemc_orig_snapshot import GENERIC, PUBLIC, _pin, write_snapshot

IDENTITIES = "stage1.6-identity-registry.json"
BASELINE = "cemc-orig-stage1.6-registry.json"
POLICY = "stage1.6-grib2-review.json"
RULES = "stage1.6-grib2-rules.json"
BATCHES = {"q2m-znt": "2", "gfs-22-45": "3", "full-library": "4"}


def build_snapshot(batch, author=AUTHOR):
    """Return the parameter/mapping pair and its pins without installing it."""
    raw_rules = (author / RULES).read_bytes()
    reviewed = json.loads(raw_rules)
    if reviewed.get("schema_version") != 1 or reviewed.get("task") != "1.6-08":
        raise ValueError("expected the reviewed Stage 1.6-08 rule group")
    documents = {}
    for name in (IDENTITIES, BASELINE, POLICY):
        raw = (author / name).read_bytes()
        if sha256(raw).hexdigest() != reviewed["authoring_sha256"][name]:
            raise ValueError(f"{name} differs from the reviewed rule group's input")
        documents[name] = json.loads(raw)

    version = BATCHES[batch]
    parameters = Parameters({
        "api_version": "cedarkit.parameters/v1",
        "id": "cedarkit.parameters.public",
        "version": "2",
        "parameters": documents[IDENTITIES]["unified_parameters"],
    })
    mapping_rows = list(documents[BASELINE]["generic_grib2_mappings"])
    mapping_rows.extend(
        rule["mapping"] for rule in reviewed["rules"]
        if int(BATCHES[rule["batch"]]) <= int(version)
    )
    mappings = Mappings({
        "api_version": "cedarkit.mappings/v1",
        "id": "cedarkit.grib2.generic",
        "version": version,
        "backend": "grib2",
        "mappings": mapping_rows,
        "tables": [],
    })
    validate_standalone_grib2(parameters, mappings)
    files = {PUBLIC: encode(parameters.to_dict()), GENERIC: encode(mappings.to_dict())}
    files["manifest.json"] = encode({
        "schema_version": 1,
        "task": "1.6-08",
        "batch": batch,
        "authoring": {**reviewed["authoring_sha256"], RULES: sha256(raw_rules).hexdigest()},
        "v57_catalog": documents[IDENTITIES]["catalog"],
        "standalone": {
            "parameter_registry": _pin(PUBLIC, files[PUBLIC]),
            "mappings": {"grib2": _pin(GENERIC, files[GENERIC])},
        },
        "counts": {
            "parameters": len(parameters.to_dict()["parameters"]),
            "mappings": len(mapping_rows),
        },
    })
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", choices=tuple(BATCHES), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        write_snapshot(build_snapshot(args.batch), args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
