# Claude Code client canary

**Purpose:** make a controlled live request from an installed, managed Claude Code client. **Prerequisites:** the approved Azure CLI session, installed Claude Code, and the managed gateway launch environment. **Boundary:** the script does not configure credentials, source managed settings, or export their values to its parent shell.

```bash
python3 scripts/test/claude_code_canary.py
```

Run it from the environment that launches Claude Code with the managed settings. It creates a temporary repository, performs deterministic restricted work, emits a small JSON result, and removes the temporary repository. It does not modify the current repository.

To make a second request after the chosen refresh interval:

```bash
python3 scripts/test/claude_code_canary.py --refresh-after-seconds 360
```

Choose the wait for the managed helper/cache policy. Confirm request success, refresh, and revocation behavior on pilot devices before broad rollout.
