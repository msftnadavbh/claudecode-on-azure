# Platform constraints

These service limits shape the deployment. Validate current service availability, quota, and SKU support in your selected region. Documented constraints do not guarantee capacity or eligibility.

| Constraint | Implemented consequence |
| --- | --- |
| Claude Code gateway mode uses `ANTHROPIC_BASE_URL` and `apiKeyHelper` | Managed clients use a dynamic Entra token helper, not a static key. |
| Foundry uses deployment names | APIM allowlists three configured deployment names in existing mode; greenfield maps one managed deployment to all three roles rather than using marketing model labels. |
| SSE requires unbuffered responses | APIM forwards streaming responses with buffering disabled and diagnostics capture zero body bytes. |
| APIM v2 connection authority ceiling is 2,048 | Aggregate concurrent admission is configured below 2,048 per gateway; it is approximate, not global. |
| StandardV2 is public/non-zone-redundant | The baseline uses StandardV2; PremiumV2 is required for private VNet injection or zone redundancy. |
| APIM is not a Traffic Manager Azure Endpoint | Optional public Traffic Manager uses external APIM FQDN endpoints. |
| Foundry quota scope varies | A second resource or region does not automatically add effective quota. |

`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` reduces credential exposure to child processes but is not same-user process isolation. APIM circuit breaking is gateway-instance-local and only responds to backend 5xx; it does not retry streaming POSTs.

Use [capacity and load](03-capacity-plan.md) to measure capacity and [networking](networking.md) for topology constraints. Recheck the current first-party guidance before regional deployment:

- [Connect Claude Code to an LLM gateway](https://code.claude.com/docs/en/llm-gateway-connect)
- [Claude models in Microsoft Foundry](https://learn.microsoft.com/azure/foundry/foundry-models/how-to/use-foundry-models-claude)
- [APIM v2 service tiers](https://learn.microsoft.com/azure/api-management/v2-service-tiers-overview)
- [APIM Premium v2 VNet injection](https://learn.microsoft.com/azure/api-management/inject-vnet-v2)
- [Server-sent events through APIM](https://learn.microsoft.com/azure/api-management/how-to-server-sent-events)
