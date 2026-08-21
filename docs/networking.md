# Networking profiles

## Public enterprise gateway

Managed workstation -> public APIM HTTPS endpoint -> public or customer-configured Foundry endpoint.

Entra auth remains mandatory. Add enterprise custom DNS/certificates outside this minimal template. For optional public HA, CNAME the approved name to the Traffic Manager FQDN.

## Private enterprise gateway

Corp/VPN -> Premium v2 APIM VNet injection -> existing Foundry private endpoint.

Set `APIM_NETWORKING_PROFILE=private` and supply one dedicated VNet-injection subnet per APIM region.

Create customer DNS records mapping the APIM default hostname to its private VIP, link DNS to client networks, and validate corporate resolution. Configure routes, NSGs, DNS, and egress required by APIM and Entra. The template does not create or alter Foundry private endpoints, DNS, firewalls, or public access; provide Foundry endpoint URLs that resolve from the APIM subnet.

The subnet must be dedicated to one APIM instance, at least `/27` (`/24` recommended), associated with an NSG, and delegated to `Microsoft.Web/hostingEnvironments`. Premium v2 injection is creation-time only. Customers whose topology specifically requires APIM Private Link plus outbound VNet integration can retain that as a separate advanced networking overlay; it is not part of the baseline template.

Traffic Manager is deployed only for public HA. Private HA uses customer-specific corporate DNS failover, which this template intentionally does not create.
