# Shared Claude model discovery (repository feature, opt-in)

The repository policy implements authenticated `GET /v1/models` by reading the bound Foundry account's **ARM deployment inventory** and returning a local public projection. It does not proxy the unsupported `/anthropic/v1/models` inference route. Inference model acceptance remains backend-owned. Claude Code and Claude Desktop can opt into that same gateway endpoint after an approved deployment and verification. **PR6's dynamic source changes are not deployed; the separately owned dated live pilot below is still static.**

The opt-in governance collector is separate: it reports **already-deployed** Anthropic models, including unfamiliar names, generations and SKUs, and catalog-only candidates, but **never deploys** them. Role pins are not advanced automatically. They are configuration, not protection against an administrator retargeting a deployment under the same name. Desktop's native alias and refusal-fallback mapping still requires the release gate below.

**The repository-wide opt-in is not deployed; the bounded live exception is recorded below.** The original upstream clients still use the generic gateway route: Entra → APIM → Foundry, with `ANTHROPIC_BASE_URL`/`apiKeyHelper` for Claude Code. Do not switch them to native Foundry mode. The live pilot's `claude-api` API, `foundry-claude` backend and strict authorization differ from this repository's `claude`, `foundry-backend` and optional role-OR-Desktop authorization. Full IaC adoption/ownership remains unresolved: do not deploy the repository against that pilot merely to enable discovery. Further publication and client changes require separate approval and live verification.

## 2026-10-26 bounded live pilot — configured/API-verified

With separate approval, the pilot operator created **only** operation `models` (`GET /v1/models`) and its operation policy on existing APIM `apim-claudecode-project-test-01`, resource group `claudepoc-rg`, subscription `68eab0d1-ab81-4851-b2dd-173dede87582`, API `claude-api`; backend `foundry-claude` was preserved. The lead's fresh semantic verification confirmed unchanged existing parent API/service policies, both POST routes, backends and model deployments. No RBAC or named-value edits were made: the verified write scope was limited to the two new resources, not a snapshot of RBAC assignments or all named values. **No models were deployed.**

The response is a static reviewed snapshot: `claude-opus-5-5` (default), then `claude-opus-5`. The 5.5 row includes native `anthropic_family_tier: "opus"` and `is_family_default: true` to preserve Desktop's Opus pin. Client discovery reads **this gateway catalog**, not an automatically refreshed Azure inventory. The daily collector remains artifact-only and disabled until configured; this publication did not enable it or the repository's broader inference-policy integration.

