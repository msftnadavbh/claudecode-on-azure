variable "resource_group_name" {
  type        = string
  description = "Existing resource group in existing mode; new resource group created in greenfield mode."

  validation {
    condition     = length(var.resource_group_name) > 0
    error_message = "resource_group_name must not be empty."
  }
}

variable "deployment_mode" {
  type        = string
  description = "existing adopts the supplied Foundry target; greenfield creates the resource group and Foundry target."
  default     = "existing"

  validation {
    condition     = contains(["existing", "greenfield"], var.deployment_mode)
    error_message = "deployment_mode must be existing or greenfield."
  }
}

variable "location" {
  type        = string
  description = "Primary Azure region."

  validation {
    condition     = length(var.location) > 0
    error_message = "location must not be empty."
  }
}

variable "secondary_location" {
  type        = string
  description = "Secondary Azure region when deploy_secondary is enabled."
  default     = ""
}

variable "apim_name" {
  type        = string
  description = "Primary APIM service name."

  validation {
    condition     = length(var.apim_name) > 0
    error_message = "apim_name must not be empty."
  }
}

variable "secondary_apim_name" {
  type        = string
  description = "Secondary APIM service name when deploy_secondary is enabled."
  default     = ""
}

variable "deploy_secondary" {
  type        = bool
  description = "Deploy an independent secondary APIM failure domain."
  default     = false
}

variable "publisher_email" {
  type        = string
  description = "APIM publisher email."

  validation {
    condition     = length(var.publisher_email) >= 3
    error_message = "publisher_email must be at least three characters."
  }
}

variable "publisher_name" {
  type        = string
  description = "APIM publisher name."

  validation {
    condition     = length(var.publisher_name) > 0
    error_message = "publisher_name must not be empty."
  }
}

variable "entra_tenant_id" {
  type        = string
  description = "Microsoft Entra tenant ID that issues caller tokens."

  validation {
    condition     = length(var.entra_tenant_id) == 36
    error_message = "entra_tenant_id must be 36 characters."
  }
}

variable "expected_audience" {
  type        = string
  description = "Expected Entra audience."

  validation {
    condition     = length(var.expected_audience) > 0
    error_message = "expected_audience must not be empty."
  }
}

variable "required_app_role" {
  type        = string
  description = "Entra app role required to invoke the gateway."

  validation {
    condition     = length(var.required_app_role) > 0
    error_message = "required_app_role must not be empty."
  }
}

variable "enable_claude_desktop_delegated_auth" {
  type        = bool
  description = "Allow Claude Desktop delegated access as an alternative to the app role."
  default     = false
}

variable "claude_desktop_client_id" {
  type        = string
  description = "Public client ID used by managed Claude Desktop."
  default     = "disabled"
}

variable "claude_desktop_delegated_scope" {
  type        = string
  description = "Delegated scope claim required from managed Claude Desktop."
  default     = "disabled"
}

variable "foundry_base_url" {
  type        = string
  description = "Primary Foundry Anthropic base URL, including /anthropic."

  default = ""

  validation {
    condition     = var.foundry_base_url == "" || can(regex("^https://[a-z0-9.-]+\\.services\\.ai\\.azure\\.com/anthropic$", lower(var.foundry_base_url)))
    error_message = "foundry_base_url must be HTTPS on *.services.ai.azure.com with exactly the /anthropic path."
  }
}

variable "secondary_foundry_base_url" {
  type        = string
  description = "Secondary Foundry Anthropic base URL. Empty uses foundry_base_url."
  default     = ""

  validation {
    condition     = var.secondary_foundry_base_url == "" || can(regex("^https://[a-z0-9.-]+\\.services\\.ai\\.azure\\.com/anthropic$", lower(var.secondary_foundry_base_url)))
    error_message = "secondary_foundry_base_url must be HTTPS on *.services.ai.azure.com with exactly the /anthropic path."
  }
}

