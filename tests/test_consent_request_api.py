import unittest
import json
from app import create_app, db
from app.models import User, DocumentType, DocumentField, FieldClassification, Document, ConsentRequest, RequestedField, ConsentRequestStatus, ConsentStatus # Import ConsentStatus
from app.services.consent_service import ConsentService # Import ConsentService

class ConsentRequestAPITestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            # Create users
            self.owner = User(username='consentowner', email='consentowner@example.com', role='owner')
            self.requester1 = User(username='requester1', email='req1@example.com', role='requester')
            self.requester2 = User(username='requester2', email='req2@example.com', role='requester')
            db.session.add_all([self.owner, self.requester1, self.requester2])
            db.session.commit()
            self.owner_id = self.owner.id # Store ID
            self.requester1_id = self.requester1.id # Store ID
            self.requester2_id = self.requester2.id # Store ID


            # Create Document Type
            self.doc_type = DocumentType(name="FinancialReport", description="Confidential financial report", owner_id=self.owner_id)
            self.field_open = DocumentField(name="ReportPeriod", classification=FieldClassification.OPEN, document_type=self.doc_type)
            self.field_controlled = DocumentField(name="NetProfit", classification=FieldClassification.CONTROLLED, document_type=self.doc_type)
            self.field_closed = DocumentField(name="InternalAuditNotes", classification=FieldClassification.CLOSED, document_type=self.doc_type)
            db.session.add_all([self.doc_type, self.field_open, self.field_controlled, self.field_closed])
            db.session.commit()
            self.doc_type_id = self.doc_type.id # Store ID
            self.field_open_name = self.field_open.name
            self.field_controlled_name = self.field_controlled.name
            self.field_closed_name = self.field_closed.name

            # Ingest a document
            self.document1 = Document(name="Q1 Report", document_type_id=self.doc_type_id, owner_id=self.owner_id, file_path="/reports/q1.pdf")
            db.session.add(self.document1)
            db.session.commit()
            self.doc1_id = self.document1.id


    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_create_consent_request_success(self):
        payload = {
            "requester_id": self.requester1_id,
            "document_id": self.doc1_id,
            "requested_field_names": ["ReportPeriod", "NetProfit"],
            "request_message": "Need Q1 financial data for planning."
        }
        response = self.client.post('/api/consent-requests', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 201, msg=response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(data['requester_id'], self.requester1_id)
        self.assertEqual(data['document_id'], self.doc1_id)
        self.assertEqual(data['status'], ConsentRequestStatus.PENDING.value)
        self.assertIn("ReportPeriod", [f['field_name'] for f in data['requested_fields']])
        self.assertIn("NetProfit", [f['field_name'] for f in data['requested_fields']])

        # Verify DB
        with self.app.app_context():
            cr = ConsentRequest.query.get(data['id'])
            self.assertIsNotNone(cr)
            self.assertEqual(len(cr.requested_fields), 2)

    def test_create_consent_request_for_own_document(self):
        payload = {
            "requester_id": self.owner_id, # Owner is the requester
            "document_id": self.doc1_id,
            "requested_field_names": ["NetProfit"]
        }
        response = self.client.post('/api/consent-requests', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 403) # Or 400 depending on error mapping
        self.assertIn("Cannot request consent for your own document", response.get_json()['error'])

    def test_create_consent_request_non_existent_document(self):
        payload = {
            "requester_id": self.requester1_id,
            "document_id": 999, # Non-existent doc
            "requested_field_names": ["NetProfit"]
        }
        response = self.client.post('/api/consent-requests', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 404)
        self.assertIn("Document with ID 999 not found", response.get_json()['error'])

    def test_create_consent_request_non_existent_field(self):
        payload = {
            "requester_id": self.requester1_id,
            "document_id": self.doc1_id,
            "requested_field_names": ["NonExistentField", "NetProfit"]
        }
        response = self.client.post('/api/consent-requests', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400) # Service returns generic error for this
        self.assertIn("Field 'NonExistentField' does not exist", response.get_json()['error'])

    def test_create_consent_request_for_closed_field(self):
        payload = {
            "requester_id": self.requester1_id,
            "document_id": self.doc1_id,
            "requested_field_names": ["InternalAuditNotes"] # Closed field
        }
        response = self.client.post('/api/consent-requests', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 403) # Or 400
        self.assertIn("classified as closed and cannot be requested", response.get_json()['error'])

    def test_create_consent_request_empty_field_list(self):
        payload = {
            "requester_id": self.requester1_id,
            "document_id": self.doc1_id,
            "requested_field_names": [] # Empty list
        }
        response = self.client.post('/api/consent-requests', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("requested_field_names cannot be empty", response.get_json()['error']) # API check

        # Test if service catches it if API check is bypassed (e.g. service used directly)
        with self.app.app_context():
            _, error = ConsentService.create_consent_request(self.requester1_id, self.doc1_id, [])
            self.assertIn("At least one field must be requested", error)


    def test_get_consent_request_by_id(self):
        # Create a request first
        # Need to be in app_context for service call if it uses db.session implicitly
        with self.app.app_context():
            cr, _ = ConsentService.create_consent_request(self.requester1_id, self.doc1_id, ["NetProfit"], "Test message")
            db.session.commit() # Ensure it's committed so GET request can find it
            cr_id = cr.id

        response = self.client.get(f'/api/consent-requests/{cr_id}')
        self.assertEqual(response.status_code, 200, msg=response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(data['id'], cr_id)
        self.assertEqual(data['requester']['id'], self.requester1_id)
        self.assertEqual(data['document']['id'], self.doc1_id)
        self.assertEqual(data['document']['owner']['id'], self.owner_id)
        self.assertIn("NetProfit", [f['field_name'] for f in data['requested_fields']])

    def test_get_non_existent_consent_request(self):
        response = self.client.get('/api/consent-requests/9999')
        self.assertEqual(response.status_code, 404)

    def test_list_consent_requests_for_owner(self):
        with self.app.app_context():
            ConsentService.create_consent_request(self.requester1_id, self.doc1_id, ["NetProfit"])
            ConsentService.create_consent_request(self.requester2_id, self.doc1_id, ["ReportPeriod"])
            db.session.commit() # Ensure these are committed

        response = self.client.get(f'/api/consent-requests?owner_id={self.owner_id}')
        self.assertEqual(response.status_code, 200, msg=response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(len(data), 2)
        # Check if owner_id in document matches
        for item in data:
            self.assertEqual(item['document']['owner']['id'], self.owner_id)

    def test_list_consent_requests_for_requester(self):
        with self.app.app_context():
            ConsentService.create_consent_request(self.requester1_id, self.doc1_id, ["NetProfit"])
            # Create another request for a different document (not strictly necessary for this test)
            doc2 = Document(name="Q2 Report", document_type_id=self.doc_type_id, owner_id=self.owner_id, file_path="/reports/q2.pdf")
            db.session.add(doc2)
            db.session.commit() # Commit doc2
            doc2_id = doc2.id
            ConsentService.create_consent_request(self.requester1_id, doc2_id, ["ReportPeriod"])
            ConsentService.create_consent_request(self.requester2_id, self.doc1_id, ["ReportPeriod"]) # Belongs to another requester
            db.session.commit() # Commit all requests

        response = self.client.get(f'/api/consent-requests?requester_id={self.requester1_id}')
        self.assertEqual(response.status_code, 200, msg=response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(len(data), 2)
        for item in data:
            self.assertEqual(item['requester']['id'], self.requester1_id)

    def test_list_consent_requests_no_filter(self):
        response = self.client.get('/api/consent-requests')
        self.assertEqual(response.status_code, 400) # As per current implementation
        self.assertIn("Must provide either requester_id or owner_id", response.get_json()['error'])

    # --- Tests for Actioning Consent Requests ---

    def _create_pending_request(self, requester_id, field_names=["ReportPeriod", "NetProfit"]):
        """Helper to create a pending consent request for self.doc1_id."""
        with self.app.app_context():
            req, err = ConsentService.create_consent_request(
                requester_id=requester_id,
                document_id=self.doc1_id,
                requested_field_names=field_names,
                request_message="Test request for actioning"
            )
            self.assertIsNone(err)
            self.assertIsNotNone(req)
            db.session.commit()
            return req.id

    def test_action_consent_request_approve_all_implicit(self):
        request_id = self._create_pending_request(self.requester1_id)
        payload = {
            "owner_id": self.owner_id,
            "overall_status": "APPROVED",
            "owner_message": "All approved.",
            "valid_until_days": 30,
            "access_count_total": 10
        }
        response = self.client.post(f'/api/consent-requests/{request_id}/action', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200, msg=response.get_data(as_text=True))
        data = response.get_json()

        self.assertEqual(data['consent_request']['status'], ConsentRequestStatus.APPROVED.value)
        self.assertIsNotNone(data['consent_grant'])
        grant = data['consent_grant']
        self.assertEqual(grant['status'], ConsentStatus.ACTIVE.value)
        self.assertEqual(grant['access_count_total'], 10)
        self.assertEqual(grant['access_count_remaining'], 10)
        self.assertIsNotNone(grant['valid_until'])
        self.assertEqual(len(grant['consented_fields']), 2) # ReportPeriod, NetProfit (as per helper)
        consented_field_names = {cf['field_name'] for cf in grant['consented_fields']}
        self.assertIn("ReportPeriod", consented_field_names)
        self.assertIn("NetProfit", consented_field_names)

    def test_action_consent_request_approve_explicit_fields(self):
        request_id = self._create_pending_request(self.requester1_id, field_names=["ReportPeriod", "NetProfit"])
        payload = {
            "owner_id": self.owner_id,
            "overall_status": "APPROVED",
            "approved_field_names": ["NetProfit"], # Explicitly only NetProfit
            "owner_message": "Only NetProfit approved."
        }
        response = self.client.post(f'/api/consent-requests/{request_id}/action', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['consent_request']['status'], ConsentRequestStatus.APPROVED.value)
        grant = data['consent_grant']
        self.assertIsNotNone(grant)
        self.assertEqual(len(grant['consented_fields']), 1)
        self.assertEqual(grant['consented_fields'][0]['field_name'], "NetProfit")

    def test_action_consent_request_partially_approve(self):
        request_id = self._create_pending_request(self.requester1_id, field_names=["ReportPeriod", "NetProfit"])
        payload = {
            "owner_id": self.owner_id,
            "overall_status": "PARTIALLY_APPROVED",
            "approved_field_names": ["ReportPeriod"], # Only ReportPeriod
            "owner_message": "ReportPeriod approved, NetProfit denied for now."
        }
        response = self.client.post(f'/api/consent-requests/{request_id}/action', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['consent_request']['status'], ConsentRequestStatus.PARTIALLY_APPROVED.value)
        grant = data['consent_grant']
        self.assertIsNotNone(grant)
        self.assertEqual(len(grant['consented_fields']), 1)
        self.assertEqual(grant['consented_fields'][0]['field_name'], "ReportPeriod")

    def test_action_consent_request_deny(self):
        request_id = self._create_pending_request(self.requester1_id)
        payload = {
            "owner_id": self.owner_id,
            "overall_status": "DENIED",
            "owner_message": "Not approved at this time."
        }
        response = self.client.post(f'/api/consent-requests/{request_id}/action', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['consent_request']['status'], ConsentRequestStatus.DENIED.value)
        self.assertIsNone(data['consent_grant']) # No grant for denial

    def test_action_consent_request_not_owner(self):
        request_id = self._create_pending_request(self.requester1_id)
        payload = {
            "owner_id": self.requester2_id, # Wrong owner
            "overall_status": "APPROVED"
        }
        response = self.client.post(f'/api/consent-requests/{request_id}/action', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertIn("not the owner", response.get_json()['error'])

    def test_action_consent_request_already_actioned(self):
        request_id = self._create_pending_request(self.requester1_id)
        action_payload = {"owner_id": self.owner_id, "overall_status": "DENIED"}
        self.client.post(f'/api/consent-requests/{request_id}/action', data=json.dumps(action_payload), content_type='application/json') # First action

        response = self.client.post(f'/api/consent-requests/{request_id}/action', data=json.dumps(action_payload), content_type='application/json') # Second attempt
        self.assertEqual(response.status_code, 403)
        self.assertIn("not in a pending state", response.get_json()['error'])

    def test_action_consent_partially_approve_requires_fields(self):
        request_id = self._create_pending_request(self.requester1_id)
        payload = {
            "owner_id": self.owner_id,
            "overall_status": "PARTIALLY_APPROVED",
            # approved_field_names is missing
        }
        response = self.client.post(f'/api/consent-requests/{request_id}/action', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("approved_field_names list must be provided", response.get_json()['error'])

    def test_action_consent_approve_field_not_requested(self):
        request_id = self._create_pending_request(self.requester1_id, field_names=["ReportPeriod"]) # Only ReportPeriod requested
        payload = {
            "owner_id": self.owner_id,
            "overall_status": "APPROVED",
            "approved_field_names": ["ReportPeriod", "NetProfit"] # NetProfit was not requested
        }
        response = self.client.post(f'/api/consent-requests/{request_id}/action', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400) # Service should catch this
        self.assertIn("approved but not originally requested", response.get_json()['error'])

    def test_action_consent_approve_closed_field_error(self):
        # Create a request that somehow includes a closed field (service should prevent this, but test defense)
        # For this test, we'll manually create a request that includes it, bypassing service validation for request creation
        with self.app.app_context():
            cr = ConsentRequest(requester_id=self.requester1_id, document_id=self.doc1_id, status=ConsentRequestStatus.PENDING)
            # field_closed_name was "InternalAuditNotes"
            rf = RequestedField(field_name=self.field_closed_name) # This field is CLOSED
            cr.requested_fields.append(rf)
            db.session.add(cr)
            db.session.commit()
            request_id_with_closed = cr.id

        payload = {
            "owner_id": self.owner_id,
            "overall_status": "APPROVED",
            "approved_field_names": [self.field_closed_name]
        }
        response = self.client.post(f'/api/consent-requests/{request_id_with_closed}/action', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400) # Service validation
        self.assertIn("is CLOSED and cannot be part of a consent grant", response.get_json()['error'])


if __name__ == '__main__':
    unittest.main()
