# Production readiness

Use this checklist before rollout. You need a deployed validation environment and accountable platform, security, network, Foundry, and endpoint-management owners. Passing repository checks or a smoke test is not evidence of production scale, SLOs, quota, or failover.

## Required evidence

- Foundry account, three pinned deployment names in existing mode or the one mapped deployment in greenfield mode, effective quota and headroom, and a direct Foundry local-auth/RBAC review.
- Entra audience, role assignments, token refresh, caller isolation, APIM managed-identity `Foundry User`, and no client static credential.
- Protected GitHub environments/reviewers, immutable OIDC federation, external versioned/soft-deleted Blob state, reviewed source/inputs/summary, and no destructive plan.
- Measured APIM capacity and selected `per-user < aggregate < 2048` gateway-local admission limits; separate approved Foundry load evidence.
- Alert destination, safe diagnostics, incident ownership, client rollback, and last-known-good non-destructive OpenTofu rollback rehearsal.
- Managed Claude Code pilots on macOS/Linux/WSL; your pilot-tested native Windows helper before Windows expansion. Desktop only if its preview gates pass.
- Public smoke for public topology; retained in-network `ha-smoke` evidence for private deployment and any HA release.
- Approved SLOs, RTO/RPO, DNS and certificate ownership, and an operator traffic procedure where applicable.

Run `scripts/test/validate.sh`, Foundry preflight, protected deployment evidence, and client canaries as inputs to—not replacements for—these approvals.
