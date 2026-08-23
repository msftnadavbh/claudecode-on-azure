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
  value = var.opus_deployment_name
}

output "sonnetModel" {
  value = var.sonnet_deployment_name
}

output "haikuModel" {
  value = var.haiku_deployment_name
}
