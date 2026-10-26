#!/usr/bin/env python3
"""Discover deployed Claude models with read-only Azure CLI calls; never deploy models."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from model_catalog import ACCOUNT_ID, BASE_URL, deployment_id, parse_json, read_catalog, text, validate_catalog


TIMEOUT_SECONDS = 60
IDENTITY_FIELDS = ("model_name", "model_version", "sku", "hosting")
MODEL_METADATA = ("publisher", "format", "capabilities", "finetuneCapabilities", "deprecation",
                  "lifecycleStatus", "replacementConfig", "isDefaultVersion", "maxCapacity",
                  "modelCatalogAssetId", "callRateLimit", "baseModel")


def az(*command):
    try:
        result = subprocess.run(("az", *command, "--output", "json", "--only-show-errors"),
                                check=True, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
        return parse_json(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        # CLI diagnostics can contain account data; never relay stdout/stderr to CI logs.
        raise ValueError("read-only Azure CLI call failed, timed out, or returned invalid JSON") from error


def object_value(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def inventory(value, label, allow_empty=False):
    # Azure CLI materializes all pages; a REST envelope/nextLink is not complete inventory.
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ValueError(f"{label} must be a complete list; unexpected empty or partial inventory")
    for item in value:
        object_value(item, label + " entry")
    return value


def state(item):
    properties = object_value(item.get("properties"), "resource properties")
    value = properties.get("provisioningState", item.get("provisioningState"))
    if item.get("provisioningState", value) != value:
        raise ValueError("conflicting provisioning states")
    return text(value, "provisioningState")


def optional_text(value, label, warnings=None):
    if value is None or isinstance(value, str) and not value.strip():
        if warnings is not None:
            warnings.append(f"{label} is unknown; recorded as null, not inferred from the catalog.")
        return None
    return text(value, label)


def is_anthropic(model):
    text(model.get("name"), "model name")
    markers = [optional_text(model.get(key), f"model {key}") for key in ("format", "publisher")]
    if not any(markers):
        raise ValueError("model must identify its format or publisher; incomplete inventory")
    return any(value and value.lower() == "anthropic" for value in markers)


def identity(model, sku, warnings, label):
    result = {
        "model_name": text(model.get("name"), f"{label} model name"),
        "model_version": optional_text(model.get("version"), f"{label} model version", warnings),
        "sku": optional_text(sku.get("name"), f"{label} SKU", warnings),
    }
    hosting = {key: optional_text(model.get(source), f"{label} {source}")
               for key, source in (("source", "source"), ("source_account", "sourceAccount"))}
    if any(hosting.values()):
        result["hosting"] = hosting
    return result


def same_identity(left, right):
    return all(left.get(key) == right.get(key) for key in IDENTITY_FIELDS)


def metadata(model):
    return {key: model[key] for key in MODEL_METADATA if key in model}


def discover(args, previous):
    expected_id = (f"/subscriptions/{args.subscription}/resourceGroups/{args.resource_group}"
                   f"/providers/Microsoft.CognitiveServices/accounts/{args.account}")
    common = ("--resource-group", args.resource_group, "--name", args.account, "--subscription", args.subscription)
    account = object_value(az("cognitiveservices", "account", "show", *common), "Foundry account")
    if account.get("kind") != "AIServices" or state(account) != "Succeeded":
        raise ValueError("Foundry account must be AIServices with provisioning state Succeeded")
    if text(account.get("id"), "Foundry account id").lower() != expected_id.lower():
        raise ValueError("Foundry account resource ID does not match the explicit target")
    subdomain = text(account["properties"].get("customSubDomainName"), "customSubDomainName")
    if args.expected_base_url.lower() != f"https://{subdomain.lower()}.services.ai.azure.com/anthropic":
        raise ValueError("expected base URL is not owned by the specified Foundry account")
    location = text(account.get("location"), "Foundry account location")
    warnings = ["Last-known-deployed models are not proof of runtime availability; stale entries are not pruned.",
                "Quota is regional usage only, not deployment headroom or permission to deploy."]
    old = {model["id"]: model for model in previous["models"]} if previous else {}
    models, seen, folded_ids, deployed, excluded, stale = {}, set(), set(), [], [], []
    deployments = inventory(az("cognitiveservices", "account", "deployment", "list", *common), "deployments")
    for item in deployments:
        name = text(item.get("name"), "deployment name")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name) or name.lower() in folded_ids:
            raise ValueError("invalid or duplicate deployment ID in inventory")
        seen.add(name)
        folded_ids.add(name.lower())
        if "id" in item and text(item["id"], "deployment ARM ID").lower() != f"{expected_id}/deployments/{name}".lower():
            raise ValueError("deployment ARM ID belongs to a different account or deployment")
        provisioning = state(item)
        properties = item["properties"]
        raw_model = properties.get("model")
        model = object_value(raw_model, "deployment model") if raw_model is not None else None
        if model is None and provisioning == "Succeeded":
            raise ValueError("Succeeded deployment has no model; incomplete inventory")
        sku = object_value({} if item.get("sku") is None else item["sku"], "deployment SKU")
        anthropic = is_anthropic(model) if model is not None else False
        if anthropic:
            current = identity(model, sku, warnings, name)
            if name in old and not same_identity(old[name], current):
                raise ValueError(f"existing deployment ID {name!r} changed model/version/hosting identity; review required")
            if provisioning == "Succeeded":
                deployment_id(name)
                models[name] = old.get(name) or {"id": name, "display_name": name,
                    "description": f"Azure deployment of {current['model_name']}.", **current}
                deployed.append({"id": name, **current, "metadata": metadata(model),
                                 "capacity": sku.get("capacity"), "sku_metadata": sku,
                                 "version_upgrade_option": properties.get("versionUpgradeOption"),
                                 "deployment_state": properties.get("deploymentState")})
        elif name in old and provisioning == "Succeeded":
            raise ValueError(f"existing deployment ID {name!r} is no longer Anthropic; review required")
        if name not in models:
            reason = f"provisioning state {provisioning}" if provisioning != "Succeeded" else "not Anthropic"
            excluded.append({"id": name, "reason": reason})
            if name in old:
                stale.append({"id": name, "reason": reason})
    stale.extend({"id": name, "reason": "missing from deployment inventory"} for name in old.keys() - seen)
    for name, model in old.items():
        models.setdefault(name, model)

    catalog_rows, candidates, usage_names, catalog_keys = [], [], set(), set()
    available = inventory(az("cognitiveservices", "account", "list-models", *common), "account model catalog")
    for model in available:
        skus = inventory([] if model.get("skus") is None else model["skus"], "catalog SKUs", allow_empty=True)
        if not is_anthropic(model):
            continue
        for sku in skus or [{}]:
            current = identity(model, sku, warnings, "catalog model")
            key = json.dumps(current, sort_keys=True)
            if key in catalog_keys:
                raise ValueError("duplicate model/version/SKU/hosting in account model catalog")
            catalog_keys.add(key)
            catalog_rows.append({**current, "metadata": metadata(model), "sku_metadata": sku})
            if not any(same_identity(current, item) for item in deployed):
                candidates.append(current)
            if sku.get("usageName"):
                usage_names.add(text(sku["usageName"], "SKU usageName"))

    quota = []
    usage = inventory(az("cognitiveservices", "usage", "list", "--location", location,
                         "--subscription", args.subscription), "quota", allow_empty=True)
    for row in usage:
        name = row.get("name")
        label = text((name.get("value") or name.get("localizedValue")) if isinstance(name, dict) else name, "quota name")
        if label in usage_names or any(marker in label.lower() for marker in ("claude", "anthropic")):
            quota.append({"name": label, "current_value": row.get("currentValue"),
                          "limit": row.get("limit"), "unit": row.get("unit")})
    if not quota:
        warnings.append("No Claude/Anthropic quota rows were returned.")
    default = previous["default_model"] if previous else args.default_model
    catalog = {"schema_version": 1, "account_resource_id": expected_id,
               "base_url": args.expected_base_url, "default_model": default,
               "models": sorted(models.values(), key=lambda model: (model["id"] != default, model["id"]))}
    validate_catalog(catalog, account_resource_id=expected_id, base_url=args.expected_base_url)
    report = {"schema_version": 1, "account_resource_id": expected_id, "base_url": args.expected_base_url,
              "deployed": sorted(deployed, key=lambda item: item["id"]),
              "catalog": sorted(catalog_rows, key=lambda item: json.dumps(item, sort_keys=True)),
              "catalog_only_candidates": sorted(candidates, key=lambda item: json.dumps(item, sort_keys=True)),
              "excluded_deployments": sorted(excluded, key=lambda item: item["id"]),
              "stale": sorted(stale, key=lambda item: item["id"]),
              "quota": sorted(quota, key=lambda item: item["name"]), "warnings": sorted(set(warnings))}
    return catalog, report


def write_outputs(outputs):
    staged = []
    try:
        for path, content in outputs:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as output:
                staged.append((Path(output.name), path))
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
        # shortcut: replaces are per-file; use a transactional bundle if consumers need pair-atomic publication.
        for temporary, path in staged:
            os.replace(temporary, path)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("subscription", "resource-group", "account", "expected-base-url", "catalog-file", "report-file"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--default-model", help="Required for bootstrap; must match the preserved default thereafter.")
    args = parser.parse_args(argv)
    try:
        expected_id = (f"/subscriptions/{args.subscription}/resourceGroups/{args.resource_group}"
                       f"/providers/Microsoft.CognitiveServices/accounts/{args.account}")
        if not ACCOUNT_ID.fullmatch(text(expected_id, "account resource ID")):
            raise ValueError("supply an explicit subscription UUID, resource group and account name")
        if not BASE_URL.fullmatch(args.expected_base_url) or not args.expected_base_url.endswith("/anthropic"):
            raise ValueError("expected base URL must be HTTPS on *.services.ai.azure.com ending exactly in /anthropic")
        catalog_path, report_path = Path(args.catalog_file), Path(args.report_file)
        if catalog_path.resolve() == report_path.resolve():
            raise ValueError("catalog and report must be different files")
        for path in (catalog_path, report_path):
            if path.is_symlink() or not path.parent.is_dir() or path.exists() and not path.is_file():
                raise ValueError("output paths require existing parent directories and must not be symlinks or directories")
        previous = read_catalog(catalog_path, account_resource_id=expected_id, base_url=args.expected_base_url) if catalog_path.exists() else None
        if previous and args.default_model is not None and args.default_model != previous["default_model"]:
            raise ValueError("--default-model cannot change the preserved default_model")
        if previous is None and args.default_model is None:
            raise ValueError("--default-model is required to bootstrap a catalog")
        deployment_id(previous["default_model"] if previous else args.default_model)
        catalog, report = discover(args, previous)
        content = (json.dumps(catalog, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        report["catalog_sha256"] = sha256(content).hexdigest()
        report_content = (json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        # Stage both files first; a report write failure must not promote a catalog.
        write_outputs(((report_path, report_content), (catalog_path, content)))
        result, code = {"ok": True, "models": len(catalog["models"]), "catalog_sha256": report["catalog_sha256"]}, 0
    except (ValueError, OSError) as error:
        result, code = {"ok": False, "errors": [str(error)]}, 1
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
