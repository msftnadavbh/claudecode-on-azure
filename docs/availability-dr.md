# Availability and disaster recovery

Baseline production deploys one fixed-capacity, public, single-region `StandardV2` APIM service. Use `PremiumV2` only for zone redundancy or private VNet injection. Set `DEPLOY_SECONDARY=true` to add regional HA; the secondary uses the primary Foundry target unless secondary parameters are explicitly overridden. Set `TRAFFIC_MANAGER_ENABLED=true` for public priority routing; private HA relies on customer-managed corporate DNS.

When enabled, the public DNS chain is `enterprise hostname -> Traffic Manager FQDN -> active APIM FQDN`. APIM is represented by Traffic Manager External Endpoints because API Management isn't a supported Azure Endpoint resource type.

- **RTO target:** customer-approved; DNS detection consists of 30-second probes, three tolerated failures, and a 30-second DNS TTL.
- **RPO:** no persistent application data is stored in APIM. Configuration RPO is the last successful IaC deployment.
- **In-flight streams:** lost during failure; clients retry. No transparent POST replay is configured.
- **Failback:** validate primary health and smoke tests, then re-enable/restore primary endpoint priority. Perform manually to avoid flapping.
- **Configuration synchronization:** apply the reviewed `infra/tofu` plan; never patch only one regional policy.
- **Counters:** request/token counters are local and can reset or duplicate on failover. Strict global budget enforcement is intentionally deferred.

Run the protected `ha-smoke` workflow from both in-network runner sites before a drill. It records endpoint health and connectivity for the direct primary, direct secondary, and failover URLs; verifies gateway-local health, unauthenticated rejection, all three token-count routes, and an incremental Sonnet stream; and retains a short-lived JSON artifact. Operator evidence proves the traffic change. A private deployment can succeed, but release remains pending this in-network `ha-smoke` evidence because the hosted deployment runner cannot reach internal APIM.

The workflow never changes DNS or Traffic Manager. For a real drill, an authorized network operator captures `readiness`, performs the approved external traffic change, captures `observe-failover`, restores traffic, and captures `observe-failback`. A no-change rollback rehearsal captures `rollback-before` and `rollback-after` around review of the last-known-good commit and its what-if; it does not deploy or prove RTO.

`/claude/health` is intentionally APIM-local. Automatic DNS failover detects APIM and regional gateway failures, not Foundry/model availability. Backend alerts and the circuit breaker detect provider failures; operators validate the secondary and manually fail over when appropriate. No billable inference probe is used.
