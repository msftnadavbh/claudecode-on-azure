#!/usr/bin/env python3
"""Write deployment inputs from the CI environment as JSON tfvars."""
import json
import os
import sys


def required(name):
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"{name} must be set")
    return value


def boolean(name, default="false"):
    value = os.environ.get(name, default).lower()
    if value not in ("true", "false"):
        raise ValueError(f"{name} must be true or false")
    return value == "true"


def integer(name, default=None):
    value = os.environ.get(name, default)
    if value is None or value == "":
        raise ValueError(f"{name} must be set")
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def values():
    profile = required("ENVIRONMENT_PROFILE")
    if profile not in ("poc", "prod"):
        raise ValueError("ENVIRONMENT_PROFILE must be poc or prod")
    foundry_subscription = required("FOUNDRY_SUBSCRIPTION_ID")
    foundry_resource_group = required("FOUNDRY_RESOURCE_GROUP")
    foundry_account = required("FOUNDRY_ACCOUNT_NAME")
    desktop_enabled = boolean("CLAUDE_DESKTOP_DELEGATED_AUTH_ENABLED")
    result = {
        "resource_group_name": required("AZURE_RESOURCE_GROUP"),
        "location": required("AZURE_LOCATION"),
        "secondary_location": os.environ.get("AZURE_SECONDARY_LOCATION", ""),
        "apim_name": required("APIM_NAME"),
        "secondary_apim_name": os.environ.get("APIM_SECONDARY_NAME", ""),
        "deploy_secondary": boolean("DEPLOY_SECONDARY"),
        "publisher_email": required("APIM_PUBLISHER_EMAIL"),
        "publisher_name": required("APIM_PUBLISHER_NAME"),
        "entra_tenant_id": required("ENTRA_TENANT_ID"),
        "expected_audience": required("APIM_EXPECTED_AUDIENCE"),
        "required_app_role": required("APIM_REQUIRED_APP_ROLE"),
        "enable_claude_desktop_delegated_auth": desktop_enabled,
        "foundry_base_url": required("FOUNDRY_BASE_URL"),
        "foundry_subscription_id": foundry_subscription,
        "foundry_resource_id": f"/subscriptions/{foundry_subscription}/resourceGroups/{foundry_resource_group}/providers/Microsoft.CognitiveServices/accounts/{foundry_account}",
        "opus_deployment_name": required("ANTHROPIC_DEFAULT_OPUS_MODEL"),
        "sonnet_deployment_name": required("ANTHROPIC_DEFAULT_SONNET_MODEL"),
        "haiku_deployment_name": required("ANTHROPIC_DEFAULT_HAIKU_MODEL"),
        "per_user_rate_limit": integer("PER_USER_RATE_LIMIT"),
        "per_user_token_limit": integer("PER_USER_TOKEN_LIMIT"),
        "per_user_concurrent_stream_limit": integer("PER_USER_CONCURRENT_STREAM_LIMIT"),
        "aggregate_concurrent_stream_limit": integer("AGGREGATE_CONCURRENT_STREAM_LIMIT"),
        "apim_sku_name": os.environ.get("APIM_SKU", "StandardV2"),
        "default_capacity": integer("APIM_DEFAULT_CAPACITY"),
        "zone_redundant": boolean("APIM_ZONE_REDUNDANT"),
        "networking_profile": os.environ.get("APIM_NETWORKING_PROFILE", "public"),
        "apim_subnet_resource_id": os.environ.get("APIM_SUBNET_RESOURCE_ID", ""),
        "secondary_apim_subnet_resource_id": os.environ.get("APIM_SECONDARY_SUBNET_RESOURCE_ID", ""),
        "observability_enabled": profile == "prod",
        "existing_workspace_resource_id": os.environ.get("LOG_ANALYTICS_WORKSPACE_RESOURCE_ID", ""),
        "existing_app_insights_resource_id": os.environ.get("APPLICATION_INSIGHTS_RESOURCE_ID", ""),
        "action_group_resource_id": os.environ.get("ACTION_GROUP_RESOURCE_ID", ""),
        "traffic_manager_enabled": boolean("TRAFFIC_MANAGER_ENABLED"),
        "traffic_manager_name": os.environ.get("TRAFFIC_MANAGER_NAME", ""),
    }
    if desktop_enabled:
        result["claude_desktop_client_id"] = required("CLAUDE_DESKTOP_CLIENT_ID")
        result["claude_desktop_delegated_scope"] = required("CLAUDE_DESKTOP_DELEGATED_SCOPE")
    return result


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        raise ValueError("usage: generate_tfvars.py OUTPUT")
    with open(argv[0], "w", encoding="utf-8") as output:
        json.dump(values(), output, sort_keys=True)
        output.write("\n")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
