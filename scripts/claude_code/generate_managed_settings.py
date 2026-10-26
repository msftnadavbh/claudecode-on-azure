#!/usr/bin/env python3
"""Generate Claude Code managed-settings.json files without installing them."""

import argparse
import json
import re
import shlex
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit
from uuid import UUID


PLATFORM_PATHS = {
    "macos": "/Library/Application Support/ClaudeCode/managed-settings.json",
    "linux": "/etc/claude-code/managed-settings.json",
    "windows": r"C:\Program Files\ClaudeCode\managed-settings.json",
}
WINDOWS_DEVICES = {"CON", "PRN", "AUX", "NUL"} | {f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)}


def selected_platforms(args: argparse.Namespace) -> tuple[str, ...]:
    platform = getattr(args, "platform", "all")
    return tuple(PLATFORM_PATHS) if platform == "all" else (platform,)


def _nonempty(value: str, option: str) -> str:
    if not value.strip() or any(ord(character) < 32 for character in value):
        raise ValueError(f"{option} must be non-empty and contain no control characters")
    return value


def validate(args: argparse.Namespace) -> None:
    if str(UUID(args.tenant_id)) != args.tenant_id:
        raise ValueError("--tenant-id must be a canonical UUID")
    gateway = urlsplit(args.gateway_url)
    if gateway.scheme != "https" or not gateway.netloc or gateway.username or gateway.password or gateway.query or gateway.fragment:
        raise ValueError("--gateway-url must be an HTTPS URL without credentials, query, or fragment")

    audience = urlsplit(args.audience)
    if audience.scheme not in {"api", "https"} or not audience.netloc:
        raise ValueError("--audience must be a full api:// or https:// audience URI")

    for platform in selected_platforms(args):
        option = f"--{platform}-helper-path"
        helper = getattr(args, f"{platform}_helper_path", None)
        if helper is None:
            raise ValueError(f"{option} is required for {platform}")
        _nonempty(helper, option)
        if platform != "windows":
            if not PurePosixPath(helper).is_absolute():
                raise ValueError(f"{option} must be absolute")
            continue
        windows = helper.replace("/", "\\")
        parts = windows[3:].split("\\")
        if (not re.fullmatch(r"[A-Za-z]:\\[A-Za-z0-9_.\\-]+", windows)
                or not PureWindowsPath(windows).is_absolute()
                or any(not part or part in {".", ".."} or part.endswith(".")
                       or part.split(".")[0].upper() in WINDOWS_DEVICES
                       for part in parts)):
            raise ValueError("--windows-helper-path must be a safe drive-qualified ASCII path without spaces or shell metacharacters")

    for option in ("--opus-model", "--sonnet-model", "--haiku-model"):
        _nonempty(getattr(args, option[2:].replace("-", "_")), option)


def build_settings(args: argparse.Namespace, helper_path: str, platform: str) -> dict[str, object]:
    """Return the single semantic policy, parameterized only by OS helper path."""
    settings = {
        "apiKeyHelper": str(PureWindowsPath(helper_path)) if platform == "windows" else shlex.quote(helper_path),
        "env": {
            "ANTHROPIC_BASE_URL": args.gateway_url,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": args.haiku_model,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": args.opus_model,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": args.sonnet_model,
            "APIM_AUDIENCE": args.audience,
            "APIM_TENANT_ID": args.tenant_id,
            "CLAUDE_CODE_API_KEY_HELPER_TTL_MS": "300000",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "1",
        },
    }
    if getattr(args, "enable_model_discovery", False):
        settings["env"]["CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY"] = "1"
    return settings


def write_outputs(args: argparse.Namespace) -> dict[str, Path]:
    validate(args)
    output_dir = Path(args.output_dir)
    outputs = {}
    for platform in selected_platforms(args):
        path = output_dir / platform / "managed-settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        helper_path = getattr(args, f"{platform}_helper_path")
        path.write_bytes((json.dumps(build_settings(args, helper_path, platform), indent=2, sort_keys=True) + "\n").encode("utf-8"))
        outputs[platform] = path
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Claude Code managed settings without installing them.")
    parser.add_argument("--gateway-url", required=True)
    parser.add_argument("--audience", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--platform", choices=("all", *PLATFORM_PATHS), default="all", help="Generate only this OS; only its helper path is required (default: all).")
    parser.add_argument("--macos-helper-path")
    parser.add_argument("--linux-helper-path")
    parser.add_argument("--windows-helper-path")
    parser.add_argument("--opus-model", required=True)
    parser.add_argument("--sonnet-model", required=True)
    parser.add_argument("--haiku-model", required=True)
    parser.add_argument("--enable-model-discovery", action="store_true", help="Opt in after publishing the gateway /v1/models endpoint.")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    try:
        outputs = write_outputs(args)
    except ValueError as error:
        parser.error(str(error))
    for platform, path in outputs.items():
        print(f"{platform}: {path} -> {PLATFORM_PATHS[platform]}")


if __name__ == "__main__":
    main()
