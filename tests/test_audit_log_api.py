import unittest
import json
from app import create_app, db
from app.models import User, AuditLog
from app.services.audit_service import AuditService

class AuditLogAPITestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            # Create some users for context
            self.user1 = User(username='audituser1', email='audit1@example.com', role='owner')
            self.user2 = User(username='audituser2', email='audit2@example.com', role='requester')
            db.session.add_all([self.user1, self.user2])
            db.session.commit()
            self.user1_id = self.user1.id
            self.user2_id = self.user2.id

            # Create some sample audit logs
            AuditService.log_action("USER_LOGIN", user_id=self.user1_id, details={"ip": "127.0.0.1"})
            AuditService.log_action("DOCUMENT_UPLOAD", user_id=self.user1_id, target_resource_type="Document", target_resource_id=101)
            AuditService.log_action("FIELD_ACCESS_DENIED", user_id=self.user2_id, target_resource_type="Document", target_resource_id=101, details={"field": "Salary"})
            AuditService.log_action("CONSENT_GRANTED", user_id=self.user1_id, target_resource_type="ConsentRequest", target_resource_id=201)
            # db.session.commit() is called by AuditService.log_action

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_list_audit_logs_no_filter(self):
        response = self.client.get('/api/audit-logs')
        self.assertEqual(response.status_code, 200, msg=response.get_data(as_text=True))
        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 4) # All logs created in setUp

    def test_list_audit_logs_filter_by_user_id(self):
        response = self.client.get(f'/api/audit-logs?user_id={self.user1_id}')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 3) # USER_LOGIN, DOCUMENT_UPLOAD, CONSENT_GRANTED
        for log in data:
            self.assertEqual(log['user_id'], self.user1_id)

    def test_list_audit_logs_filter_by_action(self):
        response = self.client.get('/api/audit-logs?action=USER_LOGIN')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['action'], "USER_LOGIN")

        # Partial match
        response_partial = self.client.get('/api/audit-logs?action=ACCESS')
        self.assertEqual(response_partial.status_code, 200)
        data_partial = response_partial.get_json()
        self.assertEqual(len(data_partial), 1)
        self.assertEqual(data_partial[0]['action'], "FIELD_ACCESS_DENIED")


    def test_list_audit_logs_filter_by_target_resource_type(self):
        response = self.client.get('/api/audit-logs?target_resource_type=Document')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 2) # DOCUMENT_UPLOAD, FIELD_ACCESS_DENIED
        for log in data:
            self.assertEqual(log['target_resource_type'], "Document")

    def test_list_audit_logs_filter_by_target_resource_id(self):
        response = self.client.get('/api/audit-logs?target_resource_id=101')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 2) # DOCUMENT_UPLOAD, FIELD_ACCESS_DENIED on Doc 101
        for log in data:
            self.assertEqual(log['target_resource_id'], 101)

    def test_list_audit_logs_combined_filters(self):
        response = self.client.get(f'/api/audit-logs?user_id={self.user1_id}&target_resource_type=Document')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['action'], "DOCUMENT_UPLOAD")
        self.assertEqual(data[0]['user_id'], self.user1_id)
        self.assertEqual(data[0]['target_resource_type'], "Document")
        self.assertEqual(data[0]['target_resource_id'], 101)

    def test_list_audit_logs_empty_result(self):
        response = self.client.get('/api/audit-logs?action=NON_EXISTENT_ACTION')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 0)

if __name__ == '__main__':
    unittest.main()
