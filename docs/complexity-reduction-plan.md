# Complexity Reduction Plan

The production baseline is one fixed-capacity public Standard v2 APIM instance, one Foundry target, Entra user authentication, managed-identity backend authentication, and one telemetry plane. Operators add capabilities only when measured requirements justify them.

| Classification | Capability | Decision and tradeoff |
| --- | --- | --- |
| KEEP | Claude Code primary client baseline; Entra per-user access, APIM governance, Foundry, native Messages API, `apiKeyHelper`, model pinning, managed identity, credential stripping, SSE, zero-body logging, 5xx-only circuit breaker, OIDC, synthetic load tests | These are the security, compatibility, reliability, and deployment boundaries. The starting circuit rule is 50 backend 5xx responses per minute; it never trips on 429 and never retries POSTs. |
| KEEP | Local `GET /claude/health` and built-in `Foundry User` | Health remains free of inference cost. The built-in role is broader than inference-only; use a customer-managed custom role only when security review requires its lifecycle. |
| SIMPLIFY | Production topology and Foundry configuration | Production is one fixed-capacity, public, single-region `StandardV2` APIM. A secondary APIM defaults to the same Foundry account/deployment, avoiding duplicate model synchronization. A separate target remains an explicit parameter override. |
| SIMPLIFY | Premium v2 zones and private networking | Use `PremiumV2` only for `properties.zoneRedundant` or creation-time `Internal` VNet injection. Customers needing the older PE plus outbound-integration topology can maintain it as a separate networking overlay. |
| SIMPLIFY | Deployment authority | OpenTofu is the active, preferred deployment path. Workflow apply regenerates from the same commit and inputs, verifies redacted planned-change digests, then applies the verified equivalent plan. |
| SIMPLIFY | Per-user controls | Generation uses RPM and token limits. Token counting uses only RPM. Hourly request quotas are removed because request count is a poor proxy for model cost. Add a business-specific quota policy only when required. |
| SIMPLIFY | Observability | All APIM regions share one workspace and Application Insights component by default. Existing shared resource IDs are accepted; separate regional telemetry remains a customer compliance overlay. |
| OPTIONAL | Claude Desktop preview, secondary APIM, Traffic Manager, separate secondary Foundry, Premium v2 zone redundancy, private networking, Action Group actions | Desktop requires official-configuration, managed-report, inference, refresh, and revocation canaries on the pinned version. HA requires `deploy_secondary`; public DNS failover additionally requires `traffic_manager_enabled`. Action Group wiring is optional in IaC, but release requires an approved, tested incident destination. |
| REMOVE | Forced dual region, manual zone arrays/count arithmetic, APIM private endpoint/DNS/lockdown module, per-APIM telemetry, default hourly quota, Bicep deployment authority | These mechanisms added resources, deployment coupling, or policy overlap without improving the baseline boundary. `migration/bicep` remains a deprecated, non-authoritative reference only. |

Progression: **PoC -> production baseline -> optional HA -> optional private networking -> customer-specific advanced security**.

**Final Bicep removal gate:** remove `migration/bicep` only after PoC and production imports, two zero-change plans, the first successful OpenTofu apply, and a rollback rehearsal.
