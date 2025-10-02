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

## Next Steps

- Swap the in-memory job store with Firestore/PubSub integrations as per the target architecture.
- Implement the Vertex AI adapter and prompt orchestration layer behind `ProposalGenerator`.
- Expand dictionaries (sections, presets, coefficients) and move them to Firestore for runtime management.
- Add integration tests covering the Slack/Asana/Sheets distribution once APIs are connected.
