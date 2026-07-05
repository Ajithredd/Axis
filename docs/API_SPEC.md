# API Specification - AI Alignment Engine (Axis)

All endpoints are prefixed with `/api/v1` on the backend host (`http://localhost:8080`).

---

## 1. Authentication
Axis uses stateless JWT (JSON Web Tokens). Include the token in the `Authorization` header for all requests except `/auth/login`.

```http
Authorization: Bearer <JWT_TOKEN>
```

---

## 2. Global Error Format
When an API error occurs, the server responds with a matching HTTP status code and a standard error payload:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Feature with ID 'F-102' was not found.",
    "details": [
      "Requested resource URI: /api/v1/features/F-102"
    ]
  },
  "timestamp": "2026-06-11T23:26:08Z"
}
```

---

## 3. Endpoints Spec

### 3.1. Authentication Interface
* **POST `/auth/login`**
  * **Description:** Authenticate user credentials and return a token.
  * **Request Headers:** `Content-Type: application/json`
  * **Request Body:**
    ```json
    {
      "username": "developer_ajith",
      "password": "securepassword123"
    }
    ```
  * **Response (200 OK):**
    ```json
    {
      "success": true,
      "data": {
        "token": "eyJhbGciOiJIUzUxMiJ9...",
        "role": "DEVELOPER",
        "username": "developer_ajith"
      },
      "error": null,
      "timestamp": "2026-06-11T23:26:08Z"
    }
    ```
  * **Validation Rules:**
    * `username`: Required, non-empty.
    * `password`: Required, minimum 8 characters.

---

### 3.2. Ingestion Gateway
* **POST `/ingest/gitlab`**
  * **Description:** Webhook endpoint for GitLab activities.
  * **Authentication:** Authenticated via pre-configured webhook header secret token: `X-Gitlab-Token`.
  * **Request Body:** Standard GitLab Webhook JSON payload (Push, Comment, Issue, or Merge Request).
  * **Response (202 Accepted):**
    ```json
    {
      "success": true,
      "data": {
        "event_id": "evt-77a8342a-a9e1",
        "status": "QUEUED"
      },
      "error": null,
      "timestamp": "2026-06-11T23:26:09Z"
    }
    ```

---

### 3.3. Features Interface
* **GET `/features`**
  * **Description:** Retrieve list of active features.
  * **Query Parameters:**
    * `limit` (int, default 20)
    * `offset` (int, default 0)
  * **Response (200 OK):**
    ```json
    {
      "success": true,
      "data": [
        {
          "feature_id": "feat-100",
          "title": "Multisource Ingestion Pipeline",
          "status": "IN_PROGRESS",
          "owner": "ajith_pm",
          "created_at": "2026-06-11T17:56:11Z"
        }
      ],
      "error": null,
      "timestamp": "2026-06-11T23:26:10Z"
    }
    ```

* **GET `/features/{feature_id}`**
  * **Description:** Retrieve detailed information, requirements list, and conflicts for a single feature.
  * **Response (200 OK):**
    ```json
    {
      "success": true,
      "data": {
        "feature_id": "feat-100",
        "title": "Multisource Ingestion Pipeline",
        "status": "IN_PROGRESS",
        "owner": "ajith_pm",
        "requirements": [
          {
            "req_id": "req-101",
            "text": "Support GitLab issue and commit webhooks",
            "version": 2
          }
        ],
        "conflicts": [
          {
            "conflict_id": "conf-402",
            "severity": "HIGH",
            "description": "Slack thread claims GitLab integration delayed, but GitLab milestone has not shifted.",
            "detected_at": "2026-06-11T20:10:00Z"
          }
        ],
        "created_at": "2026-06-11T17:56:11Z"
      },
      "error": null,
      "timestamp": "2026-06-11T23:26:11Z"
    }
    ```

---

### 3.4. AI Conversation Interface
* **POST `/chat/query`**
  * **Description:** Send queries to the Feature Intelligence Graph.
  * **Request Body:**
    ```json
    {
      "query": "Why was the database schema changed for the event ingestion log?",
      "conversation_id": "chat-498c-882f"
    }
    ```
  * **Response (200 OK):**
    ```json
    {
      "success": true,
      "data": {
        "response": "The schema was changed to include raw payload logs for indexing flexibility. This was decided during the meeting on June 10th and approved by ajith_pm.",
        "citations": [
          {
            "source": "GitLab Commit c3b782f",
            "url": "https://gitlab.example.com/project/commits/c3b782f",
            "quote": "Migration added: Raw payload column to activity_events table"
          },
          {
            "source": "Meeting Transcript MT-20260610",
            "url": "file:///c:/Users/ajith/Desktop/AI_Agents/Clarity/docs/transcripts/MT-20260610.vtt",
            "quote": "Ajith: 'We need raw event retention in case we re-run vector classifications later.'"
          }
        ]
      },
      "error": null,
      "timestamp": "2026-06-11T23:26:15Z"
    }
    ```
