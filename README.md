# Consent Management System (Python Backend)

This project is a Python-based backend system for managing consent for accessing fields within documents. It allows document "owners" to define document types, ingest documents, and grant or deny access to specific fields for "requesters."

## Features (Initial Scope)

*   **Document Type Management**: Define document schemas with fields classified as `open`, `controlled`, or `closed`.
*   **PDF Data Extraction**: During ingestion, parses the content of the provided PDF to extract key-value data based on the document type's defined fields.
*   **Document Ingestion**: Ingests documents, linking them to a defined type and storing both the file reference and the extracted data.
*   **Consent Request Workflow**: Requesters can ask for access to specific document fields.
*   **Consent Provisioning**: Owners can approve (fully/partially) or deny consent requests, setting conditions like expiry and access counts.
*   **Access Enforcement**: The system checks field classifications and consent grants before returning the real, extracted data for authorized fields.
*   **Audit Logging**: Basic logging of access attempts and other key actions.
*   **API-Only Interface**: All interactions are through RESTful API endpoints.

For more details on functionality, see `FUNCTIONALITY.md`.
For architectural details, see `DESIGN.md`.

## Setup and Installation

### Prerequisites

*   Python 3.10+ (developed with 3.12)
*   `pip` for package installation
*   `virtualenv` (recommended)

### Environment Setup

1.  **Clone the repository (if applicable)**:
    ```bash
    # git clone <repository_url>
    # cd <repository_directory>
    ```

2.  **Create and activate a virtual environment**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\\Scripts\\activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

The application uses Flask's built-in development server.

1.  **Ensure your virtual environment is activated.**
2.  **Run the Flask application**:
    ```bash
    python run.py
    ```
    The application will typically be available at `http://127.0.0.1:5000`.
    The API endpoints are under the `/api` prefix (e.g., `http://127.0.0.1:5000/api/health`).

    An initial SQLite database file (`app.db`) will be created in the `app/` directory when the application first starts and models are defined.

## Running Tests

The project uses Python's built-in `unittest` framework.

1.  **Ensure your virtual environment is activated and dependencies are installed.**
2.  **Discover and run all tests from the project root directory**:
    ```bash
    python -m unittest discover -v tests
    ```
    Or, to run a specific test file:
    ```bash
    python -m unittest -v tests.test_document_api # Example
    ```

## Project Structure

```
.
├── app/                    # Main application package
│   ├── api/                # API blueprints and routes
│   ├── models/             # SQLAlchemy database models
│   ├── services/           # Business logic services
│   ├── __init__.py         # Application factory (create_app)
│   └── config.py           # Configuration settings
├── tests/                  # Unit and integration tests
├── venv/                   # Virtual environment (if created, gitignored)
├── .gitignore
├── DESIGN.md               # System architecture and design notes
├── FUNCTIONALITY.md        # Description of implemented features and scope
├── README.md               # This file
├── requirements.txt        # Python package dependencies
└── run.py                  # Main script to run the Flask application
```

## API Interaction

Interaction with the system is via REST API calls. You can use tools like `curl`, Postman, or custom scripts to interact with the endpoints defined in the `app/api/` modules.

Key categories of endpoints include:
*   User Management (`/api/users`)
*   Document Type Management (`/api/document-types`)
*   Document Ingestion & Access (`/api/documents`)
*   Consent Request Workflow (`/api/consent-requests`)
*   Consent Grant Management (`/api/consents`)
*   Audit Log Viewing (`/api/audit-logs`)
*   System Health (`/api/health`)

Refer to `DESIGN.md` for a more detailed overview of API endpoints and example payloads.
(Example: `GET http://127.0.0.1:5000/api/health` to check if the API is running).
```
