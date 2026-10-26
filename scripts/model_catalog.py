"""Shared, offline validation for the reviewed Claude deployment catalog."""
import json
from pathlib import Path
import re
import unicodedata


ACCOUNT_ID = re.compile(r"/subscriptions/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/resourceGroups/[^/]+/providers/Microsoft\.CognitiveServices/accounts/[^/]+", re.I)
BASE_URL = re.compile(r"https://[a-z0-9][a-z0-9.-]*\.services\.ai\.azure\.com/anthropic", re.I)
MODEL_FIELDS = {"id", "display_name", "description", "model_name", "model_version", "sku"}


def text(value, label):
    if (not isinstance(value, str) or not value or value != value.strip()
            or any(unicodedata.category(char) in ("Cc", "Cs") for char in value)):
        raise ValueError(f"{label} must be a non-empty, trimmed string without control characters")
    return value


def deployment_id(value):
    text(value, "deployment id")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise ValueError("deployment id must be an Azure deployment name, not an ARM resource ID")
    if not any(marker in value.lower() for marker in ("claude", "anthropic")):
        raise ValueError(f"deployment id {value!r} must contain claude or anthropic for Claude Code discovery")
    return value


def parse_json(raw):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = value
        return result

    def invalid_constant(_):
        raise ValueError("non-finite JSON number")

    try:
        return json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("invalid JSON") from error


def validate_catalog(catalog, *, account_resource_id=None, base_url=None, default_model=None, required_models=()):
    fields = {"schema_version", "account_resource_id", "base_url", "default_model", "models"}
    if not isinstance(catalog, dict) or set(catalog) != fields:
        raise ValueError("model catalog must contain exactly the schema_version:1 catalog fields")
    if type(catalog["schema_version"]) is not int or catalog["schema_version"] != 1:
        raise ValueError("model catalog schema_version must be 1")
    resource_id = text(catalog["account_resource_id"], "model catalog account_resource_id")
    url = text(catalog["base_url"], "model catalog base_url")
    if not ACCOUNT_ID.fullmatch(resource_id) or not BASE_URL.fullmatch(url) or not url.endswith("/anthropic"):
        raise ValueError("model catalog requires an account ARM ID and HTTPS Foundry /anthropic base_url")
    if account_resource_id is not None and resource_id.lower() != account_resource_id.lower():
        raise ValueError("model catalog account_resource_id does not match the primary backend account")
    if base_url is not None and (not BASE_URL.fullmatch(base_url) or not base_url.endswith("/anthropic") or url.lower() != base_url.lower()):
        raise ValueError("model catalog base_url does not match the primary backend URL")
    default = deployment_id(catalog["default_model"])
    if default_model is not None and default != default_model:
        raise ValueError("model catalog default_model must remain the configured Opus pin")
    models = catalog["models"]
    if not isinstance(models, list) or not models:
        raise ValueError("model catalog models must be a non-empty list")
    ids, folded_ids = set(), set()
    for model in models:
        if not isinstance(model, dict) or not MODEL_FIELDS <= set(model) or set(model) - MODEL_FIELDS - {"hosting"}:
            raise ValueError("model catalog entry has missing or unknown fields")
        identifier = deployment_id(model["id"])
        if identifier.lower() in folded_ids:
            raise ValueError(f"duplicate model catalog deployment id {identifier!r}")
        ids.add(identifier)
        folded_ids.add(identifier.lower())
        for field in ("display_name", "description", "model_name"):
            text(model[field], f"model catalog {field}")
        for field in ("model_version", "sku"):
            if model[field] is not None:
                text(model[field], f"model catalog {field}")
        hosting = model.get("hosting")
        if hosting is not None:
            if not isinstance(hosting, dict) or set(hosting) != {"source", "source_account"} or not any(hosting.values()):
                raise ValueError("model catalog hosting must identify source and/or source_account")
            for field, value in hosting.items():
                if value is not None:
                    text(value, f"model catalog hosting.{field}")
    if models[0]["id"] != default:
        raise ValueError("model catalog default_model must be present and first")
    if not set(required_models) <= ids:
        raise ValueError("model catalog must include all existing role pins")
    return catalog


def read_catalog(path, **bindings):
    try:
        catalog = parse_json(Path(path).read_bytes())
    except OSError as error:
        raise ValueError("cannot read model catalog file") from error
    return validate_catalog(catalog, **bindings)
