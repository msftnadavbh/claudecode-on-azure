# Claude Code managed settings

This generator is the sole production Claude Code client-configuration path. Generate, but do not install, the non-secret terminal configuration:

```bash
python3 scripts/claude_code/generate_managed_settings.py \
  --gateway-url https://gateway.example/claude \
  --audience api://gateway-app-id \
  --macos-helper-path "/Library/Company/Claude/apim-user-token-helper.sh" \
  --linux-helper-path /opt/company/claude/apim-user-token-helper.sh \
  --windows-helper-path 'C:\Program Files\Company\Claude\apim-user-token-helper.cmd' \
  --opus-model opus-pinned --sonnet-model sonnet-pinned --haiku-model haiku-pinned \
  --output-dir out/claude-code
```

Deploy the generated UTF-8 `managed-settings.json` with device management to:

| Platform | Generated artifact | Managed location |
| --- | --- | --- |
| macOS | `macos/managed-settings.json` | `/Library/Application Support/ClaudeCode/managed-settings.json` |
| Linux/WSL | `linux/managed-settings.json` | `/etc/claude-code/managed-settings.json` |
| Windows | `windows/managed-settings.json` | `C:\Program Files\ClaudeCode\managed-settings.json` |

The files use generic `ANTHROPIC_BASE_URL` gateway mode, each platform's dynamic `apiKeyHelper`, its five-minute TTL, subprocess environment scrubbing, pinned models, and disabled nonessential traffic. The helper's dynamic credential bypasses the initial login prompt; do not set `forceLoginMethod`, because current Claude Code guidance says it conflicts with `apiKeyHelper`. No static token, API key, Foundry-native setting, shell profile, or per-user environment setup is generated.

Rollback: redeploy the previous managed file and helper with the same MDM/GPO tool, then restart Claude Code. Do not remove the managed file as a recovery mechanism; that can return the client to unmanaged or direct-provider settings.
