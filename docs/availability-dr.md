# Availability and disaster recovery

Production deploys independent Premium v2 APIM services in two regions with priority Traffic Manager routing. Both services are zone-enabled and configured from the same deployment.

- **RTO target:** customer-approved; DNS detection consists of 30-second probes, three tolerated failures, and a 30-second DNS TTL.
- **RPO:** no persistent application data is stored in APIM. Configuration RPO is the last successful IaC deployment.
- **In-flight streams:** lost during failure; clients retry. No transparent POST replay is configured.
- **Failback:** validate primary health and smoke tests, then re-enable/restore primary endpoint priority. Perform manually to avoid flapping.
- **Configuration synchronization:** redeploy `infra/main.bicep`; never patch only one regional policy.
- **Counters:** request/token counters are local and can reset or duplicate on failover. Strict global budget enforcement is intentionally deferred.

Test quarterly by disabling the primary Traffic Manager endpoint, resolving the enterprise DNS name, running `smoke.sh`, restoring primary, and recording detection/failover/failback times. Traffic Manager health proves gateway availability, while authenticated smoke tests prove Foundry reachability and RBAC.
