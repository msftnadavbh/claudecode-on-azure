data "azurerm_client_config" "current" {}

locals {
  resource_group_id                         = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/resourceGroups/${var.resource_group_name}"
  minimum_capacity                          = coalesce(var.minimum_capacity, var.default_capacity)
  maximum_capacity                          = coalesce(var.maximum_capacity, var.default_capacity)
  secondary_foundry_base_url                = var.secondary_foundry_base_url != "" ? var.secondary_foundry_base_url : var.foundry_base_url
  secondary_foundry_resource_id             = var.secondary_foundry_resource_id != "" ? var.secondary_foundry_resource_id : var.foundry_resource_id
  traffic_manager_name                      = var.traffic_manager_name != "" ? var.traffic_manager_name : "${var.apim_name}-failover"
  deploy_traffic_manager                    = var.deploy_secondary && var.networking_profile == "public" && coalesce(var.traffic_manager_enabled, true)
  use_existing_telemetry                    = var.existing_workspace_resource_id != "" && var.existing_app_insights_resource_id != ""
  existing_app_insights_id_segments         = split("/", var.existing_app_insights_resource_id)
  existing_app_insights_resource_group_name = local.use_existing_telemetry ? local.existing_app_insights_id_segments[4] : null
  existing_app_insights_name                = local.use_existing_telemetry ? local.existing_app_insights_id_segments[8] : null
  app_insights_id                           = local.use_existing_telemetry ? var.existing_app_insights_resource_id : try(azurerm_application_insights.shared["shared"].id, null)
  workspace_id                              = local.use_existing_telemetry ? var.existing_workspace_resource_id : try(azurerm_log_analytics_workspace.shared["shared"].id, null)
  app_insights_connection_string            = local.use_existing_telemetry ? try(data.azurerm_application_insights.existing["shared"].connection_string, null) : try(azurerm_application_insights.shared["shared"].connection_string, null)

  apim_instances = merge({
    primary = {
      name                = var.apim_name
      location            = var.location
      foundry_base_url    = var.foundry_base_url
      subnet_resource_id  = var.apim_subnet_resource_id
      foundry_resource_id = var.foundry_resource_id
    }
    }, var.deploy_secondary ? {
    secondary = {
      name                = var.secondary_apim_name
      location            = var.secondary_location
      foundry_base_url    = local.secondary_foundry_base_url
      subnet_resource_id  = var.secondary_apim_subnet_resource_id
      foundry_resource_id = local.secondary_foundry_resource_id
    }
  } : {})

  named_values = {
    "entra-tenant-id"                       = var.entra_tenant_id
    "expected-audience"                     = var.expected_audience
    "required-app-role"                     = var.required_app_role
    "claude-desktop-delegated-auth-enabled" = tostring(var.enable_claude_desktop_delegated_auth)
    "claude-desktop-client-id"              = var.claude_desktop_client_id
    "claude-desktop-delegated-scope"        = var.claude_desktop_delegated_scope
    "per-user-rate-limit"                   = tostring(var.per_user_rate_limit)
    "per-user-token-limit"                  = tostring(var.per_user_token_limit)
    "per-user-concurrent-stream-limit"      = tostring(var.per_user_concurrent_stream_limit)
    "aggregate-concurrent-stream-limit"     = tostring(var.aggregate_concurrent_stream_limit)
    "environment-profile"                   = var.environment_profile
  }

  operations = {
    messages = {
      display_name = "Create message"
      method       = "POST"
      url_template = "/v1/messages"
      policy_path  = "${path.module}/../../apim/policies/claude-messages.xml"
    }
    count-tokens = {
      display_name = "Count message tokens"
      method       = "POST"
      url_template = "/v1/messages/count_tokens"
      policy_path  = "${path.module}/../../apim/policies/claude-count-tokens.xml"
    }
    health = {
      display_name = "Gateway health"
      method       = "GET"
      url_template = "/health"
      policy_path  = "${path.module}/policies/health.xml"
    }
  }

  apim_operation_instances = {
    for pair in setproduct(keys(local.apim_instances), keys(local.operations)) :
    "${pair[0]}/${pair[1]}" => merge(local.apim_instances[pair[0]], local.operations[pair[1]], {
      apim_key      = pair[0]
      operation_key = pair[1]
    })
  }
}

