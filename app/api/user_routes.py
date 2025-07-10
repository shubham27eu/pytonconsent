from flask import request, jsonify
from . import bp # The API blueprint
from app.services.user_service import UserService
from app.models import User # For type hinting and serialization structure

def serialize_user(user: User):
    """Serializes a User object to a dictionary."""
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }

@bp.route('/users', methods=['POST'])
def create_user_route():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    username = data.get('username')
    email = data.get('email')
    role = data.get('role')

    user, error = UserService.create_user(username=username, email=email, role=role)

    if error:
        if "already exists" in error:
            return jsonify({"error": error}), 409 # Conflict
        return jsonify({"error": error}), 400 # Bad request (e.g. validation error)

    return jsonify(serialize_user(user)), 201

@bp.route('/users/<int:user_id>', methods=['GET'])
def get_user_route(user_id):
    user = UserService.get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(serialize_user(user)), 200

@bp.route('/users', methods=['GET'])
def list_users_route():
    # Add filtering query parameters if needed, e.g. /users?username=someuser
    username_filter = request.args.get('username')
    if username_filter:
        user = UserService.get_user_by_username(username_filter)
        users_list = [user] if user else []
    else:
        users_list = UserService.get_all_users()

    return jsonify([serialize_user(u) for u in users_list]), 200
