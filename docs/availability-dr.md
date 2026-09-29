# Availability and disaster recovery

This page defines implemented HA behavior and the required operating steps. For HA or private topology, prepare second-region resources, a DNS design, and in-network runners. This repository does not create private DNS, custom DNS or certificates, or model-aware Foundry failover. Optional public Traffic Manager Priority routing automatically selects healthy gateways.

The default is one public, single-region, fixed-capacity `StandardV2` APIM. Enable a second APIM with `DEPLOY_SECONDARY=true`; it uses the primary Foundry target unless a complete secondary Foundry configuration is supplied. Public HA can enable Traffic Manager priority routing. Private HA uses your DNS. PremiumV2 is required for private injection or zone redundancy.

| Behavior | Meaning |
| --- | --- |
| Stream recovery | In-flight streams fail on regional loss; no stream migration or inference POST replay is configured. |
| Foundry recovery | There is no automatic Foundry failover. Operators validate the secondary target and change traffic when appropriate. |
| Health | `/claude/health` tests APIM only. Traffic Manager detects APIM/regional gateway health, not model availability. |
| Counters | RPM/TPM/monthly quota/concurrency are gateway-local and can reset or duplicate after failover. |
| Public Priority failback | When primary is healthy again, Traffic Manager automatically reselects it for new DNS answers. Resolver/client DNS caching delays traffic movement; there is no implemented manual hold-down. |
| Private failback | Private DNS and traffic changes are operator-owned under the approved network procedure. |

Run `ha-smoke` from both labeled in-network runner sites before a private or HA rollout. It observes configured direct and failover URLs but never changes DNS or Traffic Manager. An authorized operator captures readiness, conducts the approved drill, and retains failover/failback evidence, including automatic public primary reselection and observed DNS-cache timing. For private DNS, the operator performs the approved traffic changes. Set and approve RTO/RPO and DNS settings before rollout; gateway-local health is not evidence of Foundry health.
