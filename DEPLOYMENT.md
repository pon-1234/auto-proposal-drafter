# Deployment Guide

This guide covers deploying the Auto Proposal Drafter to Google Cloud Platform.

## Prerequisites

- GCP Project: `auto-proposal-drafter` (Project #714947184343)
- `gcloud` CLI installed and configured
- Terraform installed (>= 1.5)
- Docker installed

## Infrastructure Setup

### 1. Initialize Terraform State Bucket

```bash
# Create GCS bucket for Terraform state
gsutil mb -p auto-proposal-drafter -l asia-northeast1 gs://auto-proposal-drafter-tfstate

# Enable versioning
gsutil versioning set on gs://auto-proposal-drafter-tfstate
```

### 2. Deploy Infrastructure with Terraform

```bash
cd terraform

# Initialize Terraform
terraform init

# Review planned changes
terraform plan

# Apply infrastructure
terraform apply
```

This creates:
- Firestore database
- Pub/Sub topics and subscriptions
- Service accounts with IAM bindings
- Artifact Registry repository
- Cloud Scheduler jobs
- Monitoring alert policies

### 3. Configure Secrets

Store API keys and tokens in Secret Manager:

```bash
# Notion API key
echo -n "YOUR_NOTION_API_KEY" | gcloud secrets versions add notion-api-key --data-file=-

# HubSpot API key
echo -n "YOUR_HUBSPOT_API_KEY" | gcloud secrets versions add hubspot-api-key --data-file=-

# Slack signing secret
echo -n "YOUR_SLACK_SIGNING_SECRET" | gcloud secrets versions add slack-signing-secret --data-file=-

# Slack bot token
echo -n "YOUR_SLACK_BOT_TOKEN" | gcloud secrets versions add slack-bot-token --data-file=-

# Asana access token
echo -n "YOUR_ASANA_ACCESS_TOKEN" | gcloud secrets create asana-access-token --data-file=-
```

## Application Deployment

### Option 1: Cloud Build (Recommended)

Set up Cloud Build triggers for automatic deployment:

```bash
# Create trigger for main branch (dev environment)
gcloud builds triggers create github \
  --name=deploy-dev \
  --repo-name=auto-proposal-drafter \
  --repo-owner=YOUR_GITHUB_ORG \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml

# Create trigger for staging
gcloud builds triggers create github \
  --name=deploy-staging \
  --repo-name=auto-proposal-drafter \
  --repo-owner=YOUR_GITHUB_ORG \
  --tag-pattern="^v.*-staging$" \
  --build-config=cloudbuild-staging.yaml

# Create trigger for production
gcloud builds triggers create github \
  --name=deploy-prod \
  --repo-name=auto-proposal-drafter \
  --repo-owner=YOUR_GITHUB_ORG \
  --tag-pattern="^v[0-9]+\.[0-9]+\.[0-9]+$" \
  --build-config=cloudbuild-prod.yaml
```

### Option 2: Manual Deployment

```bash
# Build and deploy manually
gcloud builds submit \
  --config=cloudbuild.yaml \
  --substitutions=_ENVIRONMENT=dev
```

## Post-Deployment Configuration

### 1. Initialize Firestore Indexes

Create composite indexes for efficient querying:

```bash
# Deploy Firestore indexes
gcloud firestore indexes composite create \
  --collection-group=jobs \
  --query-scope=COLLECTION \
  --field-config=field-path=status,order=ASCENDING \
  --field-config=field-path=created_at,order=DESCENDING
```

### 2. Configure Cloud Scheduler

The Terraform setup creates a Cloud Scheduler job for periodic Notion polling. Adjust the schedule if needed:

```bash
gcloud scheduler jobs update http notion-poll \
  --schedule="*/15 * * * *" \
  --time-zone="Asia/Tokyo"
```

### 3. Set Up Monitoring

Create notification channels for alerts:

```bash
# Create email notification channel
gcloud alpha monitoring channels create \
  --display-name="Engineering Team" \
  --type=email \
  --channel-labels=email_address=engineering@example.com

# Update alert policy with notification channel
# Get the channel ID from the previous command
CHANNEL_ID="projects/auto-proposal-drafter/notificationChannels/CHANNEL_ID"

# Update Terraform variables and re-apply
cd terraform
terraform apply -var="notification_channels=[\"$CHANNEL_ID\"]"
```

## Verification

### 1. Test API Health

```bash
API_URL=$(gcloud run services describe api --region=asia-northeast1 --format='value(status.url)')
curl $API_URL/health
```

### 2. Test Draft Generation

```bash
curl -X POST $API_URL/v1/drafts:generate \
  -H "Content-Type: application/json" \
  -d '{
    "source": "manual",
    "record_id": "OPP-2025-001",
    "payload": {
      "id": "OPP-TEST-001",
      "title": "Test Opportunity",
      "company": "Test Company",
      "goal": "リード獲得",
      "persona": "企業の経営者",
      "deadline": "2025-12-31",
      "budget_band": "200-300万円",
      "must_have": ["高いCVR"],
      "references": [],
      "constraints": [],
      "assets": {"copy": false, "photo": false}
    }
  }'
```

### 3. Check Job Status

```bash
# Get job ID from previous response
JOB_ID="job_xxx"
curl $API_URL/v1/jobs/$JOB_ID
```

### 4. View Logs

```bash
# API logs
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=api" \
  --limit=50 \
  --format=json

# Worker logs
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=worker" \
  --limit=50 \
  --format=json
```

## Rollback

If deployment fails, rollback to previous revision:

```bash
# List revisions
gcloud run revisions list --service=api --region=asia-northeast1

# Rollback to specific revision
gcloud run services update-traffic api \
  --region=asia-northeast1 \
  --to-revisions=api-00001-xyz=100
```

## Scaling Configuration

### Auto-scaling

Adjust instance limits in `cloudbuild.yaml` or via gcloud:

```bash
# Update API scaling
gcloud run services update api \
  --region=asia-northeast1 \
  --min-instances=1 \
  --max-instances=20

# Update Worker scaling
gcloud run services update worker \
  --region=asia-northeast1 \
  --min-instances=0 \
  --max-instances=50
```

### Resource Limits

```bash
# Update API resources
gcloud run services update api \
  --region=asia-northeast1 \
  --memory=2Gi \
  --cpu=4

# Update Worker resources
gcloud run services update worker \
  --region=asia-northeast1 \
  --memory=8Gi \
  --cpu=4
```

## Cost Optimization

### Development Environment

For dev environment, minimize costs:

```bash
gcloud run services update api --region=asia-northeast1 --min-instances=0
gcloud run services update worker --region=asia-northeast1 --min-instances=0
gcloud scheduler jobs pause notion-poll
```

### Production Environment

For prod, ensure high availability:

```bash
gcloud run services update api --region=asia-northeast1 --min-instances=2
gcloud run services update worker --region=asia-northeast1 --min-instances=1
```

## Troubleshooting

### Jobs Not Processing

Check Pub/Sub subscription:

```bash
gcloud pubsub subscriptions describe draft-requests-worker
gcloud pubsub topics publish draft-requests --message='{"job_id":"test","source":"manual","record_id":"test"}'
```

### Worker Timeout

Increase timeout (max 3600s for Cloud Run):

```bash
gcloud run services update worker \
  --region=asia-northeast1 \
  --timeout=1800s
```

### Firestore Permission Errors

Verify service account IAM bindings:

```bash
gcloud projects get-iam-policy auto-proposal-drafter \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:api-service@*"
```

## Next Steps

1. **Integration Tests**: Set up end-to-end tests in CI/CD pipeline
2. **Load Testing**: Use `locust` or similar to test at scale
3. **Disaster Recovery**: Set up regular Firestore backups
4. **Custom Domain**: Map custom domain to Cloud Run service
5. **API Authentication**: Add OAuth2/API key authentication for production
