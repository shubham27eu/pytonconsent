from flask import request, jsonify
from . import bp  # The API blueprint
from app.services.audit_service import AuditService
from app.models import AuditLog
from .user_routes import serialize_user # For embedding user info if needed

def serialize_audit_log(log: AuditLog):
    """Serializes an AuditLog object to a dictionary."""
    if not log:
        return None
    serialized = {
        "id": log.id,
        "user_id": log.user_id,
        "action": log.action,
        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        "details": log.details if log.details else {},
        "target_resource_type": log.target_resource_type,
        "target_resource_id": log.target_resource_id
    }
    # Optionally serialize user details if user is present
    if log.user:
        serialized["user"] = serialize_user(log.user) # Assumes user relationship is loaded or handled
    return serialized

@bp.route('/audit-logs', methods=['GET'])
def list_audit_logs_route():
    # Supported filters
    user_id = request.args.get('user_id', type=int)
    action = request.args.get('action', type=str)
    target_resource_type = request.args.get('target_resource_type', type=str)
    target_resource_id = request.args.get('target_resource_id', type=int)

    # Start with a base query
    query = AuditLog.query

    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if action is not None:
        query = query.filter(AuditLog.action.ilike(f"%{action}%")) # Case-insensitive partial match
    if target_resource_type is not None:
        query = query.filter(AuditLog.target_resource_type == target_resource_type)
    if target_resource_id is not None:
        query = query.filter(AuditLog.target_resource_id == target_resource_id)

    # Order by most recent first
    logs = query.order_by(AuditLog.timestamp.desc()).all()

    # For more complex filtering or if AuditService had more advanced methods,
    # those would be called here. For now, direct model querying is fine for these filters.

    return jsonify([serialize_audit_log(log) for log in logs]), 200
