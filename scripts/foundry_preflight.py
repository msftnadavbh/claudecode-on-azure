#!/usr/bin/env python3
"""Read-only preflight for an existing Foundry Anthropic account."""
import argparse
import json
import subprocess
from urllib.parse import urlsplit


class PreflightError(Exception):
    pass


def az(*command):
    try:
        return json.loads(subprocess.run(
            ("az", *command, "--output", "json"), check=True, capture_output=True, text=True
        ).stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        raise PreflightError(f"Azure CLI failed: {error}") from error


def host(url, expected_base=False):
    try:
        parsed = urlsplit(url)
        valid = parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password
        if expected_base:
            valid = valid and parsed.path == "/anthropic" and not parsed.query and not parsed.fragment
        if not valid:
            raise ValueError
        return parsed.hostname.lower()
    except ValueError as error:
        raise PreflightError("--expected-base-url must be an HTTPS URL ending exactly in /anthropic") from error


def mappings(values):
    if len(values) != 3:
        raise PreflightError("exactly three --deployment role=deployment mappings are required")
    result = {}
    for value in values:
        role, separator, deployment = value.partition("=")
        if not separator or not role or not deployment or role in result:
            raise PreflightError("--deployment must be a unique non-empty role=deployment mapping")
        result[role] = deployment
    if set(result) != {"opus", "sonnet", "haiku"}:
        raise PreflightError("--deployment roles must be opus, sonnet, and haiku")
    return result


def state(item):
    return item.get("properties", {}).get("provisioningState", item.get("provisioningState"))


def run(args):
    wanted = mappings(args.deployment)
    expected_host = host(args.expected_base_url, True)
    current = az("account", "show", "--subscription", args.subscription)
    if current.get("id") != args.subscription:
        raise PreflightError(f"Azure subscription context is {current.get('id')!r}, expected {args.subscription!r}")

    account = az("cognitiveservices", "account", "show", "--resource-group", args.resource_group,
                 "--name", args.account, "--subscription", args.subscription)
    if account.get("kind") != "AIServices" or state(account) != "Succeeded":
        raise PreflightError("Foundry account must be an AIServices account with provisioning state Succeeded")
    properties = account.get("properties", {})
    canonical_host = f"{properties.get('customSubDomainName', args.account).lower()}.services.ai.azure.com"
    returned_endpoint = account.get("endpoint") or properties.get("endpoint")
    if expected_host != canonical_host or (returned_endpoint and host(returned_endpoint) != expected_host):
        raise PreflightError("--expected-base-url host is not owned by the specified Foundry account")

    deployments = az("cognitiveservices", "account", "deployment", "list", "--resource-group", args.resource_group,
                     "--name", args.account, "--subscription", args.subscription)
    by_name = {item.get("name"): item for item in deployments}
    report_deployments = {}
    for role, deployment_name in sorted(wanted.items()):
        deployment = by_name.get(deployment_name)
        properties = deployment.get("properties", {}) if deployment else {}
        model = properties.get("model", {})
        if not deployment or state(deployment) != "Succeeded" or model.get("format", "").lower() != "anthropic":
            raise PreflightError(f"deployment {deployment_name!r} for role {role!r} must exist, be Succeeded, and be Anthropic")
        sku = deployment.get("sku", {})
        report_deployments[role] = {
            "capacity": sku.get("capacity"), "deployment": deployment_name, "model": model.get("name"),
            "sku": sku.get("name"), "version": model.get("version"),
        }

    usage = az("cognitiveservices", "usage", "list", "--location", account.get("location", ""),
               "--subscription", args.subscription)
    quota_rows = []
    for row in usage:
        name = row.get("name", {})
        label = (name.get("value") or name.get("localizedValue") or "") if isinstance(name, dict) else str(name)
        if "claude" in label.lower() or "anthropic" in label.lower():
            quota_rows.append({"current_value": row.get("currentValue"), "limit": row.get("limit"),
                               "name": label, "unit": row.get("unit")})
    quota_rows.sort(key=lambda row: row["name"])
    warnings = ["Quota rows are regional usage only; quota scope and deployment headroom are not inferred."]
    if not quota_rows:
        warnings.append("No Claude/Anthropic quota rows were returned; this is a warning, not a quota failure.")
    return {
        "account": {"endpoint_host": expected_host, "kind": account["kind"], "location": account.get("location"),
                    "name": args.account, "provisioning_state": state(account)},
        "deployments": report_deployments, "ok": True, "quota": {"claude_rows": quota_rows},
        "subscription": args.subscription, "warnings": warnings,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--expected-base-url", required=True)
    parser.add_argument("--deployment", action="append", default=[], metavar="ROLE=DEPLOYMENT")
    args = parser.parse_args(argv)
    try:
        result, code = run(args), 0
    except PreflightError as error:
        result, code = {"errors": [str(error)], "ok": False, "warnings": []}, 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
