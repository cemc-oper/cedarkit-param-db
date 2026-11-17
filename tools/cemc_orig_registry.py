"""Project product definitions from the reviewed CEMC ORIG authoring registry."""

from copy import deepcopy


def product_parameter_definitions(registry, dataset):
    """Return the product's parameters in publication order."""
    public = {row["parameter_id"]: row for row in registry["public_parameters"]}
    definitions = []
    for row in registry["products"][dataset]["parameters"]:
        if "definition" in row:
            if row.keys() != {"definition"}:
                raise ValueError("a scoped definition cannot also inherit a public definition")
            definitions.append(deepcopy(row["definition"]))
            continue

        parameter_id = row["public_parameter_id"]
        fields = row.get("set", {})
        removed = set(row.get("remove", ()))
        if "parameter_id" in fields or "parameter_id" in removed:
            raise ValueError(f"product projection cannot replace the ID of {parameter_id}")
        if removed & fields.keys():
            raise ValueError(f"product projection both sets and removes fields for {parameter_id}")
        definition = deepcopy(public[parameter_id])
        for field in removed:
            del definition[field]
        definition.update(deepcopy(fields))
        definitions.append(definition)
    return definitions
