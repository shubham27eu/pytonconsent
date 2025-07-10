# Consent Management System - Initial Functional Scope

This document outlines the core functionality planned for the initial development phase of the Consent Management System. The system will be operated via a REST API, with interactions performed through API calls (terminal input is fine for this, no dedicated UI in this phase).

## Core Modules & Services

The system will be composed of the following core modules:

1.  **User Management (Implicit)**:
    *   While full user authentication and registration are not the primary focus for the initial build, the system will support distinct user roles:
        *   `owner`: Users who can register document types and ingest documents they own. They are responsible for granting or denying consent for their documents.
        *   `requester`: Users who can request access to documents and their specific fields.
    *   Users will be identifiable (e.g., by a username or ID) to link them to documents, types, and consents.

2.  **Document Type Management**:
    *   **Register Document Type**: An `owner` can define a new document type (e.g., "Payslip", "Invoice").
    *   **Define Fields**: For each document type, the `owner` specifies the fields it contains (e.g., "Employee Name", "Salary Amount", "Invoice Number").
    *   **Classify Fields**: Each field must be classified by the `owner` as:
        *   `open`: Data is generally accessible without specific consent once a document is shared (access rules might still apply at document level).
        *   `controlled`: Data requires explicit consent from the document `owner` for a `requester` to access.
        *   `closed`: Data is highly sensitive and generally not available for request or view by typical requesters (internal system fields or highly restricted data).

3.  **Document Ingestion**:
    *   **Ingest Document**: An `owner` can add a new document to the system.
    *   **Link to Document Type**: The ingested document must be associated with a pre-registered `DocumentType`.
    *   **Store Metadata**: Basic metadata (e.g., document name, owner, upload date) will be stored. The actual document file storage will be represented by a path/reference initially.

4.  **Consent Management**:
    *   **Request Document Access**: A `requester` can ask for access to specific fields of a particular document.
    *   **Review Consent Request**: The `owner` of the document is notified (conceptually, via API check) of pending requests.
    *   **Provide Consent**: The `owner` can:
        *   Approve the request for some or all `controlled` fields.
        *   Deny the request for some or all `controlled` fields.
        *   Set conditions for approved consent (e.g., validation period, number of times it can be accessed).

5.  **Data Access & Enforcement**:
    *   **Access Document Fields**: A `requester` can attempt to retrieve data from a document's fields.
    *   **Enforce Consent**: The system will check:
        *   The classification of the requested field.
        *   If `controlled`, whether a valid, active consent exists from the `owner` for the `requester` and the specific field.
        *   Consent conditions (e.g., expiry, access count).
    *   Access is granted or denied based on these checks. `Open` fields are accessible if the document itself is accessible to the requester (basic document-level permission might be a future addition, for now, focus is on field-level consent). `Closed` fields are generally not accessible.

6.  **Auditing**:
    *   **Log Key Actions**: The system will maintain an audit log of important events, such as:
        *   Document type registration.
        *   Document ingestion.
        *   Consent requests.
        *   Consent grants/denials/revocations.
        *   Data access attempts (successful and failed).

## Out of Initial Scope (Examples)

*   Complex UI for users.
*   Advanced user authentication/authorization (e.g., OAuth2, RBAC beyond simple roles).
*   Document content parsing (OCR, NLP for field extraction). Assumes fields are known or provided as metadata.
*   Automated PII detection.
*   Data masking for partially consented fields.
*   Real-time notifications.
*   Advanced policy engine for consent rules.
*   Version control for document types or documents.

This initial scope aims to build the foundational backend services for managing document types, documents, and the consent lifecycle for field-level access.
