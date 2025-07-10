from app import db
from app.models import AuditLog, User # User for context if needed

class AuditService:
    @staticmethod
    def log_action(action: str, user_id: int = None, details: dict = None,
                   target_resource_type: str = None, target_resource_id: int = None):
        """
        Logs an action to the audit trail.

        Args:
            action: A string describing the action (e.g., "DOCUMENT_ACCESS_ATTEMPT").
            user_id: ID of the user performing the action (optional).
            details: A dictionary containing any relevant context for the action.
            target_resource_type: Type of the main resource targeted (e.g., "Document", "Consent").
            target_resource_id: ID of the main resource targeted.
        """
        try:
            log_entry = AuditLog(
                user_id=user_id,
                action=action,
                details=details,
                target_resource_type=target_resource_type,
                target_resource_id=target_resource_id
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            # Log this failure to a more critical logging system (e.g., stderr, file logger)
            # For now, just print, but avoid crashing the calling operation.
            print(f"Failed to write audit log: {e}")
            db.session.rollback()

    @staticmethod
    def get_logs_for_resource(resource_type: str, resource_id: int):
        return AuditLog.query.filter_by(target_resource_type=resource_type, target_resource_id=resource_id).order_by(AuditLog.timestamp.desc()).all()

    @staticmethod
    def get_logs_by_user(user_id: int):
        return AuditLog.query.filter_by(user_id=user_id).order_by(AuditLog.timestamp.desc()).all()
