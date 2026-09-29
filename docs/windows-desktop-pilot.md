# Windows Desktop Opus 5.5 pilot — local Gateway mode

## Current path: no registry or new consent required

The Windows host has an applied local Gateway configuration in `%LOCALAPPDATA%\Claude-3p\configLibrary\7c3f7918-d444-45f0-8a55-172cb6d8dcaa.json`. It uses `helper-script` and now selects `claude-opus-5-5`. Registry/MDM delivery is optional, not a prerequisite for this single-device test.

A separate native Windows Entra helper was installed at `%LOCALAPPDATA%\claudecodepoc\desktop-entra-pilot.cmd` with its PowerShell implementation alongside it. Its fixed arguments select the existing pilot tenant/audience, and it privately obtains a JWT from native Windows Azure CLI. It does not use the old helper's subscription-key path and does not change Azure CLI defaults. Both the helper check and native Desktop Chat inference passed.

After confirming Desktop was fully stopped, the applied JSON was backed up as `7c3f7918-d444-45f0-8a55-172cb6d8dcaa.pre-entra-opus55.bak` in the same directory. Only the helper path, TTL (240 seconds), explicit bearer auth scheme, and existing model entry were changed. The applied configuration ID and unrelated settings were preserved. APIM needed **no change** because it already accepts the Azure CLI token and strictly checks the pilot user, role, scope and audience.

Native Claude Desktop `2.7032.0.0` was relaunched through its registered Windows application identity. The model picker displayed **Opus 5.5 via Microsoft Foundry**. A new chat requesting exactly `WINDOWS_DESKTOP_OPUS55_OK` returned that exact response. Its installed embedded Claude Code engine is `2.1.280`, meeting the observed model minimum. Neither HKLM nor HKCU policy was created. This verifies Desktop **Chat**; Code-tab tool workflows, Cowork, long-lived refresh, and revocation were not tested in this check.

The active local configuration leaves Code and Cowork enabled by their defaults; both are untested. Hardening options from the separately generated MDM profile were **not applied** to this existing local configuration.

The dedicated Desktop public-client app described below was prepared for the alternative browser-OIDC route. It remains unused and unactivated at APIM. Its consent denial does not block the existing helper route; do not use preauthorization or another privilege change to bypass that denial.

## Earlier MDM/OIDC preparation (not applied)

### Earlier preparation checks

- Host: Windows 11 Pro, build 26300, reached through WSL interop.
- Signed-in Windows account: `MIDDLEEAST\nadavbh`.
- Installed native MSIX: Claude `2.7032.0.0`.
- Neither HKLM nor HKCU Claude policy was present during preparation.
- Generated Windows configuration uses HKCU, UTF-16LE/CRLF, string values, and OIDC access tokens. Both Windows files were copied and hash-checked at `C:\Users\nadavbh\Downloads\Claude-Opus-5.5-Pilot`.
- Chat and Code are enabled; Cowork is disabled pending virtualization/readiness verification. All three model tiers map to `claude-opus-5-5`, not cheaper separate models.

### Alternative identity prepared, not yet authorized by the gateway

- Tenant: `16b3c013-d300-468d-ac64-7eda0820b6d3` (`fdpo.onmicrosoft.com`). Azure changes remain restricted to subscription `68eab0d1-ab81-4851-b2dd-173dede87582`.
- Desktop native client: `0fe8735f-c1ae-4716-8338-d86b2615851f` (`claudecode-project-test-01-desktop-pilot`).
- Client application object: `17ed3100-5de7-4116-a074-0a42cbf1edfd`; Desktop client service principal: `29d2c195-9e48-47c8-8a77-b5d6abf938c0`.
- Existing gateway resource service principal: `802f51c7-08a3-48df-a6b1-c97b0e8ed3db`; preserve its user role assignment when rolling back Desktop.
- Native redirect: `http://127.0.0.1/callback`; no client secret.
- Assignment required; only the existing pilot user was assigned.
- Requested scope: `api://810dcce2-fcdd-4675-906e-b2aea60afe0e/AiGateway.Invoke`.
- Stable Desktop deployment organization UUID: `5c4a2a63-8fbc-4aef-88d0-9445cf041fd9`.
- Programmatic per-user consent was rejected with `Authorization_RequestDenied`. No wider grant, preauthorization workaround, or directory privilege change was attempted.

### Alternative OIDC activation steps — not needed for the working helper route

1. Import `claude-desktop-managed.reg` under the intended Windows user's identity with permission to write HKCU policy. Current permissions are read-only; use approved elevation for that same account, not a different administrator's HKCU. Recheck that HKLM policy remains absent. No registry changes have been made yet.
2. Create the permitted workspace `%USERPROFILE%\Documents\Claude`. This host's shell Documents folder is redirected to OneDrive; the profile's `~/Documents/Claude` is deliberately a different path.
3. Open Claude Desktop and verify third-party managed configuration. Sign in using the assigned pilot Entra account. The user must complete consent/MFA; if tenant policy requires administrator consent, stop for the Entra administrator.
4. Verify access-token issuance for the gateway audience, preserving v1 resource-token format and the exact scope/role/user. Do not capture tokens, browser cookies, authorization codes, or authenticated HAR files.
5. Review and apply only the extra Desktop client ID in the existing APIM validator's client allowlist. Preserve CLI access and the exact tenant/audience/version plus user AND role AND scope restrictions. Do not deploy the repository's broader role-OR-Desktop policy.
6. Verify native Chat/Code inference and streaming against Opus 5.5, installed embedded engine compatibility (the tested CLI minimum is 2.1.280), and CLI regression. Desktop package version alone does not prove engine readiness. Refresh, revocation and Cowork require separate tests.

The live gateway continues to allow the Azure CLI application identity, which is also used by the working Desktop helper route. The unused OIDC client is not allowlisted. The generated registry files are not evidence for the OIDC path and should not be imported for this local helper setup.

## Rollback

For the active local helper configuration, fully quit Desktop before restoring the adjacent JSON backup. The old helper uses subscription keys and may not work against the current JWT-protected API; restoring its configuration is not service restoration. Preserve APIM's current JWT protection and use the verified standalone CLI if troubleshooting.

Sign out before removing configuration. The removal file deletes only generated values; it does not delete the whole policy key, restore overwritten values, or clear token caches. Snapshot any existing policy before import. Remove only the Desktop client ID from APIM if activated; keep the CLI-only JWT policy on the keyless API. Disable/remove only the dedicated Desktop assignment/consent when appropriate.
