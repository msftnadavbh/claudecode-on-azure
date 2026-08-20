# Architecture and Security Boundaries

## Current State in This Repository

The repository baseline was effectively empty at initialization (`README.md` only). There was no local PoC implementation to refactor in place, so this change set establishes a production-aligned baseline structure and implementation artifacts directly.

## Target Architecture

Developer workstation
-> Claude Code
-> APIM (`/claude/v1/messages`)
-> APIM validates Entra JWT and derives stable user key
-> APIM applies authz/rate/quota/token policy
-> APIM strips caller `Authorization`
-> APIM authenticates with managed identity to Foundry
-> Microsoft Foundry Claude deployment

## Security Boundaries

- Boundary 1: Developer identity (Entra token) terminates at APIM.
- Boundary 2: APIM-to-Foundry uses APIM managed identity only.
- Boundary 3: No shared bearer secret for 500+ developer population.
- Boundary 4: Telemetry excludes request/response body by default.

## Scale Risks

- Long-lived SSE streams drive concurrent connection pressure independent of simple request-rate calculations.
- Subagents/parallel workers multiply active streams per human user.
- Model quotas and APIM gateway capacity can bottleneck independently.

## Availability Risks

- Regional dependency when only a single Foundry deployment exists.
- APIM policy failures causing hard reject spikes during token-claim format drift.
- Retry storms if transient backend failure handling is misconfigured.

## Production Blockers Addressed

- Shared APIM key as production identity boundary.
- Reliance on APIM management-plane secret access by end developers.
- Missing profile separation for PoC tiny limits vs production sizing.
- Missing synthetic SSE test harness for gateway capacity testing.
