from app import db
from datetime import datetime, timezone
from enum import Enum as PyEnum

class ConsentRequestStatus(PyEnum):
    PENDING = "pending"
    APPROVED = "approved" # Indicates the request as a whole has been approved (leading to a Consent grant)
    PARTIALLY_APPROVED = "partially_approved" # Some fields approved, some denied
    DENIED = "denied"   # Indicates the request as a whole has been denied
    CANCELLED = "cancelled" # Cancelled by requester

class ConsentRequest(db.Model):
    __tablename__ = 'consent_requests'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    requested_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.Enum(ConsentRequestStatus), nullable=False, default=ConsentRequestStatus.PENDING)

    # Message from requester (optional)
    request_message = db.Column(db.Text, nullable=True)
    # Message from owner when actioning (optional)
    owner_message = db.Column(db.Text, nullable=True)


    # Relationships
    # Fields specifically requested in this request
    requested_fields = db.relationship('RequestedField', backref='consent_request', lazy='joined', cascade="all, delete-orphan")
    # The actual consent grant, if this request is approved
    consent_grant = db.relationship('Consent', backref='consent_request', uselist=False, lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<ConsentRequest ID: {self.id} for Doc: {self.document_id} by User: {self.requester_id} Status: {self.status.value}>'
