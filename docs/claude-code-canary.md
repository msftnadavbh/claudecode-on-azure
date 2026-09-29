# Claude Code client canary

Use this script to make a controlled live request from an installed, managed Claude Code client. You need an approved Azure CLI session, installed Claude Code, and the managed gateway launch environment. The script does not configure credentials, source managed settings, or export their values to its parent shell.

```bash
python3 scripts/test/claude_code_canary.py
```

Run it from the environment that launches Claude Code with the managed settings, including both `APIM_AUDIENCE` and `APIM_TENANT_ID` (caller tenant UUID) and the model variables. Deploy these settings before the tenant-required helper. It creates a temporary repository, performs deterministic restricted work, emits a small JSON result, and removes the temporary repository. It does not modify the current repository.

To launch a separate Claude process after an operator-selected wait (the existing flag remains compatible):

```bash
python3 scripts/test/claude_code_canary.py --refresh-after-seconds 360
```

The output mode is `separate-process-wait`. Both invocations use `--no-session-persistence`; this demonstrates only separate-process success across a wait, not same-session refresh or recovery from a 401. A manual long-lived client pilot must still verify helper TTL, token expiry/refresh, 401 handling, and revoked access before broad rollout. No production refresh guarantee is inferred from this canary.

For a no-tools, explicit-model inference check after the `claude-opus-5-5` deployment and APIM subscription/auth configuration are approved and available, supply `ANTHROPIC_BASE_URL=https://<gateway>/claude`, `APIM_AUDIENCE`, and `APIM_TENANT_ID` in the launch environment, then run:

```bash
python3 scripts/test/claude_code_canary.py --inference-only \
  --model claude-opus-5-5 --token-helper /absolute/path/to/apim-user-token-helper.sh
```

This mode uses an isolated temporary Claude configuration, only the specified HTTPS gateway and token helper, and one client invocation with tools/MCP disabled and nonessential traffic disabled; its timeout is capped at 300 seconds and kills the POSIX client process group on timeout. It does not require the three role-model defaults or persist local settings. Managed policies remain authoritative even with `--bare`: verify the pinned client/device policy and helper compatibility before use; this flag is not a policy bypass. It requires the deployment to exist; catalog availability is not deployment. Success checks the client JSON result and reported model usage against the requested model, not model self-identification; it does **not** independently prove APIM/backend routing or HTTP request counts. Confirm those using approved gateway/backend telemetry. Do not bypass APIM or run this live check before authorization and deployment approval.
