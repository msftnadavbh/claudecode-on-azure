#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import plistlib
from urllib.parse import urlsplit
import uuid


POLICY_KEY = r"HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Claude"


def build_settings(args: argparse.Namespace) -> dict[str, str]:
    models = [
        {"anthropicFamilyTier": family, "isFamilyDefault": True, "name": name}
        for family, name in (
            ("sonnet", args.sonnet_model),
            ("opus", args.opus_model),
            ("haiku", args.haiku_model),
        )
    ]
    oidc = {
        "appendOfflineAccess": True,
        "bearerTokenType": "access_token",
        "clientId": args.desktop_client_id,
        "issuer": f"https://login.microsoftonline.com/{args.tenant_id}/v2.0",
        "scopes": f"openid profile email {args.delegated_scope}",
    }
    values = {
        "allowedWorkspaceFolders": '[{"mode":"rw","path":"~/Documents/Claude"}]',
        "autoModeEnabled": "false",
        "chatAdvancedFileAnalysisEnabled": "false",
        "chatTabEnabled": "true",
        "coworkEgressAllowedHosts": "[]",
        "coworkTabEnabled": "true",
        "deploymentDisplayName": args.organization,
        "deploymentOrganizationUuid": args.deployment_org_id,
        "disableBundledSkills": "true",
        "disableDeploymentModeChooser": "true",
        "disabledBuiltinTools": '["WebSearch","WebFetch"]',
        "inferenceCredentialKind": "interactive",
        "inferenceGatewayAuthScheme": "bearer",
        "inferenceGatewayBaseUrl": args.gateway_url,
        "inferenceGatewayOidc": json.dumps(oidc, sort_keys=True, separators=(",", ":")),
        "inferenceGatewayOidcAuthFlow": "browser",
        "inferenceModels": json.dumps(models, sort_keys=True, separators=(",", ":")),
        "inferenceProvider": "gateway",
        "isClaudeCodeForDesktopEnabled": "true",
        "isDesktopExtensionEnabled": "false",
        "isLocalDevMcpEnabled": "false",
        "managedMcpServers": "[]",
        "mcpPersistentAlwaysAllowEnabled": "false",
        "modelDiscoveryEnabled": "false",
        "skillCreationEnabled": "false",
        "toolSearchEnabled": "false",
    }
    return dict(sorted(values.items()))


def validate(args: argparse.Namespace) -> None:
    for name in ("tenant_id", "desktop_client_id", "deployment_org_id"):
        value = getattr(args, name)
        try:
            parsed = uuid.UUID(value)
        except ValueError as error:
            raise ValueError(f"--{name.replace('_', '-')} must be a UUID") from error
        if str(parsed) != value.lower():
            raise ValueError(f"--{name.replace('_', '-')} must be a canonical UUID")

    gateway = urlsplit(args.gateway_url)
    if gateway.scheme != "https" or not gateway.netloc or gateway.username or gateway.query or gateway.fragment or gateway.path.rstrip("/").endswith("/v1"):
        raise ValueError("--gateway-url must be an HTTPS URL without credentials, query, or fragment")

    scope = urlsplit(args.delegated_scope)
    if scope.scheme not in {"api", "https"} or not scope.netloc or not scope.path.strip("/"):
        raise ValueError("--delegated-scope must be a full api:// or https:// delegated scope URI")

    for name in ("organization", "sonnet_model", "opus_model", "haiku_model"):
        value = getattr(args, name)
        if not value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError(f"--{name.replace('_', '-')} must be non-empty and contain no control characters")


def write_outputs(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    validate(args)
    settings = build_settings(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    namespace = uuid.UUID(args.deployment_org_id)
    profile_id = str(uuid.uuid5(namespace, "com.anthropic.claudefordesktop.managed"))
    payload_id = str(uuid.uuid5(namespace, "com.anthropic.claudefordesktop.preferences"))
    profile = {
        "PayloadContent": [{
            "PayloadContent": {
                "com.anthropic.claudefordesktop": {
                    "Forced": [{"mcx_preference_settings": settings}]
                }
            },
            "PayloadDisplayName": "Claude Desktop Managed Configuration",
            "PayloadIdentifier": f"com.anthropic.claudefordesktop.preferences.{payload_id}",
            "PayloadType": "com.apple.ManagedClient.preferences",
            "PayloadUUID": payload_id,
            "PayloadVersion": 1,
        }],
        "PayloadDescription": "Managed third-party inference configuration for Claude Desktop.",
        "PayloadDisplayName": "Claude Desktop Managed Configuration",
        "PayloadIdentifier": f"com.anthropic.claudefordesktop.managed.{profile_id}",
        "PayloadOrganization": args.organization,
        "PayloadScope": "System",
        "PayloadType": "Configuration",
        "PayloadUUID": profile_id,
        "PayloadVersion": 1,
    }
    macos = output_dir / "claude-desktop-managed.mobileconfig"
    macos.write_bytes(plistlib.dumps(profile, fmt=plistlib.FMT_XML, sort_keys=True))

    lines = ["Windows Registry Editor Version 5.00", "", f"[{POLICY_KEY}]"]
    lines.extend(f'"{key}"="{value.replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))}"' for key, value in settings.items())
    windows = output_dir / "claude-desktop-managed.reg"
    windows.write_bytes(b"\xff\xfe" + ("\r\n".join(lines) + "\r\n").encode("utf-16le"))

    removal = output_dir / "claude-desktop-managed-remove.reg"
    removal.write_bytes(
        b"\xff\xfe"
        + (f"Windows Registry Editor Version 5.00\r\n\r\n[-{POLICY_KEY}]\r\n").encode("utf-16le")
    )
    return macos, windows, removal


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Claude Desktop managed configuration files.")
    parser.add_argument("--gateway-url", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--desktop-client-id", required=True)
    parser.add_argument("--delegated-scope", required=True)
    parser.add_argument("--deployment-org-id", required=True)
    parser.add_argument("--organization", required=True)
    parser.add_argument("--sonnet-model", required=True)
    parser.add_argument("--opus-model", required=True)
    parser.add_argument("--haiku-model", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    try:
        paths = write_outputs(args)
    except ValueError as error:
        parser.error(str(error))
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
