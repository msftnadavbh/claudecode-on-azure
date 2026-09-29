# CURRENT DEPLOYED STATE

**Inspection:** 2026-09-29, approximately 11:35–11:46 UTC.

**Mode:** read-only inspection plus small inference/token-counting requests. No configuration, policy, deployment, RBAC, registry, or state changes were made. The budget demo was not run.

**Scope of this report:** the tables below are a dated inspection snapshot, not a continuously refreshed status page.

**Subsequent local CLI correction (2026-09-29):** an interactive Bash function loaded from `~/.config/claudecodepoc/claude.sh` still launched a legacy Opus 5/native-Foundry wrapper when running from `/home/nadav`. This was outside the initial project's canary coverage. The function was corrected to launch the installed Claude binary with the verified project settings and without the legacy provider/credential overrides. A normal `hello` request through interactive Bash from `/home/nadav` then succeeded on Claude Code `2.1.284`, reporting `claude-opus-5-5`. Existing terminals must reload that shell function or be reopened. The parent workspace's local settings now symlink to the repository-local settings; these machine-local configuration changes are not committed here. No Azure controls were changed by that correction.

```text
Claude Code on WSL                         Windows Claude Desktop
  project-local settings                   local Gateway configuration
  Linux Azure CLI token helper             native Windows Azure CLI token helper
                  \                         /
                   Microsoft Entra access token
                   (same pilot user, Azure CLI client)
                                |
                                v
https://apim-claudecode-project-test-01.azure-api.net/claude
  StandardV2 APIM, public endpoint
  strict tenant + audience + client + user + role + scope checks
                                |
                      APIM system-assigned identity
                                |
                                v
https://project-test-01.services.ai.azure.com/anthropic
  Foundry account: project-test-01
  deployment: claude-opus-5-5
  Anthropic model version 2, hosted on Azure
  GlobalStandard, capacity 40
```

**Azure scope**
- Subscription: `68eab0d1-ab81-4851-b2dd-173dede87582`
- Subscription name: `MCAPS-Hybrid-REQ-162389-2026-nadavbh`
- Tenant: `16b3c013-d300-468d-ac64-7eda0820b6d3`
- Resource group: `claudepoc-rg`
- Region: `eastus2`

**Repository at inspection**
- Path: `/home/nadav/tools/claudecode-prod/claudecodepoc-hard`
- Branch: `main`
- Commit: `fe699acbaaf008b93e497b669379902749a3fe9d`
- Working tree: **clean at inspection, before creating this report**
- Tracking: `azure/main`
- `azure` remote: `https://github.com/msftnadavbh/claudecode-on-azure.git`
- GitHub’s current `main` SHA matched the checked-out commit.
- A second remote, `origin`, points to `msftnadavbh/claudecodepoc-hard`; it is **not** the branch’s tracking remote.

# ACTIVE CONTROLS

These were read from **live Azure configuration**, not inferred from repository files.

- Entra token validation before backend forwarding.
- Exact tenant and gateway audience.
- Access-token version `1.0`.
- Azure CLI client application restriction.
- Exact pilot-user object ID restriction.
- `Gateway.Invoke` app role **and** `AiGateway.Invoke` delegated scope.
- Incoming credential headers/query parameters removed before backend forwarding.
- APIM system-assigned managed identity authenticates to Foundry.
- Foundry local/key authentication disabled.
- HTTPS backend with certificate-name and certificate-chain validation.
- Unbuffered response forwarding.
- Application Insights request/dependency/trace integration.
- API-level body logging disabled; selected noncredential headers recorded.

**Not currently active:** user RPM, TPM limits, monthly quota, concurrency limits, circuit breaker, retries, model allowlist, or an APIM Content Safety policy.

# IMPLEMENTED IN REPO BUT NOT DEPLOYED

| Repository feature | Current pilot |
|---|---|
| Per-principal RPM limiting | Not deployed |
| TPM through `llm-token-limit` | Not deployed |
| Optional monthly token quota | Not deployed; temporary demonstration policy has been removed |
| Model-deployment allowlist | Not deployed |
| Per-user concurrency limit | Not deployed |
| Aggregate concurrency limit | Not deployed |
| Backend 5xx circuit breaker | Not deployed |
| APIM-local `/claude/health` operation | Not deployed |
| Optional Desktop OIDC authorization branch | Not deployed; Desktop uses the existing Azure CLI helper route |
| PremiumV2 private VNet-injected profile | Not deployed |
| Secondary gateway / optional Traffic Manager | Not deployed |

