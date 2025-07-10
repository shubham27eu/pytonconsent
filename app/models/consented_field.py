from app import db

class ConsentedField(db.Model):
    __tablename__ = 'consented_fields'

    id = db.Column(db.Integer, primary_key=True)
    consent_id = db.Column(db.Integer, db.ForeignKey('consents.id'), nullable=False)
    # Storing field name that was approved. Must match a field_name from the associated RequestedFields.
    field_name = db.Column(db.String(100), nullable=False)

    # Optional: per-field access count, if different from the main Consent's access_count.
    # If null, the main Consent's access_count applies.
    # access_count_total_for_field = db.Column(db.Integer, nullable=True)
    # access_count_remaining_for_field = db.Column(db.Integer, nullable=True)

    __table_args__ = (db.UniqueConstraint('consent_id', 'field_name', name='_consent_field_name_uc'),)

    def __repr__(self):
        return f'<ConsentedField {self.field_name} for ConsentID: {self.consent_id}>'
