#!/usr/bin/env python3
"""Generate (but never execute) OpenTofu imports for the gateway topology."""
import argparse
import json
import re
import shlex
import sys
import uuid
from pathlib import Path


class ManifestError(Exception):
    pass


UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
RESOURCE_ID = re.compile(r"^/subscriptions/[^/]+/resourceGroups/[^/]+/providers/[^/]+(?:/[^/]+/[^/]+)+$", re.I)
RESOURCE_GROUP = re.compile(r"^[-\w().]{1,90}$", re.ASCII)
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,62}$")
ADDRESS = re.compile(r'^[A-Za-z0-9_.\-\[\]"]+$')

NAMED_VALUES = (
    "entra-tenant-id", "expected-audience", "required-app-role",
    "claude-desktop-delegated-auth-enabled", "claude-desktop-client-id",
    "claude-desktop-delegated-scope", "per-user-rate-limit", "per-user-token-limit",
    "per-user-concurrent-stream-limit", "aggregate-concurrent-stream-limit", "environment-profile",
)
ALERTS = {
    "high-capacity": "cpu",
    "high-memory": "memory",
    "gateway-errors": "requests",
    "gateway-5xx": "gateway_5xx",
    "backend-5xx": "backend_5xx",
}
FOUNDRY_USER_ROLE = "53ca6127-db72-4b80-b1b0-d745d6d5456d"
MONITORING_PUBLISHER_ROLE = "3913510d-42f4-4e42-8a64-420c390055eb"


def resource_id(subscription, resource_group, provider, *parts):
    return "/subscriptions/{}/resourceGroups/{}/providers/{}/{}".format(
        subscription, resource_group, provider, "/".join(parts)
    )


def require_uuid(value, label):
    if not UUID.fullmatch(value):
        raise ManifestError(f"{label} must be a UUID")
    try:
        if str(uuid.UUID(value)) != value.lower():
            raise ValueError
    except ValueError as error:
        raise ManifestError(f"{label} must be a UUID") from error


def require_name(value, label):
    if not NAME.fullmatch(value):
        raise ManifestError(f"{label} must be 1-63 letters, numbers, or hyphens and start with a letter or number")


def require_resource_id(value, label, resource_type=None):
    if not RESOURCE_ID.fullmatch(value):
        raise ManifestError(f"{label} must be a full Azure resource ID")
    if resource_type and f"/providers/{resource_type.lower()}/" not in value.lower():
        raise ManifestError(f"{label} must identify {resource_type}")


def address_overrides(values):
    result = {}
    for value in values:
        key, separator, address = value.partition("=")
        if not separator or not key or not ADDRESS.fullmatch(address) or key in result:
            raise ManifestError("--address must be a unique key=OpenTofu-address mapping")
        result[key] = address
    return result


