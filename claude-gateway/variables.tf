variable "subscription_id" {
  type        = string
  description = "Subscription containing the new POC resource group and existing subnet."
  validation {
    condition     = can(regex("^[0-9a-fA-F-]{36}$", var.subscription_id))
    error_message = "Provide the deployment subscription UUID."
  }
}

variable "resource_group_name" {
  type        = string
  description = "NEW isolated POC resource group. Do not import or reuse a production group."
  validation {
    condition     = can(regex("^[a-zA-Z0-9_-]{3,80}$", var.resource_group_name))
    error_message = "Use a new resource group name (3-80 letters, digits, underscores or hyphens)."
  }
}

variable "location" {
  type        = string
  description = "Azure region of the existing subnet."
}

variable "subnet_id" {
  type        = string
  description = "Existing operator-owned subnet with private management and approved outbound routing."
  validation {
    condition     = can(regex("(?i)^/subscriptions/[0-9a-f-]{36}/resourceGroups/[^/]+/providers/Microsoft.Network/virtualNetworks/[^/]+/subnets/[^/]+$", var.subnet_id))
    error_message = "Provide a complete existing subnet resource ID."
  }
}

variable "foundry_resource_id" {
  type        = string
  description = "Existing Microsoft.CognitiveServices/accounts account; may be in another subscription in the same tenant."
  validation {
    condition     = can(regex("(?i)^/subscriptions/[0-9a-f-]{36}/resourceGroups/[^/]+/providers/Microsoft.CognitiveServices/accounts/[a-zA-Z0-9-]+$", var.foundry_resource_id))
    error_message = "Provide a Foundry account resource ID, not a project or model deployment ID."
  }
}

variable "ssh_public_key" {
  type        = string
  description = "Operator SSH PUBLIC key only; never a private key."
  validation {
    condition     = can(regex("^(ssh-ed25519|ssh-rsa) [A-Za-z0-9+/=]+", var.ssh_public_key))
    error_message = "Provide an OpenSSH public key."
  }
}

variable "client_cidrs" {
  type        = list(string)
  description = "Explicit RFC1918 IPv4 client ranges allowed to HTTPS 8443. No public ranges."
  validation {
    condition = length(var.client_cidrs) > 0 && alltrue([
      for cidr in var.client_cidrs : can(cidrnetmask(cidr)) && anytrue([
        for private in ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"] :
        try(cidrcontains(private, cidrhost(cidr, 0)) && cidrcontains(private, cidrhost(cidr, -1)), false)
      ])
    ])
    error_message = "Each client CIDR must be entirely within RFC1918 IPv4 space."
  }
}

variable "management_cidrs" {
  type        = list(string)
  description = "Explicit RFC1918 IPv4 operator ranges allowed to SSH 22; prefer individual /32s."
  validation {
    condition = length(var.management_cidrs) > 0 && alltrue([
      for cidr in var.management_cidrs : can(cidrnetmask(cidr)) && anytrue([
        for private in ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"] :
        try(cidrcontains(private, cidrhost(cidr, 0)) && cidrcontains(private, cidrhost(cidr, -1)), false)
      ])
    ])
    error_message = "Each management CIDR must be entirely within RFC1918 IPv4 space."
  }
}