The full repository policy is **not identical to the pilot policy**:
- Live API ID: `claude-api`; repository API ID: `claude`.
- Live backend: `foundry-claude`; repository backend: `foundry-backend`.
- Live authorization is a strict pilot-user **AND role AND scope** restriction.
- The repository’s general authorization supports different role/Desktop branches.

# VERIFIED LIVE TESTS

## Claude Code canary

Executed the repository inference-only canary, using the existing project configuration’s endpoint, tenant, audience, and helper in the child process environment.

```json
{
  "client_invocations": 1,
  "mode": "inference-only",
  "ok": true,
  "reported_models": ["claude-opus-5-5"],
  "requested_model": "claude-opus-5-5"
}
```

- Request succeeded: **YES**
- Requested model: `claude-opus-5-5`
- Claude Code `modelUsage`: `claude-opus-5-5`
- Proves an actual Claude Code invocation currently succeeds against the configured gateway with that requested model: **YES**
- Model identity is supported by the unchanged backend routing and live Foundry deployment—not model self-identification.

## Gateway smoke

```text
GET /claude/health:                         404
POST /claude/v1/messages without identity: 401
POST /claude/v1/messages/count_tokens
  without identity:                       401
authenticated count_tokens — Opus:         200
authenticated count_tokens — Sonnet:       200
authenticated count_tokens — Haiku:        200
authenticated streaming messages:          200
all three configured model mappings:       claude-opus-5-5
```

**Overall `smoke.sh`: FAILED, exit 1**, solely because it expects a healthy `/claude/health` response and the deployed pilot has no health operation. Authentication, token counting, and complete-record SSE checks passed.

A separate check using the **native Windows helper** also returned **200** from authenticated `count_tokens`.

# CLAUDE CODE

| Setting | Current value |
|---|---|
| Version | `2.1.283` |
| Project-local settings | `/home/nadav/tools/claudecode-prod/claudecodepoc-hard/.claude/settings.local.json` |
| `ANTHROPIC_BASE_URL` | `https://apim-claudecode-project-test-01.azure-api.net/claude` |
| Selected/default model | `claude-opus-5-5` |
| Opus mapping | `claude-opus-5-5` |
| Sonnet mapping | `claude-opus-5-5` |
| Haiku mapping | `claude-opus-5-5` |
| `apiKeyHelper` | `/home/nadav/tools/claudecode-prod/claudecodepoc-hard/scripts/auth/apim-user-token-helper.sh` |
| `APIM_TENANT_ID` configured | **Yes** |
| `APIM_AUDIENCE` configured | **Yes** |
| `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` | `1` |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | `1` |
| Helper TTL | `300000` milliseconds |
| All aliases map to Opus 5.5 | **Yes** |
| Fresh inference proof | **Passed** |

**Settings sources inspected**
- `~/.claude/settings.json`: theme and TUI preferences; no routing override.
- `~/.claude/settings.local.json`: permissions; no routing override.
- Project `.claude/settings.json`: absent.
- Project `.claude/settings.local.json`: supplies model, helper, and environment.
- `/etc/claude-code/managed-settings.json`: absent.
- `/etc/claude-code/managed-settings.d`: absent.

**Parent shell versus Claude environment**
- The listed gateway/model/tenant/audience/TTL/scrubbing variables were **not present in the parent WSL shell**.
- They are configured for injection into Claude Code.
- The inspection supplied the existing values only to the canary/smoke child processes.
- No static Anthropic credential, custom-header credential, or native Foundry-mode override was present in the parent shell.

# CLAUDE DESKTOP

| Item | Current observation |
|---|---|
| Installed native Windows package | **`2.9939.2.0`** |
| Installed embedded Claude Code directory | `2.1.281` |
| Active configuration | `C:\Users\nadavbh\AppData\Local\Claude-3p\configLibrary\7c3f7918-d444-45f0-8a55-172cb6d8dcaa.json` |
| Provider | `gateway` |
| Gateway URL | `https://apim-claudecode-project-test-01.azure-api.net/claude` |
| Credential kind | `helper-script` |
| Helper | `C:\Users\nadavbh\AppData\Local\claudecodepoc\desktop-entra-pilot.cmd` |
| Helper TTL | `240` seconds |
| Auth scheme | `bearer` |
| Configured model | `claude-opus-5-5` |
| Configured label | `Opus 5.5 via Microsoft Foundry` |
| HKLM Claude policy | Absent |
| HKCU Claude policy | Absent |

