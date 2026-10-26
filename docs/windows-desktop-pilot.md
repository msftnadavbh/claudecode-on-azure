# Windows Desktop Opus 5.5 pilot — local Gateway mode

## Current path: no registry or new consent required

The Windows host has an applied local Gateway configuration in `%LOCALAPPDATA%\Claude-3p\configLibrary\7c3f7918-d444-45f0-8a55-172cb6d8dcaa.json`. It uses `helper-script` and now selects `claude-opus-5-5`. Registry/MDM delivery is optional, not a prerequisite for this single-device test.

A separate native Windows Entra helper was installed at `%LOCALAPPDATA%\claudecodepoc\desktop-entra-pilot.cmd` with its PowerShell implementation alongside it. Its fixed arguments select the existing pilot tenant/audience and the approved subscription account described below, and it privately obtains a JWT from native Windows Azure CLI. It does not use the old helper's subscription-key path and does not change Azure CLI defaults. Earlier helper and native Desktop Chat checks passed; the latest check's scope is recorded separately below.

After confirming Desktop was fully stopped, the applied JSON was backed up as `7c3f7918-d444-45f0-8a55-172cb6d8dcaa.pre-entra-opus55.bak` in the same directory. Only the helper path, TTL (240 seconds), explicit bearer auth scheme, and existing model entry were changed. The applied configuration ID and unrelated settings were preserved. APIM needed **no change** because it already accepts the Azure CLI token and strictly checks the pilot user, role, scope and audience.

Native Claude Desktop `2.7032.0.0` was relaunched through its registered Windows application identity. The model picker displayed **Opus 5.5 via Microsoft Foundry**. A new chat requesting exactly `WINDOWS_DESKTOP_OPUS55_OK` returned that exact response. Its installed embedded Claude Code engine is `2.1.280`, meeting the observed model minimum. Neither HKLM nor HKCU policy was created. This verifies Desktop **Chat**; Code-tab tool workflows, Cowork, long-lived refresh, and revocation were not tested in this check.

The active local configuration leaves Code and Cowork enabled by their defaults; both are untested. Hardening options from the separately generated MDM profile were **not applied** to this existing local configuration.

### 2026-10-19 helper diagnostics and account selection

The native Windows CLI default was `ME-MngEnvMCAP304024-nadavbh-1` (`864c2aac-c1e8-4240-a855-8d9b00ceee7a`). Its cached account selector differed from the gateway subscription, `MCAPS-Hybrid-REQ-162389-2026-nadavbh` (`68eab0d1-ab81-4851-b2dd-173dede87582`). An explicit `--tenant` did not select that gateway account; the old helper still used the default account and its protected probe returned `AADSTS530036`.

With approval, the installed CMD now uses the absolute Windows PowerShell path and adds `-SubscriptionId` for the gateway subscription, preserving its fixed tenant/audience. The revised PS1 validates that subscription's cached tenant, user-account type, public cloud and enabled state before acquiring its token. It reports only fixed redacted diagnostics and never changes the global default. Installation preserved file ACLs and the Desktop profile, with code-only backups named `desktop-entra-pilot.ps1.pre-diagnostics-20261019T112713Z.bak` and `desktop-entra-pilot.cmd.pre-diagnostics-20261019T112713Z.bak` alongside the helper.

The installed CMD then passed a protected check: exit 0, one valid raw-token output, empty stderr, **12.099s**, and the original global default unchanged. No interactive login, cache clearing, policy change, or cloud deployment was needed. Installed PS1 SHA-256: `b5fbff4e15ee2d21384872d295c79c5fab841bcd8e6705848cb7f05482694fca`. The native fake suite had 18 passing methods and the separately documented expected caller-EOF availability failure; see [managed settings](claude-code-managed-settings.md).

Desktop relaunch was requested through `Claude_pzs8sxrjxfjjc!Claude`. The protected helper check proves token acquisition, not current Chat/Code inference or APIM authorization; those still require a GUI retry. The historical Chat verification above is not a new end-to-end result.

### Local metadata recovery after a Desktop update

In Desktop `2.9939.4`, the observed configuration editor uses `entries.map`, while the runtime uses `appliedId` to select the applied JSON. A missing `entries` in `configLibrary/_meta.json` can therefore break the editor even when the applied Gateway profile is intact. This script only repairs that missing index; it does not alter the profile, credentials, policy, or gateway. The earlier live metadata repair kept the applied profile hash unchanged and Desktop was relaunched; GUI error clearance has **not** been verified.

