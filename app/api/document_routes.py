from flask import request, jsonify
from . import bp  # The API blueprint
from app.services.document_service import DocumentService
from app.services.document_type_service import DocumentTypeService # To serialize doc type
from app.models import Document
from .document_type_routes import serialize_document_type # Re-use for nested doc_type

# Basic schema for response marshalling
def serialize_document(doc: Document):
    serialized = {
        "id": doc.id,
        "name": doc.name,
        "document_type_id": doc.document_type_id,
        "owner_id": doc.owner_id,
        "file_path": doc.file_path,
        "uploaded_at": doc.uploaded_at.isoformat(),
        "additional_metadata": doc.additional_metadata if doc.additional_metadata else {}
    }
    # Optionally embed the document type details
    if doc.document_type:
         serialized["document_type"] = serialize_document_type(doc.document_type)
    return serialized

@bp.route('/documents', methods=['POST'])
def ingest_document_route():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    name = data.get('name')
    document_type_id = data.get('document_type_id')
    owner_id = data.get('owner_id') # Assuming owner_id is passed.
    file_path = data.get('file_path') # Path or reference to the document content.
    additional_metadata = data.get('additional_metadata') # Optional

    if not all([name, document_type_id, owner_id, file_path]):
        return jsonify({"error": "Missing required fields: name, document_type_id, owner_id, file_path"}), 400

    if not isinstance(owner_id, int) or not isinstance(document_type_id, int):
        return jsonify({"error": "owner_id and document_type_id must be integers"}), 400

    document, error = DocumentService.ingest_document(
        name=name,
        document_type_id=document_type_id,
        owner_id=owner_id,
        file_path=file_path,
        additional_metadata=additional_metadata
    )

    if error:
        # More specific error codes could be returned based on error type
        # e.g. 404 if owner or doc_type not found, 400 for validation, 409 for conflict
        return jsonify({"error": error}), 400

    return jsonify(serialize_document(document)), 201


@bp.route('/documents/<int:doc_id>', methods=['GET'])
def get_document_route(doc_id):
    # Future: Add permission checks here (e.g., is user owner or has consent?)
    document = DocumentService.get_document_by_id(doc_id)
    if not document:
        return jsonify({"error": "Document not found"}), 404
    return jsonify(serialize_document(document)), 200

@bp.route('/documents', methods=['GET'])
def list_documents_route():
    # Future: Add permission checks and filtering (e.g., by owner, by requester with consent)
    # For now, lists all documents.
    # Add query param for owner_id filtering
    owner_id_filter = request.args.get('owner_id', type=int)
    if owner_id_filter:
        documents = DocumentService.get_documents_by_owner(owner_id_filter)
    else:
        documents = DocumentService.get_all_documents()

    return jsonify([serialize_document(doc) for doc in documents]), 200

@bp.route('/documents/<int:doc_id>/access-fields', methods=['POST'])
def access_document_fields_route(doc_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    requester_id = data.get('requester_id') # Assuming requester_id is passed (e.g. from authenticated user context later)
    field_names = data.get('field_names') # List of strings

    if not isinstance(requester_id, int) or not isinstance(field_names, list):
        return jsonify({"error": "Missing or invalid type for required fields: requester_id (int), field_names (list)"}), 400

    if not field_names:
        return jsonify({"error": "field_names list cannot be empty"}), 400

    # Import AccessService here to avoid circular dependency at module load time if AccessService imports things from API routes (it doesn't now)
    from app.services.access_service import AccessService

    accessed_data, error = AccessService.can_access_fields(
        requester_id=requester_id,
        document_id=doc_id,
        field_names=field_names
    )

    if error:
        # Determine appropriate status code based on error message content
        if "not found" in error.lower():
            status_code = 404
        elif "access denied" in error.lower() or "no active consent grant" in error.lower() or "not part of your active consent grant" in error.lower() or "classified as closed" in error.lower():
            status_code = 403 # Forbidden
        else:
            status_code = 400 # Bad request (e.g. validation error)
        return jsonify({"error": error, "accessed_data": None}), status_code

    if not accessed_data : # Should be caught by error, but as a safeguard
        return jsonify({"error": "No fields were accessible.", "accessed_data": None}), 403


    return jsonify({"message": "Access granted for requested fields.", "accessed_data": accessed_data}), 200
