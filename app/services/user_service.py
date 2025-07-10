from app import db
from app.models import User

class UserService:
    @staticmethod
    def create_user(username: str, email: str, role: str):
        """
        Creates a new user.

        Args:
            username: The user's username.
            email: The user's email address.
            role: The user's role ('owner' or 'requester').

        Returns:
            Tuple: (User | None, error_message | None)
        """
        if not username or not email or not role:
            return None, "Username, email, and role are required."

        if User.query.filter_by(username=username).first():
            return None, f"Username '{username}' already exists."

        if User.query.filter_by(email=email).first():
            return None, f"Email '{email}' already exists."

        valid_roles = ['owner', 'requester']
        if role not in valid_roles:
            return None, f"Invalid role '{role}'. Must be one of {valid_roles}."

        user = User(username=username, email=email, role=role)

        try:
            db.session.add(user)
            db.session.commit()
            return user, None
        except Exception as e:
            db.session.rollback()
            # Log error e
            return None, f"Database error: {str(e)}"

    @staticmethod
    def get_user_by_id(user_id: int):
        return User.query.get(user_id)

    @staticmethod
    def get_user_by_username(username: str):
        return User.query.filter_by(username=username).first()

    @staticmethod
    def get_all_users():
        return User.query.all()
