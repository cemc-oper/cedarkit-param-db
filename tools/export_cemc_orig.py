"""Stage reviewed CEMC ORIG resources and their pinned catalog."""

import argparse
import hashlib
import json
from pathlib import Path

from cedarkit_query import Catalog, Mappings, Parameters, validate_resource_set

AUTHOR = Path(__file__).resolve().parents[1] / "authoring/cemc-orig-batch1.json"


def encode(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--catalog-version", type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--additions", type=Path)
    args = parser.parse_args()
    author = json.loads(AUTHOR.read_bytes())
    if args.additions:
        additions = json.loads(args.additions.read_bytes())
        for system, product in additions["products"].items():
            baseline = author["products"][system]
            for kind in ("parameters", "mappings"):
                resource = baseline[kind]
                extra = product[kind]
                if int(extra["version"]) <= int(resource["version"]):
                    parser.error(f"{system} {kind} additions need a newer version")
                resource["version"] = extra["version"]
                resource[kind].extend(extra[kind])
    catalog = Catalog(json.loads(args.catalog.read_bytes())).to_dict()
    datasets = {row["id"]: row for row in catalog["datasets"]}
    files = {}
    pins_changed = False
    for system, resources in author["products"].items():
        dataset = datasets[resources["dataset"]]
        parameters = Parameters(resources["parameters"]).to_dict()
        mappings = Mappings(resources["mappings"]).to_dict()
        validate_resource_set(parameters, [mappings], catalog, dataset["id"])
        for kind, resource, ref in (
            ("parameters", parameters, dataset["parameter_registry"]),
            ("mappings", mappings, dataset["mappings"]["grib2"]),
        ):
            filename = f"current-{system}-{kind}.json"
            raw = files[filename] = encode(resource)
            digest = hashlib.sha256(raw).hexdigest()
            if ref.get("sha256") not in {None, digest} and int(ref["version"]) >= int(
                resource["version"]
            ):
                parser.error(f"{filename} needs a newer content version")
            pins_changed |= ref.get("sha256") != digest
            ref.update(version=resource["version"], sha256=digest)
    if args.catalog_version is not None or (args.additions and pins_changed):
        if args.catalog_version is None or args.catalog_version <= int(catalog["version"]):
            parser.error("changed resource pins require a newer --catalog-version")
        catalog["version"] = str(args.catalog_version)
    files["catalog-v1.json"] = encode(catalog)
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        parser.error("--output must be empty")
    for name, raw in files.items():
        (args.output / name).write_bytes(raw)


if __name__ == "__main__":
    main()