def build(args):
    require_uuid(args.subscription, "--subscription")
    if not RESOURCE_GROUP.fullmatch(args.resource_group):
        raise ManifestError("--resource-group is not a valid Azure resource group name")
    for label, value in (("--primary-apim", args.primary_apim), ("--secondary-apim", args.secondary_apim),
                         ("--workspace-name", args.workspace_name), ("--app-insights-name", args.app_insights_name),
                         ("--traffic-manager-name", args.traffic_manager_name)):
        if value:
            require_name(value, label)
    overrides = address_overrides(args.address)
    if args.observability == "managed" and (not args.workspace_name or not args.app_insights_name):
        raise ManifestError("managed observability requires --workspace-name and --app-insights-name")
    if args.observability == "external":
        if not args.workspace_id or not args.app_insights_id:
            raise ManifestError("external observability requires --workspace-id and --app-insights-id")
        require_resource_id(args.workspace_id, "--workspace-id", "Microsoft.OperationalInsights/workspaces")
        require_resource_id(args.app_insights_id, "--app-insights-id", "Microsoft.Insights/components")
    elif args.workspace_id or args.app_insights_id:
        raise ManifestError("--workspace-id and --app-insights-id are only valid with external observability")
    for label, value, resource_type in (
        ("--action-group-id", args.action_group_id, "Microsoft.Insights/actionGroups"),
        ("--primary-apim-subnet-id", args.primary_apim_subnet_id, "Microsoft.Network/virtualNetworks/subnets"),
        ("--secondary-apim-subnet-id", args.secondary_apim_subnet_id, "Microsoft.Network/virtualNetworks/subnets"),
    ):
        if value:
            require_resource_id(value, label, resource_type)

    regions = [("primary", args.primary_apim, args.primary_foundry_account_id, args.primary_foundry_role_assignment)]
    if args.secondary_apim:
        if not args.secondary_foundry_account_id or not args.secondary_foundry_role_assignment:
            raise ManifestError("secondary APIM requires --secondary-foundry-account-id and --secondary-foundry-role-assignment")
        regions.append(("secondary", args.secondary_apim, args.secondary_foundry_account_id, args.secondary_foundry_role_assignment))
    elif args.secondary_apim_subnet_id:
        raise ManifestError("--secondary-apim-subnet-id requires --secondary-apim")
    if args.traffic_manager_name and not args.secondary_apim:
        raise ManifestError("--traffic-manager-name requires --secondary-apim")
    for region, _, foundry_id, role_assignment in regions:
        require_resource_id(foundry_id, f"--{region}-foundry-account-id", "Microsoft.CognitiveServices/accounts")
        require_uuid(role_assignment, f"--{region}-foundry-role-assignment")
    if args.observability != "disabled":
        for region in (item[0] for item in regions):
            role_assignment = getattr(args, f"{region}_monitoring_role_assignment")
            if not role_assignment:
                raise ManifestError(f"observability requires --{region}-monitoring-role-assignment")
            require_uuid(role_assignment, f"--{region}-monitoring-role-assignment")

    imports, excluded = [], []

    def add(key, azure_id, default):
        imports.append({"address": overrides.get(key, default), "id": azure_id})

    for region, apim_name, foundry_id, foundry_role in regions:
        apim_id = resource_id(args.subscription, args.resource_group, "Microsoft.ApiManagement", "service", apim_name)
        add(f"{region}.apim", apim_id, f'azapi_resource.apim["{region}"]')
        add(f"{region}.backend", f"{apim_id}/backends/foundry-backend", f'azurerm_api_management_backend.foundry["{region}"]')
        for name in NAMED_VALUES:
            slug = name.replace("-", "_")
            add(f"{region}.named_value.{name}", f"{apim_id}/namedValues/{name}",
                f'azurerm_api_management_named_value.gateway["{region}/{name}"]')
        api_id = f"{apim_id}/apis/claude"
        add(f"{region}.api", api_id, f'azurerm_api_management_api.claude["{region}"]')
        add(f"{region}.api_policy", f"{api_id}/policies/policy", f'azurerm_api_management_api_policy.claude["{region}"]')
        for operation in ("messages", "count-tokens", "health"):
            slug = operation.replace("-", "_")
            operation_id = f"{api_id}/operations/{operation}"
            add(f"{region}.operation.{operation}", operation_id,
                f'azurerm_api_management_api_operation.claude["{region}/{operation}"]')
            add(f"{region}.operation_policy.{operation}", f"{operation_id}/policies/policy",
                f'azurerm_api_management_api_operation_policy.claude["{region}/{operation}"]')
        role_id = f"{foundry_id}/providers/Microsoft.Authorization/roleAssignments/{foundry_role}"
        add(f"{region}.foundry_role", role_id, f'azurerm_role_assignment.foundry_user["{region}"]')
        excluded.append({"id": foundry_id, "reason": "Existing Foundry account is externally owned; only its role assignment is managed."})

        if args.observability != "disabled":
            add(f"{region}.logger", f"{apim_id}/loggers/application-insights",
                f'azapi_resource.application_insights_logger["{region}"]')
            add(f"{region}.api_diagnostic", f"{api_id}/diagnostics/applicationinsights",
                f'azurerm_api_management_api_diagnostic.claude["{region}"]')
            add(f"{region}.diagnostic_setting", f"{apim_id}|send-to-log-analytics",
                f'azurerm_monitor_diagnostic_setting.apim["{region}"]')
            monitoring_role = getattr(args, f"{region}_monitoring_role_assignment")
            app_insights_id = (resource_id(args.subscription, args.resource_group, "Microsoft.Insights", "components", args.app_insights_name)
                               if args.observability == "managed" else args.app_insights_id)
            add(f"{region}.monitoring_role", f"{app_insights_id}/providers/Microsoft.Authorization/roleAssignments/{monitoring_role}",
                f'azurerm_role_assignment.monitoring_metrics_publisher["{region}"]')
            for alert, resource_name in ALERTS.items():
                add(f"{region}.alert.{alert}", resource_id(args.subscription, args.resource_group, "Microsoft.Insights", "metricAlerts", f"{apim_name}-{alert}"),
                    f'azurerm_monitor_metric_alert.{resource_name}["{region}"]')
        if args.autoscale:
            add(f"{region}.autoscale", resource_id(args.subscription, args.resource_group, "Microsoft.Insights", "autoscalesettings", f"{apim_name}-autoscale"),
                f'azurerm_monitor_autoscale_setting.apim["{region}"]')

    if args.observability == "managed":
        add("observability.workspace", resource_id(args.subscription, args.resource_group, "Microsoft.OperationalInsights", "workspaces", args.workspace_name),
            'azurerm_log_analytics_workspace.shared["shared"]')
        add("observability.app_insights", resource_id(args.subscription, args.resource_group, "Microsoft.Insights", "components", args.app_insights_name),
            'azurerm_application_insights.shared["shared"]')
    elif args.observability == "external":
        excluded.extend((
            {"id": args.workspace_id, "reason": "Log Analytics workspace is externally owned and must not be imported."},
            {"id": args.app_insights_id, "reason": "Application Insights is externally owned and must not be imported."},
        ))
    for label, value in (("APIM integration subnet", args.primary_apim_subnet_id),
                         ("secondary APIM integration subnet", args.secondary_apim_subnet_id),
                         ("Action Group", args.action_group_id)):
        if value:
            excluded.append({"id": value, "reason": f"{label} is externally owned and must not be imported."})
    if args.traffic_manager_name:
        profile_id = resource_id(args.subscription, args.resource_group, "Microsoft.Network", "trafficManagerProfiles", args.traffic_manager_name)
        add("traffic_manager.profile", profile_id, 'azurerm_traffic_manager_profile.failover["failover"]')
        add("traffic_manager.primary", f"{profile_id}/externalEndpoints/primary", 'azurerm_traffic_manager_external_endpoint.apim["primary"]')
        add("traffic_manager.secondary", f"{profile_id}/externalEndpoints/secondary", 'azurerm_traffic_manager_external_endpoint.apim["secondary"]')

    imports.sort(key=lambda item: item["address"])
    excluded.sort(key=lambda item: item["id"])
    return {"imports": imports, "excluded": excluded, "version": 1}


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--subscription", required=True)
    result.add_argument("--resource-group", required=True)
    result.add_argument("--primary-apim", required=True)
    result.add_argument("--primary-foundry-account-id", required=True)
    result.add_argument("--primary-foundry-role-assignment", required=True)
    result.add_argument("--secondary-apim")
    result.add_argument("--secondary-foundry-account-id")
    result.add_argument("--secondary-foundry-role-assignment")
    result.add_argument("--observability", choices=("disabled", "managed", "external"), default="disabled")
    result.add_argument("--workspace-name")
    result.add_argument("--app-insights-name")
    result.add_argument("--workspace-id")
    result.add_argument("--app-insights-id")
    result.add_argument("--primary-monitoring-role-assignment")
    result.add_argument("--secondary-monitoring-role-assignment")
    result.add_argument("--action-group-id")
    result.add_argument("--primary-apim-subnet-id")
    result.add_argument("--secondary-apim-subnet-id")
    result.add_argument("--autoscale", action="store_true")
    result.add_argument("--traffic-manager-name")
    result.add_argument("--address", action="append", default=[], metavar="KEY=ADDRESS")
    result.add_argument("--var-file", required=True, type=Path)
    result.add_argument("--shell-output", required=True, type=Path)
    result.add_argument("--json-output", required=True, type=Path)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        manifest = build(args)
    except ManifestError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    args.json_output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    commands = ["# Review each command before running it; this file does not execute imports."]
    commands.extend(
        "tofu -chdir=infra/tofu import -input=false -var-file={} {} {}".format(
            shlex.quote(str(args.var_file)), shlex.quote(item["address"]), shlex.quote(item["id"])
        )
        for item in manifest["imports"]
    )
    args.shell_output.write_text("\n".join(commands) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
