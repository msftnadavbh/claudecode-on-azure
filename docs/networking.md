# Networking

Select a supported gateway network profile. You need network approval, a DNS design, and an APIM SKU. This repository does not create subnets, DNS zones or records, certificates, routes, NSGs, Foundry private endpoints, or firewall rules.

| Profile | APIM | You provide |
| --- | --- | --- |
| Public baseline | `StandardV2`, public endpoint | Entra access, any enterprise hostname/certificate, and Foundry endpoint reachability. |
| Private gateway | `PremiumV2` VNet injection | A dedicated subnet per APIM region, NSG/routing/DNS/egress, and a Foundry endpoint resolvable from that subnet. |
| Public HA | Two gateways plus optional Traffic Manager | CNAME/custom hostname and approved traffic-change process. |
| Private HA | Two private gateways | Corporate DNS failover and labeled in-network smoke runners. |

Set `APIM_NETWORKING_PROFILE=private` only with `PremiumV2` and `APIM_SUBNET_RESOURCE_ID`; secondary private APIM also needs `APIM_SECONDARY_SUBNET_RESOURCE_ID`. PremiumV2 injection is a creation-time choice. Use a dedicated subnet per instance; the platform guidance baseline is at least `/27` (`/24` recommended).

The template creates no enterprise gateway hostname. Default APIM URLs are `https://<apim-name>.azure-api.net/claude`. A private deployment is not releasable until in-network `ha-smoke` evidence is retained.
