# Security

**Purpose:** describe the gateway's identity and telemetry controls. **Prerequisites:** customer-owned Entra application/assignments and Foundry security review. **Boundary:** this repository does not create Entra registrations or enforce Foundry `disableLocalAuth`, remove other Foundry RBAC, or secure customer workstations.

## Identity and credential boundary

- APIM validates tenant, audience, `oid`, `tid`, and the configured app role. The optional Desktop preview can instead use its configured client ID and exact delegated scope.
- APIM deletes caller `Authorization`, API-key, subscription-key, and legacy credential query values before requesting Foundry with its managed identity.
- APIM receives `Foundry User` on the customer account. Customer release gates must separately assess direct Foundry local authentication and existing direct inference RBAC.
- Three configured deployment names are allowlisted. Do not put shared provider credentials or direct Foundry settings on client devices.

## Diagnostics and clients

APIM diagnostics collect no bodies or selected headers; IP collection is disabled. Safe traces hold request ID, tenant, validated identity, and operation. Success is sampled at 10%; errors are retained. When customer-supplied telemetry is used, local authentication must be disabled on that Application Insights resource.

Managed Claude Code settings use credential refresh and subprocess environment scrubbing. Scrubbing is not process isolation; device management owns installation, permissions, version pinning, updates, and rollback. Desktop is disabled by default and remains an optional preview.
