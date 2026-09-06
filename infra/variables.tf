variable "project_id" {
  type        = string
  description = "The single GCP project this entire build deploys into (one environment, per C18/§0.5)"
  default     = "ledgerloop-880ac9"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "image_tag" {
  type        = string
  description = "Container image tag (git short SHA) — passed at apply time from CI"
  default     = "local"
}
