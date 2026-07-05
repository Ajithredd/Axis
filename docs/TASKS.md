# Project Tasks & Roadmaps - AI Alignment Engine (Axis)

## 1. MVP Scope
The MVP will focus on integrating **GitLab** and **Slack** ingestion, constructing a basic relational database representation of features, indexing requirements text in **Qdrant**, and serving a clean **React UI** with an AI Chat Interface capable of showing sources/citations.

---

## 2. Epics & Checklist

### Epic 1: Base Platform & Ingestion Engine (Backend)
- [ ] **Feature 1.1: Core Backend Setup**
  - [ ] Initialize Spring Boot application with dependencies (JPA, Web, Security, PostgreSQL).
  - [ ] Configure PostgreSQL database integration and schema migrations.
  - [ ] Set up Docker Compose for local PostgreSQL and Qdrant.
- [ ] **Feature 1.2: GitLab Webhook Connector**
  - [ ] Create endpoint `/api/v1/ingest/gitlab` to receive issue, commit, and MR webhooks.
  - [ ] Build parser to extract descriptions, comments, and commit messages.
  - [ ] Implement retry and error handling policies for failed ingestion events.
- [ ] **Feature 1.3: Activity Event Log**
  - [ ] Implement relational schema for saving raw payload entries.
  - [ ] Create database repository to query raw history.

### Epic 2: AI Intelligence & Storage (Python/Core)
- [ ] **Feature 2.1: Python Agent Setup**
  - [ ] Initialize FastAPI project with LangGraph and LlamaIndex.
  - [ ] Implement client adapter to communicate with Qdrant vector database.
- [ ] **Feature 2.2: LLM Classification Agent**
  - [ ] Design prompts to classify incoming text and map it to a `FeatureId` and `RequirementId`.
  - [ ] Implement Python endpoint `/agent/classify` called by Spring Boot.
- [ ] **Feature 2.3: Vector Embeddings Pipeline**
  - [ ] Implement chunking utility for long transcripts and Confluence updates.
  - [ ] Set up embedding generation using `text-embedding-3-small`.
  - [ ] Write logic to upsert embeddings into Qdrant collection.

### Epic 3: User Interface & Delivery Layer (Frontend)
- [ ] **Feature 3.1: Frontend Scaffolding**
  - [ ] Initialize React + TypeScript application with Vite.
  - [ ] Build basic router and layout structure.
  - [ ] Configure standard style tokens in Vanilla CSS.
- [ ] **Feature 3.2: Chat Interface**
  - [ ] Implement chat component with streaming response rendering.
  - [ ] Build inline citation component mapping references to source links.
- [ ] **Feature 3.3: Role-Aware Dashboards**
  - [ ] Create Developer View (showing recent API contract changes and technical dependencies).
  - [ ] Create QA View (highlighting requirements changes and regression warnings).
  - [ ] Create Product Owner View (audit history, approval tracking, conflict flags).

### Epic 4: Advanced Agents & Notifications
- [ ] **Feature 4.1: Conflict Detection System**
  - [ ] Implement background task to run conflict checking prompts over current feature sets.
  - [ ] Generate `Conflict` model and save to PostgreSQL database.
- [ ] **Feature 4.2: Dependency & Impact Engine**
  - [ ] Build graph logic to connect feature nodes, APIs, and test assets.
  - [ ] Build alert rule engine to identify affected stakeholders based on graph distance.
- [ ] **Feature 4.3: Smart Notifications**
  - [ ] Implement real-time WebSockets or Server-Sent Events (SSE) notification panel in the UI.
  - [ ] Deliver context-aware messages (e.g., "Requirement updated, QA suite affected").

---

## 3. Future Enhancements
* [ ] **Slack & Teams Connectors:** Bi-directional app installation for Slack/Teams to query Axis directly via `/axis ask <question>`.
* [ ] **Confluence Sync Daemon:** Scheduled cron indexing of entire wiki spaces.
* [ ] **Automatic Code-Review Integration:** CI/CD step checking PR changes against requirements to ensure code complies before merging.
* [ ] **Predictive Risk Assessment:** Machine learning model to predict which features are most likely to suffer from alignment drift based on high developer activity but zero PM updates.
