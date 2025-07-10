# Consent Management System - Architecture & Design

## 1. Introduction

This document outlines the architectural design for the Consent Management System. The system allows users (owners) to define document types, ingest documents, and manage consent for access to these documents by other users (requesters). Access control is enforced at the field level based on consent.

## 2. Key User Workflows

1.  **Register Document Type**:
    *   An `owner` submits a definition for a new document type, including its name, description, and a list of fields.
    *   For each field, the `owner` specifies its name and classification (`open`, `controlled`, `closed`).
    *   System validates and stores this definition.

2.  **Ingest Document**:
    *   An `owner` uploads/registers a document.
    *   The document is associated with a pre-defined `DocumentType`.
    *   Metadata (name, owner, reference to content) is stored.

3.  **Request Document Access**:
    *   A `requester` identifies a document and specific fields they wish to access.
    *   A `ConsentRequest` is created with `pending` status.

4.  **Provide Consent**:
    *   The `owner` of the document reviews a `pending` `ConsentRequest`.
    *   The `owner` approves or denies access for each `controlled` field listed in the request.
    *   Conditions like validity period or access count can be specified for approved fields.
    *   The `ConsentRequest` status is updated, and a `Consent` grant record is created if approved.

5.  **Access Document Data (with Consent Enforcement)**:
    *   A `requester` attempts to read specific fields from a document.
    *   System checks field classification and consent status.
    *   Data is returned (placeholder) or access is denied. All attempts are audited.

6.  **User Management**:
    *   Administrators or the system can create users with roles (`owner`, `requester`).

7.  **Audit Trail Review**:
    *   Authorized users can review audit logs for system activity.

8.  **Consent Grant Management**:
    *   Owners can review and revoke active consent grants they've issued.
    *   Requesters/Owners can list relevant grants.

## 3. System Components

*   **API Layer (Flask)**: Exposes RESTful endpoints.
*   **Service Layer (Business Logic)**: Contains core logic for use cases.
*   **Data Access Layer (DAL - SQLAlchemy)**: Manages database interactions.
*   **Database (SQLite for dev, PostgreSQL for prod)**: Stores all persistent data.
*   **(Conceptual) File Storage**: Represents document content storage (path reference).

## 4. High-Level Architecture Diagram (Text/PlantUML Style)

```plantuml
@startuml
skinparam componentStyle uml2

package "User Interaction (API Client/Terminal)" {
  actor Requester
  actor Owner
  actor SystemAdmin (conceptual for user creation/audit viewing)
}

package "Consent Management System" {
  component "API Layer (Flask)" as API
  component "Service Layer" as Services
  component "Data Access Layer (SQLAlchemy)" as DAL
  database "Database (SQL)" as DB
  folder "Document Content Storage" as FileStore
}

Requester --> API
Owner --> API
SystemAdmin --> API

API -> Services : Handles HTTP requests
Services -> DAL : For data persistence and retrieval
DAL <-> DB : CRUD operations
Services -> FileStore : (Conceptual) Store/retrieve document files
Services -> Services : (Internal service calls if needed)

note right of Services
  Business Logic for:
  - User Management
  - Document Type Mgt
  - Document Ingestion
  - Consent Request Mgt
  - Consent Granting & Mgt
  - Access Enforcement
  - Auditing
end note
@enduml
```

## 5. Data Flow Annotations (Examples)

*   **User Creation**: `Admin/System -> API (/users) -> UserService -> DAL -> DB`
*   **Document Type Registration**: `Owner -> API (/document-types) -> DocumentTypeService -> DAL -> DB`
*   **Access Data**: `Requester -> API (/documents/{id}/access-fields) -> AccessService -> DAL (fetch doc type, fields, consent) -> DB`. Logic within AccessService determines if access is granted. AuditService is called.
*   **Revoke Consent**: `Owner -> API (/consents/{id}/revoke) -> ConsentService -> DAL -> DB`. AuditService is called.

## 6. API Endpoints

### User Management
*   `POST /api/users`: Create a new user.
    *   Payload: `{"username": "...", "email": "...", "role": "owner|requester"}`
*   `GET /api/users/<int:user_id>`: Get a specific user.
*   `GET /api/users`: List all users.
    *   Query Params: `?username=...`

### Document Types
*   `POST /api/document-types`: (Owner) Create new document type.
    *   Payload: `{"name": "...", "description": "...", "owner_id": ..., "fields": [{"name": "...", "classification": "open|controlled|closed"}, ...]}`
*   `GET /api/document-types`: List all document types.
*   `GET /api/document-types/<int:type_id>`: Get a specific document type.

### Documents
*   `POST /api/documents`: (Owner) Ingest new document.
    *   Payload: `{"name": "...", "document_type_id": ..., "owner_id": ..., "file_path": "...", "additional_metadata": {...}}`
*   `GET /api/documents`: List documents.
    *   Query Params: `?owner_id=...`
*   `GET /api/documents/<int:doc_id>`: Get a specific document's metadata.

### Consent Requests
*   `POST /api/consent-requests`: (Requester) Request access to fields of a document.
    *   Payload: `{"requester_id": ..., "document_id": ..., "requested_field_names": ["...", ...], "request_message": "..."}`
*   `GET /api/consent-requests`: List consent requests.
    *   Query Params: `?requester_id=...`, `?owner_id=...` (owner of the document), `?status=PENDING|APPROVED|...`
*   `GET /api/consent-requests/<int:request_id>`: Get a specific consent request.
*   `POST /api/consent-requests/<int:request_id}/action`: (Owner) Approve/deny a request.
    *   Payload: `{"owner_id": ..., "overall_status": "APPROVED|DENIED|PARTIALLY_APPROVED", "approved_field_names": ["...", ...], "owner_message": "...", "valid_until_days": ..., "access_count_total": ...}`

### Consent Grants (Direct Management)
*   `GET /api/consents`: List consent grants.
    *   Query Params: `?document_id=...`, `?owner_id=...` (approving owner), `?requester_id=...`, `?status=ACTIVE|EXPIRED|...`
*   `GET /api/consents/<int:grant_id>`: Get a specific consent grant.
*   `POST /api/consents/<int:grant_id>/revoke`: (Owner) Revoke an active consent grant.
    *   Payload: `{"revoking_user_id": ...}` (ID of the owner performing revocation)

### Data Access (Enforcement Point)
*   `POST /api/documents/<int:doc_id}/access-fields`: (Requester) Request to retrieve specific field data.
    *   Payload: `{"requester_id": ..., "field_names": ["...", ...]}`. Returns placeholder data if allowed.

### Audit Logs
*   `GET /api/audit-logs`: List audit log entries.
    *   Query Params: `?user_id=...`, `?action=...`, `?target_resource_type=...`, `?target_resource_id=...`

### Health Check
*   `GET /api/health`: System health check.

## 7. Technology Stack

*   **Backend Framework**: Flask
*   **ORM**: SQLAlchemy
*   **Database**: SQLite (for development), PostgreSQL (recommended for production)
*   **Language**: Python
*   **API Style**: RESTful JSON
```
