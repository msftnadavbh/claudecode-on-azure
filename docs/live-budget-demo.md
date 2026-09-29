# Temporary native token-budget demonstration

**Manual, opt-in, billable, and live-verified on the locked pilot.** This runner installs a
temporary quota, demonstrates it, then restores the original **absent operation
policy**. It does not leave a budget enabled for later interactive use.

## Verified rehearsal

Run `bda8e7b4-f526-41c3-b265-7403e17bc971` used a **1,024-token monthly demo quota**, independently acquired Linux/Windows helper tokens for the same validated tenant/user, and no authentication changes.

| Request | Status | Native remaining estimate | Backend usage |
| --- | --- | --- | --- |
| Linux helper | 200 | 526 | 494 input + 4 output |
| Windows helper | 200 | 28 | 494 input + 4 output |
| Linux helper | 200 | 526 | 494 input + 4 output |
| Linux helper | 403 | 28 | No usage response; native `x-demo-retry-after: 153138` |
| After policy restoration | 200 | No demo headers | 14 input + 5 output |

The intermediate increase in the remaining estimate and third successful request are real observed behavior, not omitted errors. This proves native quota denial after usage, **not exact global accounting or a hard 1,024-token spend ceiling**. The runner verified operation-policy absence and unchanged protected configuration hashes after removal. Normal service is restored; no demo quota remains active. These were bounded synthetic HTTP probes using each client's helper credentials, not requests submitted through the two application UIs.

Recovery state is retained at `~/.local/state/claude-budget-demo/bda8e7b4-f526-41c3-b265-7403e17bc971/state.json` with `restored: true`.

## 90-second evidence walkthrough (not a 90-second live run)

1. Show the [Opus 5.5 CLI pilot](opus-5-5-pilot.md) and [Windows Desktop Chat pilot](windows-desktop-pilot.md): both used real, separately acquired Entra credentials through the strict keyless APIM API; Desktop used local Gateway `helper-script`, **not** the unused OIDC registration or a registry policy. Do not display tokens, config files, or local recovery state.
2. Point to the table above: Linux 200 (526 remaining), Windows 200 (28), Linux 200 (526), then Linux 403 with native retry-after; after policy removal a 200 had no demo headers. The synthetic HTTP requests used helper tokens, **not** either application's UI. They demonstrate a shared tenant/user counter key and an observed denial, not accurate shared accounting, application-UI quota behavior, or a dollar cap.
3. State that the operation policy was removed and verified absent. Repository monthly quota remains disabled by default (`0`), and the full OpenTofu configuration was not applied to this pilot. A new live run requires idle clients, explicit approval, billable requests, recovery time and the safeguards below; it cannot be promised to finish in 90 seconds.

## Before running

- Obtain lead review for changes to the runner. The recorded rehearsal completed architecture and independent security review before execution.
- Fully stop Claude Code, Windows Desktop, and every other client using this
  pilot user. Keep them stopped until restoration is confirmed. The temporary
  quota covers **all messages for that user**, not just this script.
- Use this Linux/WSL workstation with already authenticated Linux and native
  Windows Azure CLI sessions. The native helper must already exist at
  `C:\Users\nadavbh\AppData\Local\claudecodepoc\desktop-entra-pilot.cmd`.
  No login, consent, assignment, default subscription, client configuration,
  secret, or infrastructure changes are made.
- Keep the reviewed strict API-policy reference at
  `/tmp/opencode/claude55-live-private/candidate-policy.xml`; its SHA-256 is pinned
  in the runner. It is read only for initial validation; the protected state
  retains its canonical structural digest for subsequent checks and recovery.
  Recovery does not require the temporary reference file. No other old snapshots
  or scripts are read/imported.
- Python 3.11+ standard library only; control-plane read access and permission
  to create/delete the single operation policy are required. Tokens stay in
  captured process output/memory, never command arguments or files. Local claim
  inspection is **not** signature verification; the inherited strict APIM
  validator verifies both independently acquired gateway tokens.

From the repository root:

