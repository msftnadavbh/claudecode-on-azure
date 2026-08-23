#!/usr/bin/env python3
"""Generate Claude Code managed-settings.json files without installing them."""

import argparse
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit


PLATFORM_PATHS = {
    "macos": "/Library/Application Support/ClaudeCode/managed-settings.json",
    "linux": "/etc/claude-code/managed-settings.json",
    "windows": r"C:\Program Files\ClaudeCode\managed-settings.json",
}


def _nonempty(value: str, option: str) -> str:
    if not value.strip() or any(ord(character) < 32 for character in value):
        raise ValueError(f"{option} must be non-empty and contain no control characters")
    return value


def validate(args: argparse.Namespace) -> None:
    gateway = urlsplit(args.gateway_url)
    if gateway.scheme != "https" or not gateway.netloc or gateway.username or gateway.password or gateway.query or gateway.fragment:
        raise ValueError("--gateway-url must be an HTTPS URL without credentials, query, or fragment")

    audience = urlsplit(args.audience)
    if audience.scheme not in {"api", "https"} or not audience.netloc:
        raise ValueError("--audience must be a full api:// or https:// audience URI")

    if not PurePosixPath(args.macos_helper_path).is_absolute() or not PurePosixPath(args.linux_helper_path).is_absolute():
        raise ValueError("macOS and Linux helper paths must be absolute")
    if not PureWindowsPath(args.windows_helper_path).is_absolute():
        raise ValueError("--windows-helper-path must be absolute")

    for option in ("--macos-helper-path", "--linux-helper-path", "--windows-helper-path", "--opus-model", "--sonnet-model", "--haiku-model"):
        _nonempty(getattr(args, option[2:].replace("-", "_")), option)


def build_settings(args: argparse.Namespace, helper_path: str) -> dict[str, object]:
    """Return the single semantic policy, parameterized only by OS helper path."""
    return {
        "apiKeyHelper": helper_path,
        "env": {
            "ANTHROPIC_BASE_URL": args.gateway_url,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": args.haiku_model,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": args.opus_model,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": args.sonnet_model,
            "APIM_AUDIENCE": args.audience,
            "CLAUDE_CODE_API_KEY_HELPER_TTL_MS": "300000",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "1",
        },
    }


def write_outputs(args: argparse.Namespace) -> dict[str, Path]:
    validate(args)
    output_dir = Path(args.output_dir)
    outputs = {}
    helper_paths = {
        "macos": args.macos_helper_path,
        "linux": args.linux_helper_path,
        "windows": args.windows_helper_path,
    }
    for platform in PLATFORM_PATHS:
        path = output_dir / platform / "managed-settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((json.dumps(build_settings(args, helper_paths[platform]), indent=2, sort_keys=True) + "\n").encode("utf-8"))
        outputs[platform] = path
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Claude Code managed settings without installing them.")
    parser.add_argument("--gateway-url", required=True)
    parser.add_argument("--audience", required=True)
    parser.add_argument("--macos-helper-path", required=True)
    parser.add_argument("--linux-helper-path", required=True)
    parser.add_argument("--windows-helper-path", required=True)
    parser.add_argument("--opus-model", required=True)
    parser.add_argument("--sonnet-model", required=True)
    parser.add_argument("--haiku-model", required=True)
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
