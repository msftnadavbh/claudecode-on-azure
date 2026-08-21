# Availability and disaster recovery

Baseline production deploys one zone-redundant Premium v2 APIM service. Set `DEPLOY_SECONDARY=true` to add regional HA. The secondary uses the primary Foundry target unless secondary parameters are explicitly overridden. Set `TRAFFIC_MANAGER_ENABLED=true` for public priority routing; private HA relies on customer-managed corporate DNS.

When enabled, the public DNS chain is `enterprise hostname -> Traffic Manager FQDN -> active APIM FQDN`. APIM is represented by Traffic Manager External Endpoints because API Management isn't a supported Azure Endpoint resource type.

- **RTO target:** customer-approved; DNS detection consists of 30-second probes, three tolerated failures, and a 30-second DNS TTL.
- **RPO:** no persistent application data is stored in APIM. Configuration RPO is the last successful IaC deployment.
- **In-flight streams:** lost during failure; clients retry. No transparent POST replay is configured.
- **Failback:** validate primary health and smoke tests, then re-enable/restore primary endpoint priority. Perform manually to avoid flapping.
- **Configuration synchronization:** redeploy `infra/main.bicep`; never patch only one regional policy.
- **Counters:** request/token counters are local and can reset or duplicate on failover. Strict global budget enforcement is intentionally deferred.

For HA public profiles, test quarterly by disabling the primary Traffic Manager endpoint, resolving the enterprise DNS name, running `smoke.sh`, restoring primary, and recording detection/failover/failback times. Exercise equivalent customer-managed DNS controls for private HA. DNS health proves gateway availability, while authenticated smoke tests prove Foundry reachability and RBAC.

`/claude/health` is intentionally APIM-local. Automatic DNS failover detects APIM and regional gateway failures, not Foundry/model availability. Backend alerts and the circuit breaker detect provider failures; operators validate the secondary and manually fail over when appropriate. No billable inference probe is used.
