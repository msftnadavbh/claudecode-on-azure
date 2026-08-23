resource "azurerm_role_assignment" "foundry_user" {
  provider                         = azurerm.foundry
  for_each                         = local.apim_instances
  name                             = uuidv5("11fb06fb-712d-4ddd-98c7-e71bbd588830", "${each.value.foundry_resource_id}-${azapi_resource.apim[each.key].output.identity.principalId}-53ca6127-db72-4b80-b1b0-d745d6d5456d")
  scope                            = each.value.foundry_resource_id
  role_definition_id               = "/subscriptions/${split("/", each.value.foundry_resource_id)[2]}/providers/Microsoft.Authorization/roleDefinitions/53ca6127-db72-4b80-b1b0-d745d6d5456d"
  principal_id                     = azapi_resource.apim[each.key].output.identity.principalId
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "monitoring_metrics_publisher" {
  provider                         = azurerm.telemetry
  for_each                         = var.observability_enabled ? local.apim_instances : {}
  name                             = uuidv5("11fb06fb-712d-4ddd-98c7-e71bbd588830", "${local.app_insights_id}-${azapi_resource.apim[each.key].output.identity.principalId}-3913510d-42f4-4e42-8a64-420c390055eb")
  scope                            = local.app_insights_id
  role_definition_id               = "/subscriptions/${split("/", local.app_insights_id)[2]}/providers/Microsoft.Authorization/roleDefinitions/3913510d-42f4-4e42-8a64-420c390055eb"
  principal_id                     = azapi_resource.apim[each.key].output.identity.principalId
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

resource "azurerm_monitor_metric_alert" "cpu" {
  for_each            = var.observability_enabled ? local.apim_instances : {}
  name                = "${each.value.name}-high-capacity"
  resource_group_name = var.resource_group_name
  scopes              = [azapi_resource.apim[each.key].id]
  description         = "APIM gateway CPU capacity is sustained above 70 percent."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.ApiManagement/service"
    metric_name      = "CpuPercent_Gateway"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 70
  }

  dynamic "action" {
    for_each = var.action_group_resource_id == "" ? [] : [var.action_group_resource_id]
    content { action_group_id = action.value }
  }
}

resource "azurerm_monitor_metric_alert" "memory" {
  for_each            = var.observability_enabled ? local.apim_instances : {}
  name                = "${each.value.name}-high-memory"
  resource_group_name = var.resource_group_name
  scopes              = [azapi_resource.apim[each.key].id]
  description         = "APIM gateway memory is sustained above the configured threshold."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.ApiManagement/service"
    metric_name      = "MemoryPercent_Gateway"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = var.memory_alert_threshold
  }

  dynamic "action" {
    for_each = var.action_group_resource_id == "" ? [] : [var.action_group_resource_id]
    content { action_group_id = action.value }
  }
}

resource "azurerm_monitor_metric_alert" "requests" {
  for_each            = var.observability_enabled ? local.apim_instances : {}
  name                = "${each.value.name}-gateway-errors"
  resource_group_name = var.resource_group_name
  scopes              = [azapi_resource.apim[each.key].id]
  description         = "APIM reports sustained authentication, authorization, or throttling responses."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.ApiManagement/service"
    metric_name      = "Requests"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 5

    dimension {
      name     = "GatewayResponseCode"
      operator = "Include"
      values   = ["401", "403", "429"]
    }
  }

  dynamic "action" {
    for_each = var.action_group_resource_id == "" ? [] : [var.action_group_resource_id]
    content { action_group_id = action.value }
  }
}

resource "azurerm_monitor_metric_alert" "gateway_5xx" {
  for_each            = var.observability_enabled ? local.apim_instances : {}
  name                = "${each.value.name}-gateway-5xx"
  resource_group_name = var.resource_group_name
  scopes              = [azapi_resource.apim[each.key].id]
  description         = "APIM reports sustained client-visible gateway 5xx responses."
  severity            = 1
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.ApiManagement/service"
    metric_name      = "Requests"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 5

    dimension {
      name     = "GatewayResponseCodeCategory"
      operator = "Include"
      values   = ["5xx"]
    }
  }

  dynamic "action" {
    for_each = var.action_group_resource_id == "" ? [] : [var.action_group_resource_id]
    content { action_group_id = action.value }
  }
}

resource "azurerm_monitor_metric_alert" "backend_5xx" {
  for_each            = var.observability_enabled ? local.apim_instances : {}
  name                = "${each.value.name}-backend-5xx"
  resource_group_name = var.resource_group_name
  scopes              = [azapi_resource.apim[each.key].id]
  description         = "Foundry reports sustained backend 5xx responses through APIM."
  severity            = 1
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.ApiManagement/service"
    metric_name      = "Requests"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 5

    dimension {
      name     = "BackendResponseCodeCategory"
      operator = "Include"
      values   = ["5xx"]
    }
  }

  dynamic "action" {
    for_each = var.action_group_resource_id == "" ? [] : [var.action_group_resource_id]
    content { action_group_id = action.value }
  }
}

resource "azurerm_traffic_manager_profile" "failover" {
  for_each               = local.deploy_traffic_manager ? { failover = true } : {}
  name                   = local.traffic_manager_name
  resource_group_name    = var.resource_group_name
  traffic_routing_method = "Priority"

  dns_config {
    relative_name = local.traffic_manager_name
    ttl           = 30
  }

  monitor_config {
    protocol                     = "HTTPS"
    port                         = 443
    path                         = "/claude/health"
    interval_in_seconds          = 30
    timeout_in_seconds           = 10
    tolerated_number_of_failures = 3
  }
}

resource "azurerm_traffic_manager_external_endpoint" "apim" {
  for_each = local.deploy_traffic_manager ? {
    primary   = { priority = 1 }
    secondary = { priority = 2 }
  } : {}

  name       = each.key
  profile_id = azurerm_traffic_manager_profile.failover["failover"].id
  target     = "${local.apim_instances[each.key].name}.azure-api.net"
  priority   = each.value.priority
}
