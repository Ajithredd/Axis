# Project Structure & Directory Layout - AI Alignment Engine (Axis)

This document maps out the recommended folder layout for the three codebases making up the Axis system: the Spring Boot Backend, the React Frontend, and the Python Agent service.

---

## 1. Directory Tree Overview

```text
axis/
├── backend/                  # Spring Boot application root
│   ├── src/
│   │   ├── main/
│   │   │   ├── java/com/axis/
│   │   │   │   ├── config/      # App & Security configurations
│   │   │   │   ├── controller/  # REST APIs & Ingestion controllers
│   │   │   │   ├── model/       # JPA entities
│   │   │   │   ├── repository/  # Database repository interfaces
│   │   │   │   └── service/     # Business logic & integrations
│   │   │   └── resources/
│   │   │       ├── db/changelog/# Liquibase/Flyway migrations
│   │   │       └── application.yml
│   │   └── test/                # JUnit tests
│   ├── build.gradle
│   └── Dockerfile
│
├── frontend/                 # React SPA root
│   ├── src/
│   │   ├── assets/              # Icons, global styling configuration
│   │   ├── components/          # Reusable shared UI components
│   │   ├── context/             # Auth and global states
│   │   ├── hooks/               # Custom react hooks
│   │   ├── pages/               # Page layout views
│   │   ├── services/            # API call modules (matching API_SPEC)
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
│
├── agents/                   # Python FastAPI Agent service
│   ├── app/
│   │   ├── agents/              # LangGraph workflow definitions
│   │   ├── indexer/             # LlamaIndex vector operations
│   │   ├── models/              # Pydantic schemas
│   │   └── main.py              # FastAPI startup file
│   ├── requirements.txt
│   └── Dockerfile
│
├── docs/                     # Design documentation (This directory)
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── TASKS.md
│   ├── CODING_GUIDELINES.md
│   ├── AI_CONTEXT.md
│   ├── API_SPEC.md
│   ├── DATABASE_SCHEMA.md
│   └── PROJECT_STRUCTURE.md
│
└── docker-compose.yml        # Orchestrates the local runtime
```

---

## 2. Module Responsibilities & Boundaries

### 2.1. Backend (Java / Spring Boot)
* **Goal:** Provides transactional integrity, manages PostgreSQL metadata, receives webhook events, and controls client auth sessions.
* **Boundaries:** Does not talk directly to LLM APIs. Delegates semantic queries and classification tasks to the Python agent service via HTTP post requests.

### 2.2. Frontend (React / TypeScript)
* **Goal:** Provides the web view. Displays role-aware views and interfaces directly with the chat API.
* **Boundaries:** Only communicates with the Spring Boot backend (`/api/v1/...`). Never connects directly to the databases (PostgreSQL/Qdrant) or the Python Agent service.

### 2.3. Agents (Python / FastAPI)
* **Goal:** Performs AI classification, runs conflict detection graphs, and executes LlamaIndex retrieval algorithms.
* **Boundaries:** Stateless service. Relies on the database credentials and configurations to write to Qdrant, but leaves PostgreSQL mutation control to the Spring Boot backend.
