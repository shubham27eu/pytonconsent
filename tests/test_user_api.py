import unittest
import json
from app import create_app, db
from app.models import User

class UserAPITestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:' # Ensure in-memory for tests
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_create_user_success(self):
        payload = {
            "username": "newuser",
            "email": "newuser@example.com",
            "role": "requester"
        }
        response = self.client.post('/api/users',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201, msg=response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(data['username'], "newuser")
        self.assertEqual(data['email'], "newuser@example.com")
        self.assertEqual(data['role'], "requester")
        self.assertIn("id", data)
        self.assertIn("created_at", data)

        # Verify database content
        with self.app.app_context():
            user = User.query.filter_by(username="newuser").first()
            self.assertIsNotNone(user)
            self.assertEqual(user.email, "newuser@example.com")

    def test_create_user_duplicate_username(self):
        # Create initial user
        payload1 = {"username": "testuser", "email": "user1@example.com", "role": "owner"}
        self.client.post('/api/users', data=json.dumps(payload1), content_type='application/json')

        # Attempt to create user with same username
        payload2 = {"username": "testuser", "email": "user2@example.com", "role": "requester"}
        response = self.client.post('/api/users', data=json.dumps(payload2), content_type='application/json')
        self.assertEqual(response.status_code, 409) # Conflict
        data = response.get_json()
        self.assertIn("Username 'testuser' already exists", data['error'])

    def test_create_user_duplicate_email(self):
        payload1 = {"username": "userA", "email": "test@example.com", "role": "owner"}
        self.client.post('/api/users', data=json.dumps(payload1), content_type='application/json')

        payload2 = {"username": "userB", "email": "test@example.com", "role": "requester"}
        response = self.client.post('/api/users', data=json.dumps(payload2), content_type='application/json')
        self.assertEqual(response.status_code, 409) # Conflict
        data = response.get_json()
        self.assertIn("Email 'test@example.com' already exists", data['error'])

    def test_create_user_missing_fields(self):
        payload = {"username": "incomplete"} # Missing email and role
        response = self.client.post('/api/users', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("Username, email, and role are required", data['error'])

    def test_create_user_invalid_role(self):
        payload = {"username": "roleuser", "email": "role@example.com", "role": "admin"} # Invalid role
        response = self.client.post('/api/users', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("Invalid role 'admin'", data['error'])

    def test_get_user_by_id(self):
        # Create a user first
        user_payload = {"username": "getme", "email": "getme@example.com", "role": "owner"}
        post_response = self.client.post('/api/users', data=json.dumps(user_payload), content_type='application/json')
        self.assertEqual(post_response.status_code, 201)
        user_id = post_response.get_json()['id']

        # Fetch the user
        get_response = self.client.get(f'/api/users/{user_id}')
        self.assertEqual(get_response.status_code, 200)
        data = get_response.get_json()
        self.assertEqual(data['id'], user_id)
        self.assertEqual(data['username'], "getme")

    def test_get_nonexistent_user(self):
        response = self.client.get('/api/users/9999') # Assuming 9999 does not exist
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertIn("User not found", data['error'])

    def test_list_users(self):
        # Create a couple of users
        self.client.post('/api/users', data=json.dumps({"username":"u1", "email":"e1@example.com", "role":"owner"}), content_type='application/json')
        self.client.post('/api/users', data=json.dumps({"username":"u2", "email":"e2@example.com", "role":"requester"}), content_type='application/json')

        response = self.client.get('/api/users')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)
        usernames = {item['username'] for item in data}
        self.assertIn("u1", usernames)
        self.assertIn("u2", usernames)

    def test_list_users_filter_by_username(self):
        self.client.post('/api/users', data=json.dumps({"username":"filteruser", "email":"filter@example.com", "role":"owner"}), content_type='application/json')
        self.client.post('/api/users', data=json.dumps({"username":"anotheruser", "email":"another@example.com", "role":"requester"}), content_type='application/json')

        response = self.client.get('/api/users?username=filteruser')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['username'], "filteruser")

    def test_list_users_filter_by_nonexistent_username(self):
        response = self.client.get('/api/users?username=nosuchuser')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 0)


if __name__ == '__main__':
    unittest.main()
