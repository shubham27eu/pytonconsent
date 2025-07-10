import unittest
import json
from app import create_app, db
from app.models import User, DocumentType, Document, DocumentField, FieldClassification

class DocumentAPITestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            # Create a dummy owner user
            self.owner_user = User(username='docowner', email='docowner@example.com', role='owner')
            db.session.add(self.owner_user)
            db.session.commit()
            self.owner_id = self.owner_user.id

            # Create a dummy document type
            self.doc_type = DocumentType(name="Invoice", description="Standard Invoice", owner_id=self.owner_id)
            # Add fields to the document type (not strictly necessary for ingest test but good for completeness)
            self.doc_type.fields.append(DocumentField(name="InvoiceNumber", classification=FieldClassification.OPEN))
            self.doc_type.fields.append(DocumentField(name="TotalAmount", classification=FieldClassification.CONTROLLED))
            db.session.add(self.doc_type)
            db.session.commit()
            self.doc_type_id = self.doc_type.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_ingest_document_success(self):
        payload = {
            "name": "Invoice #123",
            "document_type_id": self.doc_type_id,
            "owner_id": self.owner_id,
            "file_path": "/path/to/invoice_123.pdf",
            "additional_metadata": {"client_id": "CUST001", "year": 2023}
        }
        response = self.client.post('/api/documents',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201, msg=response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(data['name'], "Invoice #123")
        self.assertEqual(data['document_type_id'], self.doc_type_id)
        self.assertEqual(data['owner_id'], self.owner_id)
        self.assertEqual(data['file_path'], "/path/to/invoice_123.pdf")
        self.assertEqual(data['additional_metadata']['client_id'], "CUST001")

        # Verify database content
        with self.app.app_context():
            doc = Document.query.filter_by(name="Invoice #123").first()
            self.assertIsNotNone(doc)
            self.assertEqual(doc.additional_metadata['year'], 2023)

    def test_ingest_document_missing_required_fields(self):
        payload = {
            "name": "Another Invoice",
            # document_type_id is missing
            "owner_id": self.owner_id,
            "file_path": "/path/to/another_invoice.pdf"
        }
        response = self.client.post('/api/documents',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("Missing required fields", data['error'])

    def test_ingest_document_owner_not_found(self):
        payload = {
            "name": "Test Doc",
            "document_type_id": self.doc_type_id,
            "owner_id": 999, # Non-existent owner
            "file_path": "/path/to/doc.pdf"
        }
        response = self.client.post('/api/documents',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400) # Service returns generic error for now
        data = response.get_json()
        self.assertIn("Owner not found", data['error'])

    def test_ingest_document_type_not_found(self):
        payload = {
            "name": "Test Doc",
            "document_type_id": 999, # Non-existent document type
            "owner_id": self.owner_id,
            "file_path": "/path/to/doc.pdf"
        }
        response = self.client.post('/api/documents',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400) # Service returns generic error
        data = response.get_json()
        self.assertIn("DocumentType with ID 999 not found", data['error'])

    def test_ingest_document_empty_filepath(self):
        payload = {
            "name": "Test Doc Empty Path",
            "document_type_id": self.doc_type_id,
            "owner_id": self.owner_id,
            "file_path": "" # Empty file path
        }
        response = self.client.post('/api/documents',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400, msg=response.get_data(as_text=True))
        data = response.get_json()
        # The current API validation `if not all(...)` treats an empty string file_path as a missing field.
        self.assertIn("Missing required fields", data['error'])

    def test_get_document_success(self):
        # First, ingest a document
        ingest_payload = {
            "name": "Gettable Doc", "document_type_id": self.doc_type_id,
            "owner_id": self.owner_id, "file_path": "/path/to/gettable.doc"
        }
        post_response = self.client.post('/api/documents', data=json.dumps(ingest_payload), content_type='application/json')
        self.assertEqual(post_response.status_code, 201)
        doc_id = post_response.get_json()['id']

        # Now, fetch it
        get_response = self.client.get(f'/api/documents/{doc_id}')
        self.assertEqual(get_response.status_code, 200)
        data = get_response.get_json()
        self.assertEqual(data['name'], "Gettable Doc")
        self.assertIn("document_type", data) # Check if doc type is embedded
        self.assertEqual(data["document_type"]["name"], "Invoice")


    def test_get_nonexistent_document(self):
        response = self.client.get('/api/documents/9999')
        self.assertEqual(response.status_code, 404)

    def test_list_documents(self):
        # Ingest a couple of documents
        p1 = {"name": "Doc1", "dt_id": self.doc_type_id, "o_id": self.owner_id, "fp": "/p/1"}
        p2 = {"name": "Doc2", "dt_id": self.doc_type_id, "o_id": self.owner_id, "fp": "/p/2"}
        self.client.post('/api/documents', data=json.dumps({"name":p1["name"], "document_type_id":p1["dt_id"], "owner_id":p1["o_id"], "file_path":p1["fp"]}), content_type='application/json')
        self.client.post('/api/documents', data=json.dumps({"name":p2["name"], "document_type_id":p2["dt_id"], "owner_id":p2["o_id"], "file_path":p2["fp"]}), content_type='application/json')

        response = self.client.get('/api/documents')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)
        # Check if at least 2 documents are present (could be more if other tests didn't clean up perfectly, but setUp/tearDown should handle this)
        self.assertGreaterEqual(len(data), 2)
        names = {item['name'] for item in data}
        self.assertIn("Doc1", names)
        self.assertIn("Doc2", names)

    def test_list_documents_by_owner(self):
        # Create another owner and their document
        with self.app.app_context():
            other_owner = User(username='otherowner', email='other@example.com', role='owner')
            db.session.add(other_owner)
            db.session.commit()
            other_owner_id = other_owner.id

        p1 = {"name": "Doc1_Owner1", "dt_id": self.doc_type_id, "o_id": self.owner_id, "fp": "/p/o1_1"}
        p2 = {"name": "Doc2_Owner2", "dt_id": self.doc_type_id, "o_id": other_owner_id, "fp": "/p/o2_1"}
        self.client.post('/api/documents', data=json.dumps({"name":p1["name"], "document_type_id":p1["dt_id"], "owner_id":p1["o_id"], "file_path":p1["fp"]}), content_type='application/json')
        self.client.post('/api/documents', data=json.dumps({"name":p2["name"], "document_type_id":p2["dt_id"], "owner_id":p2["o_id"], "file_path":p2["fp"]}), content_type='application/json')

        # List documents for self.owner_id
        response = self.client.get(f'/api/documents?owner_id={self.owner_id}')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], "Doc1_Owner1")
        self.assertEqual(data[0]['owner_id'], self.owner_id)


if __name__ == '__main__':
    unittest.main()
