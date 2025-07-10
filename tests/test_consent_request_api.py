import unittest
import json
from app import create_app, db
from app.models import User, DocumentType, DocumentField, FieldClassification, Document, ConsentRequest, RequestedField, ConsentRequestStatus, Consent, ConsentStatus, AuditLog # Import Consent, ConsentStatus and AuditLog
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
            self.field_controlled = DocumentField(name="NetProfit", classification=FieldClassification.CONTROLLED, document_type=self.doc_type) # Keep one for general use
            self.field_closed = DocumentField(name="InternalAuditNotes", classification=FieldClassification.CLOSED, document_type=self.doc_type)
            db.session.add_all([self.doc_type, self.field_open, self.field_controlled, self.field_closed])
            db.session.commit()
            self.doc_type_id = self.doc_type.id # Store ID
            self.field_open_name = self.field_open.name
            self.field_controlled_name = self.field_controlled.name # Use this one in tests
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
            "requested_field_names": [self.field_open_name, self.field_controlled_name],
            "request_message": "Need Q1 financial data for planning."
        }
        response = self.client.post('/api/consent-requests', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 201, msg=response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(data['requester_id'], self.requester1_id)
        self.assertEqual(data['document_id'], self.doc1_id)
        self.assertEqual(data['status'], ConsentRequestStatus.PENDING.value)
        requested_names_in_response = {f['field_name'] for f in data['requested_fields']}
        self.assertIn(self.field_open_name, requested_names_in_response)
        self.assertIn(self.field_controlled_name, requested_names_in_response)

        # Verify DB
        with self.app.app_context():
            cr = ConsentRequest.query.get(data['id'])
            self.assertIsNotNone(cr)
            self.assertEqual(len(cr.requested_fields), 2)

    def test_create_consent_request_for_own_document(self):
        payload = {
            "requester_id": self.owner_id,
            "document_id": self.doc1_id,
            "requested_field_names": [self.field_controlled_name]
        }
        response = self.client.post('/api/consent-requests', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertIn("Cannot request consent for your own document", response.get_json()['error'])

    def test_create_consent_request_non_existent_document(self):
        payload = {
            "requester_id": self.requester1_id,
            "document_id": 999,
            "requested_field_names": [self.field_controlled_name]
        }
        response = self.client.post('/api/consent-requests', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 404)
        self.assertIn("Document with ID 999 not found", response.get_json()['error'])

    def test_create_consent_request_non_existent_field(self):
        payload = {
            "requester_id": self.requester1_id,
            "document_id": self.doc1_id,
            "requested_field_names": ["NonExistentField", self.field_controlled_name]
        }
        response = self.client.post('/api/consent-requests', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Field 'NonExistentField' does not exist", response.get_json()['error'])

    def test_create_consent_request_for_closed_field(self):
        payload = {
            "requester_id": self.requester1_id,
            "document_id": self.doc1_id,
            "requested_field_names": [self.field_closed_name]
        }
        response = self.client.post('/api/consent-requests', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertIn("classified as closed and cannot be requested", response.get_json()['error'])

    def test_create_consent_request_empty_field_list(self):
        payload = {
            "requester_id": self.requester1_id,
            "document_id": self.doc1_id,
            "requested_field_names": []
        }
        response = self.client.post('/api/consent-requests', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("requested_field_names cannot be empty", response.get_json()['error'])

        with self.app.app_context():
            _, error = ConsentService.create_consent_request(self.requester1_id, self.doc1_id, [])
            self.assertIn("At least one field must be requested", error)

    def test_get_consent_request_by_id(self):
        with self.app.app_context():
            cr, _ = ConsentService.create_consent_request(self.requester1_id, self.doc1_id, [self.field_controlled_name], "Test message")
            db.session.commit()
            cr_id = cr.id

        response = self.client.get(f'/api/consent-requests/{cr_id}')
        self.assertEqual(response.status_code, 200, msg=response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(data['id'], cr_id)
        self.assertEqual(data['requester']['id'], self.requester1_id)
        self.assertEqual(data['document']['id'], self.doc1_id)
        self.assertEqual(data['document']['owner']['id'], self.owner_id)
        self.assertIn(self.field_controlled_name, [f['field_name'] for f in data['requested_fields']])

    def test_get_non_existent_consent_request(self):
        response = self.client.get('/api/consent-requests/9999')
        self.assertEqual(response.status_code, 404)

    def test_list_consent_requests_for_owner(self):
        with self.app.app_context():
            ConsentService.create_consent_request(self.requester1_id, self.doc1_id, [self.field_controlled_name])
            ConsentService.create_consent_request(self.requester2_id, self.doc1_id, [self.field_open_name])
            db.session.commit()

        response = self.client.get(f'/api/consent-requests?owner_id={self.owner_id}')
        self.assertEqual(response.status_code, 200, msg=response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(len(data), 2)
        for item in data:
            self.assertEqual(item['document']['owner']['id'], self.owner_id)

    def test_list_consent_requests_for_requester(self):
        with self.app.app_context():
            ConsentService.create_consent_request(self.requester1_id, self.doc1_id, [self.field_controlled_name])
            doc2 = Document(name="Q2 Report", document_type_id=self.doc_type_id, owner_id=self.owner_id, file_path="/reports/q2.pdf")
            db.session.add(doc2)
            db.session.commit()
            doc2_id = doc2.id
            ConsentService.create_consent_request(self.requester1_id, doc2_id, [self.field_open_name])
            ConsentService.create_consent_request(self.requester2_id, self.doc1_id, [self.field_open_name])
            db.session.commit()

        response = self.client.get(f'/api/consent-requests?requester_id={self.requester1_id}')
        self.assertEqual(response.status_code, 200, msg=response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(len(data), 2)
        for item in data:
            self.assertEqual(item['requester']['id'], self.requester1_id)

    def test_list_consent_requests_no_filter(self):
        response = self.client.get('/api/consent-requests')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Must provide either requester_id or owner_id", response.get_json()['error'])

    # --- Tests for Actioning Consent Requests ---

    def _create_pending_request(self, requester_id, field_names=None):
        """Helper to create a pending consent request for self.doc1_id."""
        if field_names is None:
            field_names = [self.field_open_name, self.field_controlled_name]
        with self.app.app_context():
            req, err = ConsentService.create_consent_request(
                requester_id=requester_id,
                document_id=self.doc1_id,
                requested_field_names=field_names,
                request_message="Test request for actioning"
            )
            self.assertIsNone(err, f"Error creating pending request: {err}")
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
        self.assertEqual(len(grant['consented_fields']), 2)
        consented_field_names_resp = {cf['field_name'] for cf in grant['consented_fields']}
        self.assertIn(self.field_open_name, consented_field_names_resp)
        self.assertIn(self.field_controlled_name, consented_field_names_resp)

    def test_action_consent_request_approve_explicit_fields(self):
        request_id = self._create_pending_request(self.requester1_id, field_names=[self.field_open_name, self.field_controlled_name])
        payload = {
            "owner_id": self.owner_id,
            "overall_status": "APPROVED",
            "approved_field_names": [self.field_controlled_name],
            "owner_message": "Only NetProfit approved."
        }
        response = self.client.post(f'/api/consent-requests/{request_id}/action', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['consent_request']['status'], ConsentRequestStatus.APPROVED.value)
        grant = data['consent_grant']
        self.assertIsNotNone(grant)
        self.assertEqual(len(grant['consented_fields']), 1)
        self.assertEqual(grant['consented_fields'][0]['field_name'], self.field_controlled_name)

    def test_action_consent_request_partially_approve(self):
        request_id = self._create_pending_request(self.requester1_id, field_names=[self.field_open_name, self.field_controlled_name])
        payload = {
            "owner_id": self.owner_id,
            "overall_status": "PARTIALLY_APPROVED",
            "approved_field_names": [self.field_open_name],
            "owner_message": "ReportPeriod approved, NetProfit denied for now."
        }
        response = self.client.post(f'/api/consent-requests/{request_id}/action', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['consent_request']['status'], ConsentRequestStatus.PARTIALLY_APPROVED.value)
        grant = data['consent_grant']
        self.assertIsNotNone(grant)
        self.assertEqual(len(grant['consented_fields']), 1)
        self.assertEqual(grant['consented_fields'][0]['field_name'], self.field_open_name)

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
        self.assertIsNone(data['consent_grant'])

    def test_action_consent_request_not_owner(self):
        request_id = self._create_pending_request(self.requester1_id)
        payload = {
            "owner_id": self.requester2_id,
            "overall_status": "APPROVED"
        }
        response = self.client.post(f'/api/consent-requests/{request_id}/action', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertIn("not the owner", response.get_json()['error'])

    def test_action_consent_request_already_actioned(self):
        request_id = self._create_pending_request(self.requester1_id)
        action_payload = {"owner_id": self.owner_id, "overall_status": "DENIED"}
        self.client.post(f'/api/consent-requests/{request_id}/action', data=json.dumps(action_payload), content_type='application/json')

        response = self.client.post(f'/api/consent-requests/{request_id}/action', data=json.dumps(action_payload), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertIn("not in a pending state", response.get_json()['error'])

    def test_action_consent_partially_approve_requires_fields(self):
        request_id = self._create_pending_request(self.requester1_id)
        payload = {
            "owner_id": self.owner_id,
            "overall_status": "PARTIALLY_APPROVED",
        }
        response = self.client.post(f'/api/consent-requests/{request_id}/action', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("approved_field_names list must be provided", response.get_json()['error'])

    def test_action_consent_approve_field_not_requested(self):
        request_id = self._create_pending_request(self.requester1_id, field_names=[self.field_open_name])
        payload = {
            "owner_id": self.owner_id,
            "overall_status": "APPROVED",
            "approved_field_names": [self.field_open_name, self.field_controlled_name]
        }
        response = self.client.post(f'/api/consent-requests/{request_id}/action', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("approved but not originally requested", response.get_json()['error'])

    def test_action_consent_approve_closed_field_error(self):
        with self.app.app_context():
            cr = ConsentRequest(requester_id=self.requester1_id, document_id=self.doc1_id, status=ConsentRequestStatus.PENDING)
            rf = RequestedField(field_name=self.field_closed_name)
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
        self.assertEqual(response.status_code, 400)
        self.assertIn("is CLOSED and cannot be part of a consent grant", response.get_json()['error'])

    def test_list_consent_grants_requires_filter(self):
        response = self.client.get('/api/consents')
        self.assertEqual(response.status_code, 400)
        self.assertIn("At least one filter", response.get_json()['error'])

    # --- Tests for Direct Consent Grant Management (View, List, Revoke) ---

    def test_get_specific_consent_grant(self):
        request_id = self._create_pending_request(self.requester1_id, field_names=[self.field_controlled_name])
        action_payload = {"owner_id": self.owner_id, "overall_status": "APPROVED", "approved_field_names": [self.field_controlled_name]}
        action_response = self.client.post(f'/api/consent-requests/{request_id}/action', data=json.dumps(action_payload), content_type='application/json')
        self.assertEqual(action_response.status_code, 200)
        grant_id = action_response.get_json()['consent_grant']['id']

        response = self.client.get(f'/api/consents/{grant_id}')
        self.assertEqual(response.status_code, 200, msg=response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(data['id'], grant_id)
        self.assertEqual(data['owner_id'], self.owner_id)
        self.assertEqual(len(data['consented_fields']), 1)
        self.assertEqual(data['consented_fields'][0]['field_name'], self.field_controlled_name)
        self.assertIn('consent_request_details', data)
        self.assertEqual(data['consent_request_details']['id'], request_id)

    def test_get_non_existent_consent_grant(self):
        response = self.client.get('/api/consents/99999')
        self.assertEqual(response.status_code, 404)

    def test_list_consent_grants_by_owner(self):
        req_id1 = self._create_pending_request(self.requester1_id, field_names=[self.field_controlled_name])
        self.client.post(f'/api/consent-requests/{req_id1}/action',
                         data=json.dumps({"owner_id": self.owner_id, "overall_status": "APPROVED", "approved_field_names": [self.field_controlled_name]}),
                         content_type='application/json')

        req_id2 = self._create_pending_request(self.requester2_id, field_names=[self.field_open_name])
        self.client.post(f'/api/consent-requests/{req_id2}/action',
                         data=json.dumps({"owner_id": self.owner_id, "overall_status": "APPROVED", "approved_field_names": [self.field_open_name]}),
                         content_type='application/json')

        response = self.client.get(f'/api/consents?owner_id={self.owner_id}')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 2)
        for grant_data in data:
            self.assertEqual(grant_data['owner_id'], self.owner_id)

    def test_list_consent_grants_by_requester(self):
        req_id1 = self._create_pending_request(self.requester1_id, field_names=[self.field_controlled_name])
        self.client.post(f'/api/consent-requests/{req_id1}/action',
                         data=json.dumps({"owner_id": self.owner_id, "overall_status": "APPROVED", "approved_field_names": [self.field_controlled_name]}),
                         content_type='application/json')
        req_id2 = self._create_pending_request(self.requester2_id, field_names=[self.field_open_name])
        self.client.post(f'/api/consent-requests/{req_id2}/action',
                         data=json.dumps({"owner_id": self.owner_id, "overall_status": "APPROVED", "approved_field_names": [self.field_open_name]}),
                         content_type='application/json')

        response = self.client.get(f'/api/consents?requester_id={self.requester1_id}')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 1)
        # Check a field from the grant to confirm it's the right one, rather than nested details
        self.assertIn(self.field_controlled_name, [cf['field_name'] for cf in data[0]['consented_fields']])
        # And ensure the owner is correct as a sanity check (though filter is on requester)
        self.assertEqual(data[0]['owner_id'], self.owner_id)

    def test_list_consent_grants_by_document(self):
        req_id1 = self._create_pending_request(self.requester1_id, field_names=[self.field_controlled_name])
        self.client.post(f'/api/consent-requests/{req_id1}/action',
                         data=json.dumps({"owner_id": self.owner_id, "overall_status": "APPROVED", "approved_field_names": [self.field_controlled_name]}),
                         content_type='application/json')

        response = self.client.get(f'/api/consents?document_id={self.doc1_id}')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 1)
        # Check basic grant details, not the nested consent_request_details for list view
        self.assertEqual(data[0]['owner_id'], self.owner_id)
        # To verify it's the correct grant, we might need to check consented fields or rely on the count.
        # For now, confirming a grant is returned and it's for the correct owner is a basic check.
        # A more robust check would involve inspecting parts of the linked consent_request_id if it's returned,
        # or ensuring the `ConsentService.list_consent_grants` correctly filters.
        # The service joins on ConsentRequest and filters by document_id, so this should be correct.
        # Let's assume the service filter works and just check a field from the grant itself.
        self.assertIn(self.field_controlled_name, [cf['field_name'] for cf in data[0]['consented_fields']])

    def test_list_consent_grants_by_status_active(self):
        req_id1 = self._create_pending_request(self.requester1_id, field_names=[self.field_controlled_name])
        action_res = self.client.post(f'/api/consent-requests/{req_id1}/action',
                         data=json.dumps({"owner_id": self.owner_id, "overall_status": "APPROVED", "approved_field_names": [self.field_controlled_name]}),
                         content_type='application/json')
        self.assertEqual(action_res.status_code, 200, "Actioning consent request failed")
        consent_grant_data = action_res.get_json().get('consent_grant')
        self.assertIsNotNone(consent_grant_data, "Consent grant was not created after action")
        grant_id = consent_grant_data['id']
        self.assertEqual(consent_grant_data['status'], ConsentStatus.ACTIVE.value, "Created grant is not ACTIVE in API response")

        # Directly verify DB state before calling the list API
        with self.app.app_context():
            grant_in_db = Consent.query.get(grant_id)
            self.assertIsNotNone(grant_in_db, f"Grant {grant_id} not found in DB before listing")
            self.assertEqual(grant_in_db.status, ConsentStatus.ACTIVE, f"Grant {grant_id} in DB is not ACTIVE before listing. Status: {grant_in_db.status}")

            # Test service method directly
            listed_grants_direct = ConsentService.list_consent_grants(status=ConsentStatus.ACTIVE)
            self.assertTrue(any(g.id == grant_id for g in listed_grants_direct),
                            f"Grant {grant_id} not found by direct service call. Found IDs: {[g.id for g in listed_grants_direct]}")


        response = self.client.get(f'/api/consents?status=ACTIVE')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(any(g['id'] == grant_id for g in data), f"Grant {grant_id} not found in API list response: {data}")
        self.assertTrue(all(g['status'] == ConsentStatus.ACTIVE.value for g in data), f"Not all grants in API list response are ACTIVE (expected '{ConsentStatus.ACTIVE.value}'): {data}")

    def test_revoke_consent_grant_success(self):
        req_id = self._create_pending_request(self.requester1_id, field_names=[self.field_controlled_name])
        action_payload = {"owner_id": self.owner_id, "overall_status": "APPROVED", "approved_field_names": [self.field_controlled_name]}
        action_response = self.client.post(f'/api/consent-requests/{req_id}/action', data=json.dumps(action_payload), content_type='application/json')
        grant_id = action_response.get_json()['consent_grant']['id']

        revoke_payload = {"revoking_user_id": self.owner_id}
        response = self.client.post(f'/api/consents/{grant_id}/revoke', data=json.dumps(revoke_payload), content_type='application/json')
        self.assertEqual(response.status_code, 200, msg=response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(data['consent_grant']['status'], ConsentStatus.REVOKED.value)
        self.assertEqual(data['consent_grant']['id'], grant_id)

        with self.app.app_context():
            grant = Consent.query.get(grant_id)
            self.assertEqual(grant.status, ConsentStatus.REVOKED)
            log = AuditLog.query.filter_by(action="CONSENT_REVOKED", target_resource_id=grant_id).first()
            self.assertIsNotNone(log)
            self.assertEqual(log.user_id, self.owner_id)

    def test_revoke_consent_grant_not_owner(self):
        req_id = self._create_pending_request(self.requester1_id, field_names=[self.field_controlled_name])
        action_payload = {"owner_id": self.owner_id, "overall_status": "APPROVED", "approved_field_names": [self.field_controlled_name]}
        action_response = self.client.post(f'/api/consent-requests/{req_id}/action', data=json.dumps(action_payload), content_type='application/json')
        grant_id = action_response.get_json()['consent_grant']['id']

        revoke_payload = {"revoking_user_id": self.requester1_id}
        response = self.client.post(f'/api/consents/{grant_id}/revoke', data=json.dumps(revoke_payload), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertIn("does not have permission", response.get_json()['error'])

    def test_revoke_consent_grant_not_active(self):
        req_id = self._create_pending_request(self.requester1_id, field_names=[self.field_controlled_name])
        action_payload = {"owner_id": self.owner_id, "overall_status": "APPROVED", "approved_field_names": [self.field_controlled_name]}
        action_response = self.client.post(f'/api/consent-requests/{req_id}/action', data=json.dumps(action_payload), content_type='application/json')
        grant_id = action_response.get_json()['consent_grant']['id']

        self.client.post(f'/api/consents/{grant_id}/revoke', data=json.dumps({"revoking_user_id": self.owner_id}), content_type='application/json')

        response = self.client.post(f'/api/consents/{grant_id}/revoke', data=json.dumps({"revoking_user_id": self.owner_id}), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertIn("not currently active", response.get_json()['error'])

if __name__ == '__main__':
    unittest.main()
