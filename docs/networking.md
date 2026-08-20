# Networking profiles

## Public enterprise gateway

Managed workstation -> public APIM HTTPS endpoint -> public or customer-configured Foundry endpoint.

Entra auth remains mandatory. Add enterprise custom DNS/certificates outside this minimal template or CNAME the approved name to the Traffic Manager FQDN.

## Private enterprise gateway

Corp/VPN -> APIM private endpoint -> Premium v2 outbound VNet integration -> existing Foundry private endpoint.

Set `APIM_NETWORKING_PROFILE=private`. Supply, for each APIM region:

- a dedicated delegated outbound-integration subnet;
- a different private-endpoint subnet;
- the existing `privatelink.azure-api.net` private DNS zone resource ID.

Link the DNS zone to client VNets and validate resolution from corporate networks. Configure routes, NSGs, DNS, and egress required by APIM and Entra. The template does not create or alter Foundry private endpoints, DNS, firewalls, or public access; provide existing Foundry endpoint URLs that resolve from the APIM integration subnets.

Traffic Manager is public DNS routing. A fully private corporate DNS failover implementation may replace it while retaining the two APIM instances; this customer-specific DNS integration is intentionally not created.
