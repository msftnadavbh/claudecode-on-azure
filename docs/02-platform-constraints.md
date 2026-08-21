# Verified platform constraints

Verified against first-party documentation on 2026-08-20:

- Generic gateway mode uses `ANTHROPIC_BASE_URL`; `apiKeyHelper` supplies the dynamic gateway credential.
- `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` strips Anthropic/cloud credentials from child environments but is not host-process isolation.
- Foundry deployment names, not marketing model aliases, are configured for Opus/Sonnet/Haiku.
- Foundry Claude Entra authentication uses scope `https://ai.azure.com/.default`; APIM therefore requests its managed-identity token with resource `https://ai.azure.com`.
- Anthropic support in APIM LLM policies requires a v2 tier, so PoC uses Basic v2.
- APIM is not a supported Traffic Manager Azure Endpoint resource type; public failover uses External Endpoints targeting APIM gateway FQDNs.
- APIM v2 scaling and alerting use `CpuPercent_Gateway`; the classic `Capacity` metric is unsupported for v2 tiers.
- Premium v2 zone redundancy is a creation-time `properties.zoneRedundant` setting in the current ARM preview schema; it does not use classic manual zone placement.
- Premium v2 `Internal` VNet injection isolates inbound and outbound traffic at creation and uses one dedicated subnet per APIM instance.
- `buffer-response="false"` is required for SSE; body logging stays at zero bytes.
- Premium v2 is deployed as separate regional services because it does not provide classic Premium geo-replication.
- Backend circuit breaking can propagate overload but must not blindly replay streaming POSTs.
- Global Standard and Data Zone quota scopes differ; additional resources do not imply additional effective quota.

References:

- [Claude Code on Microsoft Foundry](https://code.claude.com/docs/en/microsoft-foundry)
- [Connect Claude Code to an LLM gateway](https://code.claude.com/docs/en/llm-gateway-connect)
- [Claude Code environment variables](https://code.claude.com/docs/en/env-vars)
- [Foundry authentication and authorization](https://learn.microsoft.com/azure/foundry/concepts/authentication-authorization-foundry)
- [Use Claude models in Foundry](https://learn.microsoft.com/azure/foundry/foundry-models/how-to/use-foundry-models-claude)
- [APIM LLM token limit](https://learn.microsoft.com/azure/api-management/llm-token-limit-policy)
- [APIM v2 tiers](https://learn.microsoft.com/azure/api-management/v2-service-tiers-overview)
- [Enable APIM availability zones](https://learn.microsoft.com/azure/api-management/enable-availability-zone-support)
- [Inject Premium v2 APIM into a VNet](https://learn.microsoft.com/azure/api-management/inject-vnet-v2)
- [Traffic Manager endpoint types](https://learn.microsoft.com/azure/traffic-manager/traffic-manager-endpoint-types)
- [APIM capacity metrics](https://learn.microsoft.com/azure/api-management/api-management-capacity)
- [APIM backends](https://learn.microsoft.com/azure/api-management/backends)
- [APIM SSE](https://learn.microsoft.com/azure/api-management/how-to-server-sent-events)
