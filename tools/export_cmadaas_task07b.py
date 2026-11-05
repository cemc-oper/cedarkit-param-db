"""Export the reviewed live CMADaaS bindings into the default reki catalog."""

import argparse
import hashlib
import json
from pathlib import Path

from cedarkit_query import Catalog, Mappings, Parameters, validate_resource_set

AUTHOR = Path(__file__).resolve().parents[1] / "authoring/cmadaas-task07b.json"


def encode(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--author", type=Path, default=AUTHOR)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--catalog-version", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    author = json.loads(args.author.read_bytes())
    parameters = Parameters(author["parameters"]).to_dict()
    mappings = Mappings(author["mappings"]).to_dict()
    original = Catalog(json.loads(args.catalog.read_bytes())).to_dict()
    catalog = json.loads(json.dumps(original))
    datasets = {row["id"]: row for row in catalog["datasets"]}
    files = {
        f"current-cmadaas-{kind}.json": encode(resource)
        for kind, resource in (("parameters", parameters), ("mappings", mappings))
    }
    for service in author["services"]:
        dataset = datasets[service["id"]]
        for kind, resource in (("parameters", parameters), ("mappings", mappings)):
            digest = hashlib.sha256(files[f"current-cmadaas-{kind}.json"]).hexdigest()
            builtin = f"reki.{kind}.cmadaas.current"
            ref = (
                dataset.get("parameter_registry")
                if kind == "parameters"
                else dataset.get("mappings", {}).get("cmadaas")
            )
            if (
                ref
                and ref.get("builtin") == builtin
                and ref.get("sha256") != digest
                and int(ref["version"]) >= int(resource["version"])
            ):
                parser.error(f"{kind} needs a newer content version")
            reference = {
                "builtin": builtin,
                "version": resource["version"],
                "sha256": digest,
            }
            if kind == "parameters":
                dataset["parameter_registry"] = reference
            else:
                dataset["mappings"] = {"cmadaas": reference}
        dataset.update(service)
    for service in author["services"]:
        validate_resource_set(parameters, [mappings], catalog, service["id"])
    if args.catalog_version is not None:
        if args.catalog_version <= int(original["version"]):
            parser.error("--catalog-version must be newer")
        catalog["version"] = str(args.catalog_version)
    elif catalog != original:
        parser.error("changed catalog requires a newer --catalog-version")
    files["catalog-v1.json"] = encode(Catalog(catalog).to_dict())
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        parser.error("--output must be empty")
    for name, raw in files.items():
        (args.output / name).write_bytes(raw)


if __name__ == "__main__":
    main()