Manually **fully quit Claude Desktop first** (including background instances); this script does not check processes and cannot prevent concurrent writes. From a native Windows command prompt with Python installed, run from this repository:

```cmd
py -3 scripts\desktop\repair_config_metadata.py
```

The default directory is `%LOCALAPPDATA%\Claude-3p\configLibrary`; if using another local copy, pass `--config-dir "C:\path\to\configLibrary"`. Optional `--name "Gateway"` controls only a newly created entry name. The script requires an existing canonical UUID `appliedId` and a readable JSON-object applied profile, refuses malformed or ambiguous indexes and multiple UUID profiles, and never creates the config directory. It writes the original metadata bytes once to the exclusive backup `%LOCALAPPDATA%\Claude-3p\configLibrary-meta.backup.json` (outside `configLibrary`); if that file already exists, stop and inspect it rather than overwrite it. A valid existing index is left byte-for-byte unchanged. After repair, relaunch Desktop manually and verify the configuration editor and actual Chat behavior in the GUI; successful script execution alone does not prove the GUI error is clear. To roll back, fully quit Desktop again, inspect the backup, and restore its original bytes to `_meta.json` manually.

The dedicated Desktop public-client app described below was prepared for the alternative browser-OIDC route. It remains unused and unactivated at APIM. Its consent denial does not block the existing helper route; do not use preauthorization or another privilege change to bypass that denial.

### 2026-10-26 discovery — configured/API-verified

With approval, only two keys in the existing active local profile `%LOCALAPPDATA%\Claude-3p\configLibrary\7c3f7918-d444-45f0-8a55-172cb6d8dcaa.json` changed: `modelDiscoveryEnabled` is the **string** `"true"`, and `inferenceModels` was removed. The helper/authentication, TTL **240**, profile ID, `_meta` and ACLs were unchanged. No registry/MDM or alternative OIDC configuration was applied.

The exact original private backup is adjacent: `7c3f7918-d444-45f0-8a55-172cb6d8dcaa.json.pre-discovery-76944aac-26bc-4106-a2fd-afcf8c11aec0.bak`. Profile SHA-256 before: `e4387a636ab6c7fcb06baa5635d4c9364483e67ed258f184e837df7c54905e9a`; after: `90a0090d16c8ec0621eab27f29614a74f6161be8bddfe526f4aa5958f2c98bb9`.

The lead's offline check of the actual installed Desktop **2.42304.2.0** parser/raw configuration loader proved string `"true"` plus no `inferenceModels` selects discovery and preserves the default Opus 5.5 pin with the reviewed native fields. The existing installed helper also authorized both live catalog GET forms; [the bounded publication record](model-discovery.md#2026-10-26-bounded-live-pilot--configuredapi-verified) records exact API checks, static catalog, unchanged cloud resources and private audit evidence. This does not auto-refresh Azure inventory or prove other family aliases/refusal fallback.

**Desktop was neither launched nor quit during this change and remains closed. The user must open it.** The UI picker, startup inference and end-to-end behavior were not verified; no Messages/count-tokens/inference calls were made. This is one PC configured/API-verified, not fleet enablement or a new Chat success. Recovery must use the matching discovery backup and verified profile/metadata/helper/ACL baseline with Desktop closed and a reviewed plan; user/app drift requires manual review. Retain the adjacent backup privately, not in Git.

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

For the active local helper configuration, follow the guarded recovery boundary in the 2026-10-26 entry above; do not blindly restore an older adjacent backup. Fully quit Desktop and verify the matching profile/metadata/helper/ACL baseline and current state before any reviewed restoration. The old helper uses subscription keys and may not work against the current JWT-protected API; restoring its configuration is not service restoration. Preserve APIM's current JWT protection and use the verified standalone CLI if troubleshooting.

Sign out before removing configuration. The removal file deletes only generated values; it does not delete the whole policy key, restore overwritten values, or clear token caches. Snapshot any existing policy before import. Remove only the Desktop client ID from APIM if activated; keep the CLI-only JWT policy on the keyless API. Disable/remove only the dedicated Desktop assignment/consent when appropriate.
