# Observability

**Purpose:** operate the implemented telemetry boundary. **Prerequisites:** a customer-approved monitoring destination and incident response owner. **Boundary:** inference continues if telemetry fails; this repository does not create an incident process or capture payloads.

Production profiles can create a Log Analytics workspace and workspace-based Application Insights, or reuse both supplied resources. APIM uses its managed identity for telemetry. Externally supplied Application Insights must have local authentication disabled.

| Captured | Not captured |
| --- | --- |
| APIM resource/region, operation, status/result class, gateway CPU/memory, 401/403/429/5xx, backend 5xx, request ID, validated tenant/identity | Request/response bodies, selected headers, IP address, authorization/API keys, prompt/completion content, session/agent IDs |

Successful requests are sampled at 10%; errors are always retained and resource metrics are unsampled. Configure and test an approved incident destination: `ACTION_GROUP_RESOURCE_ID` is optional in IaC but not a release substitute. Monitor authentication failures, throttling, backend 5xx/circuit symptoms, capacity, Foundry quota signals, optional Traffic Manager health, and ingestion gaps. Do not enable body logging to diagnose an incident.