```sh
# Offline verification only:
python3 -B -m unittest discover -s scripts/test -p 'test_live_budget_demo.py' -v

# Repeat the live rehearsal only while other clients are idle:
python3 scripts/test/live_budget_demo.py run --execute --clients-idle
```

## Locked scope and expected sequence

Subscription `68eab0d1-ab81-4851-b2dd-173dede87582`, tenant
`16b3c013-d300-468d-ac64-7eda0820b6d3`, resource group `claudepoc-rg`, gateway
`apim-claudecode-project-test-01`, API `claude-api`, operation `messages`.
The **only mutation target** is `messages/policies/policy`. APIM REST uses
`2024-05-01`, with `rawxml` on policy GET/PUT and `Accept: application/json`.
Keep `rawxml`: lead verification found that `xml` double-escapes policy expressions.
The read-only Foundry deployment
lookup uses its separate Cognitive Services API version `2024-10-01`.

1. Privately inspect both gateway tokens: exact tenant/user, CLI application,
   audience, v1 format, `Gateway.Invoke` role **and** `AiGateway.Invoke` scope.
   Snapshot/hash fresh service/global and API policies, API config, operation
   definitions, separate count policy, backend, associated products/policies,
   schemas, and model configuration. Verify the pinned strict policy, v2 tier,
   routes, HTTPS/keyless API, Foundry backend and Opus 5.5 version 2 deployment.
   Unexpected/missing/paginated config fails closed; sensitive ARM responses
   stay in memory, only hashes are persisted. Hashes ignore resource-envelope
   `etag`/`systemData` and ARM resource-list ordering (sorted by ID/name), not
   configuration-array or XML element ordering. Drift reports resource paths,
   never raw configuration values.
2. Require a fresh 404 for the messages operation policy. Count a fixed synthetic
   prompt once; abort without mutation unless the input count is **480–510**.
   Lead preflight measured **494 input tokens twice**, including model overhead;
   those earlier checks stopped before policy PUT and made no policy mutation.
3. Save durable recovery state before PUT, recheck context/404, create the
   operation policy, and wait 30 seconds. The policy inherits `<base />` first
   in every section; the strict API authorization and managed identity to
   `https://ai.azure.com`/`foundry-claude` remain unchanged. Native
   `llm-token-limit` has Monthly 1024, estimation enabled, and counter key
   `demoUUID:validatedTid:validatedOid` from `pilotJwt`. It adds no unsupported
   API-schema attributes. An outbound-only static marker proves propagation;
   native quota/error headers and bodies are not synthesized or replaced.
4. Send two identical nonstreaming synthetic HTTP messages using the Linux and
   Windows **helper tokens**, then a third using the Linux token. These are
   labeled `synthetic-http-linux-helper` / `synthetic-http-windows-helper`,
   **not** actual Claude Code/Desktop application tests. Two 200 responses must
   expose genuine actual input/output usage (input 480–510, output 1–8, no cache),
   native consumed/remaining headers, and the marker. Native header estimates
   are observations: they need not equal actual usage, be positive, or decrease
   monotonically. If the third returns 200, validate it identically and send
   **one final identical fourth message**; there is no fifth demo message.
   The third or fourth must return 403 with the native numeric
   `x-demo-retry-after` header or a recognized native token-quota error code.
   Generic authorization 403s or quota-like message text alone do not qualify.
   Remaining/consumed headers are optional on denial; remaining may be negative.
   Missing required success evidence, unsupported policy/schema behavior,
   successful fourth inference, or other failure stops and attempts restore.
5. Conditionally delete only the candidate-owned policy, wait 30 seconds, then
   require policy 404, unchanged context hashes, and a tiny 200 canary without
   the marker. The normal path has **five data-plane requests total**: count,
   two successes, one denial, restored canary. The bounded extension permits
   **six total**: count, three successes, fourth-message denial, restored canary.
   There are no further inference retries or polling loops. Requests are at
   most 3,000 bytes and completions at most 8
   tokens, with no cache instructions, images, tools, or streaming. Inference
   is still billable, including third/fourth successes.

