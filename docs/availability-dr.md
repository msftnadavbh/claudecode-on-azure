# Availability and disaster recovery

**Purpose:** define implemented HA behavior and operator responsibilities. **Prerequisites:** second-region resources, DNS design, and in-network runners when HA/private topology is selected. **Boundary:** the repository does not create private DNS, custom DNS/certificates, Foundry failover, or automated operator traffic changes.

The default is one public, single-region, fixed-capacity `StandardV2` APIM. Enable a second APIM with `DEPLOY_SECONDARY=true`; it uses the primary Foundry target unless a complete secondary Foundry configuration is supplied. Public HA can enable Traffic Manager priority routing. Private HA uses customer-managed DNS. PremiumV2 is required for private injection or zone redundancy.

| Behavior | Meaning |
| --- | --- |
| Stream recovery | In-flight streams fail on regional loss; no inference POST replay is configured. |
| Foundry recovery | There is no automatic Foundry failover. Operators validate the secondary target and change traffic when appropriate. |
| Health | `/claude/health` tests APIM only. Traffic Manager detects APIM/regional gateway health, not model availability. |
| Counters | RPM/TPM/concurrency are gateway-local and can reset or duplicate after failover. |
| Failback | Manual after primary validation to avoid flapping. |

Run `ha-smoke` from both labeled in-network runner sites before a private/HA release. It observes configured direct and failover URLs but never changes DNS or Traffic Manager. An authorized operator captures readiness, performs the approved traffic change, captures failover/failback evidence, and retains it. Customer-approved RTO/RPO and DNS settings remain release decisions.
