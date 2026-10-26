#!/usr/bin/env python3
"""Render the POC's restricted configuration (JSON is also valid YAML)."""

import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import socket
import sys
from urllib.parse import urlsplit
import uuid


MINIMUM_VERSION = (2, 1, 296)  # managed.policies.code requires this gateway release.
PRIVATE_NETWORKS = tuple(ipaddress.ip_network(cidr) for cidr in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"
))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value, name):
    require(isinstance(value, str) and value == value.strip() and bool(value),
            f"{name} must be a nonempty, trimmed string")
    require(not re.search(r"REPLACE|CHANGEME|PLACEHOLDER|[<>{}$\r\n]", value, re.I),
            f"{name} contains a placeholder or expansion")
    return value


def identifier(value, name):
    text(value, name)
    require(str(uuid.UUID(value)) == value.lower() and int(uuid.UUID(value)) != 0,
            f"{name} must be a nonzero UUID")


def validate(settings):
    expected = {
        "public_url", "tenant_id", "client_id", "groups_claim", "allowed_groups",
        "foundry_resource", "models", "claude_version", "claude_sha256",
        "signed_release_verified",
    }
    require(isinstance(settings, dict) and set(settings) == expected,
            "Settings must contain exactly the keys in settings.example.json")
    url = urlsplit(text(settings["public_url"], "public_url"))
    require(url.scheme == "https" and url.port == 8443 and url.hostname
            and "." in url.hostname and url.path == "" and not url.query
            and not url.fragment and not url.username and not url.password,
            "public_url must be https://private.dns.hostname:8443 with no path")
    require(bool(re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", url.hostname)),
            "public_url must use a DNS hostname")
    require(not url.hostname.endswith((".example", ".example.com", ".invalid")),
            "Replace the example DNS hostname")
    identifier(settings["tenant_id"], "tenant_id")
    identifier(settings["client_id"], "client_id")
    require(settings["groups_claim"] in ("groups", "roles"),
            "groups_claim must be groups or roles")
    groups = settings["allowed_groups"]
    require(isinstance(groups, list) and groups, "allowed_groups cannot be empty")
    for group in groups:
        text(group, "allowed_groups entry")
        if settings["groups_claim"] == "groups":
            identifier(group, "group Object ID")
        else:
            require(bool(re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", group)),
                    "Use an exact Entra app role value")
    require(len(groups) == len(set(groups)), "Duplicate allowed group")
    require(bool(re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9-]{1,62}",
                             text(settings["foundry_resource"], "foundry_resource"))),
            "foundry_resource must be the account name, not its URL or resource ID")
    models = settings["models"]
    require(isinstance(models, list) and models, "At least one model is required")
    ids = []
    for model in models:
        require(isinstance(model, dict) and set(model) == {"id", "deployment"},
                "Each model needs exactly id and deployment")
        require(bool(re.fullmatch(r"claude-[a-z0-9]+(?:-[a-z0-9]+)+",
                                 text(model["id"], "model id"))),
                "Use an explicit canonical Claude model ID, not an alias")
        require(bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}",
                                 text(model["deployment"], "deployment"))),
                "Invalid Foundry deployment name")
        ids.append(model["id"])
    require(len(ids) == len(set(ids)), "Duplicate canonical model ID")
    version = text(settings["claude_version"], "claude_version")
    require(bool(re.fullmatch(r"\d+\.\d+\.\d+", version)), "Pin an exact stable version")
    require(tuple(map(int, version.split("."))) >= MINIMUM_VERSION,
            "This template requires gateway and pilot clients >= 2.1.296")
    digest = text(settings["claude_sha256"], "claude_sha256")
    require(bool(re.fullmatch(r"[a-f0-9]{64}", digest)) and len(set(digest)) > 1,
            "claude_sha256 must be the verified manifest's SHA256")
    require(settings["signed_release_verified"] is True,
            "Verify upstream release signature and digest before confirming signed_release_verified")
    return settings


def private_dns(hostname):
    addresses = {result[4][0] for result in socket.getaddrinfo(
        hostname, 8443, type=socket.SOCK_STREAM)}
    require(bool(addresses), "Gateway DNS resolved no addresses")
    require(all(any(ipaddress.ip_address(address) in network for network in PRIVATE_NETWORKS)
                for address in addresses),
            "Every gateway DNS address must be RFC1918 IPv4; public/IPv6/loopback rejected")


def verify_binary(path, expected_digest):
    path = Path(path)
    with path.open("rb") as binary:
        header = binary.read(20)
        require(header[:6] == b"\x7fELF\x02\x01"
                and header[18:20] == b"\x3e\x00",
                "Supply the signed-release native Linux x64 ELF binary")
        binary.seek(0)
        digest = hashlib.file_digest(binary, "sha256").hexdigest()
    require(digest == expected_digest, "Binary SHA256 differs from verified release manifest")


def render(settings):
    validate(settings)
    config = json.loads(Path(__file__).with_name("gateway.template.json").read_text())
    config["listen"]["public_url"] = settings["public_url"]
    config["oidc"].update({
        "issuer": f"https://login.microsoftonline.com/{settings['tenant_id']}/v2.0",
        "client_id": settings["client_id"],
        "groups_claim": settings["groups_claim"],
        "allowed_groups": settings["allowed_groups"],
    })
    config["upstreams"][0]["resource"] = settings["foundry_resource"]
    config["models"] = [
        {"id": model["id"], "label": model["id"],
         "upstream_model": {"foundry": model["deployment"]}}
        for model in settings["models"]
    ]
    policy = config["managed"]["policies"][0]
    policy["match"]["groups"] = settings["allowed_groups"]
    policy["code"]["availableModels"] = [model["id"] for model in settings["models"]]
    policy["code"]["model"] = settings["models"][0]["id"]
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("settings", type=Path)
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--check-dns", action="store_true")
    parser.add_argument("--field", choices=("hostname", "claude_version"))
    args = parser.parse_args()
    try:
        settings = validate(json.loads(args.settings.read_text()))
        if args.binary:
            verify_binary(args.binary, settings["claude_sha256"])
        hostname = urlsplit(settings["public_url"]).hostname
        if args.check_dns:
            private_dns(hostname)
        if args.field:
            print(hostname if args.field == "hostname" else settings[args.field])
        else:
            print(json.dumps(render(settings), indent=2))
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(f"Configuration rejected: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