**Working-state evidence**
- **Chat:** previously proven in the native Desktop UI with `WINDOWS_DESKTOP_OPUS55_OK`.
- **Current native Windows helper → gateway:** freshly verified, authenticated token counting returned **200**.
- **Current UI:** Desktop was running with a Settings modal open; the Opus 5.5 label was visible behind it.
- **Fresh `DESKTOP_DEMO_OK` reply:** **NOT VERIFIED**. UI navigation/input attempts did not establish that the new prompt was submitted or answered. No configuration was changed.
- **Desktop Code tab:** not proven.
- **Cowork:** not proven.

The installed Desktop version has changed since the earlier successful Chat test. Do not describe that historical test as a fresh test of `2.9939.2.0`.

# FOUNDRY

| Item | Live value |
|---|---|
| Account/resource | `project-test-01` |
| Resource kind | `AIServices` |
| Project | `proj-default` |
| Resource group | `claudepoc-rg` |
| Region | `eastus2` |
| Model deployment | `claude-opus-5-5` |
| Provider/model format | `Anthropic` |
| Model name | `claude-opus-5-5` |
| Model version | `2` |
| Hosting | **Hosted on Azure**; confirmed by live model catalog `hostedOn: azure` |
| Lifecycle | `GenerallyAvailable` |
| SKU | `GlobalStandard` |
| Capacity | `40` |
| Provisioning state | `Succeeded` |
| Version upgrade option | `NoAutoUpgrade` |
| Public network access | `Enabled` |
| Local/key authentication | Disabled: `disableLocalAuth: true` |
| Private endpoint connections | None |
| Deployment `raiPolicyName` metadata | `Microsoft.DefaultV2`—see Content Safety qualification below |

Endpoints:
- Native Anthropic base: `https://project-test-01.services.ai.azure.com/anthropic`
- Project: `https://project-test-01.services.ai.azure.com/api/projects/proj-default`

**`claude-opus-5-5` is deployed and healthy now:** provisioning is successful, and current gateway/Claude Code inference succeeded.

Also deployed:
- `claude-opus-5`
- Version `2`, `GlobalStandard`, capacity `40`, `Succeeded`
- Upgrade option: `OnceNewDefaultVersionAvailable`

# APIM

| Item | Live value |
|---|---|
| Resource | `apim-claudecode-project-test-01` |
| Resource group | `claudepoc-rg` |
| Region | East US 2 |
| SKU/capacity | `StandardV2`, `1` |
| Provisioning state | `Succeeded` |
| API ID | `claude-api` |
| API path | `claude` |
| `subscriptionRequired` | `false` |
| Backend | `foundry-claude` |
| Backend URL | `https://project-test-01.services.ai.azure.com/anthropic` |
| Managed identity | System-assigned |
| Principal ID | `8e0090ee-b936-41ac-a50b-05708e7ae86e` |
| Messages operation | Yes: `messages`, POST `/v1/messages` |
| Token-count operation | Yes: `count-tokens`, POST `/v1/messages/count_tokens` |
| Health operation | No |
| Associated products | None |
| Workspaces | None |
| Operation-specific policies | Both GETs returned **404**—none installed |

## Active-policy control matrix

