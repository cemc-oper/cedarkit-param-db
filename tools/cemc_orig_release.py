"""Apply a reviewed ORIG naming and catalog release to authored resources."""

from copy import deepcopy


def apply_name_review(products, release, review):
    canonical = {row["parameter_id"]: row for row in review["parameters"]}
    support = {row["parameter_id"]: row["name"] for row in review["support_definition_names_for_publication"]}
    versions = release["parameter_versions"]
    changed = set()
    for system, product in products.items():
        resource = product["parameters"]
        mapped = {row["parameter_id"] for row in product["mappings"]["mappings"]}
        for row in resource["parameters"]:
            pid = row["parameter_id"]
            if pid in support:
                if pid in mapped:
                    raise ValueError(f"directly mapped parameter cannot be renamed as a parent: {system}/{pid}")
                if row["name"] != support[pid]:
                    row["name"] = support[pid]
                    changed.add(system)
            if pid in canonical:
                decision = canonical[pid]
                aliases = list(dict.fromkeys([*row.get("aliases", []),
                                             *decision["new_aliases_by_product"].get(system, [])]))
                if row["name"] != decision["name"] or aliases != row.get("aliases", []):
                    row["name"] = decision["name"]
                    if aliases:
                        row["aliases"] = aliases
                    changed.add(system)
    if changed != versions.keys():
        raise ValueError(f"reviewed parameter revisions must name the changed products: {sorted(changed)}")
    for system, version in versions.items():
        resource = products[system]["parameters"]
        if int(version) < int(resource["version"]):
            raise ValueError(f"parameter revision would move backwards: {system}")
        resource["version"] = version


def apply_catalog_provisions(catalog, release):
    datasets = {row["id"]: row for row in catalog["datasets"]}
    for row in release["products"]:
        dataset = datasets[row["dataset"]]
        product, = [p for p in dataset["products"] if (p["id"], p["version"]) == (row["product"], row["product_version"])]
        for provision in row["provides"]:
            if provision not in product["provides"]:
                product["provides"].append(deepcopy(provision))


def apply_binding_candidate(products, catalog, candidate):
    """Overlay reviewed ORIG definitions and bindings on a staged release."""
    datasets = {row["id"]: row for row in catalog["datasets"]}
    if products.keys() != candidate["products"].keys():
        raise ValueError("binding candidate must cover the released ORIG products")
    for system, additions in candidate["products"].items():
        product = products[system]
        parameters, mappings = product["parameters"], product["mappings"]
        for kind, resource in (("parameters", parameters), ("mappings", mappings)):
            version = additions[kind]["version"]
            if int(version) <= int(resource["version"]):
                raise ValueError(f"{system} {kind} candidate needs a newer version")
            resource["version"] = version
        definitions = {row["parameter_id"]: row for row in parameters["parameters"]}
        changed = {
            row["parameter_id"]: deepcopy(row) for row in additions["parameters"]["parameters"]
        }
        if len(changed) != len(additions["parameters"]["parameters"]):
            raise ValueError(f"{system} candidate repeats a parameter definition")
        definitions.update(changed)
        parameters["parameters"] = list(definitions.values())

        dataset = datasets[product["dataset"]]
        (orig,) = [
            row for row in dataset["products"] if (row["id"], row["version"]) == ("orig", "current")
        ]
        scope = {"dataset": dataset["id"], "product": orig["id"], "product_version": orig["version"]}
        rows = additions["mappings"]["mappings"]
        bound = set(additions["provides"])
        if bound != {row["parameter_id"] for row in rows} or any(
            row["applies_to"] != scope for row in rows
        ):
            raise ValueError(f"{system} candidate mappings must match its ORIG product and provides")
        mappings["mappings"].extend(deepcopy(rows))
        orig["provides"] = [
            row for row in orig["provides"] if row["parameter"] not in bound
        ]
        orig["provides"].extend({"parameter": pid} for pid in sorted(bound))
        for kind, ref in (
            ("parameters", dataset["parameter_registry"]),
            ("mappings", dataset["mappings"]["grib2"]),
        ):
            ref.pop("builtin", None)
            ref["path"] = f"current-{system}-{kind}.json"


def apply_mapping_refinement(products, binding, refinement, current_version):
    """Apply reviewed parameter metadata and unit rules for finite ORIG cells."""
    version = refinement["catalog_version"]
    lead_fields = {"forecast_times": "forecastTime", "accumulation_lengths": "lengthOfTimeRange"}
    if (refinement["base_binding"] != binding["id"]
            or refinement.get("base_catalog_version", binding["catalog_version"]) != current_version
            or int(version) <= int(current_version)):
        raise ValueError("mapping refinement needs its base binding and a newer catalog version")
    for system, additions in refinement["products"].items():
        if metadata := additions.get("parameter_metadata"):
            parameters = products[system]["parameters"]
            if int(metadata["version"]) <= int(parameters["version"]):
                raise ValueError(f"{system} parameter refinement needs a newer parameter version")
            definitions = {row["parameter_id"]: row for row in parameters["parameters"]}
            for row in metadata["parameters"]:
                definition = definitions[row["parameter_id"]]
                for key in ("description", "description_cn"):
                    definition[key] = row[key]
                if "unit" in row:
                    definition["unit"] = row["unit"]
                if "statistics" in row:
                    definition["fixed_conditions"]["statistics"] = deepcopy(row["statistics"])
            parameters["version"] = metadata["version"]
        if metadata and "mappings" not in additions:
            continue
        resource = products[system]["mappings"]
        if int(additions["version"]) <= int(resource["version"]):
            raise ValueError(f"{system} mapping refinement needs a newer resource version")
        existing = {row["id"]: row for row in resource["mappings"]}
        for row in additions["mappings"]:
            mapping = deepcopy(existing[row["base_mapping"]])
            scope, native = mapping["applies_to"], mapping["native"]
            if ("time" in scope or mapping["when"] or "unit" in native["translate"]
                    or any(field in native["match"] for field in lead_fields.values())):
                raise ValueError("mapping refinement needs an unbounded original-value branch")
            lead_keys = lead_fields.keys() & row.keys()
            if len(lead_keys) != 1 or not row["steps"] or not row["evidence"]:
                raise ValueError("mapping refinement needs reviewed time, steps, native leads and evidence")
            (lead_key,) = lead_keys
            if not row[lead_key]:
                raise ValueError("mapping refinement needs at least one native lead")
            scope["time"] = row["time"]
            mapping["when"]["step"] = row["steps"]
            native["match"][lead_fields[lead_key]] = row[lead_key]
            if "members" in row:
                members = row["members"]
                if ("perturbationNumber" in native["match"]
                        or native["match"].get("productDefinitionTemplateNumber") not in {1, 11}
                        or not members):
                    raise ValueError("member refinement needs an unbounded ensemble carrier and reviewed members")
                mapping["when"]["member"] = members
                native["match"]["perturbationNumber"] = members
            if row.get("encoded_interval"):
                if lead_key != "accumulation_lengths":
                    raise ValueError("an encoded interval needs reviewed accumulation lengths")
                native["match"]["forecastTime"] = 0
            native["translate"]["unit"] = {"rule": "common.value_unit", "config": {"source_unit": row["source_unit"]}}
            mapping["id"] = row["id"]
            mapping["evidence"].extend(row["evidence"])
            resource["mappings"].append(mapping)
        resource["version"] = additions["version"]
    return version
