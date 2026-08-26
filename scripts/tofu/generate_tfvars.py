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


def attestation_value(name):
    raw = required(name)
    value = raw.strip()
    if raw != value:
        raise ValueError(f"{name} must be trimmed")
    if not value or value.lower() in ("example", "placeholder"):
        raise ValueError(f"{name} must be a non-placeholder value")
    return value


def values():
    profile = required("ENVIRONMENT_PROFILE")
    if profile not in ("poc", "prod"):
        raise ValueError("ENVIRONMENT_PROFILE must be poc or prod")
    mode = os.environ.get("DEPLOYMENT_MODE", "existing")
    if mode not in ("existing", "greenfield"):
        raise ValueError("DEPLOYMENT_MODE must be existing or greenfield")
    target_subscription = required("ARM_SUBSCRIPTION_ID") if mode == "greenfield" else ""
    foundry_subscription = required("FOUNDRY_SUBSCRIPTION_ID") if mode == "existing" else target_subscription
    foundry_resource_group = required("FOUNDRY_RESOURCE_GROUP") if mode == "existing" else required("AZURE_RESOURCE_GROUP")
    foundry_account = required("FOUNDRY_ACCOUNT_NAME")
    secondary_foundry_base_url = os.environ.get("SECONDARY_FOUNDRY_BASE_URL", "")
    secondary_foundry_subscription = os.environ.get("SECONDARY_FOUNDRY_SUBSCRIPTION_ID", "")
    secondary_foundry_resource_group = os.environ.get("SECONDARY_FOUNDRY_RESOURCE_GROUP", "")
    secondary_foundry_account = os.environ.get("SECONDARY_FOUNDRY_ACCOUNT_NAME", "")
    if mode == "greenfield" and any((secondary_foundry_base_url, secondary_foundry_subscription, secondary_foundry_resource_group, secondary_foundry_account)):
        raise ValueError("greenfield does not support secondary Foundry fields")
    if secondary_foundry_base_url:
        for name, value in (
            ("SECONDARY_FOUNDRY_SUBSCRIPTION_ID", secondary_foundry_subscription),
            ("SECONDARY_FOUNDRY_RESOURCE_GROUP", secondary_foundry_resource_group),
            ("SECONDARY_FOUNDRY_ACCOUNT_NAME", secondary_foundry_account),
        ):
            if not value:
                raise ValueError(f"{name} must be set when SECONDARY_FOUNDRY_BASE_URL is set")
    if mode == "greenfield" and os.environ.get("APIM_NETWORKING_PROFILE", "public") != "public":
        raise ValueError("greenfield supports public networking only")
    desktop_enabled = boolean("CLAUDE_DESKTOP_DELEGATED_AUTH_ENABLED")
    result = {
        "deployment_mode": mode,
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
        "foundry_base_url": (f"https://{foundry_account}.services.ai.azure.com/anthropic" if mode == "greenfield" else required("FOUNDRY_BASE_URL")),
        "foundry_subscription_id": foundry_subscription,
        "foundry_account_name": foundry_account,
        "foundry_resource_id": f"/subscriptions/{foundry_subscription}/resourceGroups/{foundry_resource_group}/providers/Microsoft.CognitiveServices/accounts/{foundry_account}",
        "secondary_foundry_base_url": secondary_foundry_base_url,
        "secondary_foundry_resource_id": (
            f"/subscriptions/{secondary_foundry_subscription}/resourceGroups/{secondary_foundry_resource_group}/providers/Microsoft.CognitiveServices/accounts/{secondary_foundry_account}"
            if secondary_foundry_base_url else ""
        ),
        "opus_deployment_name": "" if mode == "greenfield" else required("ANTHROPIC_DEFAULT_OPUS_MODEL"),
        "sonnet_deployment_name": "" if mode == "greenfield" else required("ANTHROPIC_DEFAULT_SONNET_MODEL"),
        "haiku_deployment_name": "" if mode == "greenfield" else required("ANTHROPIC_DEFAULT_HAIKU_MODEL"),
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
    if mode == "greenfield":
        if not boolean("ACCEPT_ANTHROPIC_MARKETPLACE_TERMS"):
            raise ValueError("ACCEPT_ANTHROPIC_MARKETPLACE_TERMS must be true for greenfield")
        sku = required("CLAUDE_MODEL_SKU").strip()
        if sku not in ("GlobalStandard", "DataZoneStandard"):
            raise ValueError("CLAUDE_MODEL_SKU must be GlobalStandard or DataZoneStandard")
        capacity = integer("CLAUDE_MODEL_CAPACITY")
        if capacity <= 0:
            raise ValueError("CLAUDE_MODEL_CAPACITY must be a positive integer")
        country = attestation_value("CLAUDE_COUNTRY_CODE")
        if len(country) != 2 or not country.isalpha() or country != country.upper():
            raise ValueError("CLAUDE_COUNTRY_CODE must be an uppercase two-letter country code")
        industry = attestation_value("CLAUDE_INDUSTRY")
        if industry not in ("education", "finance", "government", "healthcare", "manufacturing", "media", "other", "retail", "technology"):
            raise ValueError("CLAUDE_INDUSTRY must be education, finance, government, healthcare, manufacturing, media, other, retail, or technology")
        result.update({
            "foundry_project_name": required("FOUNDRY_PROJECT_NAME"),
            "foundry_location": required("FOUNDRY_LOCATION"),
            "claude_model_deployment_name": required("CLAUDE_MODEL_DEPLOYMENT_NAME"),
            "claude_model_name": required("CLAUDE_MODEL_NAME"),
            "claude_model_version": required("CLAUDE_MODEL_VERSION"),
            "claude_model_sku": sku,
            "claude_model_capacity": capacity,
            "claude_organization_name": attestation_value("CLAUDE_ORGANIZATION_NAME"),
            "claude_country_code": country,
            "claude_industry": industry,
            "accept_anthropic_marketplace_terms": True,
        })
        result["foundry_resource_id"] = f"/subscriptions/{target_subscription}/resourceGroups/{result['resource_group_name']}/providers/Microsoft.CognitiveServices/accounts/{foundry_account}"
        result["secondary_foundry_base_url"] = ""
        result["secondary_foundry_resource_id"] = ""
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
