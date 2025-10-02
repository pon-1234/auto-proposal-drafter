# Auto Proposal Drafter

Serverless-friendly Python reference implementation that turns sales opportunity records into a draft proposal bundle consisting of:

- Structure JSON (site map + page specs)
- Wire JSON (Figma plugin feed)
- Estimate JSON (pricebook style) + Markdown summary

The code mirrors the architecture described in the project brief (Cloud Run + Workflows + Pub/Sub) while keeping the default runtime local and dependency-light so the pipeline can be iterated before GCP wiring.

## Getting Started

1. Create and activate a Python >=3.10 virtual environment.
2. Install dependencies: `pip install -e .[dev]`
3. Run unit tests: `pytest`
4. Start the API locally: `uvicorn services.api.main:app --reload`

The API exposes:

- `POST /v1/drafts:generate` — enqueue generation (`payload` field accepts inline `Opportunity` JSON for local testing).
- `GET /v1/jobs/{job_id}` — poll job status/output.
- `GET /health` — health probe for Cloud Run.

A sample opportunity payload is provided at `data/opportunities/OPP-2025-001.json` for quick smoke tests.

## How It Works

- `src/auto_proposal_drafter/generator.py` encapsulates the structure/wire/estimate synthesis using the shared dictionaries in `src/auto_proposal_drafter/dictionaries.py`.
- `services/api/main.py` mimics the Cloud Run entry point. It stores jobs in-memory (`JobStore`) and defers execution to a background task. Replace `LocalOpportunityRepository` with a Notion/Firestore backed implementation for production.
- Estimates leverage a lightweight pricebook (section rates + coefficient rules) and emit per-line calculated costs.

## Production Architecture

The codebase is now production-ready with the following components:

### Infrastructure (GCP)
- **Firestore**: Job store, dictionaries, and opportunity cache
- **Pub/Sub**: Async job queue with dead-letter queue for failures
- **Cloud Run**: API (public) and Worker (internal) services
- **Secret Manager**: API keys for Notion, HubSpot, Slack, Asana
- **Vertex AI**: Gemini integration for AI-enhanced generation
- **Cloud Scheduler**: Periodic Notion polling
- **Monitoring**: Structured logging, alerts, error reporting

### Services
- **API Service** (`services/api/main.py`): Public REST API, enqueues jobs to Pub/Sub in production
- **Worker Service** (`services/worker/main.py`): Processes jobs from Pub/Sub, generates drafts
- **Post Processor** (`post_processor.py`): Distributes outputs to Notion, Sheets, Figma, Asana

### Ingestors
- **Notion** (`ingestors/notion.py`): Fetch opportunities from Notion databases
- **HubSpot** (`ingestors/hubspot.py`): Fetch opportunities from HubSpot CRM

### AI Integration
- **Vertex AI Adapter** (`vertex_ai_adapter.py`): Gemini-powered copy enhancement and section suggestions

## Deployment

See `DEPLOYMENT.md` for complete deployment instructions.

Quick start:
```bash
# Deploy infrastructure
cd terraform && terraform apply

# Deploy services
gcloud builds submit --config=cloudbuild.yaml
```

## Next Steps

- Add integration tests covering end-to-end workflows
- Implement Slack `/generate` command handler
- Move dictionaries to Firestore for runtime management
- Expand Vertex AI prompts with RAG support (Matching Engine)
- Complete operational runbooks for error recovery
