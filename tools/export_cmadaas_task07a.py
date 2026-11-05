"""Export an explicitly selected offline CMADaaS catalog and its pinned resources."""

import argparse
import hashlib
import json
from pathlib import Path

from cedarkit_query import Catalog, Mappings, Parameters, validate_resource_set

AUTHOR = Path(__file__).resolve().parents[1] / "authoring/cmadaas-task07a.json"
CATALOG_ID = "reki.cmadaas-task07a"


def encode(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--catalog-version", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    author = json.loads(AUTHOR.read_bytes())
    parameters = Parameters(author["parameters"]).to_dict()
    mappings = Mappings(author["mappings"]).to_dict()
    original = Catalog(json.loads(args.catalog.read_bytes())).to_dict()
    datasets = {row["id"]: row for row in original["datasets"]}
    files = {
        "cmadaas-task07a-parameters.json": encode(parameters),
        "cmadaas-task07a-mappings.json": encode(mappings),
    }
    replacing = original["id"] == CATALOG_ID
    catalog = {
        "api_version": "cedarkit.catalog/v1",
        "id": CATALOG_ID,
        "version": original["version"] if replacing else "1",
        "datasets": [],
    }
    for service in author["services"]:
        dataset = json.loads(json.dumps(datasets[service["id"]]))
        for kind, resource in (("parameters", parameters), ("mappings", mappings)):
            raw = files[f"cmadaas-task07a-{kind}.json"]
            digest = hashlib.sha256(raw).hexdigest()
            ref = (
                dataset.get("parameter_registry")
                if kind == "parameters"
                else dataset.get("mappings", {}).get("cmadaas")
            )
            if (
                ref
                and ref.get("sha256") != digest
                and int(ref["version"]) >= int(resource["version"])
            ):
                parser.error(f"{kind} needs a newer content version")
            reference = {
                "builtin": f"reki.{kind}.cmadaas.task07a",
                "version": resource["version"],
                "sha256": digest,
            }
            if kind == "parameters":
                dataset["parameter_registry"] = reference
            else:
                dataset["mappings"] = {"cmadaas": reference}
        dataset.update(service)
        catalog["datasets"].append(dataset)
    for dataset in catalog["datasets"]:
        validate_resource_set(parameters, [mappings], catalog, dataset["id"])
    if args.catalog_version is not None:
        if args.catalog_version < 1 or (
            replacing and args.catalog_version <= int(original["version"])
        ):
            parser.error("--catalog-version must be newer")
        catalog["version"] = str(args.catalog_version)
    elif replacing and catalog != original:
        parser.error("changed catalog requires a newer --catalog-version")
    files["cmadaas-task07a-catalog.json"] = encode(Catalog(catalog).to_dict())
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        parser.error("--output must be empty")
    for name, raw in files.items():
        (args.output / name).write_bytes(raw)


if __name__ == "__main__":
    main()
