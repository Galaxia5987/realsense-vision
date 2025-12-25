import json
from pydantic import BaseModel

from models.models import RootConfig


from copy import deepcopy

def pydantic_schema_to_bootstrap_json_forms(model: BaseModel) -> dict:
    schema = model.model_json_schema()
    defs = schema.get("$defs", {})

    def resolve_ref(ref: str) -> dict:
        # ref format: #/$defs/Name
        name = ref.split("/")[-1]
        return defs[name]

    def walk(subschema: dict, prefix: str = "") -> list[str]:
        result = []

        # Resolve $ref
        if "$ref" in subschema:
            subschema = resolve_ref(subschema["$ref"])

        schema_type = subschema.get("type")

        if schema_type == "object":
            for prop, prop_schema in subschema.get("properties", {}).items():
                path = f"{prefix}.{prop}" if prefix else prop
                result.extend(walk(prop_schema, path))

        elif schema_type == "array":
            # Arrays are editable as a whole
            result.append(prefix)

        else:
            # Primitive value
            result.append(prefix)

        return result

    root_props = schema.get("properties", {})
    form = []

    for key, prop_schema in root_props.items():
        form.extend(walk(prop_schema, key))

    return {
        "schema": {
            k: v for k, v in schema.items() if k != "$defs"
        },
        "$defs": deepcopy(defs),
        "form": form
    }

# print(RootConfig.model_json_schema())
print(json.dumps(pydantic_schema_to_bootstrap_json_forms(RootConfig)))