variable "foundry_resource_id" {
  type        = string
  description = "Resource ID of the primary Foundry account in existing mode; greenfield derives it."

  default = ""

  validation {
    condition     = var.foundry_resource_id == "" || can(regex("^/subscriptions/[0-9a-fA-F-]{36}/resourceGroups/[^/]+/providers/Microsoft\\.CognitiveServices/accounts/[^/]+$", var.foundry_resource_id))
    error_message = "foundry_resource_id must be empty or a Cognitive Services account resource ID."
  }
}

variable "foundry_subscription_id" {
  type        = string
  description = "Subscription containing the existing Foundry account and managed role assignments; greenfield uses the target subscription."

  default = ""

  validation {
    condition     = var.foundry_subscription_id == "" || can(regex("^[0-9a-fA-F-]{36}$", var.foundry_subscription_id))
    error_message = "foundry_subscription_id must be a subscription UUID."
  }
}

variable "secondary_foundry_resource_id" {
  type        = string
  description = "Resource ID of the existing secondary Foundry account. Empty uses foundry_resource_id."
  default     = ""
}

variable "opus_deployment_name" {
  type        = string
  description = "Foundry deployment name pinned for the Opus role."

  default = ""
}

variable "sonnet_deployment_name" {
  type        = string
  description = "Foundry deployment name pinned for the Sonnet role."

  default = ""
}

variable "haiku_deployment_name" {
  type        = string
  description = "Foundry deployment name pinned for the Haiku role."

  default = ""
}

variable "foundry_account_name" {
  type        = string
  description = "Foundry account name; created in greenfield mode."
  default     = ""
}

variable "foundry_project_name" {
  type        = string
  description = "New Foundry project name in greenfield mode."
  default     = ""
}

variable "foundry_location" {
  type        = string
  description = "New Foundry account location in greenfield mode."
  default     = ""
}

variable "claude_model_deployment_name" {
  type        = string
  description = "The one Anthropic deployment created and used for all Claude Code roles in greenfield mode."
  default     = ""
}

variable "claude_model_name" {
  type        = string
  description = "Exact Anthropic model catalog name for greenfield mode."
  default     = ""
}

variable "claude_model_version" {
  type        = string
  description = "Exact Anthropic model catalog version for greenfield mode."
  default     = ""
}

variable "claude_model_sku" {
  type        = string
  description = "Anthropic deployment SKU for greenfield mode."
  default     = ""

  validation {
    condition     = var.claude_model_sku == "" || contains(["GlobalStandard", "DataZoneStandard"], var.claude_model_sku)
    error_message = "claude_model_sku must be GlobalStandard or DataZoneStandard."
  }
}

variable "claude_model_capacity" {
  type        = number
  description = "Positive Anthropic deployment capacity for greenfield mode."
  default     = 0

  validation {
    condition     = var.claude_model_capacity == 0 || (var.claude_model_capacity > 0 && floor(var.claude_model_capacity) == var.claude_model_capacity)
    error_message = "claude_model_capacity must be a positive integer when set."
  }
}

variable "claude_organization_name" {
  type        = string
  description = "Organization name required by the Anthropic Marketplace attestation."
  default     = ""

  validation {
    condition     = var.claude_organization_name == "" || (var.claude_organization_name == trimspace(var.claude_organization_name) && var.claude_organization_name != "" && !contains(["example", "placeholder"], lower(var.claude_organization_name)))
    error_message = "claude_organization_name must be a trimmed non-placeholder value."
  }
}

variable "claude_country_code" {
  type        = string
  description = "Country code required by the Anthropic Marketplace attestation."
  default     = ""

  validation {
    condition     = var.claude_country_code == "" || can(regex("^[A-Z]{2}$", var.claude_country_code))
    error_message = "claude_country_code must be an uppercase two-letter country code."
  }
}

variable "claude_industry" {
  type        = string
  description = "Industry required by the Anthropic Marketplace attestation."
  default     = ""

  validation {
    condition     = var.claude_industry == "" || contains(["education", "finance", "government", "healthcare", "manufacturing", "media", "other", "retail", "technology"], var.claude_industry)
    error_message = "claude_industry must be education, finance, government, healthcare, manufacturing, media, other, retail, or technology."
  }
}

variable "accept_anthropic_marketplace_terms" {
  type        = bool
  description = "Authorize OpenTofu/modelProviderData to accept Anthropic Marketplace terms and incur billing in greenfield mode."
  default     = false
}

