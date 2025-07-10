from app import db
from datetime import datetime, timezone

class DocumentType(db.Model):
    __tablename__ = 'document_types'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) # User who defined/owns this type
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    fields = db.relationship('DocumentField', backref='document_type', lazy=True, cascade="all, delete-orphan")
    documents = db.relationship('Document', backref='document_type', lazy=True)

    def __repr__(self):
        return f'<DocumentType {self.name}>'
