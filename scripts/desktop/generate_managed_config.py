#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import plistlib
import unicodedata
from urllib.parse import urlsplit
import uuid


POLICY_KEYS = {
    "machine": r"HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Claude",
    "user": r"HKEY_CURRENT_USER\SOFTWARE\Policies\Claude",
}


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
        "coworkTabEnabled": "false" if args.disable_cowork else "true",
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
    for name in ("gateway_url", "tenant_id", "desktop_client_id", "delegated_scope", "deployment_org_id", "organization", "sonnet_model", "opus_model", "haiku_model"):
        if any(unicodedata.category(character) == "Cc" for character in getattr(args, name)):
            raise ValueError(f"--{name.replace('_', '-')} must contain no control characters")

    for name in ("tenant_id", "desktop_client_id", "deployment_org_id"):
        value = getattr(args, name)
        try:
            parsed = uuid.UUID(value)
        except ValueError as error:
            raise ValueError(f"--{name.replace('_', '-')} must be a UUID") from error
        if str(parsed) != value.lower():
            raise ValueError(f"--{name.replace('_', '-')} must be a canonical UUID")

    try:
        gateway = urlsplit(args.gateway_url)
        gateway.port  # Validate malformed and out-of-range ports even when the port is unused.
    except ValueError as error:
        raise ValueError("--gateway-url must be a valid HTTPS URL") from error
    if (gateway.scheme != "https" or not gateway.hostname or "@" in gateway.netloc
            or any(character.isspace() for character in args.gateway_url)
            or "?" in args.gateway_url or "#" in args.gateway_url
            or gateway.path.rstrip("/").endswith("/v1")):
        raise ValueError("--gateway-url must be an HTTPS URL without credentials, query, or fragment")

    try:
        scope = urlsplit(args.delegated_scope)
        scope.port
    except ValueError as error:
        raise ValueError("--delegated-scope must be a valid delegated scope URI") from error
    if (scope.scheme not in {"api", "https"} or not scope.hostname or "@" in scope.netloc
            or not scope.path.strip("/") or any(character.isspace() for character in args.delegated_scope)
            or "?" in args.delegated_scope or "#" in args.delegated_scope):
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

    policy_key = POLICY_KEYS[args.windows_scope]
    lines = ["Windows Registry Editor Version 5.00", "", f"[{policy_key}]"]
    lines.extend(f'"{key}"="{value.replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))}"' for key, value in settings.items())
    windows = output_dir / "claude-desktop-managed.reg"
    windows.write_bytes(b"\xff\xfe" + ("\r\n".join(lines) + "\r\n").encode("utf-16le"))

    removal = output_dir / "claude-desktop-managed-remove.reg"
    remove_lines = ["Windows Registry Editor Version 5.00", "", f"[{policy_key}]"]
    remove_lines.extend(f'"{key}"=-' for key in settings)
    removal.write_bytes(b"\xff\xfe" + ("\r\n".join(remove_lines) + "\r\n").encode("utf-16le"))
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
    parser.add_argument("--windows-scope", choices=("machine", "user"), default="machine")
    parser.add_argument("--disable-cowork", action="store_true")
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
