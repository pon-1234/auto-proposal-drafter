# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a serverless Python application that transforms sales opportunity records into structured proposal bundles containing:
- **Structure JSON**: Site map and page specifications
- **Wire JSON**: Wireframe data for Figma plugin consumption
- **Estimate JSON**: Pricebook-style cost breakdown with markdown summary

The architecture is designed for GCP (Cloud Run + Workflows + Pub/Sub) but runs locally by default for rapid iteration.

## Development Commands

**Setup:**
```bash
pip install -e .[dev]
```

**Run tests:**
```bash
pytest
```

**Run API locally:**
```bash
uvicorn services.api.main:app --reload
```

**Test API manually:**
```bash
curl -X POST http://localhost:8000/v1/drafts:generate \
  -H "Content-Type: application/json" \
  -d '{"source": "manual", "record_id": "OPP-2025-001"}'
```

Sample opportunity data is at `data/opportunities/OPP-2025-001.json`.

## Architecture

### Core Flow
1. **API Entry** (`services/api/main.py`): FastAPI service that exposes draft generation endpoints, uses in-memory `JobStore`, and delegates to `ProposalGenerator`
2. **Generator** (`src/auto_proposal_drafter/generator.py`): Orchestrates the generation pipeline:
   - Infers site type from opportunity metadata
   - Builds structure by resolving page presets and sections from dictionaries
   - Generates wire placeholders for Figma consumption
   - Calculates estimates using section design hours + roles/rates + coefficient rules
   - Produces markdown summary
3. **Dictionaries** (`src/auto_proposal_drafter/dictionaries.py`): Contains shared domain knowledge (page presets, section definitions, rates, coefficient rules, assumptions)
4. **Repository** (`src/auto_proposal_drafter/opportunity_repository.py`): Protocol-based abstraction for loading opportunities; local implementation reads from JSON files

### Key Design Patterns
- **Protocol-based repositories**: `OpportunityRepository` is a Protocol, allowing easy swap to Firestore/Notion
- **Dictionary-driven generation**: All domain knowledge (section types, rates, presets) is centralized in `dictionaries.py` for future Firestore migration
- **Async background jobs**: API uses FastAPI `BackgroundTasks` to simulate async job execution; replace with Pub/Sub in production
- **In-memory job store**: `JobStore` uses thread-safe in-memory storage; swap with Firestore for production

### Data Models
All models in `src/auto_proposal_drafter/models/`:
- `opportunity.py`: Input opportunity spec
- `structure.py`: Site map, page specs, section specs
- `wire.py`: Wireframe project/pages/sections for Figma
- `estimate.py`: Line items, coefficients, assumptions
- `job.py`: Job status tracking

### Estimation Logic
- Base hours come from section definitions (`design_hours` field)
- IA hours: `max(4.0, 1.5 * section_count)`
- PM hours: `max(4.0, line_item_count * 0.6)`
- Coefficients are applied via rules in `DEFAULT_COEFFICIENT_RULES` (e.g., tight deadline, missing assets)
- Final cost = `base_cost * Π(coefficients)`

## Next Steps (from README)
- Replace in-memory `JobStore` with Firestore/Pub/Sub
- Implement Vertex AI adapter for prompt orchestration
- Move dictionaries to Firestore for runtime management
- Add integration tests for Slack/Asana/Sheets distribution

## GCP Deployment
GCP Project ID: `auto-proposal-drafter` (Project #714947184343)

### Infrastructure
- **Terraform**: Infrastructure as code in `terraform/` directory
  - Firestore, Pub/Sub, Cloud Run, Secret Manager, monitoring
- **Cloud Build**: CI/CD pipelines in `cloudbuild*.yaml`
  - Automatic testing and deployment on git push
- **Services**: API (public) and Worker (internal) on Cloud Run

### Key Components Added
1. **Firestore Job Store** (`firestore_job_store.py`): Production job persistence
2. **Pub/Sub Client** (`pubsub_client.py`): Message queue integration
3. **Logging Config** (`logging_config.py`): Structured logging with trace IDs
4. **Ingestors** (`ingestors/`): Notion and HubSpot opportunity fetchers
5. **Vertex AI Adapter** (`vertex_ai_adapter.py`): Gemini integration for AI-enhanced generation
6. **Post Processor** (`post_processor.py`): Distribution to Notion/Sheets/Figma/Asana

### Deployment
See `DEPLOYMENT.md` for complete deployment guide.
