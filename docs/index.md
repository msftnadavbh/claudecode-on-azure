# Documentation

This repository creates APIM APIs and policies, APIM managed identities, `Foundry User` role assignments, optional telemetry and alerts, optional Traffic Manager, bundled shell/native Windows token helpers, and managed-client configuration generators. In greenfield mode it also creates a new resource group, Foundry account, project, and one Claude deployment. You provide Entra registrations, GitHub environments and identities, Blob state, and any required network, DNS, certificate, incident-routing, and client-management resources, including Foundry private endpoints.

The active deployment path is OpenTofu only. It creates no custom enterprise gateway hostname. `/claude/health` is APIM-local and does not test Foundry. The `migration/bicep` material is deprecated and non-authoritative; do not use it for deployment.

## Deploy

- [Getting started](getting-started.md)
- [GitHub configuration](github-configuration.md)
- [Foundry preflight](foundry-preflight.md)
- [OpenTofu adoption](../migration/tofu/tofu-adoption.md)

## Configure clients

- [Client authentication](client-authentication.md)
- [Managed Claude Code settings](claude-code-managed-settings.md)
- [Client canary](claude-code-canary.md)
- [Desktop preview](desktop-deployment.md)

## Focused live pilot evidence (not full IaC validation)

- [Opus 5.5 and Linux Claude Code](opus-5-5-pilot.md)
- [Windows Desktop local Gateway-mode Chat](windows-desktop-pilot.md)
- [Temporary native monthly quota rehearsal and recovery](live-budget-demo.md)

## Operate

- [Networking](networking.md) and [availability and DR](availability-dr.md)
- [Capacity and load](03-capacity-plan.md) and [load testing](load-testing.md)
- [Observability](observability.md)
- [Operations and rollback](operations-runbook.md)
- [Production readiness](production-readiness.md)
- [Troubleshooting](troubleshooting.md)

## Reference

- [Architecture](01-architecture.md)
- [Platform constraints](02-platform-constraints.md)
- [Security](security.md)
- [Migration and adoption](04-migration-plan.md)
