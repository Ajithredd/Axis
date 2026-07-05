---
name: backend-development-standards
description: Architecture standards, folder layout, and development guidelines for production-ready Python & FastAPI backends.
---

# Backend Development Standards

Follow these guidelines to design, implement, and extend the backend services.

## 1. Architectural Layers

To ensure scalability and testability, maintain a strict separation of concerns:

- **Routers (`api/`):** Thin interface layers handling HTTP parsing, CORS, versioning, and status codes. No business logic.
- **Service Layer (`services/`):** Houses pure python business logic. Independent of the FastAPI web framework.
- **Repository Layer (`repositories/` or CRUD database access):** Handles database queries, caching logic, and vector-search adapters.
- **Models vs. Schemas:**
  - `models/` represents the ORM database schema.
  - `schemas/` contains the Pydantic models for API request/response validation.

---

## 2. Best Practices Checklist

- [ ] **Dependency Injection:** Use FastAPI `Depends` to inject database connections, active user state, and services.
- [ ] **Type Safety:** Maintain strict type hints for all functions, parameters, and return statements.
- [ ] **Config Management:** Centralize configurations using `pydantic-settings` to load from environment variables securely.
- [ ] **Error Handling:** Use custom global exception handlers and avoid letting raw database exceptions leak to the client.
