# Claude Desktop Managed Configuration

This generator creates OS-native Claude Desktop on third-party managed configuration. It writes files only; it does not install Claude Desktop, import a profile, or change the registry.

```bash
python3 scripts/desktop/generate_managed_config.py \
  --gateway-url https://gateway.example/claude \
  --tenant-id 11111111-1111-1111-1111-111111111111 \
  --desktop-client-id 22222222-2222-2222-2222-222222222222 \
  --delegated-scope api://33333333-3333-3333-3333-333333333333/Claude.Access \
  --deployment-org-id 44444444-4444-4444-4444-444444444444 \
  --organization "Example Corp" \
  --sonnet-model sonnet-pinned \
  --opus-model opus-pinned \
  --haiku-model haiku-pinned \
  --output-dir out/desktop
```

The stable deployment organization UUID namespaces local Desktop data and deterministically derives profile UUIDs. Do not change it after rollout. The Desktop client must be an Entra public-client registration with the mobile/desktop redirect URI `http://127.0.0.1/callback` and delegated access to the exact scope passed above.

Enable the same scope at APIM with `CLAUDE_DESKTOP_DELEGATED_AUTH_ENABLED=true`, `CLAUDE_DESKTOP_CLIENT_ID`, and `CLAUDE_DESKTOP_DELEGATED_SCOPE`. The scope variable is the short `scp` claim value, such as `Claude.Access`, while `--delegated-scope` is its full URI.

Generated files:

- `claude-desktop-managed.mobileconfig`: macOS system configuration profile for `com.anthropic.claudefordesktop`.
- `claude-desktop-managed.reg`: Windows UTF-16LE policy for `HKLM\SOFTWARE\Policies\Claude`.
- `claude-desktop-managed-remove.reg`: Windows UTF-16LE removal policy that deletes that policy key.

Deploy the profile or registry file with the organization's MDM tooling, then fully quit and reopen Claude Desktop. Users authenticate through the system browser with authorization code plus PKCE; Desktop sends the resulting access token as a bearer token to the gateway and refreshes it through OIDC. The generated configuration contains no API key, token, helper path, or other static credential.

The policy enables Chat, Cowork, and Code under `~/Documents/Claude`; pins Sonnet, Opus, and Haiku deployment names with explicit family mappings; and disables model discovery, tool search, MCP, desktop extensions, WebSearch, WebFetch, bundled network-dependent skills, and agent tool egress.

Before broad rollout, inspect **Help > Troubleshooting > Copy Managed Configuration Report** on a pilot device and verify an inference request at the gateway. The Windows removal file is intentionally separate and should be deployed only when retiring this entire Claude policy key.
