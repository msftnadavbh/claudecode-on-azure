# Production readiness gates

## Automated evidence

- Shell syntax/ShellCheck, Python compile/unit tests, APIM XML/semantic assertions.
- Complete policy named-value closure and credential-order checks.
- OpenTofu formatting, provider-lock validation, and configuration validation; Bicep remains compile-only rollback reference during stabilization.
- Separate model mappings, non-hardcoded fixed production capacity, optional second region, circuit breaker, zero-body diagnostics, deploy and smoke workflow checks.
- Local async SSE success/failure behavior and secret scanning.

## Customer gates before rollout

- Replace every example tenant, audience, Foundry account/URL, model deployment, region, DNS, network, and alert destination.
- Confirm model/version/deployment-type pinning and effective Global Standard/Data Zone quota scope.
- Validate Premium v2 and zone-redundancy availability in each selected region. Premium v2 uses its zone-redundancy property, so production requires at least two units but not classic-tier zone-count multiples.
- Configure GitHub `poc` and protected `prod-primary` environments, immutable OIDC subject claims, required reviewers, deployment identity, and smoke identity app-role assignment.
- Review the sanitized OpenTofu plan summary and require the first imported plan to contain no unapproved changes.
- Deploy and smoke both routes and every enabled region; validate MI RBAC, token expiry refresh, caller isolation, per-user fairness, PoC throttling, optional DNS failover, private DNS, and circuit behavior.
- Execute measured 500–2,500 synthetic plateaus and separately approved Foundry load.
- Approve SLOs, RTO/RPO, capacity, quota, alert thresholds, incident ownership, rollback, and client version rollout.
- Require `per-user < aggregate < 2000` concurrency values from the approved capacity record; production has no compatibility defaults.
- Retain CI, Foundry preflight, sanitized OpenTofu plan summary, deployment output, smoke, and HA evidence artifacts for 90 days. Never retain raw state or plan JSON.
- Verify generated managed Claude Code settings and helpers on Windows, macOS, and Linux pilots before expanding beyond the canary group.

This sandbox performed no Azure deployment or live Claude Code/Foundry call. Compilation is necessary but is not evidence for a controlled 500+ developer rollout.
