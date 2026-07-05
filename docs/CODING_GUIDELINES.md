# Coding Guidelines - AI Alignment Engine (Axis)

## 1. Naming Conventions

### 1.1. Backend (Java / Spring Boot)
* **Classes & Interfaces:** `PascalCase` (e.g., `IngestionController`, `FeatureRepository`).
* **Methods & Variables:** `camelCase` (e.g., `processActivityEvent()`, `activityEventId`).
* **Constants:** `UPPER_SNAKE_CASE` (e.g., `MAX_RETRY_ATTEMPTS`).
* **Database Tables & Columns:** `snake_case` (e.g., `activity_events`, `feature_id`).

### 1.2. Frontend (React / TypeScript)
* **Components:** `PascalCase` (e.g., `ChatPanel.tsx`, `DashboardLayout.tsx`).
* **Hooks:** Prefix with `use` and use `camelCase` (e.g., `useFetchData.ts`).
* **Files & Folders:** `kebab-case` for non-component directories/files (e.g., `api-service.ts`, `auth-context/`).
* **Styling (CSS):** Lowercase using BEM format or camelCase for module styles (e.g., `.chat-panel__message--user` or `.chatMessage`).

---

## 2. Component Best Practices

### 2.1. React (Frontend)
* **Functional Components Only:** Define components as standard functional components with explicit TypeScript interfaces/types for props.
* **Vanilla CSS:** Write component-specific CSS using custom classes inside a corresponding style sheet. Avoid inline styles unless computing dynamic values (e.g., animations, graph layouts).
* **State Management:** Keep state local to the component unless shared. Use custom hooks to isolate API integrations and complex operations from presentational components.
* **Accessibility (a11y):** Include `aria-*` tags, use semantic HTML tags (`<button>`, `<main>`, `<article>`), and ensure keyboard navigation works for key UI elements.

### 2.2. Spring Boot (Backend)
* **Layered Architecture:** Enforce strict separation of concerns:
  * `Controller` -> handles request formatting, HTTP mapping, validation.
  * `Service` -> handles business rules, transaction boundaries, orchestration.
  * `Repository` -> handles database operations (Spring Data JPA).
* **Dependency Injection:** Use constructor injection instead of `@Autowired` fields to facilitate unit testing.
* **Lombok Usage:** Use `@Getter`, `@Setter`, and `@Builder` conservatively to prevent unintended code expansion issues. Do not use `@Data` on JPA Entity classes (use explicit getter/setter/hashcode to avoid database proxy issues).

---

## 3. API Design Standards
* **REST RESTful Principles:** Use standard HTTP methods:
  * `GET` for retrieval (must be idempotent).
  * `POST` for creation.
  * `PUT`/`PATCH` for updates.
  * `DELETE` for removal.
* **Response Wrapper:** Wrap all responses in a standard API envelope:
  ```json
  {
    "success": true,
    "data": { ... },
    "error": null,
    "timestamp": "2026-06-11T23:26:08Z"
  }
  ```
* **Versioning:** Prefix all API paths with `/api/v1/`.

---

## 4. Database Standards
* **Liquibase/Flyway Migration:** Never run raw DDL on application startup. Use database migration files for tracking database history.
* **Indexes:** Every foreign key must have an index. Columns frequently used in `WHERE` clauses (e.g., `feature_id`, `status`) must have corresponding indexes.
* **Soft Deletes:** Use `is_deleted` (boolean) or `deleted_at` (timestamp) fields instead of running hard `DELETE` commands on core transactional records.

---

## 5. Error Handling & Exception Management
* **Global Exception Handler:** In Spring Boot, implement a `@ControllerAdvice` class to catch custom exceptions (e.g., `ResourceNotFoundException`, `ConflictException`) and map them to accurate HTTP status codes (404, 409, 400).
* **No Raw Stack Traces:** Never return raw stack traces or internal system messages to the client. Logs must contain the stack trace, but response payloads must contain user-friendly error objects.
* **Frontend Resilience:** Wrap key sections of the React application in Error Boundaries to prevent total application crashes when rendering dynamic components.

---

## 6. Testing Standards
* **Test Coverage:** Aim for a minimum of 80% coverage on core business logic in the `Service` classes.
* **Backend:** Use JUnit 5 and Mockito for unit testing. Use `@SpringBootTest` and `@ActiveProfiles("test")` for integration testing with Testcontainers (if possible) or an H2 in-memory database.
* **Frontend:** Use Vitest and React Testing Library for testing presentational components and custom hooks. Mock external service files rather than doing real API requests.
