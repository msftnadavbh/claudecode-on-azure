# Claude Desktop Managed Configuration (OPTIONAL / PREVIEW)

Claude Desktop is optional and preview-only; the baseline deployment works with Desktop disabled and without Desktop inputs. This generator creates OS-native third-party gateway managed configuration. It writes files only; it does not install Claude Desktop, import a profile, or change the registry.

Official references: [third-party gateway / enterprise configuration](https://support.claude.com/en/articles/12622667-enterprise-configuration-for-claude-desktop) and the [Claude Desktop configuration/deployment reference](https://support.claude.com/en/articles/12622703-deploy-claude-desktop-for-windows) ([macOS](https://support.claude.com/en/articles/12611117-deploy-claude-desktop-for-macos)).

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

The stable deployment organization UUID namespaces local Desktop data and deterministically derives profile UUIDs. Do not change it after rollout.

## Hard prerequisites

- Assign the Desktop enterprise application to the pilot users/groups.
- Register the Desktop client as an Entra public client with redirect URI `http://127.0.0.1/callback`; grant admin consent for the exact delegated scope passed to `--delegated-scope`.
- Enable the same scope at APIM with `CLAUDE_DESKTOP_DELEGATED_AUTH_ENABLED=true`, `CLAUDE_DESKTOP_CLIENT_ID`, and `CLAUDE_DESKTOP_DELEGATED_SCOPE`. The APIM variable is the short `scp` claim value, such as `Claude.Access`; `--delegated-scope` is its full URI.
- On each pinned Desktop-version canary, capture **Help > Troubleshooting > Copy Managed Configuration Report**, verify an inference request, then verify token refresh and that access is denied after assignment or consent revocation.

Generated files:

- `claude-desktop-managed.mobileconfig`: macOS system configuration profile for `com.anthropic.claudefordesktop`.
- `claude-desktop-managed.reg`: Windows UTF-16LE policy for `HKLM\SOFTWARE\Policies\Claude`.
- `claude-desktop-managed-remove.reg`: Windows UTF-16LE removal policy that deletes that policy key.

Deploy the profile or registry file with the organization's MDM tooling, then fully quit and reopen Claude Desktop. Users authenticate through the system browser with authorization code plus PKCE; Desktop sends the resulting access token as a bearer token to the gateway and refreshes it through OIDC. The generated configuration contains no API key, token, helper path, or other static credential.

The documented core inference/OIDC/model keys are `inferenceCredentialKind`, `inferenceGatewayAuthScheme`, `inferenceGatewayBaseUrl`, `inferenceGatewayOidc`, `inferenceGatewayOidcAuthFlow`, `inferenceModels`, and `inferenceProvider`. The local workspace and tool-hardening keys are documented in the configuration reference, but must be canary-validated against the pinned Desktop version before rollout.

The Windows removal file is intentionally separate and should be deployed only when retiring this entire Claude policy key.
