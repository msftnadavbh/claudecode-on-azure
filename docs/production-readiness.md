# Production readiness gates

## Automated evidence

- Shell syntax/ShellCheck, Python compile/unit tests, APIM XML/semantic assertions.
- Complete policy named-value closure and credential-order checks.
- Bicep and PoC/production parameter compilation.
- Separate model mappings, non-hardcoded production capacity, second region, circuit breaker, zero-body diagnostics, deploy and smoke workflow checks.
- Local async SSE success/failure behavior and secret scanning.

## Customer gates before rollout

- Replace every example tenant, audience, Foundry account/URL, model deployment, region, DNS, network, and alert destination.
- Confirm model/version/deployment-type pinning and effective Global Standard/Data Zone quota scope.
- Validate Premium v2 and zone-redundancy availability in both selected regions. Premium v2 distributes units automatically, so production requires at least two units but not classic-tier zone-count multiples.
- Configure GitHub `poc` and protected `prod-primary` environments, immutable OIDC subject claims, required reviewers, deployment identity, and smoke identity app-role assignment.
- Review deployment what-if to prove no Foundry mutation beyond role assignments.
- Deploy and smoke both routes/regions, validate MI RBAC, token expiry refresh, caller isolation, per-user fairness, PoC throttling, DNS failover, private DNS, and circuit behavior.
- Execute measured 500–2,500 synthetic plateaus and separately approved Foundry load.
- Approve SLOs, RTO/RPO, capacity, quota, alert thresholds, incident ownership, rollback, and client version rollout.

This sandbox performed no Azure deployment or live Claude Code/Foundry call. Compilation is necessary but is not evidence for a controlled 500+ developer rollout.
