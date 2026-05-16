# Axis

**AI-powered alignment engine for software teams.**

**Axis** continuously ingests project activity from GitLab (and soon Slack, Confluence, email), reconstructs feature-level context, tracks requirement evolution, and surfaces relevant changes to the right people.

## Architecture

```
Connectors (GitLab, Slack*, Confluence*)  →  Normalized Events  →  Embeddings (pgvector)
                                                    ↓
                                            Semantic Search / AI Chat
```

*\* Coming soon*

### Plugin System

Adding a new integration takes **one file**:

```
app/connectors/
├── base.py          ← BaseConnector interface
├── registry.py      ← Auto-discovers plugins
├── gitlab/
│   └── connector.py ← Implements BaseConnector
├── slack/           ← Future: just add this folder
│   └── connector.py
└── confluence/      ← Future: just add this folder
    └── connector.py
```

## Quick Start

### 1. Start infrastructure

```bash
docker compose up -d
```

This starts PostgreSQL (with pgvector) and Redis.

### 2. Set up the backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux/Mac

pip install -e ".[dev]"
cp .env.example .env
# Edit .env with your GitLab and Gemini API keys
```

### 3. Run the backend

```bash
uvicorn app.main:app --reload --port 8000
```

### 4. Test the health endpoint

```bash
curl http://localhost:8000/api/health
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check + registered connectors |
| `GET` | `/api/auth/login/{type}` | Start OAuth flow for a connector |
| `GET` | `/api/auth/callback/{type}` | OAuth callback |
| `GET` | `/api/auth/connectors` | List available connectors |
| `POST` | `/api/projects/` | Create a project |
| `POST` | `/api/projects/{id}/connect` | Connect a source |
| `POST` | `/api/projects/{id}/sync` | Trigger full sync |
| `GET` | `/api/projects/{id}/status` | Sync status |
| `GET` | `/api/search/?q=...&project_id=...` | Semantic search |
| `POST` | `/api/webhooks/{type}/{project_id}` | Webhook receiver |

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL + pgvector
- **Queue**: Celery + Redis
- **Embeddings**: Google Gemini (text-embedding-004)
- **AI Agents**: LangGraph (Phase 2)
- **Frontend**: React + TypeScript (Phase 2)

## Project Structure

```
Axis/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry
│   │   ├── config.py            # Pydantic Settings
│   │   ├── database.py          # SQLAlchemy + pgvector
│   │   ├── models/              # ORM models
│   │   ├── api/                 # Route handlers
│   │   ├── connectors/          # Plugin system
│   │   │   ├── base.py          # BaseConnector interface
│   │   │   ├── registry.py      # Auto-discovery
│   │   │   └── gitlab/          # First plugin
│   │   └── services/            # Business logic
│   ├── pyproject.toml
│   └── .env.example
├── docker-compose.yml           # Postgres + Redis
└── README.md
```