| Control | Live status | Repository distinction |
|---|---|---|
| Entra JWT validation | **ACTIVE** | Also implemented |
| Exact tenant validation | **ACTIVE** | Also implemented |
| Audience validation | **ACTIVE** | Also implemented |
| `oid` validation | **ACTIVE**—exact pilot user | Repository checks identity presence; pilot is narrower |
| `tid` validation | **ACTIVE**—exact tenant | Also implemented |
| Azure CLI/client restriction | **ACTIVE**—CLI application only | General repository authorization differs |
| Specific pilot-user restriction | **ACTIVE** | Pilot-specific |
| App-role requirement | **ACTIVE**—`Gateway.Invoke` | Repository also defines role authorization |
| Delegated-scope requirement | **ACTIVE**—`AiGateway.Invoke`, conjunctive | Repository’s general role/Desktop branches differ |
| Model allowlist | **NOT ACTIVE** | Implemented in repository |
| Strip inbound Authorization | **ACTIVE** | Also implemented |
| Strip API/subscription keys | **ACTIVE** | Also implemented |
| APIM MI → Foundry | **ACTIVE** | Also implemented |
| Per-user RPM | **NOT ACTIVE** | Implemented in repository |
| TPM / `llm-token-limit` | **NOT ACTIVE** | Implemented in repository |
| Monthly quota | **NOT ACTIVE** | Implemented; demo policy removed |
| Per-user concurrency | **NOT ACTIVE** | Implemented in repository |
| Aggregate concurrency | **NOT ACTIVE** | Implemented in repository |
| Circuit breaker | **NOT ACTIVE**—backend field null | Implemented in repository |
| Backend retries | **NOT ACTIVE** | Repository also deliberately avoids inference POST retries |
| Azure AI Content Safety policy | **NOT ACTIVE** | No such policy in active path |
| Prompt Shields at APIM | **NOT ACTIVE** | Not in active path |
| Custom blocklists | **NOT ACTIVE** | Foundry blocklist listing also empty |
| Application Insights integration | **ACTIVE** | Also implemented, with different live sampling |

**Exact live authorization**
- Tenant: `16b3c013-d300-468d-ac64-7eda0820b6d3`
- Audience: `api://810dcce2-fcdd-4675-906e-b2aea60afe0e`
- Client application: `04b07795-8ddb-461a-bbee-02f9e1bf7b46`
- Token version: `1.0`
- Pilot user: `ad4d1fc5-ea1f-4e76-a56c-934f5b1b52e9`
- Role **and** scope required.
- Backend managed-identity resource: `https://ai.azure.com`
- Forwarding: `timeout="300"`, `buffer-response="false"`, no retry policy.

**Logging**
- API diagnostic: `applicationinsights`.
- Live sampling: **100%**, with `alwaysLog: allErrors`.
- API-level `logClientIp: false`.
- Request/response body capture: **0 bytes**.
- Selected protocol/correlation headers only; Authorization is not selected.
- Separate service-level `azuremonitor` diagnostic exists with `logClientIp: true` and query-parameter masking.
- Azure Monitor diagnostic-settings listing returned **empty**; do not claim a configured APIM resource-log export destination from that setting.
- Application Insights ingestion is independently proven below.

# NETWORKING

| Area | Current state |
|---|---|
| APIM public endpoint | **Yes**, `publicNetworkAccess: Enabled` |
| APIM VNet injection | **No**, `virtualNetworkType: None` |
| APIM outbound VNet integration | **No configured outbound VNet**; field null |
| APIM private endpoint | **No** |
| APIM secondary locations | None |
| Foundry public network access | **Yes** |
| Foundry private endpoint | **No** |
| Foundry firewall default | `Allow` |
| Foundry IP rules | Empty |
| Foundry VNet rules | Empty |
| Application Gateway/WAF | None found in the subscription inventory |
| Traffic Manager | None found |

**REPOSITORY SUPPORTS BUT NOT CURRENTLY DEPLOYED:** PremiumV2 internal VNet injection and private multi-gateway topology; operator-provided subnets, DNS, routing, and Foundry private endpoints. The repository does not itself provision those external networking components.

# RBAC

**Live APIM identity assignment enabling Foundry invocation:**

- Principal: `8e0090ee-b936-41ac-a50b-05708e7ae86e`
- Role: **`Cognitive Services User`**
- Scope:
  ```text
  /subscriptions/68eab0d1-ab81-4851-b2dd-173dede87582/resourceGroups/claudepoc-rg/providers/Microsoft.CognitiveServices/accounts/project-test-01
  ```

The assignment was checked directly and again with inherited-scope lookup.

| Role | Assignment to this APIM identity found |
|---|---|
| Azure AI User | **No** |
| Foundry User | **No** |
| Cognitive Services User | **Yes**, Foundry account scope |

Additional live role:
- **Monitoring Metrics Publisher**
- Scope: `appi-claudecode-project-test-01` Application Insights resource.

Do not use the repository’s intended `Foundry User` role name when describing this deployed identity.

# COST / CCU

## Azure Cost Management

**CCU LIVE VIEW VERIFIED: YES — through the live Cost Management API.**

