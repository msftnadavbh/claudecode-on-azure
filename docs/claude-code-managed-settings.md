# Managed Claude Code settings

Generate non-secret, platform-specific Claude Code configuration for device management. You need the gateway URL, Entra audience and caller tenant's canonical UUID, three role model names (one deployment mapped to all roles in greenfield), and managed helper paths. Generation writes files only; device management installs them, sets permissions, pins versions, updates, and rolls back.

```bash
python3 scripts/claude_code/generate_managed_settings.py \
  --gateway-url https://gateway.example/claude \
  --audience api://gateway-app-id \
  --tenant-id 11111111-1111-1111-1111-111111111111 \
  --macos-helper-path "/Library/Company/Claude/apim-user-token-helper.sh" \
  --linux-helper-path /opt/company/claude/apim-user-token-helper.sh \
  --windows-helper-path 'C:\ProgramData\Company\Claude\apim-user-token-helper.windows.cmd' \
  --opus-model opus-deployment --sonnet-model sonnet-deployment --haiku-model haiku-deployment \
  --output-dir out/claude-code
```

Deploy the generated file through the organization’s management system:

| Platform | Managed location |
| --- | --- |
| macOS | `/Library/Application Support/ClaudeCode/managed-settings.json` |
| Linux/WSL | `/etc/claude-code/managed-settings.json` |
| Windows | `C:\Program Files\ClaudeCode\managed-settings.json` |

The files configure generic gateway mode, a five-minute helper cache, subprocess environment scrubbing, and deployment-name defaults. They do not contain a token, API key, Foundry-native setting, or user shell-profile configuration.

`apiKeyHelper` is a shell command: the generator quotes absolute macOS/Linux helper filenames for `/bin/sh` and accepts only conservative drive-qualified ASCII Windows helper paths (no spaces, shell metacharacters, device names, or dot components), normalized to backslashes for native `cmd`. Do not pass a command as a path. On Windows install the `.cmd` and adjacent `.ps1` under an administrator-controlled, no-space `C:\ProgramData\Company\Claude` directory; lock down ACLs on the helper files **and every parent directory** against untrusted writes. The managed settings destination remains `C:\Program Files\ClaudeCode\managed-settings.json`. Native Windows Claude Code managed-mode command execution has not been verified; pilot it before rollout.

The generated environment includes `APIM_AUDIENCE` and `APIM_TENANT_ID` on every platform. Deploy settings first, verify the managed launch environment, then update the tenant-required helper. The helper fails closed when either input is missing; it never falls back to the active infrastructure tenant.

The managed file configures Claude, not its parent shell. Standalone helper/smoke/canary invocations need the values separately supplied in their launch environment. Before production, use a pinned OS/client pilot with `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` to verify that the **actual apiKeyHelper child** receives the expected nonsecret tenant/audience and inference succeeds. Record only an allowlisted tenant/audience match result and client/OS versions, never environment dumps or tokens. If inheritance fails, stop rollout rather than disabling scrubbing or falling back to another tenant/credential.

The bundled `scripts/auth/apim-user-token-helper.sh` is for macOS/Linux/WSL. Native Windows Claude Code can use `scripts/auth/apim-user-token-helper.windows.cmd` (beside its `.ps1`) as the no-argument `apiKeyHelper` in existing user settings: no registry policy or WSL bridge is needed. The supported runtime remains Windows PowerShell 5.1. Install both scripts on the Windows filesystem and point `apiKeyHelper` at the installed `.cmd`. Install native Azure CLI at `C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd`; the script also accepts explicit `-TenantId`, `-Audience`, and `-AzureCliPath` parameters when invoked directly through PowerShell. For normal helper use, pass `APIM_TENANT_ID` and `APIM_AUDIENCE` in the helper process environment.

Without the optional `-SubscriptionId`, the Windows helper preserves its explicit `--tenant` / `--resource` token request. **The tenant selects the token tenant, not the cached account:** Azure CLI uses the account associated with its global default subscription. For an approved Desktop-only binding, an administrator-controlled installed custom launcher can additionally supply `-SubscriptionId <canonical-uuid>` to the `.ps1`; the bundled no-argument `.cmd` and global subscription default remain unchanged. This mode first queries only the selected subscription's cached `id`, `tenantId`, `user.type`, `environmentName`, and `state`. All must match the requested subscription, configured tenant, `user`, `AzureCloud`, and `Enabled` before requesting a token with `--subscription` and `--resource`, **without `--tenant`** (Azure CLI rejects combining these selectors). Empty or malformed subscription arguments and invalid/mismatched metadata fail closed before any token request. There is no account discovery, fallback, login, cache copy, or global-default mutation. A cached subscription selector is **not an immutable principal pin**; APIM still enforces caller authorization, and Conditional Access can still reject the selected account.

The helper uses one monotonic 15s acquisition budget shared by metadata and token process/stream waits, with a shorter 2s private-stream-completion cap. Startup and a separately bounded cleanup tail can add wall-clock time; this is not a strict 15s end-to-end limit. Success exits 0 with only one validated raw token line on stdout and empty stderr; failure exits 1 with empty stdout and one allowlisted diagnostic line on stderr, never raw CLI errors, exception details, or configuration values. See [helper diagnostics](troubleshooting.md#windows-helper-diagnostics), including `AADSTS530036`. Azure CLI/MSAL owns sign-in and refresh; the helper never logs in or retries.

**Known PowerShell 5.1 pilot availability limitation:** an arbitrary CLI descendant can inherit extra caller-facing pipe handles and delay caller EOF after the helper process has already exited with its fixed diagnostic. There is **no end-to-end caller-completion guarantee under arbitrary descendant inheritance**. This is demonstrated by the deliberately leaky fake CLI, not by the normal installed Azure CLI; impact on the installed CLI remains unproven. Required tests measure helper-process exit separately, safely stop their known fixture child, then capture and verify output. A separate expected-failure test retains the original leaky fixture and `<10s` caller-EOF expectation; report that availability failure separately, never as a passing diagnostic/security test.

Fake-only native verification on 2026-10-19 used Python 3.14.7 and Windows PowerShell 5.1.26100.9711: the full gate had **18 passing test methods, 0 skips, and 1 expected caller-EOF availability failure**. Focused process-deadline/shared-budget checks also passed on repeated runs; the separate availability expectation remains unmet. This does not verify the installed helper or live Azure CLI behavior.

Linux unit tests skip native Windows execution: run `py -3 -I -B scripts\test\test_windows_auth_helper.py -v` on Windows (fake CLI only). Fake tests do not verify an installed launcher, live account, or client pilot; installation and any approved interactive sign-in/protected helper check remain separate, post-review operator steps. Roll back by restoring prior settings and helper, then restarting Claude Code; do not remove management as a recovery shortcut.