variable "per_user_rate_limit" {
  type        = number
  description = "Rate limit calls per minute per user identity."

  validation {
    condition     = var.per_user_rate_limit >= 1
    error_message = "per_user_rate_limit must be at least one."
  }
}

variable "per_user_token_limit" {
  type        = number
  description = "Quota tokens per minute per user identity."

  validation {
    condition     = var.per_user_token_limit >= 1
    error_message = "per_user_token_limit must be at least one."
  }
}

variable "per_user_concurrent_stream_limit" {
  type        = number
  description = "Approximate maximum concurrent forwarded requests per user identity admitted by each APIM gateway."

  validation {
    condition     = var.per_user_concurrent_stream_limit >= 1
    error_message = "per_user_concurrent_stream_limit must be at least one."
  }
}

variable "aggregate_concurrent_stream_limit" {
  type        = number
  description = "Approximate maximum concurrent forwarded requests admitted by each APIM gateway."

  validation {
    condition     = var.aggregate_concurrent_stream_limit >= 1 && var.aggregate_concurrent_stream_limit < 2048
    error_message = "aggregate_concurrent_stream_limit must be between 1 and 2047."
  }
}

variable "apim_sku_name" {
  type        = string
  description = "APIM v2 SKU."

  validation {
    condition     = contains(["BasicV2", "StandardV2", "PremiumV2"], var.apim_sku_name)
    error_message = "apim_sku_name must be BasicV2, StandardV2, or PremiumV2."
  }
}

variable "default_capacity" {
  type        = number
  description = "Initially deployed APIM capacity."

  validation {
    condition     = var.default_capacity >= 1
    error_message = "default_capacity must be at least one."
  }
}

variable "zone_redundant" {
  type        = bool
  description = "Enable Premium v2 availability-zone redundancy at creation."
  default     = false
}

variable "networking_profile" {
  type        = string
  description = "Gateway networking profile."
  default     = "public"

  validation {
    condition     = contains(["public", "private"], var.networking_profile)
    error_message = "networking_profile must be public or private."
  }
}

variable "apim_subnet_resource_id" {
  type        = string
  description = "Existing dedicated subnet ID for primary Premium v2 VNet injection."
  default     = ""
}

variable "secondary_apim_subnet_resource_id" {
  type        = string
  description = "Existing dedicated subnet ID for secondary Premium v2 VNet injection."
  default     = ""
}

variable "observability_enabled" {
  type        = bool
  description = "Deploy telemetry, APIM diagnostics, and alerts."
  default     = true
}

variable "existing_workspace_resource_id" {
  type        = string
  description = "Existing shared Log Analytics workspace ID. Provide with existing_app_insights_resource_id, or provide neither to create both."
  default     = ""
}

variable "existing_app_insights_resource_id" {
  type        = string
  description = "Existing shared Application Insights ID. Provide with existing_workspace_resource_id, or provide neither to create both."
  default     = ""

  validation {
    condition     = var.existing_app_insights_resource_id == "" || can(regex("^/subscriptions/[0-9a-fA-F-]{36}/resourceGroups/[^/]+/providers/Microsoft\\.Insights/components/[^/]+$", var.existing_app_insights_resource_id))
    error_message = "existing_app_insights_resource_id must be an Application Insights resource ID."
  }
}

variable "action_group_resource_id" {
  type        = string
  description = "Existing Action Group ID. Empty creates alerts without actions."
  default     = ""
}

variable "memory_alert_threshold" {
  type        = number
  description = "APIM gateway memory alert threshold."
  default     = 80

  validation {
    condition     = var.memory_alert_threshold >= 1 && var.memory_alert_threshold <= 100
    error_message = "memory_alert_threshold must be between 1 and 100."
  }
}

variable "traffic_manager_enabled" {
  type        = bool
  description = "Deploy optional public Traffic Manager priority routing."
  default     = false
}

variable "traffic_manager_name" {
  type        = string
  description = "Globally unique Traffic Manager profile name. Empty uses <apim_name>-failover."
  default     = ""
}
