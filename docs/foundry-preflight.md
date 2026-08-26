# Foundry preflight

Run this read-only check against the existing Foundry account and three configured deployments. You need Azure access to the account and resolved input values. The command creates and changes nothing; it does not prove quota headroom or enforce Foundry security settings.

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

It fails on mismatched active subscription, account, endpoint, deployment state, or model publisher and emits deterministic JSON describing deployment version, SKU, and capacity. Use the same deployment names in a secondary Foundry target. Treat quota rows as advisory; confirm actual quota scope and operational headroom in Foundry before release.
