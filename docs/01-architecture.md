# Architecture

## Deployed topology

```text
managed workstation -> enterprise DNS -> primary APIM -> primary Foundry Claude
                                      \-> secondary APIM -> secondary Foundry Claude
```

For public profiles, Traffic Manager uses priority External Endpoints targeting each APIM FQDN and probes `/claude/health`; private profiles use customer-managed corporate DNS failover. Each Premium v2 service has the same API revision, named values, policy, diagnostics, backend circuit breaker, capacity rules, and an independent system-assigned identity. Each identity receives the documented minimum `Foundry User` role on its existing Foundry account.

## Request path

1. Claude Code obtains a user token for the APIM application audience through `apiKeyHelper`.
2. APIM validates tenant, audience, `oid`, `tid`, and app role from the bearer `Authorization` header.
3. APIM keys request, hourly, and token controls by `tid:oid`.
4. APIM removes caller/provider credentials and keeps identity only in bounded gateway traces.
5. APIM selects the configured backend entity. Its circuit opens after repeated 429/5xx responses and honors `Retry-After`; APIM does not replay inference POSTs.
6. APIM obtains its own Foundry token and streams the native response without buffering.

Foundry accounts, model deployments, versions, deployment types, capacity, and networking are external customer resources. The template only creates APIM-owned resources and RBAC assignments.

## Availability semantics

The default is active/passive. In-flight streams fail during regional loss and must be retried by Claude Code. Per-user APIM counters are service-local, so failover can temporarily reset effective counters. Foundry quota scope may span resources/regions and is verified separately.
