# Security

## Identity boundaries

- User tokens terminate at APIM and require the configured tenant, audience, `tid`, `oid`, and either the app role or the managed Desktop client's delegated scope.
- User revocation is independent through Entra assignment/sign-in controls.
- APIM removes `Authorization`, `x-api-key`, `api-key`, APIM subscription keys, function keys, and legacy credential query parameters.
- APIM uses its managed identity for Foundry. `Foundry User` is the current documented minimum built-in role for Foundry project data actions and does not grant model deployment management.
- No shared production key or developer management-plane permission exists.

## Telemetry

APIM diagnostics explicitly capture zero request/response body bytes and no headers. Safe traces contain APIM request ID, tenant, validated user, and operation for investigations. User/session identifiers are not custom metric dimensions. Do not enable body logging: it risks source/prompt disclosure and can disrupt SSE buffering.

## Workstations

`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` applies on Windows, WSL, Linux, and macOS when supported by the installed Claude Code version. WSL is a separate Linux environment and requires its own Azure CLI sign-in/settings. Scrubbing removes environment variables; it does not stop same-user process inspection, files, shell initialization, or explicit user disclosure.

Enterprise rollout must pin/test a Claude Code version, use managed settings, OS credential protection, endpoint management, and least-privilege stdio MCP configurations.
