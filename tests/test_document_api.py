import unittest
import json
import os
from app import create_app, db
from app.models import User, DocumentType, Document, DocumentField, FieldClassification
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

class DocumentAPITestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            self.owner_user = User(username='docowner', email='docowner@example.com', role='owner')
            db.session.add(self.owner_user)
            db.session.commit()
            self.owner_id = self.owner_user.id

            self.doc_type = DocumentType(name="ProFormaInvoice", description="Standard Invoice", owner_id=self.owner_id)
            self.doc_type.fields.append(DocumentField(name="Due date", classification=FieldClassification.CONTROLLED))
            self.doc_type.fields.append(DocumentField(name="TOTAL (GBP)", classification=FieldClassification.CONTROLLED))
            db.session.add(self.doc_type)
            db.session.commit()
            self.doc_type_id = self.doc_type.id

            self.sample_pdf_path = os.path.join(os.path.dirname(__file__), 'samples', 'ingestion_test.pdf')
            os.makedirs(os.path.dirname(self.sample_pdf_path), exist_ok=True)
            c = canvas.Canvas(self.sample_pdf_path, pagesize=letter)
            c.drawString(50, 750, "Due date: 14/05/2022")
            c.drawString(50, 735, "TOTAL (GBP): £600.00")
            c.save()

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

    def test_ingest_document_success_with_extraction(self):
        payload = {
            "name": "Test Invoice Ingestion",
            "document_type_id": self.doc_type_id,
            "owner_id": self.owner_id,
            "file_path": self.sample_pdf_path,
            "additional_metadata": {"user_comment": "This is a test invoice."}
        }
        response = self.client.post('/api/documents', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 201, msg=response.get_data(as_text=True))
        data = response.get_json()

        self.assertEqual(data['name'], "Test Invoice Ingestion")
        self.assertEqual(data['file_path'], self.sample_pdf_path)
        metadata = data['additional_metadata']
        self.assertEqual(metadata.get("user_comment"), "This is a test invoice.")
        self.assertEqual(metadata.get("Due date"), "14/05/2022")
        self.assertEqual(metadata.get("TOTAL (GBP)"), "£600.00")

        with self.app.app_context():
            doc = Document.query.filter_by(name="Test Invoice Ingestion").first()
            self.assertIsNotNone(doc)
            self.assertEqual(doc.additional_metadata['Due date'], "14/05/2022")

    def test_ingest_document_missing_required_fields(self):
        payload = {"name": "Another Invoice", "owner_id": self.owner_id, "file_path": self.sample_pdf_path}
        response = self.client.post('/api/documents', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing required fields", response.get_json()['error'])

    def test_ingest_document_owner_not_found(self):
        payload = {"name": "Test Doc", "document_type_id": self.doc_type_id, "owner_id": 999, "file_path": self.sample_pdf_path}
        response = self.client.post('/api/documents', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Owner not found", response.get_json()['error'])

    def test_ingest_document_type_not_found(self):
        payload = {"name": "Test Doc", "document_type_id": 999, "owner_id": self.owner_id, "file_path": self.sample_pdf_path}
        response = self.client.post('/api/documents', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("DocumentType with ID 999 not found", response.get_json()['error'])

    def test_ingest_document_file_not_found(self):
        payload = {"name": "Test Doc", "document_type_id": self.doc_type_id, "owner_id": self.owner_id, "file_path": "/bad/path/invoice.pdf"}
        response = self.client.post('/api/documents', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("File not found at path", response.get_json()['error'])

    def test_get_document_success(self):
        ingest_payload = {"name": "Gettable Doc", "document_type_id": self.doc_type_id, "owner_id": self.owner_id, "file_path": self.sample_pdf_path}
        post_response = self.client.post('/api/documents', data=json.dumps(ingest_payload), content_type='application/json')
        self.assertEqual(post_response.status_code, 201)
        doc_id = post_response.get_json()['id']

        get_response = self.client.get(f'/api/documents/{doc_id}')
        self.assertEqual(get_response.status_code, 200)
        data = get_response.get_json()
        self.assertEqual(data['name'], "Gettable Doc")
        self.assertIn("document_type", data)
        self.assertEqual(data["document_type"]["name"], "ProFormaInvoice")
        self.assertEqual(data["additional_metadata"]["Due date"], "14/05/2022")

    def test_get_nonexistent_document(self):
        response = self.client.get('/api/documents/9999')
        self.assertEqual(response.status_code, 404)

    def test_list_documents(self):
        p1 = {"name": "Doc1", "document_type_id": self.doc_type_id, "owner_id": self.owner_id, "file_path": self.sample_pdf_path}
        p2 = {"name": "Doc2", "document_type_id": self.doc_type_id, "owner_id": self.owner_id, "file_path": self.sample_pdf_path}
        self.client.post('/api/documents', data=json.dumps(p1), content_type='application/json')
        self.client.post('/api/documents', data=json.dumps(p2), content_type='application/json')

        response = self.client.get('/api/documents')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)
        names = {item['name'] for item in data}
        self.assertIn("Doc1", names)
        self.assertIn("Doc2", names)

if __name__ == '__main__':
    unittest.main()
