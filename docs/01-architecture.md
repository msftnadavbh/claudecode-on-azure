# Architecture

Use this page to understand the request path and topology choices. You provide Foundry deployments, an Entra application, a resource group, and any selected network resources. This repository manages APIM and its integration resources; it does not create Foundry, Entra, DNS, certificates, private endpoints, or a custom hostname.

## Baseline and options

The baseline is fixed-capacity, public, single-region `StandardV2` APIM. `PremiumV2` is required for either zone redundancy or private VNet injection. An optional second APIM provides a separate regional gateway. Public HA may use optional Traffic Manager; you operate private failover DNS and all traffic changes.

## Request path

```text
Managed Claude Code -> Entra user token -> APIM /claude -> your Foundry /anthropic
```

1. Claude Code gets a user token through its managed `apiKeyHelper`.
2. APIM validates tenant, audience, `oid`, `tid`, and the app-role authorization (or the optional Desktop preview's exact delegated scope).
3. APIM applies per-user RPM, messages-only TPM, per-user concurrency, and aggregate concurrency. Concurrency counters are gateway-local and approximate; configured aggregate admission must remain below 2,048.
4. APIM strips caller credentials, obtains a managed-identity token, and calls Foundry under `Foundry User`.
5. APIM allows only the three configured deployment names and forwards native Messages/count-token routes. SSE responses are unbuffered; inference POSTs are never replayed.

The backend breaker opens after 50 backend 5xx responses in one minute. It does not trip on 429 and does not retry requests. A secondary Foundry target is optional but must expose the same three deployment names.

## Availability boundary

In-flight streams can fail during a regional event and must be retried by clients. Gateway-local counters can reset on failover. `/claude/health` is unauthenticated APIM-local health, not a Foundry/model check. See [availability and DR](availability-dr.md) for operator procedures.
