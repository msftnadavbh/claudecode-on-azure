# Observability

Production creates one shared Log Analytics workspace and workspace-based Application Insights component. Every APIM instance sends zero-body diagnostics and resource metrics to that plane and keeps its resource/region identity. Set both `LOG_ANALYTICS_WORKSPACE_RESOURCE_ID` and `APPLICATION_INSIGHTS_RESOURCE_ID` to reuse an existing shared plane.

The Application Insights logger uses the APIM system-assigned identity with `Monitoring Metrics Publisher` on the component. Successful-request diagnostic sampling is 10%; errors are always retained. Resource metrics remain unsampled. Reassess the sampling percentage from measured cost and throughput before rollout.

Captured signals include region/resource, API operation, status/result class, gateway CPU and memory, gateway 401/403/429, gateway 5xx, and backend 5xx. Safe traces add APIM request ID plus validated tenant/user for incident investigation. No prompt, completion, source body, authorization header, API key, session ID, or agent ID is captured by APIM diagnostics.

`ACTION_GROUP_RESOURCE_ID` is required for production. Alert thresholds are starting controls, not SLOs; tune from observed baselines.

- authentication/authorization failures;
- rate/quota pressure and Foundry 429;
- APIM/backend 5xx;
- CPU/memory/capacity saturation and optional autoscale;
- optional Traffic Manager endpoint health;
- circuit-open symptoms (clean 429/503 propagation);
- diagnostic ingestion delay/gaps.

Application Insights or Log Analytics loss must not block inference. Detect ingestion gaps through external Azure Monitor health alerts and investigate diagnostic settings; do not enable payload logging as a workaround. Deploy per-region telemetry only as a customer compliance/data-residency overlay.
