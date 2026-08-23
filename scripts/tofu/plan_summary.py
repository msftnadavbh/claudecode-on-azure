#!/usr/bin/env python3
"""Emit a safe, deterministic summary of an OpenTofu plan."""
import json
import sys
from hashlib import sha256


def summarize(plan):
    summary = []
    for change in plan.get("resource_changes", []):
        actions = change.get("change", {}).get("actions", [])
        if "delete" in actions:
            kind = "replacement" if "create" in actions else "deletion"
            raise ValueError(f"{kind} is not allowed: {change.get('address', '<unknown>')}")
        change_data = change.get("change", {})
        planned = json.dumps(
            {"actions": actions, "after": change_data.get("after"), "after_unknown": change_data.get("after_unknown")},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        summary.append({
            "address": change["address"],
            "type": change["type"],
            "actions": actions,
            "planned_change_sha256": sha256(planned).hexdigest(),
        })
    return sorted(summary, key=lambda item: (item["address"], item["type"], item["actions"]))


def main():
    print(json.dumps(summarize(json.load(sys.stdin)), separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise SystemExit(str(exc)) from exc
