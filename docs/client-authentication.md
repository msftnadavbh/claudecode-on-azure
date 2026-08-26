# Client authentication

Connect managed Claude Code clients through APIM. You provide the Entra caller application, audience, app role, assignments, consent, Azure CLI policy, and device management. This repository provides no static credential, Entra app registration, or native Windows helper.

Use generic gateway mode: clients send native Anthropic requests to `ANTHROPIC_BASE_URL=https://<apim-name>.azure-api.net/claude`; the managed `apiKeyHelper` returns only a raw Entra token. Claude Code places helper output in credential headers; APIM validates the bearer authorization, strips both caller credentials, and uses its managed identity for Foundry.

Configure the caller app so the application ID URI equals `APIM_EXPECTED_AUDIENCE`, `requestedAccessTokenVersion` remains `1`, its app-role value equals `APIM_REQUIRED_APP_ROLE`, and callers receive the required tenant, audience, `oid`, `tid`, and role claims. Expose a delegated scope, preauthorize the Azure CLI client `04b07795-8ddb-461a-bbee-02f9e1bf7b46`, and grant the approved tenant consent so the user helper can request the API token. The smoke identity uses workload federation and app-role assignment, not delegated consent.

Use [managed settings](claude-code-managed-settings.md) for deployment. The bundled shell helper supports macOS, Linux, and WSL. Azure CLI/MSAL owns sign-in and refresh; if it cannot provide a token, reauthenticate through the approved flow rather than using a key. Validate an installed client with the [canary](claude-code-canary.md).
