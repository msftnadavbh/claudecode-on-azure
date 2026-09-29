#!/usr/bin/env python3
"""Repair a missing local Desktop configLibrary entries index (quit Desktop first)."""

import argparse
import json
import os
from pathlib import Path
import tempfile
import unicodedata
from uuid import UUID


def canonical_uuid(value):
    if not isinstance(value, str):
        raise ValueError("expected canonical UUID")
    try:
        canonical = str(UUID(value))
    except ValueError:
        raise ValueError("expected canonical UUID") from None
    if canonical != value:
        raise ValueError("expected canonical UUID")
    return value


def valid_name(value):
    if not isinstance(value, str) or not value.strip() or any(unicodedata.category(c) == "Cc" for c in value):
        raise ValueError("name must be nonblank and control-free")
    return value


def repair(config_dir, name="Gateway"):
    """Operator must close Desktop; this check cannot prevent concurrent app writes."""
    valid_name(name)
    config_dir = Path(config_dir).resolve()
    original = (config_dir / "_meta.json").read_bytes()
    meta = json.loads(original)
    if not isinstance(meta, dict):
        raise ValueError("metadata must be an object")
    applied = canonical_uuid(meta.get("appliedId"))
    profile = json.loads((config_dir / f"{applied}.json").read_bytes())
    if not isinstance(profile, dict):
        raise ValueError("applied profile must be an object")
    if "entries" in meta:
        entries = meta["entries"]
        if not isinstance(entries, list) or not entries:
            raise ValueError("entries must be a nonempty list")
        ids = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("invalid entry")
            ids.append(canonical_uuid(entry.get("id")))
            valid_name(entry.get("name"))
        if len(ids) != len(set(ids)) or ids.count(applied) != 1:
            raise ValueError("duplicate or unmatched applied entry")
        return False
    for path in config_dir.glob("*.json"):
        try:
            other = UUID(path.stem)
        except ValueError:
            continue
        if str(other) != applied:
            raise ValueError("multiple profiles: choose entries manually")
    backup = config_dir.parent / "configLibrary-meta.backup.json"
    meta["entries"] = [{"id": applied, "name": name}]
    updated = (json.dumps(meta, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    with backup.open("xb") as file:
        file.write(original)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=config_dir, prefix=".meta-", suffix=".tmp", delete=False) as file:
            temp = Path(file.name)
            file.write(updated)
        if (config_dir / "_meta.json").read_bytes() != original:
            raise ValueError("metadata changed during repair; quit Desktop and inspect backup")
        os.replace(temp, config_dir / "_meta.json")
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path, help="configLibrary directory (default: LOCALAPPDATA/Claude-3p/configLibrary)")
    parser.add_argument("--name", default="Gateway")
    args = parser.parse_args()
    if args.config_dir is None:
        if not os.environ.get("LOCALAPPDATA"):
            parser.error("LOCALAPPDATA is missing; pass --config-dir")
        args.config_dir = Path(os.environ["LOCALAPPDATA"]) / "Claude-3p" / "configLibrary"
    try:
        changed = repair(args.config_dir, args.name)
    except (OSError, ValueError, UnicodeError) as exc:
        parser.exit(1, f"Repair refused: {exc}\n")
    print("Metadata repaired; restart Desktop and verify in the GUI." if changed else "Metadata already valid; unchanged.")


if __name__ == "__main__":
    main()
