Claude apps gateway: isolated Azure VM proof of concept
=====================================================

This is an ADDITION, not a migration of the repository's APIM solution. All
source, state and operator artifacts for this POC belong in claude-gateway/.
Nothing imports production state, modifies the existing subnet/Foundry account,
or changes core infrastructure, policies, client helpers or workflows. The only
write against an existing resource is an additive account-scoped Foundry role
assignment for the NEW VM identity. Never import an existing resource group.

Topology:
  private pilot CLI/browser -- HTTPS 8443 --> native "claude gateway"
      on one Ubuntu 24.04 x64 VM -- managed identity --> existing Foundry
                         |
                         +-- PostgreSQL 16, 127.0.0.1 only
                         +-- Entra OIDC browser sign-in

This is Anthropic's Claude apps gateway built into the native claude binary;
there is no LiteLLM, custom inference proxy, APIM hop, or Docker dependency.
One Standard_B2s VM and local PostgreSQL are deliberately non-HA and disposable.
The public_url setting names the private HTTPS origin, NOT a public IP.

Prerequisites / boundary
-----------------------
* OpenTofu 1.12.3; AzureRM provider 4.56.0, with its lockfile included here.
  The deploying operator authenticates to Azure on their workstation. Their
  identity needs resource creation, subnet join, and role-assignment rights
  on the target Foundry account. Register Microsoft.Compute, Microsoft.Network
  and Microsoft.CognitiveServices in the appropriate subscriptions separately;
  this module deliberately disables automatic provider registration.
* A NEW isolated resource group and an existing subnet in the VM subscription
  and chosen region. Foundry can be in another subscription in the SAME tenant.
  The account-scoped role ID 53ca6127-db72-4b80-b1b0-d745d6d5456d matches the
  core solution's Foundry User assignment (infra/tofu/monitoring.tf).
  No subscription-wide inference assignment, static Foundry key, or Azure CLI
  user login is installed on the VM.
* Operator-owned routing/NAT/firewall must ALREADY allow approved outbound
  HTTPS to Entra discovery/JWKS/token/userinfo endpoints, the selected Foundry
  endpoint and its dependencies, and Ubuntu package repositories. DNS/NTP and
  Azure VM agent platform connectivity must work. The VM also needs direct
  Azure IMDS access at 169.254.169.254. No public IP/NAT/firewall is created.
  Default NSG outbound rules are not an egress allowlist: the existing network
  boundary is responsible for approved egress. Proxy-only egress is outside
  this POC; do not weaken identity or SSRF controls to make it work.
* Private VPN/peering/management access, reviewed RFC1918 client CIDRs, and
  narrow RFC1918 SSH management CIDRs (prefer /32s). The NIC NSG allows only
  TCP 8443 and 22 from those respective ranges, then explicitly denies ALL
  other inbound, including Azure's default virtual-network allow. Existing
  subnet NSGs must also allow the intended paths. No 80/443/5432 opening.
* An operator-managed private DNS A record resolving ONLY to the VM's private
  IPv4 address and a matching CA-issued TLS certificate/full chain and
  unencrypted private key. This small implementation intentionally accepts only
  RFC1918 IPv4, not all upstream-supported private address types. Trust the CA
  on pilot clients/browser and provide its trust bundle for installation.
  There is no public DNS or certificate automation and no insecure TLS fallback.
* A dedicated single-tenant Entra confidential WEB app registration. Register
  exactly https://YOUR_PRIVATE_HOST:8443/oauth/callback (including the port).
  Configure email and group claims, assign the pilot group, enable assignment
  required, and permit openid/profile/email/offline_access and refresh tokens.
  Use group Object IDs, not display names. For group-overage/nested-membership
  cases prefer assigned App Roles; set groups_claim to "roles" and provide
  exact role values. This POC does not resolve Graph overage or nested groups.
* Approved Claude model deployments already available in the Foundry account.
  Know each canonical Claude model ID AND its possibly different deployment
  name. Configure only the models you intend to expose; built-ins are disabled.
* An approved exact native Linux x64 claude release, independently checked
  against Anthropic's GPG-SIGNED release manifest. Follow the official binary
  integrity instructions and verify the documented signing-key fingerprint.
  Record that release's version and the binary's manifest SHA256; transport it
  over private SSH. A checksum alone is not signature verification.
* The standard Ubuntu 24.04 Python 3, OpenSSL, coreutils, apt, systemd and
  user-management tools must already be present. Installation checks these
  prerequisites before validating inputs or installing PostgreSQL.