data "azurerm_application_insights" "existing" {
  provider = azurerm.telemetry
  for_each = var.observability_enabled && local.use_existing_telemetry ? { shared = true } : {}

  name                = local.existing_app_insights_name
  resource_group_name = local.existing_app_insights_resource_group_name
}

resource "azapi_resource" "apim" {
  for_each  = local.apim_instances
  type      = "Microsoft.ApiManagement/service@2025-03-01-preview"
  name      = each.value.name
  parent_id = local.resource_group_id
  location  = each.value.location

  identity {
    type = "SystemAssigned"
  }

  body = {
    sku = {
      name     = var.apim_sku_name
      capacity = var.default_capacity
    }
    properties = {
      publisherEmail              = var.publisher_email
      publisherName               = var.publisher_name
      publicNetworkAccess         = var.networking_profile == "private" ? "Disabled" : "Enabled"
      virtualNetworkType          = var.networking_profile == "private" ? "Internal" : "None"
      virtualNetworkConfiguration = var.networking_profile == "private" ? { subnetResourceId = each.value.subnet_resource_id } : null
      zoneRedundant               = var.zone_redundant
    }
  }

  schema_validation_enabled = false
  response_export_values    = ["identity.principalId"]

  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = !var.deploy_secondary || (var.secondary_location != "" && var.secondary_apim_name != "")
      error_message = "secondary_location and secondary_apim_name are required when deploy_secondary is true."
    }
    precondition {
      condition     = var.networking_profile != "private" || (var.apim_subnet_resource_id != "" && (!var.deploy_secondary || var.secondary_apim_subnet_resource_id != ""))
      error_message = "Private networking requires a subnet ID for every deployed APIM instance."
    }
    precondition {
      condition     = local.minimum_capacity <= var.default_capacity && var.default_capacity <= local.maximum_capacity && (!var.zone_redundant || local.minimum_capacity >= 2)
      error_message = "APIM capacities must be ordered, and zone-redundant capacity must be at least two units."
    }
    precondition {
      condition     = var.per_user_concurrent_stream_limit <= var.aggregate_concurrent_stream_limit
      error_message = "Per-user concurrent streams cannot exceed the aggregate limit."
    }
    precondition {
      condition     = (var.existing_workspace_resource_id == "" && var.existing_app_insights_resource_id == "") || local.use_existing_telemetry
      error_message = "Provide both existing telemetry resource IDs, or neither."
    }
    precondition {
      condition     = var.environment_profile != "prod" || var.action_group_resource_id != ""
      error_message = "Production requires an existing Action Group resource ID."
    }
  }
}

resource "azurerm_api_management_backend" "foundry" {
  for_each            = local.apim_instances
  name                = "foundry-backend"
  resource_group_name = var.resource_group_name
  api_management_name = each.value.name
  protocol            = "http"
  url                 = each.value.foundry_base_url

  circuit_breaker_rule {
    name = "foundry-overload"

    failure_condition {
      count             = 3
      interval_duration = "PT1M"

      status_code_range {
        min = 429
        max = 429
      }
      status_code_range {
        min = 500
        max = 599
      }
    }

    trip_duration              = "PT1M"
    accept_retry_after_enabled = true
  }

  depends_on = [azapi_resource.apim]
}

resource "azurerm_api_management_named_value" "gateway" {
  for_each = {
    for pair in setproduct(keys(local.apim_instances), keys(local.named_values)) :
    "${pair[0]}/${pair[1]}" => {
      apim_key = pair[0]
      name     = pair[1]
      value    = local.named_values[pair[1]]
    }
  }

  name                = each.value.name
  resource_group_name = var.resource_group_name
  api_management_name = local.apim_instances[each.value.apim_key].name
  display_name        = each.value.name
  value               = each.value.value
  secret              = false

  depends_on = [azapi_resource.apim]
}

