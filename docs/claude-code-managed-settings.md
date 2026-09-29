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

The bundled `scripts/auth/apim-user-token-helper.sh` is for macOS/Linux/WSL. Native Windows Claude Code can use `scripts/auth/apim-user-token-helper.windows.cmd` (beside its `.ps1`) as the no-argument `apiKeyHelper` in existing user settings: no registry policy or WSL bridge is needed. Install both scripts on the Windows filesystem and point `apiKeyHelper` at the installed `.cmd`. Install native Azure CLI at `C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd`; the script can also be tested with explicit `-TenantId`, `-Audience`, and `-AzureCliPath` parameters when invoked directly through PowerShell. For normal helper use, pass `APIM_TENANT_ID` and `APIM_AUDIENCE` in the helper process environment. The helper requests an explicit tenant/resource noninteractively and emits only one raw token; it suppresses token and CLI errors on failure. Azure CLI/MSAL owns sign-in and refresh. Linux unit tests skip native Windows execution: pilot the installed helper on Windows before rollout. Roll back by restoring prior settings and helper, then restarting Claude Code; do not remove management as a recovery shortcut.
