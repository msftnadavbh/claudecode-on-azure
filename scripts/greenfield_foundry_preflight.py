#!/usr/bin/env python3
"""Read-only preflight for a new greenfield Foundry Anthropic deployment."""
import argparse
import json
import subprocess


class PreflightError(Exception):
    pass


def az(*command):
    try:
        return json.loads(subprocess.run(
            ("az", *command, "--output", "json"), check=True, capture_output=True, text=True
        ).stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        raise PreflightError(f"Azure CLI failed: {error}") from error


def run(args):
    current = az("account", "show", "--subscription", args.subscription)
    if current.get("id") != args.subscription:
        raise PreflightError(f"Azure subscription context is {current.get('id')!r}, expected {args.subscription!r}")
    if not args.allow_existing_resource_group and az("group", "exists", "--name", args.resource_group, "--subscription", args.subscription):
        raise PreflightError("greenfield resource group already exists")

    catalog = az("cognitiveservices", "model", "list", "--location", args.location, "--subscription", args.subscription)
    matches = []
    for item in catalog if isinstance(catalog, list) else []:
        model = item.get("model", {}) if isinstance(item, dict) else {}
        skus = item.get("model", {}).get("skus", []) if isinstance(item, dict) else []
        if (not isinstance(item, dict) or item.get("kind") != "AIServices" or not isinstance(model, dict) or
                model.get("format") != "Anthropic" or
                model.get("name") != args.model or model.get("version") != args.version or
                not isinstance(skus, list)):
            continue
        matches.extend(sku for sku in skus if isinstance(sku, dict) and sku.get("name") == args.sku)
    if not matches:
        raise PreflightError("exact AIServices Anthropic Hosted-on-Azure model/version/SKU is unavailable")
    names = {sku.get("usageName") for sku in matches if sku.get("usageName")}
    if not names:
        raise PreflightError("catalog SKU has no usageName; quota cannot be determined safely")
    if len(names) != 1:
        raise PreflightError("catalog returned ambiguous usageName values for the selected SKU")
    name = names.pop()
    usage = az("cognitiveservices", "usage", "list", "--location", args.location, "--subscription", args.subscription)
    row = next((row for row in usage if ((row.get("name", {}).get("value") if isinstance(row.get("name"), dict) else row.get("name")) == name)), None)
    if not row:
        raise PreflightError(f"quota row {name!r} was not returned")
    available = row.get("limit", 0) - row.get("currentValue", 0)
    if available < args.capacity:
        raise PreflightError(f"quota {name!r} has {available} available, below requested capacity {args.capacity}")
    return {"model": {"capacity": args.capacity, "name": args.model, "sku": args.sku, "usage_name": name, "version": args.version}, "ok": True, "resource_group": args.resource_group, "subscription": args.subscription}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--sku", required=True, choices=("GlobalStandard", "DataZoneStandard"))
    parser.add_argument("--capacity", required=True, type=int)
    parser.add_argument("--allow-existing-resource-group", action="store_true",
                        help="Allow the resource group only after its greenfield address is confirmed in state.")
    args = parser.parse_args(argv)
    try:
        if args.capacity <= 0:
            raise PreflightError("--capacity must be positive")
        result, code = run(args), 0
    except PreflightError as error:
        result, code = {"errors": [str(error)], "ok": False, "warnings": []}, 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
