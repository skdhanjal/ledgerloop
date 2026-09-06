# Root module — one environment, one project, provisioned incrementally by the day
# that first needs each resource (C18 §0.5, §0.9). Nothing is instantiated here yet.
#
# Resource inventory by the day that introduces it (master doc, Day 27):
#   D1  (this day)  -> GCS state bucket, Artifact Registry, base IAM, this reusable module
#   D4              -> Secret Manager secrets for provider keys
#   D9              -> Cloud SQL instance (smallest tier), gateway + checkpointer schemas
#   D23             -> Cloud Storage bucket for eval artifacts
#   D27             -> Cloud Run x3 (via modules/cloud-run), VPC connector, service accounts,
#                      Identity Platform/OIDC config, Postgres RLS policies
#   D28             -> Cloud Build triggers, monitoring dashboards & alerts, Cloud Armor,
#                      Cloud Scheduler + eval job
#
# modules/cloud-run is written now and instantiated three times starting Day 4/27.
