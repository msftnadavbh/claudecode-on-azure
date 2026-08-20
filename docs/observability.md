# Observability

Each production APIM instance owns a Log Analytics workspace, workspace-based Application Insights component, APIM logger/API diagnostic, platform diagnostic setting, autoscale rule, high-capacity alert, and gateway/backend response alert.

The Application Insights logger uses the APIM system-assigned identity with `Monitoring Metrics Publisher` on the component. Successful-request diagnostic sampling is 10%; errors are always retained. Resource metrics remain unsampled. Reassess the sampling percentage from measured cost and throughput before rollout.

Captured signals include region/resource, API operation, status/result class, gateway CPU/memory/capacity platform metrics, 401/403/429/5xx rates, and backend failures. Safe traces add APIM request ID plus validated tenant/user for incident investigation. No prompt, completion, source body, authorization header, API key, session ID, or agent ID is captured by APIM diagnostics.

Set `ACTION_GROUP_RESOURCE_ID` for production destinations. Alert thresholds are starting controls, not SLOs; tune from observed baselines. Create workbook/SLO views for:

- authentication/authorization failures;
- rate/quota pressure and Foundry 429;
- APIM/backend 5xx;
- CPU/memory/capacity saturation and autoscale;
- Traffic Manager endpoint health;
- circuit-open symptoms (clean 429/503 propagation);
- diagnostic ingestion delay/gaps.

Application Insights or Log Analytics loss must not block inference. Detect ingestion gaps through external Azure Monitor health alerts and investigate diagnostic settings; do not enable payload logging as a workaround.
