# Migration from PoC

1. Keep the Basic v2 PoC isolated and preserve its tiny demonstration limits.
2. Provision production Entra applications, GitHub OIDC identities/environments, networks, DNS, monitoring destinations, and customer-owned pinned Foundry deployments.
3. Deploy the public single-region `StandardV2` baseline and RBAC through the protected OpenTofu workflow; add a secondary only when HA requires it.
4. Validate public/private connectivity, both native routes, managed-identity auth, token refresh past one lifetime, throttling isolation, and enabled failover.
5. Load-test APIM synthetically, approve Foundry quota separately, and set measured fixed capacity and user limits.
6. Distribute generated managed Claude Code settings to Windows, macOS, and Linux canaries, verify their artifact digests and live canaries, then expand while monitoring auth, 429, errors, capacity, and model aliases. Run the optional Claude Desktop preview canary only when enabling that path.
7. Remove legacy shared gateway credentials after rollback windows expire.
