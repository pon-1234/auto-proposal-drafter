# Terraform Infrastructure

This directory contains Terraform configuration for deploying the Auto Proposal Drafter infrastructure on GCP.

## Structure

- `main.tf` - Main infrastructure resources
- `variables.tf` - Input variables
- `outputs.tf` - Output values

## Resources Created

### Compute & Networking
- Cloud Run services (API and Worker)
- Service accounts with IAM bindings

### Data & Messaging
- Firestore database (native mode)
- Pub/Sub topics: draft-requests, draft-completed, draft-failed
- Pub/Sub subscriptions with push delivery

### Storage & Secrets
- Artifact Registry repository
- Secret Manager secrets (placeholders)

### Monitoring & Observability
- Cloud Scheduler job for Notion polling
- Monitoring alert policies
- Log sinks for Error Reporting

## Usage

### Initialize

```bash
# Create state bucket first
gsutil mb -p auto-proposal-drafter -l asia-northeast1 gs://auto-proposal-drafter-tfstate
gsutil versioning set on gs://auto-proposal-drafter-tfstate

# Initialize Terraform
terraform init
```

### Plan & Apply

```bash
# Review changes
terraform plan

# Apply for dev environment
terraform apply

# Apply for production
terraform apply -var="environment=prod" -var="notification_channels=[\"CHANNEL_ID\"]"
```

### Outputs

After applying, view outputs:

```bash
terraform output
```

Key outputs:
- `api_service_url` - Cloud Run API URL
- `worker_service_url` - Cloud Run Worker URL
- `pubsub_topic_draft_requests` - Draft requests topic ID

## Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `project_id` | GCP Project ID | `auto-proposal-drafter` |
| `project_number` | GCP Project Number | `714947184343` |
| `region` | GCP region | `asia-northeast1` |
| `environment` | Environment name | `dev` |
| `notification_channels` | Alert notification channels | `[]` |

## Environments

### Dev
- Min instances: 0
- Max instances: API=3, Worker=5
- Cost optimized

### Staging
- Min instances: API=1, Worker=0
- Max instances: API=5, Worker=10
- Production-like setup

### Production
- Min instances: API=1, Worker=0
- Max instances: API=20, Worker=50
- High availability

## State Management

Terraform state is stored in GCS bucket `auto-proposal-drafter-tfstate` with versioning enabled.

### Import Existing Resources

If resources were created manually:

```bash
terraform import google_cloud_run_v2_service.api projects/auto-proposal-drafter/locations/asia-northeast1/services/api
```

### State Locking

GCS backend automatically handles state locking.

## Security Notes

1. Service accounts follow principle of least privilege
2. Worker service is internal-only (no public access)
3. Secrets are stored in Secret Manager (not in Terraform state)
4. IAM bindings are managed via Terraform

## Maintenance

### Update Dependencies

```bash
terraform init -upgrade
```

### Refresh State

```bash
terraform refresh
```

### Destroy Infrastructure

**WARNING**: This will delete all resources!

```bash
terraform destroy
```
