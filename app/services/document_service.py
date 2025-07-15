from app import db
from app.models import Document, User, DocumentType
from datetime import datetime, timezone
from app.services.pdf_extraction_service import PDFExtractionService # Import the new service
import os # To check for file existence

class DocumentService:
    @staticmethod
    def ingest_document(name: str, document_type_id: int, owner_id: int, file_path: str, additional_metadata: dict = None):
        """
        Ingests a new document, extracts its content, and links it to a type and owner.

        Args:
            name: Display name or original filename of the document.
            document_type_id: ID of the DocumentType this document belongs to.
            owner_id: ID of the User who owns/uploaded this document.
            file_path: Path to the local PDF document content.
            additional_metadata: Optional dictionary for any other metadata provided by the user.

        Returns:
            Tuple: (Document | None, error_message | None)
        """
        # --- Initial validation ---
        owner = User.query.get(owner_id)
        if not owner:
            return None, "Owner not found."
        if owner.role != 'owner':
            return None, "User does not have 'owner' role (or appropriate permissions to ingest)."

        doc_type = DocumentType.query.get(document_type_id)
        if not doc_type:
            return None, f"DocumentType with ID {document_type_id} not found."

        if not file_path:
            return None, "File path cannot be empty."

        # Check if the file exists before processing
        if not os.path.exists(file_path):
            return None, f"File not found at path: {file_path}"

        # --- PDF Extraction ---
        extracted_data = PDFExtractionService.extract_data(file_path, doc_type)
        if "_pdf_extraction_error" in extracted_data:
            return None, f"Failed to process PDF: {extracted_data['_pdf_extraction_error']}"

        # --- Combine metadata ---
        # User-provided metadata takes precedence over extracted data in case of key collision.
        final_metadata = extracted_data
        if additional_metadata:
            final_metadata.update(additional_metadata) # Merge user-provided metadata

        # --- Create Document Record ---
        document = Document(
            name=name,
            document_type_id=document_type_id,
            owner_id=owner_id,
            file_path=file_path,
            additional_metadata=final_metadata,
            uploaded_at=datetime.now(timezone.utc)
        )

        try:
            db.session.add(document)
            db.session.commit()
            return document, None
        except Exception as e:
            db.session.rollback()
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
