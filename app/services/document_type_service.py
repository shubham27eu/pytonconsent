from app import db
from app.models import DocumentType, DocumentField, User, FieldClassification

class DocumentTypeService:
    @staticmethod
    def create_document_type(name: str, description: str, owner_id: int, fields_data: list[dict]):
        """
        Creates a new document type and its associated fields.

        Args:
            name: Name of the document type.
            description: Description of the document type.
            owner_id: ID of the user who owns this document type.
            fields_data: A list of dictionaries, each representing a field.
                         Each dict should have 'name' and 'classification' (str value of FieldClassification).
                         Example: [{'name': 'Employee ID', 'classification': 'open'},
                                   {'name': 'Salary', 'classification': 'controlled'}]

        Returns:
            The created DocumentType object or None if creation failed.
            Tuple: (DocumentType | None, error_message | None)
        """
        # Validate owner
        owner = User.query.get(owner_id)
        if not owner:
            return None, "Owner not found."
        if owner.role != 'owner':
            return None, "User does not have 'owner' role."

        # Validate if document type name already exists
        if DocumentType.query.filter_by(name=name).first():
            return None, f"Document type with name '{name}' already exists."

        doc_type = DocumentType(name=name, description=description, owner_id=owner_id)

        if not fields_data:
            return None, "Document type must have at least one field."

        processed_fields = []
        for field_data in fields_data:
            field_name = field_data.get('name')
            classification_str = field_data.get('classification')

            if not field_name or not classification_str:
                return None, "Each field must have a 'name' and 'classification'."

            try:
                classification_enum = FieldClassification[classification_str.upper()]
            except KeyError:
                valid_classifications = [e.value for e in FieldClassification]
                return None, f"Invalid classification '{classification_str}'. Valid are: {valid_classifications}."

            # Check for duplicate field names within this document type definition
            if any(f.name == field_name for f in processed_fields):
                return None, f"Duplicate field name '{field_name}' in definition."

            doc_field = DocumentField(
                name=field_name,
                classification=classification_enum,
                document_type=doc_type # Associate with the doc_type object
            )
            processed_fields.append(doc_field)

        try:
            db.session.add(doc_type)
            # The fields are associated via backref, they will be added if doc_type is added.
            # However, explicit add is fine for clarity or if session management requires it.
            for field in processed_fields:
                db.session.add(field) # Fields are added to session when associated with doc_type if cascade is set.
                                      # Explicit add is safer if cascade isn't perfectly configured for this.
                                      # Given current model (fields = db.relationship('DocumentField', backref='document_type', lazy=True, cascade="all, delete-orphan"))
                                      # adding doc_type to session and then committing should be enough.
                                      # Let's rely on the cascade for now. `doc_type.fields.extend(processed_fields)` would also work.

            db.session.commit()
            return doc_type, None
        except Exception as e:
            db.session.rollback()
            # Log error e
            return None, f"Database error: {str(e)}"

    @staticmethod
    def get_document_type_by_id(doc_type_id: int):
        return DocumentType.query.get(doc_type_id)

    @staticmethod
    def get_all_document_types():
        return DocumentType.query.all()
