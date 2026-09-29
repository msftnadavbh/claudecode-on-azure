# Opus 5.5 local pilot

## Verified target

- Subscription: `68eab0d1-ab81-4851-b2dd-173dede87582` only.
- Tenant: `fdpo.onmicrosoft.com` (`16b3c013-d300-468d-ac64-7eda0820b6d3`).
- Resource group/region: `claudepoc-rg`, `eastus2`.
- Gateway: `https://apim-claudecode-project-test-01.azure-api.net/claude`, existing API ID `claude-api`.
- Foundry: `project-test-01`, project `proj-default`.
- New deployment: `claude-opus-5-5`, Anthropic version `2` (hosted on Azure), GlobalStandard capacity `40`, `NoAutoUpgrade`.
- Existing `claude-opus-5` deployment retained unchanged. GlobalStandard does not guarantee processing only in East US 2; inference is billable.

## Pilot authentication

Dedicated application `claudecode-project-test-01-gateway-pilot`, client ID `810dcce2-fcdd-4675-906e-b2aea60afe0e`, exposes audience `api://810dcce2-fcdd-4675-906e-b2aea60afe0e` and delegated scope `AiGateway.Invoke`.

APIM requires the exact tenant/audience, v1 token, Azure CLI client, `Gateway.Invoke` role, delegated scope, and the assigned pilot user's object ID. Assignment is required on the resource service principal. No shared key or client secret is saved in Claude configuration. APIM retains managed-identity authentication to Foundry. Subscription-key-only callers no longer have access; widening this pilot to other users/CI requires a reviewed authorization change.

This was a surgical update of the existing API, not a full OpenTofu deployment or adoption. **Do not redeploy older Bicep or apply the current OpenTofu configuration blindly:** API/backend identifiers and authorization differ. Reconcile the pilot changes into the owning infrastructure first. Protected rollback snapshots remain local outside the repository; restoring the original no-JWT policy requires restoring and verifying subscription-key protection first.

On this workstation, durable rollback snapshots and redacted gateway probe results are stored in `~/.local/state/claude55-rollback/` (directory mode 0700).

## Local Claude Code

Opus 5.5 rejected Claude Code `2.1.243` with an explicit minimum-version error (`2.1.280`). Local Claude Code was updated to **2.1.283** and the isolated, explicit-model canary succeeded.

The saved configuration also passed a separate real invocation with subprocess scrubbing enabled and credentials supplied only by the helper. Claude Code required bubblewrap on this Linux host; Ubuntu package `0.9.0-1ubuntu0.3` was extracted under `~/.local/lib/claude-bubblewrap`, with `~/.local/bin/bwrap` pointing to its executable. No sudo or disabling of scrubbing was needed. This user-local package requires manual updates.

Project-local `.claude/settings.local.json` selects the gateway, Entra helper and deployment. Start `claude` from this repository. Global user settings are unchanged. For this single-model pilot, Opus, Sonnet and Haiku aliases all resolve to **Opus 5.5**; they are not separate cheaper deployments.

The helper uses the existing Azure CLI login in the locked tenant. It is noninteractive and returns only the token. Reauthenticate through the approved Azure login flow if the session expires; do not substitute a static key.

Nonessential traffic is disabled, so maintain Claude Code manually with `claude update`. The existing APIM subscription remains active for rollback, but its key alone cannot bypass Entra validation. Retire or rotate that subscription separately after the pilot is stable.

## Evidence and limits

- With keys still required: both operations rejected missing/wrong-audience JWTs (401) and accepted the pilot JWT (200) against Opus 5.
- After keyless cutover: the same checks passed against both Opus 5 and Opus 5.5.
- Local isolated Claude Code canary returned the exact synthetic response and reported only `claude-opus-5-5`.
- A separate native streaming request through APIM returned 200 and passed the complete-record SSE validator.
- No second-principal 403 test, long-lived token refresh test, load test, or fleet rollout certification was performed.
- Full repository governance policies (monthly quotas, concurrency controls, Desktop authorization) were not deployed as part of this focused pilot.

Subsequently, [native Windows Desktop Chat](windows-desktop-pilot.md) succeeded through a local Gateway helper-script configuration without registry policy or a new OIDC client. A [temporary operation-level monthly quota](live-budget-demo.md) was separately tested and removed; neither event constitutes full repository policy or OpenTofu deployment validation. Code-tab tools, Cowork, long-lived refresh and revocation remain untested.
