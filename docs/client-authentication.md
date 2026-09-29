# Client authentication

Connect managed Claude Code clients through APIM. You provide the Entra caller application, audience, app role, assignments, consent, Azure CLI policy, and device management. This repository provides no static credential or Entra app registration; a native Windows helper is available for installed Claude Code user settings.

Use generic gateway mode: clients send native Anthropic requests to `ANTHROPIC_BASE_URL=https://<apim-name>.azure-api.net/claude`; the managed `apiKeyHelper` returns only a raw Entra token. Claude Code places helper output in credential headers; APIM validates the bearer authorization, strips both caller credentials, and uses its managed identity for Foundry.

Configure the caller app so the application ID URI equals `APIM_EXPECTED_AUDIENCE`, `requestedAccessTokenVersion` remains `1`, its app-role value equals `APIM_REQUIRED_APP_ROLE`, and callers receive the required tenant, audience, `oid`, `tid`, and role claims. Expose a delegated scope, preauthorize the Azure CLI client `04b07795-8ddb-461a-bbee-02f9e1bf7b46`, and grant the approved tenant consent so the user helper can request the API token. The smoke identity uses workload federation and app-role assignment, not delegated consent.

Use [managed settings](claude-code-managed-settings.md) for deployment. The bundled shell helper supports macOS, Linux, and WSL; the separate `.cmd` and `.ps1` helper supports native Windows Claude Code without registry mode or a WSL bridge. Azure CLI/MSAL owns sign-in and refresh; if it cannot provide a token, reauthenticate through the approved flow rather than using a key. Validate an installed client with the [canary](claude-code-canary.md).

Set `APIM_TENANT_ID` to the caller tenant UUID and `APIM_AUDIENCE` to the API audience before rolling out the updated helper. Managed settings do not export to the parent shell: standalone tools need these launch-environment values, and a pinned OS/client pilot must verify the actual helper child receives them with scrubbing enabled. Failed inheritance stops rollout; do not disable scrubbing or use fallback credentials. The helper explicitly requests that tenant noninteractively; the currently selected subscription/infra login tenant is not a substitute. Native Windows helper implementations must follow the [same contract](claude-code-managed-settings.md).

## Repository authorization design (full deployment validation pending)

Both inference operations in the **repository policy** require a valid tenant/audience token and either the required role **OR**, only when Desktop is enabled, its exact client ID and exact scope. Desktop actors use `appid` for v1 and `azp` for v2; other token versions cannot satisfy the Desktop branch. A role-bearing app-only smoke identity remains supported. Desktop is disabled by default. The [focused live pilot](opus-5-5-pilot.md) instead requires exact CLI `appid` **AND** user **AND** role **AND** scope on a v1 token; its [Windows Desktop Chat](windows-desktop-pilot.md) uses the existing CLI-token helper, not the unused OIDC client. Do not interpret this matrix as verified live pilot authorization or deploy it over that stricter policy without review.

The endpoint matrix always tests missing authorization on both operations. With explicit approval, repeat `--negative-case safe-label=401|403=/absolute/helper` and pass `--allow-negative-auth`. Each supplied helper is executed without arguments with stdout captured in memory; it must acquire an approved test credential without writing/logging it. Labels must be non-secret lowercase letters, digits, underscores or hyphens (start with a letter). Never pass a token as a CLI argument, save it to a file, log claims, or decode it in this tooling. For example, append `--allow-negative-auth --negative-case wrong-tenant=401=/opt/test-identities/wrong-tenant` to an approved matrix invocation. Helpers are operator-owned executables, not token files.

| Case, on both messages and count_tokens | Expected |
| --- | --- |
| Missing token; wrong tenant; wrong audience; expired token | 401 |
| Valid token with neither authorization branch | 403 |
| Desktop disabled, wrong client, missing/extraneous-only scope, or unsupported actor version, **without the required role** | 403 |
| Valid required role, including app-only CI | Success |
| Enabled Desktop, exact client and scope, v1 or v2, without role | Success |

Desktop negative identities must not also carry the required role: the OR branch would correctly authorize them. Positive role and Desktop evidence are separate runs with the appropriate `--token-helper`. Negative checks issue one request per operation/case/endpoint, never retry, and retain only expected/actual status and fixed error categories, not bodies or helper errors. Unprovided cases are **not tested**, not passed. Local tests verify structure/tooling only; real Entra issuance, expiration, revocation, and APIM enforcement evidence is still required.

Each negative helper must explicitly target its own approved test tenant and audience, rather than accidentally inheriting the positive helper's configuration. Missing, empty, or whitespace `oid`/`tid` values are rejected with a generic 401 before authorization or counter-key construction; offline checks verify policy structure/order, not Entra runtime semantics.

## Standalone smoke inputs

`scripts/test/smoke.sh` is an exec adapter to the same endpoint matrix used by HA smoke. Supply `APIM_BASE_URL`, `APIM_TOKEN_HELPER` (executable path, never a token), and **all three** `ANTHROPIC_DEFAULT_OPUS_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_HAIKU_MODEL` variables. The bundled helper additionally requires `APIM_TENANT_ID` and `APIM_AUDIENCE` in the launch environment. Managed files do not populate that shell. The adapter tests health, missing auth on both inference operations, count_tokens for all three mappings, and Sonnet SSE inference only. Greenfield may map all roles to the same deployment. It returns the matrix exit status and JSON output; negative identities are not automatically enabled. The deployment workflow's existing outer retry loop is unchanged.
