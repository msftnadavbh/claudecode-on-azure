# Architecture

## Deployed topology

```text
managed workstation -> enterprise DNS -> APIM -> Foundry Claude
                                      \-> optional secondary APIM
```

The production baseline is one fixed-capacity APIM and one Foundry target. Optional HA adds a second APIM, which uses the primary Foundry account by default. Public HA can add Traffic Manager; private HA uses customer-managed DNS. APIM regions share telemetry but retain resource and region identity. Each APIM identity receives `Foundry User` on its configured account.

## Request path

1. Claude Code obtains a user token for the APIM application audience through `apiKeyHelper`.
2. APIM validates tenant, audience, `oid`, `tid`, and app role from the bearer `Authorization` header.
3. APIM keys RPM and generation-token controls by `tid:oid`; token counting receives only RPM protection.
4. APIM removes caller/provider credentials and keeps identity only in bounded gateway traces.
5. APIM selects the configured backend entity. Its circuit opens after repeated 429/5xx responses and honors `Retry-After`; APIM does not replay inference POSTs.
6. APIM obtains its own Foundry token and streams the native response without buffering.

Foundry accounts, model deployments, versions, deployment types, capacity, and networking are external customer resources. The template only creates APIM-owned resources and RBAC assignments.

## Availability semantics

Optional HA is active/passive. In-flight streams fail during regional loss and must be retried by Claude Code. Per-user APIM counters are service-local, so failover can temporarily reset effective counters. Foundry quota scope may span resources/regions and is verified separately.
