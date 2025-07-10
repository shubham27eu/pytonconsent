import unittest
import json
from app import create_app, db
from app.models import User, DocumentType, DocumentField, FieldClassification

class DocumentTypeAPITestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app() # Uses default Config which should point to a test DB or in-memory
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:' # Ensure in-memory for tests
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            # Create a dummy owner user
            self.owner_user = User(username='testowner', email='owner@example.com', role='owner')
            db.session.add(self.owner_user)
            db.session.commit()
            self.owner_id = self.owner_user.id


    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_create_document_type_success(self):
        payload = {
            "name": "Test Payslip",
            "description": "A standard payslip document.",
            "owner_id": self.owner_id,
            "fields": [
                {"name": "Employee Name", "classification": "open"},
                {"name": "Salary Amount", "classification": "controlled"},
                {"name": "Tax ID", "classification": "closed"}
            ]
        }
        response = self.client.post('/api/document-types',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data['name'], "Test Payslip")
        self.assertEqual(data['owner_id'], self.owner_id)
        self.assertEqual(len(data['fields']), 3)

        # Verify fields classifications
        field_names_classifications = {f['name']: f['classification'] for f in data['fields']}
        self.assertEqual(field_names_classifications['Employee Name'], FieldClassification.OPEN.value)
        self.assertEqual(field_names_classifications['Salary Amount'], FieldClassification.CONTROLLED.value)
        self.assertEqual(field_names_classifications['Tax ID'], FieldClassification.CLOSED.value)

        # Verify database content
        with self.app.app_context():
            doc_type = DocumentType.query.filter_by(name="Test Payslip").first()
            self.assertIsNotNone(doc_type)
            self.assertEqual(doc_type.description, "A standard payslip document.")
            self.assertEqual(len(doc_type.fields), 3)
            db_field_names_classifications = {f.name: f.classification for f in doc_type.fields}
            self.assertEqual(db_field_names_classifications['Employee Name'], FieldClassification.OPEN)


    def test_create_document_type_missing_fields(self):
        payload = {
            "name": "Test Invoice",
            # owner_id is missing
            "fields": [{"name": "Invoice Number", "classification": "open"}]
        }
        response = self.client.post('/api/document-types',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("Missing required fields", data['error'])

    def test_create_document_type_invalid_classification(self):
        payload = {
            "name": "Test Report",
            "description": "A test report.",
            "owner_id": self.owner_id,
            "fields": [
                {"name": "Report Title", "classification": "opennn"} # Invalid classification
            ]
        }
        response = self.client.post('/api/document-types',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("Invalid classification", data['error'])

    def test_create_document_type_duplicate_name(self):
        payload = {
            "name": "Unique Payslip",
            "description": "A unique payslip.",
            "owner_id": self.owner_id,
            "fields": [{"name": "Field1", "classification": "open"}]
        }
        # Create first one
        response1 = self.client.post('/api/document-types', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response1.status_code, 201)

        # Attempt to create second one with same name
        response2 = self.client.post('/api/document-types', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response2.status_code, 400)
        data = response2.get_json()
        self.assertIn("already exists", data['error'])

    def test_create_document_type_owner_not_found(self):
        payload = {
            "name": "Test Payslip NonOwner",
            "description": "A standard payslip document.",
            "owner_id": 999, # Non-existent owner
            "fields": [{"name": "Employee Name", "classification": "open"}]
        }
        response = self.client.post('/api/document-types',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("Owner not found", data['error'])

    def test_create_document_type_user_not_owner_role(self):
        with self.app.app_context():
            requester_user = User(username='testrequester', email='req@example.com', role='requester')
            db.session.add(requester_user)
            db.session.commit()
            requester_id = requester_user.id

        payload = {
            "name": "Test Payslip ReqOwner",
            "description": "A standard payslip document.",
            "owner_id": requester_id, # User exists but is not an 'owner'
            "fields": [{"name": "Employee Name", "classification": "open"}]
        }
        response = self.client.post('/api/document-types',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("User does not have 'owner' role", data['error'])

    def test_get_document_type(self):
        # First, create a document type
        payload = {
            "name": "Fetchable DT",
            "description": "Details here.",
            "owner_id": self.owner_id,
            "fields": [{"name": "F1", "classification": "open"}]
        }
        post_response = self.client.post('/api/document-types', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(post_response.status_code, 201)
        dt_id = post_response.get_json()['id']

        # Now, fetch it
        get_response = self.client.get(f'/api/document-types/{dt_id}')
        self.assertEqual(get_response.status_code, 200)
        data = get_response.get_json()
        self.assertEqual(data['name'], "Fetchable DT")
        self.assertEqual(len(data['fields']), 1)

    def test_get_nonexistent_document_type(self):
        response = self.client.get('/api/document-types/9999')
        self.assertEqual(response.status_code, 404)

    def test_list_document_types(self):
        # Create a couple of document types
        payload1 = {"name": "DT1", "owner_id": self.owner_id, "fields": [{"name":"F1","classification":"open"}]}
        payload2 = {"name": "DT2", "owner_id": self.owner_id, "fields": [{"name":"F2","classification":"closed"}]}
        self.client.post('/api/document-types', data=json.dumps(payload1), content_type='application/json')
        self.client.post('/api/document-types', data=json.dumps(payload2), content_type='application/json')

        response = self.client.get('/api/document-types')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2) # Assumes a clean DB for each test method
        names = {item['name'] for item in data}
        self.assertIn("DT1", names)
        self.assertIn("DT2", names)


if __name__ == '__main__':
    unittest.main()
