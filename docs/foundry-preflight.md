# Foundry Preflight

`scripts/foundry_preflight.py` performs read-only checks against the existing Microsoft Foundry account and the three deployments configured for Claude. It creates or changes nothing.

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

The command fails when the active Azure subscription, account, endpoint, deployment state, or model publisher differs from the requested configuration. It prints deterministic JSON containing the resolved model version, SKU, and capacity for each role.

Quota rows are advisory. Azure usage output does not reliably prove the effective Claude quota pool or deployment headroom, so missing or ambiguous rows produce warnings rather than invented conclusions. Confirm effective quota scope and headroom in Microsoft Foundry before rollout.
