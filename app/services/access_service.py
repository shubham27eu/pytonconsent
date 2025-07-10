from app import db
from app.models import User, Document, DocumentType, DocumentField, FieldClassification, Consent, ConsentRequest, ConsentStatus, ConsentedField # Added DocumentType, ConsentRequest
from app.services.audit_service import AuditService # For logging access attempts
from datetime import datetime

class AccessService:
    @staticmethod
    def can_access_fields(requester_id: int, document_id: int, field_names: list[str]):
        """
        Checks if a requester can access specified fields of a document and returns placeholder data if allowed.
        This method also records the access attempt and decrements counters if applicable.

        Args:
            requester_id: ID of the user requesting access.
            document_id: ID of the document being accessed.
            field_names: A list of field names the user wants to access.

        Returns:
            Tuple: (dict_of_field_data | None, error_message | None)
                   dict_of_field_data will be like: {"field_name": "value_placeholder_for_field_name"}
        """
        requester = User.query.get(requester_id)
        if not requester:
            AuditService.log_action("FIELD_ACCESS_DENIED", user_id=requester_id, details={"reason": "Requester not found", "document_id": document_id, "fields": field_names}, target_resource_type="Document", target_resource_id=document_id)
            return None, "Requester not found."

        document = Document.query.options(
            db.joinedload(Document.document_type).joinedload(DocumentType.fields) # Eager load for field checks
        ).get(document_id)

        if not document:
            AuditService.log_action("FIELD_ACCESS_DENIED", user_id=requester_id, details={"reason": "Document not found", "document_id": document_id, "fields": field_names}, target_resource_type="Document", target_resource_id=document_id)
            return None, "Document not found."

        if not field_names:
            return None, "No fields specified for access."

        # Document owner implicitly has access to all their own fields (unless specific deny policy)
        if document.owner_id == requester_id:
            accessed_data = {}
            valid_field_names = {f.name for f in document.document_type.fields}
            for field_name in set(field_names): # Use set to avoid duplicates
                if field_name not in valid_field_names:
                     AuditService.log_action("FIELD_ACCESS_DENIED", user_id=requester_id, details={"reason": f"Field '{field_name}' not found in document type", "document_id": document_id, "field": field_name}, target_resource_type="Document", target_resource_id=document_id)
                     return None, f"Field '{field_name}' not found in document type '{document.document_type.name}'."
                accessed_data[field_name] = f"value_placeholder_for_{field_name}" # Placeholder
            AuditService.log_action("FIELD_ACCESS_GRANTED_OWNER", user_id=requester_id, details={"document_id": document_id, "fields": list(accessed_data.keys())}, target_resource_type="Document", target_resource_id=document_id)
            return accessed_data, None

        # --- Regular access check for non-owners ---
        accessed_data = {}
        doc_type_fields_map = {field.name: field for field in document.document_type.fields}

        # Find an active consent grant for this requester and document
        # This query could be more complex if multiple grants could exist (e.g. pick the one with broadest permissions or latest)
        # For now, assume at most one active relevant grant.
        active_consent_grant = Consent.query.filter_by(
            owner_id=document.owner_id, # Consent is from the document owner
            status=ConsentStatus.ACTIVE
        ).join(Consent.consent_request).filter(
            ConsentRequest.requester_id == requester_id,
            ConsentRequest.document_id == document_id
        ).options(db.joinedload(Consent.consented_fields)).first() # Ensure consented_fields are loaded

        for field_name in set(field_names): # Use set to avoid duplicates
            doc_field = doc_type_fields_map.get(field_name)
            if not doc_field:
                AuditService.log_action("FIELD_ACCESS_DENIED", user_id=requester_id, details={"reason": f"Field '{field_name}' not found in document type", "document_id": document_id, "field": field_name}, target_resource_type="Document", target_resource_id=document_id)
                return None, f"Field '{field_name}' not found in document type '{document.document_type.name}'."

            if doc_field.classification == FieldClassification.OPEN:
                accessed_data[field_name] = f"value_placeholder_for_{field_name}"
                # Audit log for open field access can be less verbose or conditional
                AuditService.log_action("FIELD_ACCESS_GRANTED_OPEN", user_id=requester_id, details={"document_id": document_id, "field": field_name}, target_resource_type="Document", target_resource_id=document_id)
                continue

            if doc_field.classification == FieldClassification.CLOSED:
                AuditService.log_action("FIELD_ACCESS_DENIED_CLOSED", user_id=requester_id, details={"document_id": document_id, "field": field_name}, target_resource_type="Document", target_resource_id=document_id)
                return None, f"Access denied: Field '{field_name}' is classified as closed."

            # Field is CONTROLLED, requires consent grant
            if not active_consent_grant:
                AuditService.log_action("FIELD_ACCESS_DENIED_NO_GRANT", user_id=requester_id, details={"document_id": document_id, "field": field_name}, target_resource_type="Document", target_resource_id=document_id)
                return None, f"Access denied: No active consent grant found for controlled field '{field_name}'."

            # Check if this specific field is in the grant
            consented_field_names_in_grant = {cf.field_name for cf in active_consent_grant.consented_fields}
            if field_name not in consented_field_names_in_grant:
                AuditService.log_action("FIELD_ACCESS_DENIED_NOT_IN_GRANT", user_id=requester_id, details={"document_id": document_id, "field": field_name, "grant_id": active_consent_grant.id}, target_resource_type="Document", target_resource_id=document_id)
                return None, f"Access denied: Field '{field_name}' is not part of your active consent grant."

            # Perform pre-access checks (expiry, count) for the grant as a whole
            # This check might be done once per access request rather than per field if all fields share same grant conditions
            is_valid, reason = active_consent_grant.pre_access_check()
            if not is_valid:
                db.session.commit() # Commit status changes from pre_access_check (e.g. EXPIRED)
                AuditService.log_action("FIELD_ACCESS_DENIED_GRANT_INVALID", user_id=requester_id, details={"reason": reason, "document_id": document_id, "field": field_name, "grant_id": active_consent_grant.id}, target_resource_type="Document", target_resource_id=document_id)
                return None, f"Access denied for '{field_name}': {reason}."

            accessed_data[field_name] = f"value_placeholder_for_{field_name}"
            # Fall through to record access for the grant after checking all requested fields from this grant

        # If we reached here for any controlled fields, the grant is valid for them.
        # Record access attempt against the grant (e.g. decrement count)
        # This should ideally be done ONCE if multiple fields from the same grant are accessed.
        if active_consent_grant and any(doc_type_fields_map.get(fn).classification == FieldClassification.CONTROLLED for fn in accessed_data.keys() if fn in consented_field_names_in_grant):
            active_consent_grant.record_access()
            db.session.add(active_consent_grant) # Add to session to save changes like count decrement
            try:
                db.session.commit() # Commit access recording
                AuditService.log_action("FIELD_ACCESS_GRANTED_CONTROLLED", user_id=requester_id, details={"document_id": document_id, "fields": list(accessed_data.keys()), "grant_id": active_consent_grant.id}, target_resource_type="Document", target_resource_id=document_id)
            except Exception as e:
                db.session.rollback()
                # Log this failure critically
                print(f"Failed to commit access recording for grant {active_consent_grant.id}: {e}")
                # Decide if access should still be denied if audit fails. For now, proceed with data if check passed.
                # For higher security, might return error here.
                AuditService.log_action("FIELD_ACCESS_ERROR_COMMIT_GRANT_UPDATE", user_id=requester_id, details={"error": str(e), "document_id": document_id, "fields": list(accessed_data.keys()), "grant_id": active_consent_grant.id}, target_resource_type="Document", target_resource_id=document_id)


        if not accessed_data and field_names: # No fields were accessible out of those requested
             # This can happen if all requested fields were invalid, or permissions denied for all.
             # Specific error should have been returned earlier. This is a fallback.
            return None, "No data could be accessed for the requested fields."

        return accessed_data, None
