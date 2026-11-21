# [Kimi·2026-11-21] G03 cloud event path (design sections 3 and 6): one events
# topic with a pull subscription and a dead-letter policy, one dead-letter
# topic kept for replay, four BigQuery tables, one on-demand Cloud Run
# consumer job, the consumer identity and observability.
#
# Deliberately NOT here (shared G01/G02 infrastructure, their BOOTSTRAP.md):
#   - the Terraform state bucket, the github-deployer SA, WIF pool/provider
#   - project services G01 manages (run/storage/bigquery/artifactregistry/iam)
#     and the monitoring API G02 manages: re-declaring google_project_service
#     for them would fight the other projects' state. Only pubsub.googleapis.com
#     is new to this project and managed below.

# --- Service prerequisite (new to this project) ------------------------------

# Project number for the Pub/Sub service agent identity used by the
# dead-letter policy.
data "google_project" "current" {}

resource "google_project_service" "pubsub" {
  service            = "pubsub.googleapis.com"
  disable_on_destroy = false
}

# Chicken-and-egg #4 (G01/G02 lesson): build-push runs before the first apply
# can ever create the registry, so it is created by bootstrap and imported into
# state (see infra/BOOTSTRAP.md §1) — apply adopts it instead of creating it.
resource "google_artifact_registry_repository" "consumer" {
  location      = var.region
  repository_id = "aviation-events"
  format        = "DOCKER"
  description   = "G03 Aviation Event Processing images"
}

# --- Consumer identity --------------------------------------------------------
#
# The generator is a test command run locally with the owner's credentials
# (design section 6); only the consumer gets a service account.

resource "google_service_account" "runtime" {
  account_id   = "aviation-events-runtime"
  display_name = "G03 consumer runtime: pull subscription, BigQuery writes, DLQ publishes"
}

# Pull path on the events subscription.
resource "google_pubsub_subscription_iam_member" "runtime_subscriber" {
  subscription = google_pubsub_subscription.events_pull.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_pubsub_subscription_iam_member" "runtime_viewer" {
  subscription = google_pubsub_subscription.events_pull.name
  role         = "roles/pubsub.viewer"
  member       = "serviceAccount:${google_service_account.runtime.email}"
}

