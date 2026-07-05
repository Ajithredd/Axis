# AI Context File - Project Axis (AI Alignment Engine)

This file is a concise reference for AI coding agents (Claude Code, Cursor, Anti Gravity, etc.) working on Project Axis. It outlines the core architecture, constraints, rules, and system layout to minimize token overhead and ensure consistency.

---

## 1. Project Summary
* **Code Name:** Axis (AI-Powered Alignment Engine for Software Teams)
* **Goal:** Continuously ingest communication (GitLab, Confluence, Slack, Transcripts) -> reconstruct feature context -> build Feature Intelligence Graph -> detect requirement conflicts -> alert affected stakeholders.

---

## 2. Core Technologies
* **Frontend:** React, TypeScript, Vite, Vanilla CSS.
* **Backend:** Spring Boot (Java 17/21), Spring Data JPA, Spring Security.
* **Database & Vector:** PostgreSQL (relational metadata/event log) + Qdrant (vector embeddings of text/conversations).
* **AI Orchestration Service:** FastAPI (Python), LangGraph, LlamaIndex (runs adjacent to Spring Boot for LLM reasoning and agent loops).

---

## 3. Core Business Rules & Intelligence
1. **Activity-to-Graph Pipeline:** Webhook events are stored as raw logs in PostgreSQL first. Then, they are processed asynchronously: text is sent to the Python AI service, converted to embeddings, stored in Qdrant, and connected to existing database entities to update the `Feature Intelligence Graph`.
2. **Conflict Resolution Model:** Contradictions (e.g., Slack milestone != GitLab milestone) must generate a flag in the relational database containing confidence metrics and references.
3. **Change Alert Logic:** Notification routing is graph-based: if Requirement X changes, find all nodes (API endpoints, QA test cases, developers assigned) within 2 degrees of separation and send tailored, role-aware alerts.

---

## 4. Key Constraints for AI Code Generation
* **Do Not Write CSS Framework Utilities:** Use standard CSS classes in separate files. No Tailwind is allowed unless requested.
* **No Raw Starter DB Schema Scripts:** All PostgreSQL schema changes must be written as Flyway or Liquibase migration SQL scripts. Do not alter existing tables without generating a new migration.
* **No Inline LLM Calls in Spring Boot:** Spring Boot must delegate all LLM prompting and complex chains to the FastAPI service. Do not write direct LangChain/OpenAI calls in Java unless modifying external connectors.
* **Strict API Envelope:** All controller responses must return the standard wrapper: `{"success": true, "data": ..., "error": null, "timestamp": ...}`.

---

## 5. Critical Files to Inspect Before Modifying
Review these key architectural files before proposing changes:
* **System Design & PRD:**
  * [PRD.md](file:///c:/Users/ajith/Desktop/AI_Agents/Clarity/docs/PRD.md) - Product requirements and success metrics.
  * [ARCHITECTURE.md](file:///c:/Users/ajith/Desktop/AI_Agents/Clarity/docs/ARCHITECTURE.md) - Tech stack and component block diagrams.
* **API & Data Specs:**
  * [API_SPEC.md](file:///c:/Users/ajith/Desktop/AI_Agents/Clarity/docs/API_SPEC.md) - Required endpoint requests and responses.
  * [DATABASE_SCHEMA.md](file:///c:/Users/ajith/Desktop/AI_Agents/Clarity/docs/DATABASE_SCHEMA.md) - ER diagrams and entity declarations.
* **Structure & Guidelines:**
  * [PROJECT_STRUCTURE.md](file:///c:/Users/ajith/Desktop/AI_Agents/Clarity/docs/PROJECT_STRUCTURE.md) - Exact locations for components, models, and agents.
  * [CODING_GUIDELINES.md](file:///c:/Users/ajith/Desktop/AI_Agents/Clarity/docs/CODING_GUIDELINES.md) - Naming, styling, error, and testing conventions.

---

## 6. Development Workflow Rules
1. **Pre-commit Checklist:** Run `./gradlew test` (backend) and `npm run test` (frontend) before declaring a feature complete.
2. **Commit Messages:** Prefix with scope: `feat(ingest): GitLab sync`, `fix(ui): chat citation alignment`, `chore(deps): update fastapi packages`.
3. **Subagent Tasks:** If delegating, separate the ingestion logic (Spring Boot task) from agent orchestration logic (FastAPI task).
