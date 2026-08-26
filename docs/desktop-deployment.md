# Claude Desktop preview

Generate managed Claude Desktop gateway configuration when you need the optional preview. You provide a Desktop enterprise app, a public-client registration with redirect URI `http://127.0.0.1/callback`, delegated consent, pilot devices, and endpoint management. Desktop is preview-only and disabled by default; this repository does not install Desktop, create its Entra registration, or make registry or profile changes.

```bash
python3 scripts/desktop/generate_managed_config.py \
  --gateway-url https://gateway.example/claude \
  --tenant-id 11111111-1111-1111-1111-111111111111 \
  --desktop-client-id 22222222-2222-2222-2222-222222222222 \
  --delegated-scope api://33333333-3333-3333-3333-333333333333/Claude.Access \
  --deployment-org-id 44444444-4444-4444-4444-444444444444 \
  --organization "Example Corp" \
  --sonnet-model sonnet-deployment --opus-model opus-deployment --haiku-model haiku-deployment \
  --output-dir out/desktop
```

Enable `CLAUDE_DESKTOP_DELEGATED_AUTH_ENABLED=true` only with `CLAUDE_DESKTOP_CLIENT_ID` and the short delegated-scope claim value in `CLAUDE_DESKTOP_DELEGATED_SCOPE`. Assign pilot users, grant consent for the exact full scope, and validate the generated profile/registry policy against the pinned Desktop version. Deploy generated files with MDM/GPO, verify its managed configuration report, then test inference, refresh, and revoked access before any expansion.