Native gateway first shipped at 2.1.195. THIS template uses managed.policies.code
and requires gateway and pilot clients >= 2.1.296. Pick a recent organization-
approved exact version, not "latest", and check its upstream feature gates.
The installer checks the pin, SHA256, Linux x64 ELF header, private DNS, TLS,
and explicit operator confirmation. It does NOT download a binary, verify the
release signature for you, or establish that a version is organization-approved.
signed_release_verified is the operator's attestation of prior verification.

Stage 1: standalone infrastructure (operator workstation)
--------------------------------------------------------
From the repository root:

  cd claude-gateway
  umask 077
  cp terraform.tfvars.example terraform.tfvars
  # Edit every placeholder and replace BOTH example CIDR lists.
  # subnet_id must be in subscription_id and location; supply only a public SSH key.
  tofu init
  tofu fmt -check
  tofu validate
  tofu plan -out=poc.tfplan
  # Review: ONLY new POC resources and the account-scoped identity role assignment.
  tofu apply poc.tfplan
  tofu output
  GATEWAY_IP=$(tofu output -raw private_ip)

Applying creates billable Azure resources; planning does not deploy them.
No live Azure resources are deployed by the repository's local validation.

State is local to claude-gateway/claude-gateway.tfstate, never the core backend.
Keep state and saved plans access-restricted and backed up securely for destroy.
Do not pass core backend arguments, copy its state, or run from infra/tofu.
For shared use, design a SEPARATE encrypted/locked state backend before rollout;
this local-state POC is single-operator only. No secret is sent through tfvars,
resources, VM custom_data, provisioners, outputs, or cloud-init.

Create the private DNS A record now. The VM address is dynamic allocation but
normally stable for the NIC lifetime; update DNS after replacing its NIC.
Ensure the runtime foundry_resource equals "tofu output -raw foundry_resource_name".
Confirm private SSH host identity via a trusted administrative channel before
accepting its host key; do not disable SSH host-key verification.

Stage 2: approved runtime + secret provisioning
----------------------------------------------
On the workstation, staying inside claude-gateway/:

  mkdir -p artifacts
  cp settings.example.json settings.json
  # Edit all placeholders. Example model entry (only if actually deployed):
  # {"id":"claude-sonnet-4-6","deployment":"YOUR_APPROVED_DEPLOYMENT_NAME"}
  # First model is the initial CLI model. Include any required helper/Haiku model.
  # Set tenant/client IDs, exact allowed groups/roles, foundry_resource,
  # private HTTPS URL, approved exact version and verified manifest SHA256.
  # Set signed_release_verified=true ONLY after signature verification.
  # Place the verified native Linux x64 executable at artifacts/claude.
  python3 configure.py settings.json --binary artifacts/claude
  ssh "gatewayadmin@$GATEWAY_IP" 'mkdir -p ~/claude-gateway-stage && chmod 700 ~/claude-gateway-stage'
  scp install.sh configure.py gateway.template.json claude-gateway.service \
      settings.json artifacts/claude "gatewayadmin@$GATEWAY_IP:claude-gateway-stage/"
  ssh -t "gatewayadmin@$GATEWAY_IP"

On the VM, first inspect the transferred installer and supporting source.
Then promote the package and inputs into root-owned directories to prevent
unprivileged modification while sudo executes it:

  sudo install -d -m 0700 /root/claude-gateway-package /root/claude-gateway-input
  sudo install -o root -g root -m 0600 \
      ~/claude-gateway-stage/{install.sh,configure.py,gateway.template.json,claude-gateway.service} \
      /root/claude-gateway-package/
  sudo install -o root -g root -m 0600 \
      ~/claude-gateway-stage/{settings.json,claude} /root/claude-gateway-input/
  sudo -i
  cd /root/claude-gateway-input
  umask 077

Use your approved secret-management provisioning channel to create these files,
each root:root mode 0600, with no secret values in terminal history/arguments:
  tls.crt       CA-issued server certificate, followed by intermediate chain
  tls.key       corresponding unencrypted PEM private key
  ca.crt        trusted root CA bundle for certificate/readiness verification
  oidc-secret   Entra application's actual client secret (not its secret ID)

For oidc-secret only, an interactive, non-echoed alternative inside that root
shell is:

  read -r -s -p 'Entra client secret: ' OIDC_SECRET; printf '\n'
  printf '%s' "$OIDC_SECRET" > oidc-secret
  unset OIDC_SECRET
  chmod 600 tls.crt tls.key ca.crt oidc-secret settings.json claude
  bash /root/claude-gateway-package/install.sh /root/claude-gateway-input
  # Type the required confirmation only for this disposable isolated VM.

