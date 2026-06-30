# ADR 002: API Endpoints & Authentication Design

## Context and Problem Statement
To function as a true "plug-and-play" backend AI engine, Scrutinize requires a robust set of API endpoints that allow external applications (and project owners) to programmatically ingest data, query the AI, and manage their document library. 

A primary concern is **security and isolation**. We cannot require external systems to transmit sensitive plaintext passwords on every API request (e.g., Basic Auth), as this is an anti-pattern. We need a standardized, token-based authentication approach that scopes all API actions strictly to the requesting project's namespace.

## Decision
We will implement an API Key-based authentication architecture utilizing the following endpoints:

### 1. Project Registration & Key Generation
- **Endpoint**: `POST /v2/projects/signup` (and `POST /v2/projects/login`)
- **Behavior**: When a project is registered with a `name` and `password`, the system generates secure API keys for that project account. 
- **Keys Issued**:
  - `api_key`: An administrative key used for modifying data (uploading, deleting). Passed via the `X-Project-Key` header.
  - `client_key`: A read-only key safe for public frontends, used for searching/chatting. Passed via the `X-Client-Key` header.

### 2. Data Ingestion (Text, Audio, Video)
- **Endpoint**: `POST /upload`
- **Authentication**: Requires `api_key` (`X-Project-Key` header).
- **Behavior**: Accepts multipart form-data. Validates the API key, associates the uploaded media with the project's isolated namespace, and triggers the asynchronous ingestion pipelines (chunking, embedding, transcription).

### 3. Chat and Query Engine
- **Endpoint**: `POST /v2/search`
- **Authentication**: Requires `client_key` (`X-Client-Key` header) or the administrative `api_key`.
- **Behavior**: Accepts a JSON payload containing the user's query. Authenticates the request to ensure the project owner (or their users) can only query vectors and documents belonging to their specific project space.

### 4. Library Management (View & Delete)
- **View Endpoint**: `GET /library`
  - **Behavior**: Returns a JSON list of all media and documents owned by the authenticated project.
- **Delete Endpoint**: `DELETE /library/{file_id}`
  - **Behavior**: Permanently deletes a specific media file and its associated vector embeddings.
- **Authentication**: Both endpoints require the administrative `api_key` (`X-Project-Key` header) to prevent unauthorized access or deletion of cross-project data.

## Consequences
- **Positive**: External developers have a standardized, secure, and easy-to-use API surface. Projects are strictly isolated. Passwords are only transmitted once during key exchange, drastically reducing the attack surface.
- **Positive**: The dual-key system (`api_key` vs `client_key`) allows project owners to embed the chat interface directly into their public websites without risking data deletion by malicious actors.
- **Negative/Risk**: If a project owner leaks their administrative `api_key`, malicious actors could delete or corrupt their library. We must document best practices for key rotation and secrecy.
