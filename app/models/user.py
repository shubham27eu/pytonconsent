from app import db
from datetime import datetime, timezone

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    # For simplicity, using a string for role. In a real app, might be an enum or a separate Role model.
    role = db.Column(db.String(20), nullable=False, default='requester') # 'owner' or 'requester'
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    # Owned document types
    document_types_owned = db.relationship('DocumentType', backref='owner', lazy=True, foreign_keys='DocumentType.owner_id')
    # Owned documents
    documents_owned = db.relationship('Document', backref='owner', lazy=True, foreign_keys='Document.owner_id')
    # Consent requests made by this user
    consent_requests_made = db.relationship('ConsentRequest', backref='requester', lazy=True, foreign_keys='ConsentRequest.requester_id')
    # Consents approved by this user (as an owner)
    consents_approved = db.relationship('Consent', backref='approving_owner', lazy=True, foreign_keys='Consent.owner_id')
    # Audit logs related to this user
    audit_logs = db.relationship('AuditLog', backref='user', lazy=True, foreign_keys='AuditLog.user_id')


    def __repr__(self):
        return f'<User {self.username} ({self.role})>'
