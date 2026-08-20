# Complexity Reduction Plan

The production baseline is one fixed-capacity, zone-redundant Premium v2 APIM instance, one Foundry target, Entra user authentication, managed-identity backend authentication, and one telemetry plane. Operators add capabilities only when measured requirements justify them.

| Classification | Capability | Decision and tradeoff |
| --- | --- | --- |
| KEEP | Entra per-user access, APIM governance, Foundry, native Messages API, `apiKeyHelper`, model pinning, managed identity, credential stripping, SSE, zero-body logging, circuit breaker, OIDC, synthetic load tests | These are the security, compatibility, reliability, and deployment boundaries. |
| KEEP | Local `GET /claude/health` and built-in `Foundry User` | Health remains free of inference cost. The built-in role is broader than inference-only; use a customer-managed custom role only when security review requires its lifecycle. |
| SIMPLIFY | Production topology and Foundry configuration | Production defaults to one APIM. A secondary APIM defaults to the same Foundry account/deployment, avoiding duplicate model synchronization. A separate target remains an explicit parameter override. |
| SIMPLIFY | Premium v2 zones and private networking | `properties.zoneRedundant` replaces manual zone placement. Private mode uses creation-time `Internal` VNet injection and one subnet, removing the APIM private endpoint and second service update. Customers needing the older PE plus outbound-integration topology can maintain it as a separate networking overlay. |
| SIMPLIFY | Per-user controls | Generation uses RPM and token limits. Token counting uses only RPM. Hourly request quotas are removed because request count is a poor proxy for model cost. Add a business-specific quota policy only when required. |
| SIMPLIFY | Observability | All APIM regions share one workspace and Application Insights component by default. Existing shared resource IDs are accepted; separate regional telemetry remains a customer compliance overlay. |
| OPTIONAL | Secondary APIM, Traffic Manager, autoscale, separate secondary Foundry, private networking | HA requires `deploySecondary`; public DNS failover additionally requires `trafficManagerEnabled`. Start at measured fixed capacity and enable autoscale only for sustained utilization. Private HA uses customer DNS. |
| REMOVE | Forced dual region, manual zone arrays/count arithmetic, APIM private endpoint/DNS/lockdown module, per-APIM telemetry, default hourly quota | These mechanisms added resources, deployment coupling, or policy overlap without improving the baseline boundary. |

Progression: **PoC -> production baseline -> optional HA -> optional private networking -> customer-specific advanced security**.
