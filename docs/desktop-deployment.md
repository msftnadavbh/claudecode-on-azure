# Claude Desktop preview

Desktop is an optional preview. For a **local Gateway-mode `helper-script` pilot**, an [existing Windows Desktop configuration](windows-desktop-pilot.md) successfully used a native Entra helper and Chat without registry policy or a new OIDC client. That path still needs an authorized gateway token, installed helper and Azure CLI session; it did not test Code-tab tools, Cowork, refresh or revocation. The alternative managed **browser-OIDC** profile below requires a Desktop enterprise app, public-client registration with redirect URI `http://127.0.0.1/callback`, delegated consent, pilot devices, and endpoint management. This repository does not install Desktop, create its Entra registration, or apply registry/profile changes; generated OIDC files were not applied in the local pilot.

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

For the **OIDC branch only**, enable `CLAUDE_DESKTOP_DELEGATED_AUTH_ENABLED=true` with `CLAUDE_DESKTOP_CLIENT_ID` and the short delegated-scope claim value in `CLAUDE_DESKTOP_DELEGATED_SCOPE`. Assign pilot users, grant consent for the exact full scope, and validate the generated profile/registry policy against the pinned Desktop version. Deploy generated files with MDM/GPO, verify its managed configuration report, then test inference, refresh, and revoked access before any expansion. Do not apply the broader repository role-OR-Desktop policy blindly to the strict live CLI-only pilot.

For a **single Windows user-profile pilot**, append `--windows-scope user --disable-cowork` to the command above. This generates a UTF-16LE `.reg` targeting `HKEY_CURRENT_USER\SOFTWARE\Policies\Claude` and sets `coworkTabEnabled=false` in both Windows and macOS outputs (leave `--disable-cowork` off to retain the existing default). The default `--windows-scope machine` instead targets `HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Claude`; **any machine policy overrides the full user policy**, not only matching values. Confirm no machine policy before testing the user scope. Run the import only as the **pilot user's** Windows account (not an elevated different account); organizational policy may restrict writing HKCU policy values or require approved elevation, so stop and coordinate with endpoint management rather than importing into another account or hive. Restart Desktop, and check its managed-configuration report and actual login/inference. Windows 11 MSIX Desktop 2.7032 is a pilot host, not proof that the embedded Claude Code runtime meets the separate `>=2.1.280` model requirement; verify that runtime independently. A generated policy alone does not prove working auth or inference.

For rollback on a fresh pilot host, sign out of Desktop first, then import `claude-desktop-managed-remove.reg` under the **same scope and user**; it removes only generated value names and leaves other values in the policy key intact. Removing policy **does not delete cached tokens**; follow your organization's session/token revocation process separately. Import overwrites any existing values with the same names, and the removal file **does not restore overwritten values**. Back up existing policy values before importing; on a previously managed host use that backup to restore them instead of treating the removal file as a complete rollback. Neither file is imported by this generator.

The role-free Desktop branch checks client ID plus scope, **not user assignment**. Its access gate relies on external Entra assignment and consent controls. Identify separately the Desktop public-client registration/service principal (`CLAUDE_DESKTOP_CLIENT_ID`) and the gateway resource API registration/service principal (the audience app exposing the delegated scope). Entra owners must document and configure the applicable assignment-required settings, assigned users/groups, and delegated consent for this exact client/resource pair; this repository does not provision or verify those controls.

Require actual token-acquisition and inference tests for assigned and unassigned users without the gateway app role before rollout. Otherwise the role OR branch masks a Desktop assignment defect. Test both supported actor versions where used. Existing issued access tokens may remain valid after assignment or consent removal; test expiry, refresh and revoked access explicitly rather than promising immediate revocation.
