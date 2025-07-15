import unittest
import json
import os
from datetime import datetime, timedelta
from app import create_app, db
from app.models import User, DocumentType, DocumentField, FieldClassification, Document, ConsentRequest, ConsentRequestStatus, Consent, ConsentStatus, AuditLog
from app.services.consent_service import ConsentService
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

class AccessAPITestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            self.owner = User(username='accessowner', email='accessowner@example.com', role='owner')
            self.requester = User(username='accessrequester', email='accessreq@example.com', role='requester')
            db.session.add_all([self.owner, self.requester])
            db.session.commit()
            self.owner_id = self.owner.id
            self.requester_id = self.requester.id

            self.doc_type = DocumentType(name="AccessTestDocType", owner_id=self.owner_id)
            self.doc_type.fields.append(DocumentField(name="OpenField", classification=FieldClassification.OPEN))
            self.doc_type.fields.append(DocumentField(name="ControlledField1", classification=FieldClassification.CONTROLLED))
            self.doc_type.fields.append(DocumentField(name="ControlledField2", classification=FieldClassification.CONTROLLED))
            self.doc_type.fields.append(DocumentField(name="ClosedField", classification=FieldClassification.CLOSED))
            db.session.add(self.doc_type)
            db.session.commit()
            self.doc_type_id = self.doc_type.id

            # Generate a sample PDF with data to be extracted and accessed
            self.sample_pdf_path = os.path.join(os.path.dirname(__file__), 'samples', 'access_test.pdf')
            os.makedirs(os.path.dirname(self.sample_pdf_path), exist_ok=True)
            c = canvas.Canvas(self.sample_pdf_path, pagesize=letter)
            c.drawString(50, 750, "OpenField: Public Data")
            c.drawString(50, 735, "ControlledField1: Secret A")
            c.drawString(50, 720, "ControlledField2: Secret B")
            c.drawString(50, 705, "ClosedField: Internal Use Only")
            c.save()

            # Ingest the document using the service to ensure data is extracted
            from app.services.document_service import DocumentService
            self.document, error = DocumentService.ingest_document(
                name="AccessTestDoc",
                document_type_id=self.doc_type_id,
                owner_id=self.owner_id,
                file_path=self.sample_pdf_path
            )
            self.assertIsNone(error)
            self.assertIsNotNone(self.document)
            self.doc_id = self.document.id

            # Field names for easy use
            self.open_field_name = "OpenField"
            self.controlled1_name = "ControlledField1"
            self.controlled2_name = "ControlledField2"
            self.closed_field_name = "ClosedField"

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        if os.path.exists(self.sample_pdf_path):
            os.remove(self.sample_pdf_path)
        try:
            os.rmdir(os.path.dirname(self.sample_pdf_path))
        except OSError:
            pass

    def _make_access_request(self, doc_id, requester_id, field_names):
        payload = {"requester_id": requester_id, "field_names": field_names}
        return self.client.post(f'/api/documents/{doc_id}/access-fields', data=json.dumps(payload), content_type='application/json')

    def test_access_open_field_no_consent_needed(self):
        response = self._make_access_request(self.doc_id, self.requester_id, [self.open_field_name])
        self.assertEqual(response.status_code, 200, msg=response.get_data(as_text=True))
        data = response.get_json()['accessed_data']
        self.assertIn(self.open_field_name, data)
        self.assertEqual(data[self.open_field_name], "Public Data")

    def test_access_closed_field_denied(self):
        response = self._make_access_request(self.doc_id, self.requester_id, [self.closed_field_name])
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['accessed_data']
        self.assertEqual(data.get(self.closed_field_name), "********")

    def test_access_controlled_field_no_consent_denied(self):
        response = self._make_access_request(self.doc_id, self.requester_id, [self.controlled1_name])
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['accessed_data']
        self.assertEqual(data.get(self.controlled1_name), "********")

    def test_owner_access_own_document(self):
        response = self._make_access_request(self.doc_id, self.owner_id, [self.open_field_name, self.controlled1_name])
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['accessed_data']
        self.assertEqual(data.get(self.open_field_name), "Public Data")
        self.assertEqual(data.get(self.controlled1_name), "Secret A")

        # Owner CAN access their own closed fields according to current AccessService logic
        response_closed = self._make_access_request(self.doc_id, self.owner_id, [self.closed_field_name])
        self.assertEqual(response_closed.status_code, 200, msg=response_closed.get_data(as_text=True))
        data_closed = response_closed.get_json()['accessed_data']
        self.assertEqual(data_closed.get(self.closed_field_name), "Internal Use Only")

    def _setup_valid_consent(self, field_names, access_count=None, valid_until_delta_days=None):
        with self.app.app_context():
            req, _ = ConsentService.create_consent_request(self.requester_id, self.doc_id, field_names)
            db.session.commit()
            valid_delta = timedelta(days=valid_until_delta_days) if valid_until_delta_days else None
            _, grant, _ = ConsentService.action_consent_request(
                req.id, self.owner_id, approved_field_names=field_names,
                overall_status=ConsentRequestStatus.APPROVED,
                access_count_total=access_count, valid_until_delta=valid_delta
            )
            db.session.commit()
            self.assertIsNotNone(grant, "Failed to set up valid consent grant in test helper.")
            return grant.id

    def test_access_controlled_field_with_valid_consent(self):
        self._setup_valid_consent([self.controlled1_name])
        response = self._make_access_request(self.doc_id, self.requester_id, [self.controlled1_name])
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['accessed_data']
        self.assertEqual(data.get(self.controlled1_name), "Secret A")

    def test_access_controlled_field_consent_expired(self):
        self._setup_valid_consent([self.controlled1_name], valid_until_delta_days=-1) # Expired yesterday
        response = self._make_access_request(self.doc_id, self.requester_id, [self.controlled1_name])
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['accessed_data']
        self.assertEqual(data.get(self.controlled1_name), "********")

    def test_access_controlled_field_count_depleted(self):
        grant_id = self._setup_valid_consent([self.controlled1_name], access_count=1)

        # First access (should succeed and use up the count)
        response1 = self._make_access_request(self.doc_id, self.requester_id, [self.controlled1_name])
        self.assertEqual(response1.status_code, 200)

        # Second access (should fail)
        response2 = self._make_access_request(self.doc_id, self.requester_id, [self.controlled1_name])
        self.assertEqual(response2.status_code, 200)
        data = response2.get_json()['accessed_data']
        self.assertEqual(data.get(self.controlled1_name), "********")


        # Verify grant status in DB
        with self.app.app_context():
            grant = Consent.query.get(grant_id)
            self.assertEqual(grant.status, ConsentStatus.DEPLETED)
            self.assertEqual(grant.access_count_remaining, 0)

    def test_access_field_not_in_grant(self):
        self._setup_valid_consent([self.controlled1_name]) # Grant only for ControlledField1
        response = self._make_access_request(self.doc_id, self.requester_id, [self.controlled2_name]) # Requesting ControlledField2
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['accessed_data']
        self.assertEqual(data.get(self.controlled2_name), "********")

    def test_access_multiple_fields_mixed_permissions(self):
        self._setup_valid_consent([self.controlled1_name]) # Consent for ControlledField1

        # Request OpenField (allowed), ControlledField1 (allowed by grant), ControlledField2 (no grant)
        response = self._make_access_request(self.doc_id, self.requester_id, [self.open_field_name, self.controlled1_name, self.controlled2_name])
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['accessed_data']
        self.assertEqual(data.get(self.open_field_name), "Public Data")
        self.assertEqual(data.get(self.controlled1_name), "Secret A")
        self.assertEqual(data.get(self.controlled2_name), "********")

    def test_audit_log_on_access_attempt(self):
        with self.app.app_context():
            initial_log_count = AuditLog.query.count()

        self._make_access_request(self.doc_id, self.requester_id, [self.open_field_name]) # Successful access

        with self.app.app_context():
            final_log_count = AuditLog.query.count()
            self.assertGreater(final_log_count, initial_log_count)
            # Check for specific log details if necessary
            latest_log = AuditLog.query.order_by(AuditLog.timestamp.desc()).first()
            self.assertEqual(latest_log.action, "FIELD_ACCESS_GRANTED_OPEN")
            self.assertEqual(latest_log.user_id, self.requester_id)
            self.assertEqual(latest_log.target_resource_id, self.doc_id)

        # Test denied access audit
        with self.app.app_context():
            initial_log_count = AuditLog.query.count()
        self._make_access_request(self.doc_id, self.requester_id, [self.closed_field_name]) # Denied access
        with self.app.app_context():
            final_log_count = AuditLog.query.count()
            self.assertGreater(final_log_count, initial_log_count)
            latest_log = AuditLog.query.order_by(AuditLog.timestamp.desc()).first()
            self.assertEqual(latest_log.action, "FIELD_ACCESS_MASKED_CLOSED")


if __name__ == '__main__':
    unittest.main()
