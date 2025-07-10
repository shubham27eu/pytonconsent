from app import db
from datetime import datetime, timezone

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    # user_id can be null if the action is system-initiated or anonymous
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(255), nullable=False) # e.g., "USER_LOGIN", "DOCUMENT_UPLOAD", "CONSENT_GRANTED"
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    details = db.Column(db.JSON, nullable=True) # Store any relevant context, e.g., document_id, field_names

    # Optional: target resource information for easier querying
    target_resource_type = db.Column(db.String(50), nullable=True) # E.g., "Document", "ConsentRequest", "User"
    target_resource_id = db.Column(db.Integer, nullable=True)

    def __repr__(self):
        return f'<AuditLog ID: {self.id} Action: {self.action} User: {self.user_id} Time: {self.timestamp}>'