# The consumer publishes permanent failures to the DLQ itself before acking
# (design section 5); Pub/Sub's dead-letter policy covers crash loops.
resource "google_pubsub_topic_iam_member" "runtime_dlq_publisher" {
  topic  = google_pubsub_topic.dlq.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

# Transactional writes to the project's own dataset only.
resource "google_bigquery_dataset_iam_member" "runtime_writer" {
  dataset_id = google_bigquery_dataset.events.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

# --- Topics and subscriptions (design section 3) ------------------------------

resource "google_pubsub_topic" "events" {
  name = "aviation-events"
  message_storage_policy {
    # The playbook pins everything to europe-west3.
    allowed_persistence_regions = [var.region]
  }
  depends_on = [google_project_service.pubsub]
}

resource "google_pubsub_topic" "dlq" {
  name = "aviation-events-dlq"
  message_storage_policy {
    allowed_persistence_regions = [var.region]
  }
  depends_on = [google_project_service.pubsub]
}

# Pull so the exercise can nack on purpose (design section 1). Retention of
# seven days is long enough to replay a failed test, not a permanent archive.
resource "google_pubsub_subscription" "events_pull" {
  name                       = "aviation-events-pull"
  topic                      = google_pubsub_topic.events.name
  ack_deadline_seconds       = 30
  message_retention_duration = "604800s"

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = 5
  }

  depends_on = [google_pubsub_topic.dlq]
}

# Terminal storage for dead-lettered bodies plus the error reason; the replay
# command publishes selected bodies back to the events topic (design section 5).
resource "google_pubsub_subscription" "dlq" {
  name                       = "aviation-events-dlq"
  topic                      = google_pubsub_topic.dlq.name
  ack_deadline_seconds       = 30
  message_retention_duration = "604800s"
}

# Pub/Sub service agent: forwards dead-lettered messages (publisher on the
# DLQ topic, subscriber and viewer on the forwarding subscription).
resource "google_pubsub_topic_iam_member" "service_agent_dlq_publisher" {
  topic  = google_pubsub_topic.dlq.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription_iam_member" "service_agent_subscriber" {
  subscription = google_pubsub_subscription.events_pull.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription_iam_member" "service_agent_viewer" {
  subscription = google_pubsub_subscription.events_pull.name
  role         = "roles/pubsub.viewer"
  member       = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# --- Data: dataset and the four state tables (design section 3) ---------------

resource "google_bigquery_dataset" "events" {
  dataset_id    = "aviation_events"
  friendly_name = "G03 Aviation Event Processing"
  location      = "EUROPE-WEST3"
}

# Test-project tables stay destroyable (G02 pattern); the real protection is
# the 0-destroys plan rule, not deletion_protection.

resource "google_bigquery_table" "event_receipt" {
  dataset_id          = google_bigquery_dataset.events.dataset_id
  table_id            = "event_receipt"
  deletion_protection = false

  schema = jsonencode([
    { name = "event_id", type = "STRING", mode = "REQUIRED" },
    { name = "message_id", type = "STRING", mode = "REQUIRED" },
    { name = "outcome", type = "STRING", mode = "REQUIRED" },
    { name = "received_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "entity_state" {
  dataset_id          = google_bigquery_dataset.events.dataset_id
  table_id            = "entity_state"
  deletion_protection = false

  schema = jsonencode([
    { name = "entity_id", type = "STRING", mode = "REQUIRED" },
    { name = "revision", type = "INT64", mode = "REQUIRED" },
    { name = "event_id", type = "STRING", mode = "REQUIRED" },
    { name = "event_type", type = "STRING", mode = "REQUIRED" },
    { name = "event_time", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "payload", type = "STRING", mode = "REQUIRED" },
    { name = "updated_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "event_history" {
  dataset_id          = google_bigquery_dataset.events.dataset_id
  table_id            = "event_history"
  deletion_protection = false

  schema = jsonencode([
    { name = "event_id", type = "STRING", mode = "REQUIRED" },
    { name = "entity_id", type = "STRING", mode = "REQUIRED" },
    { name = "revision", type = "INT64", mode = "REQUIRED" },
    { name = "outcome", type = "STRING", mode = "REQUIRED" },
    { name = "message_id", type = "STRING", mode = "REQUIRED" },
    { name = "received_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "event_quarantine" {
  dataset_id          = google_bigquery_dataset.events.dataset_id
  table_id            = "event_quarantine"
  deletion_protection = false

  schema = jsonencode([
    { name = "delivery_key", type = "STRING", mode = "REQUIRED" },
    { name = "reason", type = "STRING", mode = "REQUIRED" },
    { name = "body", type = "STRING", mode = "REQUIRED" },
    { name = "occurrences", type = "INT64", mode = "REQUIRED" },
    { name = "first_seen_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "last_seen_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

# --- Consumer job (design sections 1 and 6) -----------------------------------
#
# A Cloud Run job, not a service: v1 is pull so the test can nack on purpose.
# One task, sequential loop, one in-flight write; it drains up to MAX_MESSAGES
# deliveries and exits. Exercises execute it on demand, like the G01 job.

resource "google_cloud_run_v2_job" "consumer" {
  name     = "aviation-event-consumer"
  location = var.region
  # Owned and rebuilt by CI; a destroy is a deploy error, not a request.
  deletion_protection = false

  template {
    task_count = 1
    # Sequence step 3: a single consumer with one in-flight write.
    parallelism = 1

    template {
      service_account = google_service_account.runtime.email
      # Retries belong to Pub/Sub redelivery, not to the task runner.
      max_retries = 0

      containers {
        image = var.image

        env {
          name  = "PUBSUB_SUBSCRIPTION"
          value = "projects/${var.project_id}/subscriptions/${google_pubsub_subscription.events_pull.name}"
        }
        env {
          name  = "PUBSUB_DLQ_TOPIC"
          value = "projects/${var.project_id}/topics/${google_pubsub_topic.dlq.name}"
        }
        env {
          name  = "BQ_DATASET"
          value = google_bigquery_dataset.events.dataset_id
        }
        env {
          name  = "MAX_MESSAGES"
          value = "10"
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }
    }
  }
}

# --- Observability: error metric and alert (G02 pattern) ----------------------
#
# monitoring.googleapis.com is already enabled by G02's project state; it is
# deliberately not re-declared here (see the header comment).

resource "google_logging_metric" "consumer_errors" {
  name        = "aviation_event_consumer_errors"
  description = "ERROR-severity log entries from the aviation-event-consumer job"
  filter      = "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"aviation-event-consumer\" AND severity>=ERROR"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_monitoring_notification_channel" "owner_email" {
  display_name = "G03 owner email"
  type         = "email"
  labels = {
    email_address = "jiahongque25@gmail.com"
  }
}

resource "google_monitoring_alert_policy" "consumer_errors" {
  display_name = "aviation-event-consumer errors"
  combiner     = "OR"

  conditions {
    display_name = "consumer logged errors"

    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.consumer_errors.name}\" AND resource.type=\"cloud_run_job\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0

      trigger {
        count = 1
      }

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.owner_email.name]
}
