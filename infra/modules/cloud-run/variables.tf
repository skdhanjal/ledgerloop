variable "project_id" {
  type        = string
  description = "GCP project ID to deploy into"
}

variable "region" {
  type        = string
  description = "Cloud Run region"
  default     = "us-central1"
}

variable "service_name" {
  type        = string
  description = "Cloud Run service name (e.g. frontend, agent-service, litellm-gateway)"
}

variable "image" {
  type        = string
  description = "Fully-qualified container image, digest-pinned where the module caller requires it"
}

variable "container_port" {
  type        = number
  description = "Port the container listens on"
  default     = 8080
}

variable "env_vars" {
  type        = map(string)
  description = "Plain (non-secret) environment variables"
  default     = {}
}

variable "secret_env_vars" {
  type = map(object({
    secret_id = string
    version   = optional(string, "latest")
  }))
  description = "Environment variables sourced from Secret Manager: NAME => { secret_id, version }"
  default     = {}
}

variable "min_instances" {
  type        = number
  description = "Minimum instance count. 0 = scale to zero (this build's default for all three services)."
  default     = 0
}

variable "max_instances" {
  type        = number
  description = "Maximum instance count — a cost and blast-radius ceiling, not just a performance knob"
  default     = 5
}

variable "cpu" {
  type    = string
  default = "1"
}

variable "memory" {
  type    = string
  default = "512Mi"
}

variable "service_account_email" {
  type        = string
  description = "Least-privilege service account identity this revision runs as"
}

variable "vpc_connector_id" {
  type        = string
  description = "Serverless VPC Access connector ID, for services that must reach Cloud SQL over private IP. Null for services that don't need it."
  default     = null
}

variable "allow_unauthenticated" {
  type        = bool
  description = "Whether the service is publicly invocable. The agent-service API enforces its own tenant-scoped auth regardless (C11/C13) — this only controls the Cloud Run IAM layer in front of it."
  default     = false
}

variable "labels" {
  type    = map(string)
  default = {}
}