At the calibrated upper input bound, four demo messages represent at most
**2,040 input + 32 output tokens**, excluding the separate count request and
restored tiny canary. An out-of-range actual response fails verification after
that request; the input check is not a server-side billing cap. At the measured
494 input plus the 8-token output cap, two successes total at most 1,004 actual
tokens; third-message denial is expected but only native evidence proves it.
The quota and observed estimates are not a dollar ledger.

The remaining header is an **estimate, not a dollar ledger**. Denial is reported
as `admission_blocked` with observed headers, **never zero-token exhaustion**,
regardless of whether remaining is positive, zero, negative, or absent. Counters are gateway-local;
this does not establish distributed accounting, concurrent overshoot bounds,
or application integration. Fresh UUIDs isolate repeated demos; they do not
reset any production counter.

## Recovery — do not ignore a failure

The runner prints its exact durable state directory before PUT:
`~/.local/state/claude-budget-demo/<uuid>/`. Directories are 0700; atomic,
fsynced `state.json` is 0600. It contains candidate XML/hash, target, original
absence, context hashes, deadline, and observed ETag, **no credentials or raw
ARM snapshots**. Output only includes safe status, allowlisted error codes,
numeric native quota headers, and numeric usage; it never includes raw errors
or model text.

```sh
# Substitute exactly the directory printed by this run, not the parent:
python3 scripts/test/live_budget_demo.py restore --execute \
  --state "$HOME/.local/state/claude-budget-demo/<uuid>"
```

`finally` is active before PUT, including ambiguous accepted-but-timed-out PUTs.
If the final context, absence, or deadline check fails before PUT, state is marked
`aborted-before-put` and no cleanup request or restored-success claim is made;
explicit recovery of that completed abort also skips cleanup. Missing phase is
not treated as an abort (older or ambiguous state still requires recovery).
SIGINT/SIGTERM/SIGHUP attempt cleanup. SIGKILL, power loss, lost credentials, network
failure or interruption during cleanup require the explicit restore command.
Recovery waits 30 seconds before its ownership read (including ambiguous PUTs)
and another 30 seconds after deletion/absence before verification. It acquires
a fresh management token rather than reusing the run's token; all post-delete
context checks use the saved policy digest even if the reference file is gone.
Run tokens require more than 900 seconds remaining; recovery's management and
canary tokens require more than 120 seconds, so a still-valid short-lived cached
token does not unnecessarily block restoration. Tenant/user/authorization checks
remain unchanged.
The saved ten-minute deadline stops further demo inference, **not an automatic
server-side expiry or background watchdog**. Recovery remains allowed after it.

Restore requires exact candidate XML structure and a current specific ETag;
when an ETag was recorded, it must still match. An ambiguous PUT with no recorded
ETag can be recovered only if the live structure is exactly this UUID's
candidate, using its freshly read ETag. Deletes never use wildcard `If-Match`.
A concurrent edit/412 or context drift is reported as failed restoration;
the runner never overwrites another policy. Leave clients stopped and escalate
to the lead/architect for manual inspection—do not change state to bypass the
guards. Creation sends `If-None-Match: *` plus fresh absence checks; operators
must prevent concurrent policy writers because APIM's documented create API
does not promise cross-resource transactional isolation. The durable state
does not replace that operational exclusion.

## Documentation basis

Context7 policy snippets had no matching native-policy documentation, so the
implementation used Microsoft Learn and its code sample search:

- [Native llm-token-limit policy](https://learn.microsoft.com/azure/api-management/llm-token-limit-policy):
  Anthropic Messages support currently requires APIM **v2 tiers**, quota 403,
  header names, actual usage vs estimation, concurrency and regional limits.
- [Operation policy GET, 2024-05-01](https://learn.microsoft.com/rest/api/apimanagement/api-operation-policy/get?view=rest-apimanagement-2024-05-01):
  `rawxml` export and ETag.

Offline mocks establish guard/cleanup behavior, **not** live APIM schema recognition, propagation, or pricing. The rehearsal above separately establishes the observed live results; it does not certify fleet-wide budgets or future-run timing.
