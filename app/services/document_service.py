from app import db
from app.models import Document, User, DocumentType
from datetime import datetime, timezone # Import timezone

class DocumentService:
    @staticmethod
    def ingest_document(name: str, document_type_id: int, owner_id: int, file_path: str, additional_metadata: dict = None):
        """
        Ingests a new document, linking it to a document type and owner.

        Args:
            name: Display name or original filename of the document.
            document_type_id: ID of the DocumentType this document belongs to.
            owner_id: ID of the User who owns/uploaded this document.
            file_path: Path or reference to the actual document content.
            additional_metadata: Optional dictionary for any other metadata.

        Returns:
            Tuple: (Document | None, error_message | None)
        """
        # Validate owner
        owner = User.query.get(owner_id)
        if not owner:
            return None, "Owner not found."
        if owner.role != 'owner': # Or any other role check if requesters can also upload for themselves
            return None, "User does not have 'owner' role (or appropriate permissions to ingest)."

        # Validate document type
        doc_type = DocumentType.query.get(document_type_id)
        if not doc_type:
            return None, f"DocumentType with ID {document_type_id} not found."

        # Potentially check if a document with the same name from the same owner already exists, if needed
        # existing_doc = Document.query.filter_by(name=name, owner_id=owner_id).first()
        # if existing_doc:
        #     return None, f"Document with name '{name}' already ingested by this owner."

        if not file_path: # Basic validation for file_path
            return None, "File path cannot be empty."

        document = Document(
            name=name,
            document_type_id=document_type_id,
            owner_id=owner_id,
            file_path=file_path,
            additional_metadata=additional_metadata,
            # model default uses lambda: datetime.now(timezone.utc), so explicit set here should also be timezone-aware
            uploaded_at=datetime.now(timezone.utc)
        )

        try:
            db.session.add(document)
            db.session.commit()
            return document, None
        except Exception as e:
            db.session.rollback()
            # Log error e
            return None, f"Database error during document ingestion: {str(e)}"

    @staticmethod
    def get_document_by_id(doc_id: int):
        return Document.query.get(doc_id)

    @staticmethod
    def get_documents_by_owner(owner_id: int):
        return Document.query.filter_by(owner_id=owner_id).all()

    @staticmethod
    def get_all_documents():
        return Document.query.all()
