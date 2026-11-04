"""Export the reviewed GFS definitions against the reki catalog template."""

import argparse
import hashlib
import json
from pathlib import Path

from cedarkit_query import load_value, validate_resource_set


def encode(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--author", type=Path, default=Path(__file__).resolve().parents[1] / "authoring"
    )
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument(
        "--catalog-version", type=int, help="new catalog content revision"
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="new or empty staging directory"
    )
    args = parser.parse_args()
    parameters = load_value(
        (args.author / "gfs-task03-parameters.json").read_text(encoding="utf-8"),
        "parameters",
    ).to_dict()

    mappings = load_value(
        (args.author / "gfs-task03-mappings.json").read_text(encoding="utf-8"),
        "mappings",
    ).to_dict()
    parameters["parameters"].sort(key=lambda row: row["parameter_id"])
    mappings["mappings"].sort(key=lambda row: row["id"])
    catalog = load_value(args.catalog.read_text(encoding="utf-8"), "catalog").to_dict()
    dataset = next(row for row in catalog["datasets"] if row["id"] == "cma_gfs_gmf")

    files = {}
    pins_changed = False
    for reference, resource, name in (
        (dataset["parameter_registry"], parameters, "current-gfs-parameters.json"),
        (dataset["mappings"]["grib2"], mappings, "current-gfs-mappings.json"),
    ):
        raw = files[name] = encode(resource)
        digest = hashlib.sha256(raw).hexdigest()
        if "sha256" in reference and digest != reference["sha256"]:
            old_version = reference.get("version")
            if old_version is not None and int(resource["version"]) <= int(old_version):
                parser.error(f"{name} changed without a newer content revision")
            pins_changed = True
        reference.update(version=resource["version"], sha256=digest)
    if pins_changed or args.catalog_version is not None:
        if args.catalog_version is None or args.catalog_version <= int(
            catalog["version"]
        ):
            parser.error("changed resource pins require a newer --catalog-version")
        catalog["version"] = str(args.catalog_version)
    validate_resource_set(parameters, [mappings], catalog, dataset["id"])
    files["catalog-v1.json"] = encode(catalog)
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        parser.error("--output must be empty")
    for filename, raw in files.items():
        (args.output / filename).write_bytes(raw)


if __name__ == "__main__":
    main()
