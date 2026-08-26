output "primaryGatewayUrl" {
  value = "https://${var.apim_name}.azure-api.net"
}

output "secondaryGatewayUrl" {
  value = var.deploy_secondary ? "https://${var.secondary_apim_name}.azure-api.net" : ""
}

output "gatewayFailoverFqdn" {
  value = local.deploy_traffic_manager ? azurerm_traffic_manager_profile.failover["failover"].fqdn : ""
}

output "opusModel" {
  value = var.deployment_mode == "greenfield" ? var.claude_model_deployment_name : var.opus_deployment_name
}

output "sonnetModel" {
  value = var.deployment_mode == "greenfield" ? var.claude_model_deployment_name : var.sonnet_deployment_name
}

output "haikuModel" {
  value = var.deployment_mode == "greenfield" ? var.claude_model_deployment_name : var.haiku_deployment_name
}

output "deploymentMode" {
  value = var.deployment_mode
}

output "foundryResourceId" {
  value = local.effective_foundry_resource_id
}

output "foundryBaseUrl" {
  value = local.effective_foundry_base_url
}

output "foundryProjectName" {
  value = var.deployment_mode == "greenfield" ? var.foundry_project_name : ""
}

output "managedFoundryDeploymentName" {
  value = var.deployment_mode == "greenfield" ? var.claude_model_deployment_name : ""
}
