from app import db

class RequestedField(db.Model):
    __tablename__ = 'requested_fields'

    id = db.Column(db.Integer, primary_key=True)
    consent_request_id = db.Column(db.Integer, db.ForeignKey('consent_requests.id'), nullable=False)
    # Storing field name directly. Could also link to DocumentField.id if preferred,
    # but name is simpler for now and avoids issues if DocumentField definitions change.
    # This implies that requested field names must match defined field names in DocumentField.
    field_name = db.Column(db.String(100), nullable=False)

    # Potential: Add a status here if individual fields within a request can be actioned separately
    # before the main Consent grant is created. For now, assuming the Consent grant handles this.
    # e.g., field_status = db.Column(db.Enum('pending', 'approved_for_grant', 'denied_for_grant'))


    __table_args__ = (db.UniqueConstraint('consent_request_id', 'field_name', name='_consent_request_field_uc'),)

    def __repr__(self):
        return f'<RequestedField {self.field_name} for RequestID: {self.consent_request_id}>'
