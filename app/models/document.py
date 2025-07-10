from app import db
from datetime import datetime, timezone

class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False) # Display name or original filename
    document_type_id = db.Column(db.Integer, db.ForeignKey('document_types.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) # User who uploaded/owns this document

    # For actual file storage, this could be a path in a local filesystem,
    # a URL to an object store (S3, GCS), or an ID in a document management system.
    file_path = db.Column(db.String(1024), nullable=True) # Nullable if content stored elsewhere or if metadata-only

    uploaded_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    additional_metadata = db.Column(db.JSON, nullable=True) # Any other relevant metadata

    # Relationships
    consent_requests = db.relationship('ConsentRequest', backref='document', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Document {self.name} (ID: {self.id})>'
