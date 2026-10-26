# Deprecated Bicep reference

This is a temporary, non-authoritative historical reference only. OpenTofu is the active deployment implementation.

**Do not deploy the current shared policies through Bicep.** `modules/apim.bicep` loads `apim/policies/claude-base.xml` as raw text and cannot substitute its new `${model_catalog_base64}` template token. The current templated policy therefore cannot be deployed by this reference. Use the owning OpenTofu deployment path only after [adoption and ownership](../tofu/tofu-adoption.md) are resolved; no Bicep code migration is provided here.

Final removal gate: remove this directory only after PoC and production imports, two zero-change plans, the first successful OpenTofu apply, and a rollback rehearsal.