The installer is initial-install-only, not an idempotent upgrade tool. It uses
Ubuntu apt packages, a nologin service user, root-owned group-readable 0640
configuration/secrets under a 0750 directory, independently random session/DB
secrets, a SCRAM database owner limited to its dedicated DB, and systemd.
The root-owned package files are checked before the renderer is invoked.
Systemd provides private writable temporary space and keeps durable service
state at /var/lib/claude-gateway.
Passwords never enter argv or DB URLs. PostgreSQL listens only on loopback;
plaintext DB transport is intentionally limited to this single host, NOT a
template for remote PostgreSQL. Remote database deployments require TLS.

gateway.template.json is JSON, a YAML subset. configure.py renders it to
/etc/claude-gateway/gateway.yaml without a Python YAML dependency. It rejects
unknown input keys and placeholders, not arbitrary upstream configuration.
The NATIVE binary performs authoritative schema validation during startup.
The systemd unit clears its environment and uses a dedicated empty home to keep
environment credentials and user Azure CLI caches out of DefaultAzureCredential.
Do not add Azure credential variables, install/login Azure CLI as the service
user, mount another user's home, or block IMDS. The VM's system-assigned identity
is the intended only available upstream credential; confirm with live inference.

Readiness failure stops/disables the service; it never retries with API keys,
HTTP, TLS verification disabled, or relaxed group restrictions. Inspect and
fix the installation in place; do NOT rerun the installer to regenerate secrets.
After correcting the cause, use "systemctl enable --now claude-gateway" and
repeat every acceptance check. Destroy/recreate a failed disposable POC if
you cannot confidently identify partial installation state.
After success remove staging/private input copies using your approved disposal
process; keep the controlled release/signature evidence and secret source of
truth elsewhere. Do not delete the active files in /etc/claude-gateway.

Acceptance (required before declaring the POC deployed)
------------------------------------------------------
The repository's offline tests do not prove Azure, native gateway or Entra work.
Complete these checks on the actual network and approved binary:

1. On the VM:
     sudo systemctl is-active claude-gateway postgresql
     sudo ss -lntp
   Expect TLS 8443, SSH 22, PostgreSQL ONLY 127.0.0.1:5432, no plaintext HTTP.
   Review restricted logs with sudo journalctl -u claude-gateway --since today.
   Do not enable debug/token logging or paste journals into tickets unredacted.
   Audit logs can contain identity and operational metadata even with telemetry
   off. Restrict journal membership, retention and VM/disk access accordingly.

2. Confirm IMDS token availability without printing/storing the token:
     curl --noproxy '*' --fail --silent --show-error -H Metadata:true \
       'http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https%3A%2F%2Fcognitiveservices.azure.com%2F' \
       --output /dev/null
   Compare the VM identity in Azure with managed_identity_principal_id output,
   and verify ONLY its intended Foundry account-scoped role. IMDS reachability
   alone does not prove upstream RBAC; role propagation can take several minutes.

3. From an allowed pilot client/browser with the private CA trusted:
     curl --fail https://YOUR_PRIVATE_HOST:8443/healthz
     curl --fail https://YOUR_PRIVATE_HOST:8443/readyz
     curl --fail https://YOUR_PRIVATE_HOST:8443/.well-known/oauth-authorization-server
   /readyz checks the database, NOT successful Foundry inference. Discovery
   confirms config/OIDC discovery/upstream client initialization/migrations.
   Test TCP 8443 from a disallowed source is blocked; SSH must work only from
   management CIDRs, and 5432 must never be reachable remotely.