The Portal UI itself was not opened during this inspection.

**Scope**
- Subscription `68eab0d1-ab81-4851-b2dd-173dede87582`
- Date range queried: **Month to date, September 2026**
- Type: `ActualCost`

**Exact returned dimensions**
- Service: **`SaaS`**
- Product: **`claude-ccu-azure-hosted-test-plan`**
- Meter:
  ```text
  Claude in Microsoft Foundry (Azure hosted) - claude-ccu-azure-hosted-test-plan - claude-consumption-units
  ```
- Unit: **`per 1 ccu`**
- Currency: USD

**Actual returned data**

| Attribution | CCU quantity | Pre-tax cost |
|---|---:|---:|
| Claude CCU meter, subscription month-to-date | **66.5704** | **$0.00** |
| September 3 | 46.9369 | $0.00 |
| September 28 | 19.6335 | $0.00 |
| Opus 5.5 Marketplace resource, month-to-date | **19.5540** | **$0.00** |
| Opus 5 Marketplace resource, month-to-date | 47.0164 | $0.00 |

Opus 5.5 billing resource:
```text
/subscriptions/68eab0d1-ab81-4851-b2dd-173dede87582/resourcegroups/claudepoc-rg/providers/microsoft.saas/resources/claude-opus-5-5-407adf74332a4e0-0b4f1b6a31034d95817b3d8fcdb02940
```

**Portal navigation for the runbook**
1. Azure Portal → **Cost Management + Billing**
2. **Cost Management → Cost analysis**
3. Select the subscription above.
4. Date: **This month**; daily granularity for September 3/28 activity.
5. Filter **Service name = SaaS** and **Product = claude-ccu-azure-hosted-test-plan**.
6. Group by **Meter** or **Resource**.
7. Inspect usage quantity/unit in the available details/export rather than expecting a nonzero dollar chart.

**Demo usefulness**
- Enough data to show actual CCU consumption: **Yes**.
- Enough data to show nonzero Claude charges: **No**—this test plan returns $0.
- Fresh per-request billing movement: **Not proven**; billing data is historical/delayed.
- The two extra rows with blank meter and quantity `1` were not counted as CCU.

## Foundry monitoring

Live Azure Monitor queries, filtered to `ModelDeploymentName = claude-opus-5-5`, returned the following over approximately **September 22–29, 2026**:

| Metric | Actual result |
|---|---:|
| `ModelRequests` | **19** |
| `InputTokens` | **4,347** |
| `OutputTokens` | **250** |
| `TotalTokens` | **4,597** |
| `TimeToResponse` | Nonzero data; latest nonzero hourly bucket average **1,343.061 ms** |
| `TimeToLastByte` | Nonzero data; latest nonzero hourly bucket average **2,174.546 ms** |
| `FoundryModelEstimatedCost` | Metric definition exists, but **no time series/data returned** |

Metrics expose deployment/model/version dimensions. These are ingested metric-window results, not guaranteed to include the inspection’s latest requests.

**Verified view:** Azure Portal → `project-test-01` → **Monitoring → Metrics**, select the above metrics and split/filter by model deployment.

The Foundry-specific portal dashboard UI was not opened; the underlying account metrics are verified.

## APIM / Application Insights

APIM Azure Monitor, same approximate seven-day range:
- `Requests`: **469**
- `Duration`: nonzero data
- `BackendDuration`: nonzero data
- No native token/CCU-emission policy is currently active at APIM.

Application Insights:
- Resource: `appi-claudecode-project-test-01`
- Workspace: `log-claudecode-project-test-01`
- Workspace ID: `8c44d8bf-247c-476b-98a3-c385c47a9c16`
- Application Insights local authentication: disabled.

Live Log Analytics results:

| Table | Rows in last seven days |
|---|---:|
| `AppRequests` | 52 |
| `AppDependencies` | 30 |
| `AppTraces` | 29 |

Latest telemetry reached **2026-09-29 11:37:12 UTC**, matching this inspection’s smoke activity.

Request status distribution: **24 × 200, 4 × 400, 15 × 401, 1 × 403, 8 × 404**.

# CONTENT SAFETY

## CURRENTLY DEPLOYED

