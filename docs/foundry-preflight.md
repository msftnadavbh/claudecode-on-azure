# Foundry preflight

Run this read-only check against the existing Foundry account and three configured deployments. You need Azure access to the account and resolved input values. The command creates and changes nothing; it does not prove quota headroom or enforce Foundry security settings.

Greenfield workflow runs `scripts/greenfield_foundry_preflight.py` against its exact account subscription, new resource-group name, location, model, version, SKU, and capacity. It requires an Azure-hosted catalog entry with `kind` `AIServices`, `model.format` `Anthropic`, and the selected nested `model.skus` entry. It uses that SKU entry's exact `usageName` to check quota; the account's `S0` SKU is not a deployment SKU. A fresh greenfield state rejects an already-existing resource group. On a partial-apply retry, the workflow passes `--allow-existing-resource-group` only after `tofu state show 'azurerm_resource_group.greenfield[0]'` confirms that exact address in the current state.

```bash
python3 scripts/foundry_preflight.py \
  --subscription "$FOUNDRY_SUBSCRIPTION_ID" \
  --resource-group "$FOUNDRY_RESOURCE_GROUP" \
  --account "$FOUNDRY_ACCOUNT_NAME" \
  --expected-base-url "$FOUNDRY_BASE_URL" \
  --deployment "opus=$ANTHROPIC_DEFAULT_OPUS_MODEL" \
  --deployment "sonnet=$ANTHROPIC_DEFAULT_SONNET_MODEL" \
  --deployment "haiku=$ANTHROPIC_DEFAULT_HAIKU_MODEL"
```

It fails on mismatched active subscription, account, endpoint, deployment state, or model publisher and emits deterministic JSON describing model, version, `version_upgrade_option`, SKU, and capacity from existing deployment data. Missing/blank versions and absent upgrade policies produce stable nonfatal warnings (absent policy is unknown); any policy other than `NoAutoUpgrade` leaves version stability unestablished. A deployment name alone is not a version pin. This check does not mutate deployments.

Use the same deployment names in a secondary Foundry target, but manually compare the actual primary/secondary **model, version, and upgrade policy** in both reports before failover approval, including a shared deployment mapped to multiple roles. Treat quota rows as advisory; confirm actual quota scope and operational headroom in Foundry before release.
