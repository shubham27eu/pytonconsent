from app import db
from datetime import datetime, timezone
from enum import Enum as PyEnum

class ConsentStatus(PyEnum):
    ACTIVE = "active"       # Consent is currently valid
    EXPIRED = "expired"     # Consent period has passed
    REVOKED = "revoked"     # Owner explicitly revoked consent
    DEPLETED = "depleted"   # Access count exhausted

class Consent(db.Model):
    __tablename__ = 'consents'

    id = db.Column(db.Integer, primary_key=True)
    # Links back to the original request that led to this consent
    consent_request_id = db.Column(db.Integer, db.ForeignKey('consent_requests.id'), nullable=False, unique=True)
    # User who granted the consent (document owner)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    granted_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # Expiration date/time for this consent. Nullable if consent never expires.
    valid_until = db.Column(db.DateTime(timezone=True), nullable=True)
    # Total number of times the consented data can be accessed. Nullable if unlimited.
    # This is an overall count for the consent grant. Per-field counts can be on ConsentedField.
    access_count_total = db.Column(db.Integer, nullable=True)
    access_count_remaining = db.Column(db.Integer, nullable=True)

    status = db.Column(db.Enum(ConsentStatus), nullable=False, default=ConsentStatus.ACTIVE)

    # Relationships
    # Fields that were actually approved as part of this consent grant
    consented_fields = db.relationship('ConsentedField', backref='consent', lazy='joined', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Consent ID: {self.id} for RequestID: {self.consent_request_id} Status: {self.status.value}>'

    def pre_access_check(self):
        """Checks if the consent is active and within limits before an access attempt."""
        if self.status != ConsentStatus.ACTIVE:
            return False, f"Consent is not active (status: {self.status.value})"

        # Ensure comparison is between two offset-aware datetimes or two offset-naive datetimes.
        # Since self.valid_until might be naive from SQLite, and we know it was stored as UTC:
        if self.valid_until:
            aware_valid_until = self.valid_until
            if self.valid_until.tzinfo is None: # If naive (e.g. from SQLite)
                aware_valid_until = self.valid_until.replace(tzinfo=timezone.utc)

            if datetime.now(timezone.utc) > aware_valid_until:
                self.status = ConsentStatus.EXPIRED
                db.session.add(self)
                # db.session.commit() # Commit should be handled by service layer
            return False, "Consent has expired"

        if self.access_count_remaining is not None and self.access_count_remaining <= 0:
            self.status = ConsentStatus.DEPLETED
            db.session.add(self)
            # db.session.commit()
            return False, "Access count depleted"

        return True, "Consent is valid for access"

    def record_access(self):
        """Records an access attempt against this consent."""
        if self.access_count_remaining is not None:
            if self.access_count_remaining > 0:
                self.access_count_remaining -= 1
                if self.access_count_remaining == 0:
                    self.status = ConsentStatus.DEPLETED
                db.session.add(self)
                return True
            else: # Should have been caught by pre_access_check
                self.status = ConsentStatus.DEPLETED
                db.session.add(self)
                return False
        return True # No count limit or already handled
