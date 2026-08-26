# Managed Claude Code settings

Generate non-secret, platform-specific Claude Code configuration for device management. You need the gateway URL, Entra audience, three Foundry deployment names, and managed helper paths. Generation writes files only; device management installs them, sets permissions, pins versions, updates, and rolls back. You provide a native Windows helper.

```bash
python3 scripts/claude_code/generate_managed_settings.py \
  --gateway-url https://gateway.example/claude \
  --audience api://gateway-app-id \
  --macos-helper-path "/Library/Company/Claude/apim-user-token-helper.sh" \
  --linux-helper-path /opt/company/claude/apim-user-token-helper.sh \
  --windows-helper-path 'C:\Program Files\Company\Claude\apim-user-token-helper.exe' \
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

The bundled `scripts/auth/apim-user-token-helper.sh` is for macOS/Linux/WSL. Pilot your native Windows helper before any Windows rollout. Roll back by redeploying the prior settings and helper, then restarting Claude Code; do not remove management as a recovery shortcut.
