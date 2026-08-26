# Production readiness gates

## Automated evidence

- Shell syntax/ShellCheck, Python compile/unit tests, APIM XML/semantic assertions.
- Complete policy named-value closure and credential-order checks.
- OpenTofu formatting, provider-lock validation, and configuration validation; `migration/bicep` remains a deprecated, non-authoritative reference until its removal gate.
- Separate model mappings, non-hardcoded fixed production capacity, optional second region, circuit breaker, zero-body diagnostics, deploy and smoke workflow checks.
- Local async SSE success/failure behavior and secret scanning.

## Customer gates before rollout

- Replace every example tenant, audience, Foundry account/URL, model deployment, region, DNS, network, and alert destination.
- Confirm model/version/deployment-type pinning and effective Global Standard/Data Zone quota scope.
- Use fixed-capacity, public, single-region `StandardV2` by default. Validate `PremiumV2` availability only when zone redundancy or private VNet injection is selected; two units are recommended for zone-redundancy outage headroom, not required.
- During adoption, set `APIM_SKU` and `APIM_ZONE_REDUNDANT` explicitly to the live resource values; do not use the new baseline defaults to retier an existing APIM instance.
- Configure GitHub `poc` and protected `prod-primary` environments, immutable OIDC subject claims, required reviewers, deployment identity, and smoke identity app-role assignment.
- Review the sanitized OpenTofu plan summary and require the first imported plan to contain no unapproved changes.
- Deploy and smoke both routes and every enabled region; validate MI RBAC, token expiry refresh, caller isolation, per-user fairness, PoC throttling, optional DNS failover, private DNS, and circuit behavior.
- Execute measured 500–2,500 synthetic plateaus and separately approved Foundry load.
- For externally supplied Application Insights, confirm local authentication is disabled and existing producers remain compatible.
- For customer-owned direct Foundry, verify `disableLocalAuth=true` (or document an approved shared-account exception), old keys are rejected after propagation, and no unintended identities retain direct inference RBAC.
- Approve SLOs, RTO/RPO, capacity, quota, alert thresholds, incident ownership, rollback, and client version rollout. An Action Group is optional in IaC, but an approved, tested incident destination is required for release.
- Require explicit measured `per-user < aggregate < 2048` approximate per-gateway admission values, with approved operational headroom below the ceiling; production has no compatibility defaults.
- Retain CI, Foundry preflight, sanitized OpenTofu plan summary, deployment output, smoke, and HA evidence artifacts for 90 days. Never retain raw state or plan JSON.
- Verify generated managed Claude Code settings and helpers on macOS/Linux/WSL pilots; native Windows requires a customer-provided, pilot-tested executable helper before expansion.
- For private networking, deployment success is not release approval: retain successful in-network `ha-smoke` evidence before release.

This sandbox performed no Azure deployment or live Claude Code/Foundry call. Compilation is necessary but is not evidence for a controlled 500+ developer rollout.
