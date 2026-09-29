# Production readiness

Use this checklist before rollout. You need a deployed validation environment and accountable platform, security, network, Foundry, and endpoint-management owners. Passing repository checks or a smoke test is not evidence of production scale, SLOs, quota, or failover.

## Required evidence

- Foundry account, three pinned deployment names in existing mode or the one mapped deployment in greenfield mode, effective quota and headroom, and a direct Foundry local-auth/RBAC review.
- Entra audience, role assignments, token refresh, caller isolation, APIM managed-identity `Foundry User`, and no client static credential.
- Protected GitHub environments/reviewers, immutable OIDC federation, external versioned/soft-deleted Blob state, reviewed source/inputs/summary, and no destructive plan.
- Measured APIM capacity and selected `per-user < aggregate < 2048` gateway-local admission limits; separate approved Foundry load evidence.
- Alert destination, safe diagnostics, incident ownership, client rollback, and last-known-good non-destructive OpenTofu rollback rehearsal.
- Managed Claude Code pilots on macOS/Linux/WSL; pilot the bundled native Windows `.cmd`/`.ps1` helper on Windows before expansion (Linux tests skip native execution). Desktop Chat's local helper pilot is not certification of Code-tab tools or Cowork.
- On each pinned OS/client version, keep `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` enabled and verify that the actual helper child receives the expected nonsecret `APIM_TENANT_ID`/`APIM_AUDIENCE`, then completes inference. Retain only allowlisted match results/version metadata, never environment dumps or credentials. Managed settings do not populate parent shells; standalone tools need launch-environment values. Failed inheritance stops rollout, not scrubbing or tenant enforcement.
- Live APIM policy compilation and TPM enforcement/streaming accounting validation are required **even when monthly quota is zero**. APIM compiles both branches; a disabled quota cannot hide invalid policy syntax. Separately validate enabled monthly quota/accounting, prompt-cache effects, and concurrent-request overshoot/gateway-local counters; do not infer any of these from a successful smoke request.
- If Desktop is enabled, record client/resource Entra app identities, external assignment-required configuration and delegated consent, and actual assigned/unassigned role-free user tests. Removal of assignment/consent is not proof of immediate revocation of already-issued tokens; retain expiry/refresh/revocation pilot evidence.
- Public smoke for public topology; retained in-network `ha-smoke` evidence for private deployment and any HA release.
- Approved SLOs, RTO/RPO, DNS and certificate ownership, and an operator traffic procedure where applicable.

Run `scripts/test/validate.sh`, Foundry preflight, protected deployment evidence, and client canaries as inputs to—not replacements for—these approvals.

The [focused Opus 5.5/CLI pilot](opus-5-5-pilot.md), [Desktop Chat pilot](windows-desktop-pilot.md), and [temporary quota rehearsal](live-budget-demo.md) do not establish full IaC adoption, global accounting, token-refresh behavior, or production readiness.
