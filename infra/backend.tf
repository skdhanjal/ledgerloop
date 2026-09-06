terraform {
  backend "gcs" {
    bucket = "ledgerloop-880ac9-tfstate"
    prefix = "terraform/state"
  }
}