- **No APIM Azure AI Content Safety policy.**
- **No APIM Prompt Shields invocation.**
- **No custom blocklist in the active APIM path.**
- Foundry custom RAI blocklist listing: **empty**.
- The deployment reports `raiPolicyName: Microsoft.DefaultV2`.
- Account policy enumeration exposes system-managed default policy definitions, including harmful-content and jailbreak entries.

**Important qualification:** that metadata does **not establish Azure Content Safety enforcement on this Claude deployment**. Microsoft’s Claude-specific documentation states that Foundry does not provide built-in deployment-time content filtering for Claude, and that Claude uses Anthropic safety systems.

- Anthropic provider safeguards: documented for this hosting offering.
- Azure-configured content-filter/Prompt Shields enforcement on these requests: **not verified and must not be claimed**.
- Model-filter metrics `RAITotalRequests`, `RAIRejectedRequests`, and `RAIHarmfulRequests` returned **no series**.
- No harmful-content or jailbreak test was performed.

Relevant first-party clarification: [Claude responsible-AI considerations](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/claude-models#responsible-ai-considerations).

## AVAILABLE BUT NOT DEPLOYED

Potential explicit additions, subject to compatibility and implementation:
- APIM `llm-content-safety` / Azure AI Content Safety inspection.
- Prompt Shields integration.
- Custom text blocklists.
- Additional request/response moderation and related telemetry.

These are optional capabilities, **not current pilot controls**, and are not implied by the `Microsoft.DefaultV2` metadata.

# SAFE CLAIMS FOR THE DEMO

- Opus 5.5 version 2 is deployed, healthy, and hosted on Azure through Foundry.
- WSL Claude Code currently completes real inference using `claude-opus-5-5`.
- The gateway rejects unauthenticated inference with **401** and accepts the approved user with **200**.
- Both client configurations use Entra token helpers; APIM uses managed identity to Foundry.
- The pilot restricts access to one exact user, client application, role, scope, tenant, and audience.
- Windows Desktop is configured for the same gateway/model; its native helper currently succeeds against the gateway.
- Actual request/token metrics and actual CCU usage records exist.
- The temporary quota demonstration is **not currently installed**.

# DO NOT CLAIM

- `/claude/health` is healthy: it returns **404**.
- The complete repository smoke suite passes against this pilot: it exits **1** because of health.
- Current quotas, TPM/RPM limits, concurrency controls, model allowlisting, or a circuit breaker are active.
- The APIM identity has Foundry User or Azure AI User: the observed role is **Cognitive Services User**.
- Private networking, private endpoints, WAF, or multi-region failover are deployed.
- Azure AI Content Safety or Prompt Shields currently filters Claude traffic.
- `Microsoft.DefaultV2` metadata alone proves Claude content filtering.
- Claude costs are increasing in dollars: current CCU test-plan rows show **$0**.
- Billing/CCU data updates immediately per prompt.
- Foundry estimated-cost monitoring has usable data: it returned none.
- Desktop `2.9939.2.0` received a fresh successful `DESKTOP_DEMO_OK` response in this inspection.
- Desktop Code, Cowork, long-lived refresh, or revocation behavior is proven.
- The full infrastructure deployment matches the focused live pilot.

# DEMO-READY STATUS

| Component | Status | Qualification |
|---|---|---|
| Foundry portal | **READY WITH QUALIFICATION** | Live deployment and underlying metrics verified; portal UI not directly exercised |
| APIM architecture | **READY** | Live gateway, backend, identity, policies, and public networking inspected |
| 401 → 200 gateway proof | **READY** | Fresh negative and authenticated checks passed |
| Claude Code | **READY** | Fresh actual canary passed with `modelUsage: claude-opus-5-5` |
| Claude Desktop | **READY WITH QUALIFICATION** | Current configuration and native helper verified; historical Chat success, no fresh UI reply verified on current package |
| Quotas | **NOT READY** | No quota currently installed; enabling a demo requires a separate authorized mutation |
| Content Safety | **NOT READY** | No explicit Azure/APIM safety control active or enforcement demonstrated |
| Private networking | **NOT READY** | Both endpoints are public; no private endpoints/VNet integration |
| CCU / Cost Management | **READY WITH QUALIFICATION** | Actual CCU quantities exist; $0 test-plan cost, delayed data, Portal UI not directly checked |
| Foundry monitoring | **READY WITH QUALIFICATION** | Actual requests/tokens/latency data exists; estimated-cost series absent; data is not instantaneous |
