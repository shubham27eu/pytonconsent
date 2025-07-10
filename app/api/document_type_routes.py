from flask import request, jsonify
from . import bp  # The API blueprint
from app.services.document_type_service import DocumentTypeService
from app.models import DocumentType, DocumentField, FieldClassification # For schema documentation/validation if using a tool

# Basic schema for response marshalling (can be more sophisticated with Marshmallow/Pydantic)
def serialize_field(field: DocumentField):
    return {
        "id": field.id,
        "name": field.name,
        "classification": field.classification.value
    }

def serialize_document_type(doc_type: DocumentType):
    return {
        "id": doc_type.id,
        "name": doc_type.name,
        "description": doc_type.description,
        "owner_id": doc_type.owner_id,
        "created_at": doc_type.created_at.isoformat(),
        "fields": [serialize_field(field) for field in doc_type.fields]
    }

@bp.route('/document-types', methods=['POST'])
def create_document_type_route():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    name = data.get('name')
    description = data.get('description')
    owner_id = data.get('owner_id') # Assuming owner_id is passed for now.
    fields_data = data.get('fields')

    if not all([name, owner_id, isinstance(fields_data, list)]):
        return jsonify({"error": "Missing required fields: name, owner_id, fields (must be a list)"}), 400

    # Basic validation for owner_id type
    if not isinstance(owner_id, int):
        return jsonify({"error": "owner_id must be an integer"}), 400

    doc_type, error = DocumentTypeService.create_document_type(
        name=name,
        description=description,
        owner_id=owner_id,
        fields_data=fields_data
    )

    if error:
        return jsonify({"error": error}), 400 # Could be 400 or 422 depending on error type

    return jsonify(serialize_document_type(doc_type)), 201


@bp.route('/document-types/<int:doc_type_id>', methods=['GET'])
def get_document_type_route(doc_type_id):
    doc_type = DocumentTypeService.get_document_type_by_id(doc_type_id)
    if not doc_type:
        return jsonify({"error": "Document type not found"}), 404
    return jsonify(serialize_document_type(doc_type)), 200

@bp.route('/document-types', methods=['GET'])
def list_document_types_route():
    doc_types = DocumentTypeService.get_all_document_types()
    return jsonify([serialize_document_type(dt) for dt in doc_types]), 200