Lead-performed live checks: missing/malformed bearer GETs returned **401**; a JWT captured only in memory from the **existing installed Windows helper** authorized bare GET and `?limit=1000`, both **200** with the exact reviewed JSON/native fields, JSON Content-Type, `Cache-Control: no-store` and no redirect. No approved denied principal was available, so **403 was not tested**. No Messages, count-tokens or inference requests were made. The [single-PC entry](windows-desktop-pilot.md#2026-10-26-discovery--configuredapi-verified) records the approved local configuration and offline installed-build check; Desktop remains closed for the user to open. Picker, startup inference and end-to-end behavior are **not verified**; this is not fleet enablement.

Execution note: the operation PUT returned **201** but its response-shape comparison stopped execution. A same-ETag GET canonically matched the intended operation. An architect-approved, independently reviewed one-shot resume used that genuine creation proof, performed only the first policy PUT, and completed validation. Original records and the successful resume receipt chain were retained; there was no operation retry or blind overwrite.

Private operational evidence is retained at `/tmp/opencode/claude-desktop-discovery-V1uxYnKS`; the independently reviewed base bundle and resume overlay are identified below. The owner must retain/archive it before cleanup. Neither Desktop nor APIM depends on that directory; the adjacent profile backup is durable locally. **Never copy private JSON/XML or credentials into Git.**

| Evidence | SHA-256 |
| --- | --- |
| Base bundle | `7eda8cc89d60a1397c1e7efc23ec588491f779221137911adc92067fe8e44afe` |
| Resume overlay | `08e81429bdfe61fc9ad5e854874c4d98f20be9d45790eb3b67c1fca5cbcbbaa9` |
| Policy JSON payload | `ab2c1e31efbc861e02c88ec4b996cf69e58d3cd3e08fca1fd4ad1dd530ec5679` |
| Models file | `7967c701d6de04f2fbd7e9e92b2dc1ae3a877929bfd3b04bdc6e4acbe927bbcc` |

**Ownership/recovery boundary:** the scoped pilot operator owns the new operation/policy pending adoption. A future adoption plan must account for both resources and the still-divergent live API IDs/authentication; **do not blindly apply the broader repository or its rollback recipe**. Recovery requires Desktop closed, a matching backup/profile/metadata/helper/ACL baseline, current owned-resource ETags and a reviewed plan. User/app drift requires manual review, not an old rollback command. The repository-managed workflow instructions below do not establish live-pilot ownership.

## Read-only discovery

This section describes the **governance collector**, not the gateway's request-time reader. Use an existing Azure CLI login with a **separately provisioned read-only identity**. The script runs only these management-plane reads, with explicit subscription/resource-group/account arguments where applicable and a 60-second timeout per subprocess:

- `az cognitiveservices account show`
- `az cognitiveservices account deployment list`
- `az cognitiveservices account list-models`
- `az cognitiveservices usage list` for the account's region

It checks `AIServices`, account `Succeeded`, the account ARM ID, and ownership of the expected HTTPS `/anthropic` URL using `customSubDomainName`. It does not change the active CLI subscription, fetch keys, invoke inference, accept Marketplace terms or write any Azure resources. No raw CLI stdout/stderr or credentials are emitted to CI logs; validation errors may identify deployment IDs.

Provision approved read-only permissions for account, deployment and model-list reads at **account scope**, plus `Microsoft.CognitiveServices/locations/usages/read` at **subscription scope** for the regional quota read. Account-scoped Reader alone is insufficient: a denied quota read fails the whole discovery run rather than producing a partial update. A successful run with a personal credential does not prove the dedicated discovery identity has these permissions.

After setting the explicit target values and the **current Opus deployment ID**, an operator can generate local review files:

```bash
mkdir -p out/model-review
python3 scripts/sync_claude_models.py \
  --subscription "${FOUNDRY_SUBSCRIPTION_ID}" \
  --resource-group "${FOUNDRY_RESOURCE_GROUP}" \
  --account "${FOUNDRY_ACCOUNT_NAME}" \
  --expected-base-url "${FOUNDRY_BASE_URL}" \
  --default-model "${ANTHROPIC_DEFAULT_OPUS_MODEL}" \
  --catalog-file out/model-review/catalog.json \
  --report-file out/model-review/report.json
```

`--default-model` is mandatory on the first run. On later runs, give the same catalog file; the default is preserved, and supplying a different default fails. Copy the previously reviewed catalog into the output location before a new discovery run if using a fresh directory. No live catalog is shipped in this repository; the test fixture is synthetic.

### Catalog and failure contract

The normalized catalog contains only:

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1` |
| `account_resource_id`, `base_url` | The single verified Foundry account and its `/anthropic` endpoint |
| `default_model` | The preserved default **deployment name** |
| `models` | Default first, then other deployment IDs in stable sorted order |
| Each model | `id`, `display_name`, `description`, `model_name`, `model_version`, `sku`; optional `hosting` with `source`/`source_account` when Azure supplies model-source identity |

`id` is the actual deployment name, not an ARM ID, family alias or invented routing name. Successful Anthropic format/publisher deployments are eligible. Claude Code recognizes discovered IDs only when they contain `claude` or `anthropic`, case-insensitively; the **collector** rejects an eligible deployment whose name fails that filter. The **runtime reader** returns its real ID, which the CLI may hide; it never invents an alias to bypass the client filter.

Version/SKU values absent from inventory become `null` with warnings. Catalog metadata is not substituted for missing deployment facts. Capabilities, retirement/deprecation, SKU/capacity, upgrade policy and regional quota stay in the separate report, not in the public model list. No 1M context, effort, family mapping or speed capability is guessed. A fast SKU/model is handled like any other deployment; a catalog-only fast variant is not enabled by `/fast`. Creating it remains a separate future action, and inference speed is unverified.

Review exact deployment IDs, not only labels/descriptions, which may contain misleading Unicode formatting.

For the **collector**, malformed JSON/schema, duplicate IDs, partial REST envelopes instead of complete CLI lists, unexpected empty deployment/catalog lists, wrong account/backend, and conflicting deployment identities fail before changing output bytes. A model/version/SKU/source identity change under an existing ID requires review; even a change between unknown and known version/SKU is not silently accepted. Existing labels/descriptions and the default are retained. Missing or non-`Succeeded` previous entries are retained and listed as **stale** in this governance baseline. A non-empty inventory where all previous deployments failed can therefore retain an entirely stale governance catalog. This is deliberately different from the runtime reader, which rebuilds a complete fresh list and removes absent entries, including returning an empty list.

To accept an intentional identity change, use separately approved, out-of-band read-only inspection of the current deployment on the explicit account. Review its identity diff against the previous reviewed catalog and the impact on pinned roles. Only after approval, explicitly update that existing catalog entry's approved identity fields (`model_name`, `model_version`, `sku`, `hosting`), keeping its deployment ID, the default and other entries intact, then rerun sync and review the resulting catalog/report. **Never delete the entire catalog or rebootstrap to silently accept retargeting or a changed default.** A sync rejected for retargeting leaves the old report in place; it is not evidence of the new identity.

**Last-known-deployed is not runtime availability or authorization to redeploy.** Check the report and actual endpoint behavior before promotion. A regional quota row is not proof of model availability, remaining deployment capacity, permissions or performance. Catalog-only candidates are compared by model/version/SKU/source identity against the successful deployment inventory.

Both files are validated/serialized and staged before replacement, with an atomic replace per file. The report includes `catalog_sha256`. A filesystem failure between the two replaces can leave a complete report for a catalog that was not promoted; reject a mismatched pair rather than treating the report as proof of a successful update.

## Disabled-by-default scheduled workflow

`.github/workflows/sync-models.yml` supports manual runs and a daily schedule. Its only job is skipped unless `vars.MODEL_DISCOVERY_ENABLED == 'true'`. This effective value can come from the repository or, if unset there, the organization.

Before opting in, owners must separately configure the protected GitHub environment **`model-discovery`**:

- Restrict **deployment branches and tags** to a selected branch rule naming only the repository's **default branch**, with no tag rules. This is required before enabling either manual dispatch or the daily schedule; do not leave the environment unrestricted or assume "Protected branches only" means the default branch alone.
- Secrets `AZURE_MODEL_DISCOVERY_CLIENT_ID` and `AZURE_MODEL_DISCOVERY_TENANT_ID`. Configure the identity's GitHub OIDC federation for this environment and the approved account-scope reads plus subscription-scope usage read above. Verify these with the dedicated identity, not a personal credential. It must not be the deployment writer identity. There is **no fallback** to `AZURE_CLIENT_ID` or `AZURE_TENANT_ID`.
- Variables `FOUNDRY_SUBSCRIPTION_ID`, `FOUNDRY_RESOURCE_GROUP`, `FOUNDRY_ACCOUNT_NAME`, `FOUNDRY_BASE_URL`, and `ANTHROPIC_DEFAULT_OPUS_MODEL` for the one explicit account/default.
- Optional `MODEL_CATALOG_FILE`: repository-relative path of the previously reviewed, committed catalog. When configured, it is read from `github.sha`, not from an arbitrary runner path. Leave unset only for an explicit-default bootstrap.

The workflow uses `contents: read` and job-scoped `id-token: write`. It uploads catalog/report artifacts only; it does not deploy models or APIM, run OpenTofu, commit files, open PRs or dispatch another workflow. Check the report's catalog hash and retain review evidence. Artifacts contain account/model metadata; keep access restricted appropriately.

Governance promotion is deliberately separate: **review artifact → commit approved catalog → owning deployment workflow's optional review input**. The discovery workflow cannot approve its own output. This artifact is not the runtime publication mechanism or an inference allowlist.

## OpenTofu integration and gateway behavior

Set optional `MODEL_CATALOG_FILE` in the protected environment used by `deploy.yml` to a committed repository-relative catalog path. Plan and apply both read that path at the checked-out `github.sha`; neither invokes discovery. `generate_tfvars.py` validates and embeds the **contents** as `model_catalog` in `inputs.tfvars.json`, not a file path that OpenTofu can reopen. The existing `inputs_sha256` approval check freezes all catalog contents; the plan artifact also includes the catalog and its own hash in `run-context.json`.

The optional governance input still requires the primary account/base URL, all three existing role pins, and `default_model == opus_deployment_name`. Essential schema, uniqueness, binding and default checks also apply to direct OpenTofu tfvars. For compatibility, this **review-input mode** rejects greenfield and a distinct secondary Foundry account/backend; an independent secondary APIM using the **same** Foundry account is allowed. Without that input, distinct secondary accounts and greenfield's one configured deployment for all three roles remain supported. None of these catalog contents populate runtime inventory or decide inference membership.

OpenTofu embeds base64 JSON containing **each APIM instance's own Foundry account resource ID** and its configured Opus/Sonnet/Haiku pins. Account/model names are data, not raw C# or XML interpolation. Both primary and secondary IDs are validated as unencoded account IDs with a subscription UUID and safe resource names. Valid Unicode letters/digits and punctuation in resource-group names are URI-encoded; URL delimiters, control characters, encoded input IDs and traversal are rejected again at runtime before an identity request. The backend URL and account ID must still describe the same intended target; verify that binding before deployment.

### Runtime inventory and authorization boundary

`GET /v1/models` (including `?limit=1000`) inherits the unchanged Entra role-OR-configured-Desktop authorization, caller identity key and a separate per-user RPM counter. Only then may it read the internal cache or ARM. It uses `send-request mode="new"`, with no copied caller headers, body or query, to:

```text
GET https://management.azure.com{this-instance-account-resource-id}/deployments?api-version=2024-10-01
Managed identity resource: https://management.azure.com/
```

The JSON is returned locally **before** inference identity acquisition (`https://ai.azure.com`), backend selection or inference concurrency admission. No inventory request is made on either POST operation. The unauthenticated `/health` exception, credential stripping, inference throttles and backend-owned model validation are unchanged. This does **not** replace the live pilot's stricter auth policy.

The existing account-scoped `azurerm_role_assignment.foundry_user` uses role ID `53ca6127-db72-4b80-b1b0-d745d6d5456d` (**Foundry User**, formerly Azure AI User). Its `Microsoft.CognitiveServices/*/read` action includes deployments/read. The policy now depends on that existing assignment; **no new role or grant is introduced**. A later release must verify the actual assignment for every APIM identity/account, propagation, and outbound DNS/HTTPS access to public-Azure `management.azure.com:443`, including private-network gateways. A source dependency does not prove live permission or connectivity. The collector's separate identity and subscription-scope quota permission are not runtime prerequisites.

Successful (`Succeeded`) deployments with Anthropic `model.format` or `model.publisher` are included; failed/creating and other publishers are omitted. Model **deployment names**, not catalog candidates or project names, are the public `id` and `display_name`. An added or removed deployment in the bound account is reflected on a later fresh read, without regenerating policy or running the collector. Merely adding a model to the global Foundry model catalog, or to another account, does not publish it here.

The reader validates the response envelope, essential row fields, account-bound IDs, and case-insensitive ID uniqueness across pages. A malformed successful deployment fails the whole read. Complete valid empty inventory returns `200 {"data":[]}`. Each refresh rebuilds the list; no old entries are merged. Present Opus/Sonnet/Haiku pins come first, deduplicated, then remaining IDs in ordinal sorted order. Missing pins are **not fabricated**. Known families are derived from the **actual model name**, with native `anthropic_family_tier` and `is_family_default` only for that family; a default is true only for its matching configured pin. All-Opus pins never relabel an Opus deployment as Sonnet/Haiku. Unfamiliar families remain discoverable without guessed family, speed, context or effort capabilities. No ARM identity, tags, SKU or other private metadata is projected.

Account deployment administrators therefore control what all authorized gateway callers can discover and ask the backend to serve. The review artifact does not veto runtime publication or protect pins against retargeting. A per-model audience boundary requires separately governed accounts, not an assumption that this shared inventory is a per-user allowlist.

### Freshness, bounds, and failures

- Only complete, validated successes, including an empty list, are placed in APIM's **internal value cache for 30 seconds**. The bounded hashed key includes account, pins and projection version; distinct secondary accounts cannot share it. Authentication always precedes lookup. Hits do not rewrite the cache or extend its TTL; there is no stale fallback or partial cache write.
- On a miss, a separate **account-keyed admission limit of 10 reads per 10 seconds** protects ARM (at most three page calls per admitted read). It does not share inference counters. Cache writes are asynchronous and the internal cache is volatile, so an initial client burst or cache outage can produce discovery `503`s before the cache warms. These APIM-local controls are approximate, not a distributed lock or a subscription-wide quota guarantee.
- At most **3 pages, 1,000 total deployment rows**, and **1 MiB per page** (body bytes, decoded string length and UTF-8 byte count) are processed. APIM buffers/reads the response before the size check: this is a processing bound, not a streaming network/memory cap. The elapsed processing budget is **5 seconds**, checked before/after page reads and before publication, with a **2-second send-request timeout per page**. An in-flight call may finish after the budget; its late result is rejected. Managed-identity token acquisition/cold latency remains platform behavior, not a promised hard client deadline.
- `nextLink` is untrusted. Only HTTPS `management.azure.com` on the standard port, the exact bound deployments path, API version `2024-10-01`, and one `$skiptoken` continuation parameter are accepted (including encoded keys/token values). Userinfo, fragments, traversal/ambiguous paths, duplicate/unknown parameters and repeated tokens are rejected **before another identity request**. Opaque token encoding is preserved. Unsupported continuation shapes or a remaining link after page three fail closed, never publish a partial list. Verify real provider pagination compatibility at release.
- ARM denial/throttling, transport/token failures, malformed data, unsafe links, exhausted bounds and miss-admission failures produce the same redacted **503**. No ARM body, exception, URL, subscription details or token is returned. Caller **401/403** and per-user **429** remain unchanged. There are no HTTP-failure retries or mutation calls, and known-ID inference is independent of an ARM discovery outage.

Responses have JSON Content-Type and `Cache-Control: no-store`; that client-facing header is independent of the short internal value cache. End-to-end freshness is **gateway TTL + ARM propagation + client refresh**, normally at launch. It is not instant, an already-open picker is not polled by this policy, and cached/fallback client entries are not evidence of a successful refresh. A missing default pin may make Desktop choose the first remaining entry; no pin-resolution guarantee is implied.

Stock discovery deadlines are about **3 seconds for CLI and 10 seconds for Desktop**. Cold managed identity, ARM latency or long pagination can exceed the CLI deadline despite the gateway bounds. Before rollout, verify actual policy compilation, permitted account reads, observed continuation encoding, cold **and** warm latency/cache behavior, add/remove/empty refreshes, and the pinned clients. Do not change installed clients or introduce new timeout settings as part of this source fix.

### Disabling the catalog and rollback compatibility

The `models` operation and its operation policy are created **even without a catalog**. Once deployed, record that discovery-capable source revision as the **oldest compatible rollback baseline** for this feature. Older revisions would delete those resources, which the existing `plan_summary.py` destructive-change gate rejects; they are not a supported rollback through the standard workflow.

To disable future collector jobs, set the **repository-level** `MODEL_DISCOVERY_ENABLED` variable explicitly to `false`; preserve the previous `MODEL_CATALOG_FILE` path **and its reviewed catalog file**. Deleting or unsetting the repository variable inherits any organization value; collection is disabled then only if that inherited value is not `true`. This does not cancel an in-flight job or require an APIM apply. `MODEL_CATALOG_FILE` is only the collector's previous reviewed baseline and an optional deployment governance input: removing that deployment input disables neither the collector nor runtime discovery, and deleting the baseline risks silently rebootstrapping identity/default review. Undo client opt-in through the client owner as described below. Removing the operation/policy requires a separately approved deletion path; **do not relax the destructive-change gate**. See [operations and rollback](operations-runbook.md).

## Client opt-in, only after the endpoint is published

Both generators default to their previous outputs. Append `--enable-model-discovery` to the existing generation command only after the owning endpoint has been published and verified:

- **Claude Code:** [managed settings generator](claude-code-managed-settings.md) adds only `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` to `env`, preserving the helper, generic gateway URL and all role pins. The upstream client requests `GET /v1/models?limit=1000` with its helper authentication at startup. Serve it directly, without a redirect; discovery failure can leave cached/fallback picker entries, which is not evidence of successful discovery. An existing `availableModels` restriction (or a picker configured to replace built-ins) can still hide discovered entries.
- **Managed Desktop:** [configuration generator](desktop-deployment.md) sets `modelDiscoveryEnabled` to the existing string encoding `"true"` and **omits `inferenceModels`**, including its explicit `anthropicFamilyTier`/`isFamilyDefault` mappings. An explicit list overrides native discovery. The endpoint supplies native family/default fields for known families, but neither these fields nor ordering prove that Desktop preserves all configured role mappings; a missing default may leave the first remaining entry selected. The Windows `.reg` also explicitly deletes a previous `inferenceModels` value in the selected `--windows-scope` (`machine` by default, or `user`); omission alone would leave the old registry value active. The removal `.reg` covers that key as well, preserving unrelated policy values. No files are installed/imported by generation. Back up existing policy; the removal file does not restore an overwritten fixed list.

The actual [Windows Desktop pilot](windows-desktop-pilot.md) uses a **local Gateway/helper-script profile**, not the generated MDM/browser-OIDC profile. Do not apply an OIDC profile or register a new client to obtain model discovery. The separately approved 2026-10-26 local change is recorded above; any further change must retain its connection/helper/config metadata. Check higher-precedence managed policy for a remaining fixed list. This repository adds no local-profile installer or automatic profile mutation.

**Required Desktop release gate for broader rollout:** on the pinned Desktop build, verify that bare `opus`, `sonnet` and `haiku` aliases **and refusal fallback** actually resolve to the approved pinned deployment IDs. Putting all three pins ahead of older alphabetically sorted models is a mitigation, not a mapping guarantee. In particular, cross-family mappings such as the pilot's all-Opus pins cannot be assumed from list order. Outside the bounded pilot exception above, if resolution is wrong or unverified, **keep Desktop discovery disabled and retain the existing fixed list** until a supported mapping resolution is established. The pilot's offline default-Opus check does not satisfy this full gate. Terminal role pins remain explicit; do not substitute unproven Desktop metadata or native options for this release gate.

Restart the pinned clients after their separately approved opt-in. Verify helper-authenticated listing, rejected unauthenticated/unauthorized listing, default ordering, an additional deployed model in both pickers, exact model selection and inference, and unchanged token/concurrency controls. Offline tests do not prove APIM policy compilation, actual client behavior, live availability or speed. To roll back client discovery, regenerate without the flag and restore any backed-up local/managed configuration through its owner; do not silently prune or retarget the catalog.

## Offline policy logic tests

From the repository root, with OpenTofu and an installed .NET SDK:

```bash
python3 -B -m unittest discover -s scripts/test -p 'test_dynamic_model_policy.py' -v
```

The provider-free console renders the actual Tofu templates. The harness extracts and compiles the XML-decoded C# (C# 5-compatible, within APIM's C# 7 subset) and executes it against synthetic `value`/`nextLink` envelopes. It uses the SDK's bundled Newtonsoft.Json assembly, not a NuGet package or a production dependency; missing compilers fail the suite. Existing CI unittest discovery includes these tests without a workflow change.

For an explicitly approved WSL/native-compiler check, set `CSC` to the existing compiler executable, `NEWTONSOFT_JSON` to a compatible existing assembly, and `POLICY_TEST_BUILD_ROOT` to an approved Windows temporary parent (host/WSL paths). The harness copies only test inputs/the assembly into an owned `opencode-pr6-*` directory, uses PowerShell `-NoProfile` with a clean process environment, and removes only its own directory afterward. No installed client, global configuration or original assembly is changed. Compiler/assembly and generated-expression hashes are printed. No toolchain is installed automatically.

JWT validation, HTTP calls, cache storage and rate counters are test doubles; the real policy conditions, configuration validation, pagination checks, state transitions, projection and error handling execute as C#. These tests do not certify APIM policy acceptance, live managed identity/RBAC/egress, distributed cache/rate-limit semantics or client deadlines. Those remain separately approved release checks.

## Sources

- [Claude Code gateway protocol](https://code.claude.com/docs/en/llm-gateway-protocol)
- [Desktop discovery and explicit model list](https://claude.com/docs/third-party/claude-desktop/configuration#modeldiscoveryenabled)
- [Azure CLI account/model reads](https://learn.microsoft.com/en-us/cli/azure/cognitiveservices/account)
- [Azure account model metadata](https://learn.microsoft.com/python/api/azure-mgmt-cognitiveservices/azure.mgmt.cognitiveservices.models.accountmodel)
- [Subscription-scope quota read permissions](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/role-based-access-control)
- [GitHub environment deployment branch restrictions](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)
- [APIM policy expressions](https://learn.microsoft.com/en-us/azure/api-management/api-management-policy-expressions)
- [ARM deployment inventory, API 2024-10-01](https://learn.microsoft.com/en-us/rest/api/aiservices/accountmanagement/deployments/list?view=rest-aiservices-accountmanagement-2024-10-01)
- [Foundry User role actions](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/ai-machine-learning#foundry-user)
- [APIM send-request](https://learn.microsoft.com/en-us/azure/api-management/send-request-policy), [value-cache lookup](https://learn.microsoft.com/en-us/azure/api-management/cache-lookup-value-policy) and [asynchronous value-cache storage](https://learn.microsoft.com/en-us/azure/api-management/cache-store-value-policy)

Documentation was checked through Context7, then Microsoft Learn for Azure schema gaps and the official Desktop reference for its discovery/list precedence.