4. Use dedicated managed PILOT machines/profiles, not existing APIM clients.
   Deploy the following client-side managed settings through your MDM (substitute
   the real private URL; do not put these keys in the gateway-delivered policy):
     {
       "forceLoginMethod": "gateway",
       "forceLoginGatewayUrl": "https://YOUR_PRIVATE_HOST:8443",
       "env": {"CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "1"}
     }
   Remove/replace conflicting APIM pilot-profile configuration using your MDM
   process: apiKeyHelper, ANTHROPIC_BASE_URL, static credential variables,
   provider switches, and old deployment-name model overrides. Do not edit the
   main generators or disable scrubbing. Verify the effective managed settings
   on the pinned OS/client; there is no settings-migration automation here.
   parentSettingsBehavior: "merge" is relevant only when deliberately merging
   Claude Desktop parent settings. Desktop is NOT implemented/tested in this POC.
   Never push forceLoginMethod or forceLoginOrgUUID from managed.policies.code.

5. Start the approved Claude Code client, run /login and complete gateway
   browser SSO. Check /status, /model, effective policy and the presented URL.
   In a signed-in terminal, perform a real, billable tiny inference:
     claude -p --model YOUR_CANONICAL_ALLOWED_ID 'Reply with exactly POC_OK.'
   Check that the expected Foundry deployment received it under the VM identity.
   Also test a streaming interactive response. Helpers/background tasks may need
   an explicitly mapped Haiku deployment; add only approved canonical IDs.

6. Negative checks: unassigned/non-allowed user sign-in must fail. A signed-in
   pilot requesting an existing canonical model NOT in availableModels must
   receive a rejection, not be routed to Foundry. Built-in models must not
   silently reappear. Test group removal/disabled-user refresh and re-login;
   an already minted bearer can remain valid for up to the one-hour session TTL.
   Verify TLS hostname/trust failure is not bypassed and loss of PostgreSQL makes
   /readyz fail. Stop the gateway manually if you require no inference during a
   DB outage: direct-to-VM clients are NOT automatically readiness-gated.

Operations, limitations, teardown
--------------------------------
* No HA, backups/restore automation, SLA, load balancing, rolling upgrades,
  budget/spend controls, admin API keys, telemetry forwarding or unattended
  service-token inference flow. This is a human SSO CLI pilot, not CI auth.
  The telemetry section is omitted (off); nonessential client/server traffic
  is disabled. No prompts, tokens or credentials are intentionally logged by
  these scripts, but review native runtime logs and network behavior yourself.
* The native gateway defaults to 256 concurrent upstream requests and queues
  additional requests. This small VM is not capacity-tested; that concurrency
  limit is not a throughput or memory-capacity guarantee. Keep the pilot small.
* Existing bearer sessions can still infer during a PostgreSQL outage. No
  load balancer gates requests on readiness in this topology.
* Do not co-host untrusted workloads: other processes with OS-level access can
  reach IMDS; systemd hardening is not an identity boundary against root.
  The gateway can distribute powerful client policy; control admin/root access.
* Access gating is group-based with a deny-all catch-all and explicit model
  mappings. There is one permitted group-set/policy, not per-team administration.
  Client gateway login replaces claude.ai sign-in; do not expect Enterprise
  web/mobile, SCIM, or claude.ai server-managed settings through this gateway.
* Before an upgrade, save a protected DB backup and config/release records,
  verify the new signed binary and schema gates, stop the service, install the
  verified binary root:root 0755, update the private install record, then start
  and repeat acceptance. Gateway boot can migrate the DB: binary-only rollback
  is not safe without matching DB/config recovery. Installer reruns are refused.
* Rotate TLS/OIDC secrets through root-owned 0640 files, atomically replacing
  approved content and restarting. Replacing session-secret invalidates all
  sessions immediately; upstream supports staged arrays for overlap if needed.
  Rotate the database role password and file together while the service is
  stopped. Keep secret values out of command arguments and shell tracing.
* For teardown, first remove the dedicated pilot MDM policy, revoke the POC app
  credential/assignments and sign-ins, remove private DNS, stop the VM service,
  and securely retain/dispose of evidence and sensitive disk/backups as required.
  Back on the SAME operator state directory:
     cd claude-gateway
     tofu plan -destroy -out=destroy.tfplan
     tofu apply destroy.tfplan
  Verify deletion of the POC RG/resources and VM identity role assignment, while
  the pre-existing subnet, Foundry account and production APIM remain intact.
  Keep state until teardown verification completes; never manually delete state
  instead of destroying resources. DNS/Entra/MDM changes are operator-managed
  and are not removed by tofu destroy.

Local validation (from repository root)
---------------------------------------
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s claude-gateway/tests -v
  bash -n claude-gateway/install.sh
  shellcheck claude-gateway/install.sh
  tofu -chdir=claude-gateway fmt -check
  tofu -chdir=claude-gateway init -backend=false
  tofu -chdir=claude-gateway validate

Tests use Python's standard library only, safe fake identifiers and in-memory
binary fixtures; they create no scratch files. No cloud deployment or native gateway
startup is claimed by offline tests. Signing approval, native schema/startup,
systemd/PostgreSQL installation, IMDS/RBAC, private routing/DNS/TLS, SSO,
deprovisioning and positive/negative inference remain live operator gates.

Authoritative upstream references (review when choosing your release):
  https://code.claude.com/docs/en/claude-apps-gateway
  https://code.claude.com/docs/en/claude-apps-gateway-config
  https://code.claude.com/docs/en/claude-apps-gateway-deploy
  https://code.claude.com/docs/en/setup#binary-integrity-and-code-signing