resource "azurerm_api_management_api" "claude" {
  for_each              = local.apim_instances
  name                  = "claude"
  resource_group_name   = var.resource_group_name
  api_management_name   = each.value.name
  revision              = "1"
  display_name          = "Claude Messages API"
  path                  = "claude"
  protocols             = ["https"]
  subscription_required = false

  depends_on = [azapi_resource.apim]
}

resource "azurerm_api_management_api_policy" "claude" {
  for_each            = local.apim_instances
  api_name            = azurerm_api_management_api.claude[each.key].name
  api_management_name = each.value.name
  resource_group_name = var.resource_group_name
  xml_content         = file("${path.module}/../../apim/policies/claude-base.xml")
}

resource "azurerm_api_management_api_operation" "claude" {
  for_each            = local.apim_operation_instances
  operation_id        = each.value.operation_key
  api_name            = azurerm_api_management_api.claude[each.value.apim_key].name
  api_management_name = each.value.name
  resource_group_name = var.resource_group_name
  display_name        = each.value.display_name
  method              = each.value.method
  url_template        = each.value.url_template
}

resource "azurerm_api_management_api_operation_policy" "claude" {
  for_each            = local.apim_operation_instances
  api_name            = azurerm_api_management_api.claude[each.value.apim_key].name
  api_management_name = each.value.name
  resource_group_name = var.resource_group_name
  operation_id        = azurerm_api_management_api_operation.claude[each.key].operation_id
  xml_content         = file(each.value.policy_path)
}

resource "azurerm_log_analytics_workspace" "shared" {
  for_each            = var.observability_enabled && !local.use_existing_telemetry ? { shared = true } : {}
  name                = "${var.apim_name}-logs"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_application_insights" "shared" {
  for_each            = var.observability_enabled && !local.use_existing_telemetry ? { shared = true } : {}
  name                = "${var.apim_name}-insights"
  location            = var.location
  resource_group_name = var.resource_group_name
  application_type    = "web"
  workspace_id        = azurerm_log_analytics_workspace.shared[each.key].id
  disable_ip_masking  = false
}

resource "azapi_resource" "application_insights_logger" {
  for_each  = var.observability_enabled ? local.apim_instances : {}
  type      = "Microsoft.ApiManagement/service/loggers@2024-05-01"
  name      = "application-insights"
  parent_id = azapi_resource.apim[each.key].id

  body = {
    properties = {
      loggerType = "applicationInsights"
      isBuffered = false
      credentials = {
        connectionString = local.app_insights_connection_string
        identityClientId = "SystemAssigned"
      }
    }
  }
}

resource "azurerm_api_management_api_diagnostic" "claude" {
  for_each                 = var.observability_enabled ? local.apim_instances : {}
  identifier               = "applicationinsights"
  resource_group_name      = var.resource_group_name
  api_management_name      = each.value.name
  api_name                 = azurerm_api_management_api.claude[each.key].name
  api_management_logger_id = azapi_resource.application_insights_logger[each.key].id
  sampling_percentage      = 10
  always_log_errors        = true
  log_client_ip            = false
  verbosity                = "information"
  frontend_request {
    body_bytes     = 0
    headers_to_log = []
  }
  frontend_response {
    body_bytes     = 0
    headers_to_log = []
  }
  backend_request {
    body_bytes     = 0
    headers_to_log = []
  }
  backend_response {
    body_bytes     = 0
    headers_to_log = []
  }
}

resource "azurerm_monitor_diagnostic_setting" "apim" {
  for_each                   = var.observability_enabled ? local.apim_instances : {}
  name                       = "send-to-log-analytics"
  target_resource_id         = azapi_resource.apim[each.key].id
  log_analytics_workspace_id = local.workspace_id

  enabled_log { category_group = "audit" }
  enabled_metric { category = "AllMetrics" }
}
