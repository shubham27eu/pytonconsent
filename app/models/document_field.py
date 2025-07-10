from app import db
from enum import Enum as PyEnum

class FieldClassification(PyEnum):
    OPEN = "open"         # Freely accessible
    CONTROLLED = "controlled" # Requires explicit consent
    CLOSED = "closed"       # Generally not accessible, sensitive internal fields

class DocumentField(db.Model):
    __tablename__ = 'document_fields'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # Using db.Enum for field classification for database-level type checking if supported,
    # otherwise, a String with validation in the application layer.
    # SQLAlchemy's Enum requires the Python enum type.
    classification = db.Column(db.Enum(FieldClassification), nullable=False)
    document_type_id = db.Column(db.Integer, db.ForeignKey('document_types.id'), nullable=False)

    # Add a unique constraint for field name within a document type
    __table_args__ = (db.UniqueConstraint('name', 'document_type_id', name='_document_type_field_name_uc'),)


    def __repr__(self):
        return f'<DocumentField {self.name} ({self.classification.value}) for DT {self.document_type_id}>'
