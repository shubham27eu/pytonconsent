from app import db
from app.models import (
    User, Document, DocumentType, DocumentField, FieldClassification,
    ConsentRequest, ConsentRequestStatus, RequestedField,
    Consent, ConsentStatus, ConsentedField
)
from datetime import datetime, timedelta, timezone # Import timezone

class ConsentService:
    @staticmethod
    def create_consent_request(requester_id: int, document_id: int, requested_field_names: list[str], request_message: str = None):
        """
        Creates a new consent request for specific fields of a document.

        Args:
            requester_id: ID of the user requesting consent.
            document_id: ID of the document for which consent is requested.
            requested_field_names: A list of field names being requested.
            request_message: Optional message from the requester.

        Returns:
            Tuple: (ConsentRequest | None, error_message | None)
        """
        requester = User.query.get(requester_id)
        if not requester:
            return None, "Requester not found."
        # Potentially add role check if only certain roles can request, but generally any user can request.

        document = Document.query.get(document_id)
        if not document:
            return None, f"Document with ID {document_id} not found."

        if document.owner_id == requester_id:
            return None, "Cannot request consent for your own document." # Or allow, depending on policy

        if not requested_field_names:
            return None, "At least one field must be requested."

        # Validate requested fields against the document type
        doc_type = document.document_type
        if not doc_type: # Should not happen if data is consistent
            return None, f"Document type not found for document ID {document_id}."

        valid_fields_for_request = []
        doc_type_field_map = {field.name: field for field in doc_type.fields}

        for field_name in set(requested_field_names): # Use set to avoid duplicate processing
            if field_name not in doc_type_field_map:
                return None, f"Field '{field_name}' does not exist in document type '{doc_type.name}'."

            doc_field = doc_type_field_map[field_name]
            if doc_field.classification == FieldClassification.CLOSED:
                return None, f"Field '{field_name}' is classified as closed and cannot be requested."

            # If field is OPEN, it can still be part of a request, owner might just auto-approve or ignore.
            # Or, policy could be to not allow requesting OPEN fields. For now, allow.
            valid_fields_for_request.append(field_name)

        if not valid_fields_for_request: # Should be caught by earlier checks if all were invalid
            return None, "No valid fields found for request after validation."


        # Check for existing pending/active consent requests for the same document, requester, and fields (optional, to prevent spam)
        # This logic can be complex if checking for exact subset/superset of fields.
        # For now, allow multiple requests, owner can manage them.

        consent_request = ConsentRequest(
            document_id=document_id,
            requester_id=requester_id,
            status=ConsentRequestStatus.PENDING,
            request_message=request_message,
            # model default uses lambda: datetime.now(timezone.utc), so explicit set here should also be timezone-aware
            requested_at=datetime.now(timezone.utc)
        )
        db.session.add(consent_request)

        # Create RequestedField entries
        # Must flush to get consent_request.id if not using nested objects with cascade immediately
        # db.session.flush() # Not strictly needed if we add objects to request's collection before commit

        for field_name in valid_fields_for_request:
            req_field = RequestedField(consent_request_id=consent_request.id, field_name=field_name)
            consent_request.requested_fields.append(req_field) # Appending to relationship collection

        try:
            # db.session.add(consent_request) # Already added
            # for field_obj in created_requested_fields: # If created separately
            #     db.session.add(field_obj)
            db.session.commit()
            return consent_request, None
        except Exception as e:
            db.session.rollback()
            # Log error e
            return None, f"Database error during consent request creation: {str(e)}"

    @staticmethod
    def get_consent_request_by_id(consent_request_id: int):
        # Eager load related fields for easier serialization/use
        return ConsentRequest.query.options(
            db.joinedload(ConsentRequest.requested_fields),
            db.joinedload(ConsentRequest.document).joinedload(Document.document_type).joinedload(DocumentType.fields),
            db.joinedload(ConsentRequest.requester),
            db.joinedload(ConsentRequest.document).joinedload(Document.owner)
        ).get(consent_request_id)

    @staticmethod
    def get_consent_requests_for_owner(owner_id: int, status: ConsentRequestStatus = None):
        query = ConsentRequest.query.join(Document).filter(Document.owner_id == owner_id)
        if status:
            query = query.filter(ConsentRequest.status == status)
        return query.order_by(ConsentRequest.requested_at.desc()).all()

    @staticmethod
    def get_consent_requests_by_requester(requester_id: int, status: ConsentRequestStatus = None):
        query = ConsentRequest.query.filter_by(requester_id=requester_id)
        if status:
            query = query.filter(ConsentRequest.status == status)
        return query.order_by(ConsentRequest.requested_at.desc()).all()

    # More methods will be added for approving/denying consent, etc.
    # This is just the start for the "Request the Document" use case.

    @staticmethod
    def action_consent_request(
        consent_request_id: int,
        owner_id: int,
        approved_field_names: list[str] = None, # List of field names owner approves
        # denied_field_names: list[str] = None, # Could explicitly track denied, or assume not in approved is denied
        overall_status: ConsentRequestStatus = None, # e.g. PENDING, APPROVED, DENIED, PARTIALLY_APPROVED
        owner_message: str = None,
        valid_until_delta: timedelta = None, # e.g., timedelta(days=30)
        access_count_total: int = None
    ):
        """
        Allows a document owner to approve, partially approve, or deny a consent request.
        Creates a Consent grant if approved or partially approved.

        Args:
            consent_request_id: ID of the consent request to action.
            owner_id: ID of the user actioning the request (must be document owner).
            approved_field_names: List of field names explicitly approved by the owner.
                                  If overall_status is APPROVED, and this is None, all requested controlled fields are approved.
                                  If overall_status is PARTIALLY_APPROVED, this list is mandatory.
            overall_status: The new status for the ConsentRequest (APPROVED, DENIED, PARTIALLY_APPROVED).
            owner_message: Optional message from the owner.
            valid_until_delta: Optional timedelta for how long the consent is valid from now.
            access_count_total: Optional total number of times the consented data can be accessed.

        Returns:
            Tuple: (ConsentRequest | None, Consent | None, error_message | None)
        """
        consent_request = ConsentRequest.query.options(
            db.joinedload(ConsentRequest.document),
            db.joinedload(ConsentRequest.requested_fields) # Ensure requested_fields are loaded
        ).get(consent_request_id)

        if not consent_request:
            return None, None, "Consent request not found."

        if consent_request.document.owner_id != owner_id:
            return None, None, "User is not the owner of the document related to this consent request."

        if consent_request.status not in [ConsentRequestStatus.PENDING]:
             # Add other statuses from which it can be actioned if necessary (e.g. if re-approval is allowed)
            return None, None, f"Consent request is not in a pending state (current status: {consent_request.status.value})."

        if not overall_status or overall_status not in [ConsentRequestStatus.APPROVED, ConsentRequestStatus.DENIED, ConsentRequestStatus.PARTIALLY_APPROVED]:
            return None, None, "Invalid overall_status provided. Must be APPROVED, DENIED, or PARTIALLY_APPROVED."

        # Update ConsentRequest
        consent_request.status = overall_status
        if owner_message:
            consent_request.owner_message = owner_message

        db.session.add(consent_request)
        created_consent_grant = None

        if overall_status == ConsentRequestStatus.DENIED:
            # No Consent grant is created for denial.
            try:
                db.session.commit()
                return consent_request, None, None
            except Exception as e:
                db.session.rollback()
                return None, None, f"Database error while denying consent request: {str(e)}"

        # --- Handle APPROVED or PARTIALLY_APPROVED ---

        # Determine the set of fields that are actually approved by the owner
        final_approved_fields_from_owner = set(approved_field_names) if approved_field_names is not None else set()

        # Get all fields requested by the user
        all_requested_field_names = {rf.field_name for rf in consent_request.requested_fields}

        # Get the document's field classifications
        doc_type_fields_map = {f.name: f.classification for f in consent_request.document.document_type.fields}

        actual_consented_fields_for_grant = []

        if overall_status == ConsentRequestStatus.APPROVED:
            if approved_field_names is None: # Owner approves all requested (non-closed) fields implicitly
                for field_name in all_requested_field_names:
                    # We already filtered out CLOSED fields during request creation.
                    # Here, we're just confirming what goes into the grant.
                    # OPEN fields can also be part of grant if owner explicitly includes them or if policy implies it.
                    # For simplicity, let's assume owner's approval covers what was requested.
                    # If a field is OPEN, consent is technically not needed but it's fine to record it as "consented".
                    if doc_type_fields_map.get(field_name) != FieldClassification.CLOSED:
                         actual_consented_fields_for_grant.append(field_name)
            else: # Owner explicitly lists fields for an APPROVED status
                for field_name in final_approved_fields_from_owner:
                    if field_name not in all_requested_field_names:
                        db.session.rollback() # Rollback any changes to consent_request status
                        return None, None, f"Field '{field_name}' was approved but not originally requested."
                    if doc_type_fields_map.get(field_name) == FieldClassification.CLOSED:
                        db.session.rollback()
                        return None, None, f"Field '{field_name}' is CLOSED and cannot be part of a consent grant."
                    actual_consented_fields_for_grant.append(field_name)

        elif overall_status == ConsentRequestStatus.PARTIALLY_APPROVED:
            if not approved_field_names: # Must specify which fields for partial approval
                db.session.rollback()
                return None, None, "For PARTIALLY_APPROVED status, approved_field_names must be provided."
            for field_name in final_approved_fields_from_owner:
                if field_name not in all_requested_field_names:
                    db.session.rollback()
                    return None, None, f"Field '{field_name}' was approved but not originally requested."
                if doc_type_fields_map.get(field_name) == FieldClassification.CLOSED:
                    db.session.rollback()
                    return None, None, f"Field '{field_name}' is CLOSED and cannot be part of a consent grant."
                actual_consented_fields_for_grant.append(field_name)

        if not actual_consented_fields_for_grant and overall_status != ConsentRequestStatus.DENIED:
             # This case might arise if PARTIALLY_APPROVED with empty approved_field_names,
             # or if APPROVED implicitly but all requested fields were somehow invalid (though unlikely given earlier checks)
            db.session.rollback()
            return None, None, "No fields were ultimately approved for this consent grant."


        # Create Consent grant object
        valid_until_datetime = None
        if valid_until_delta:
            valid_until_datetime = datetime.now(timezone.utc) + valid_until_delta

        new_consent_grant = Consent(
            consent_request_id=consent_request.id,
            owner_id=owner_id, # Document owner
            granted_at=datetime.now(timezone.utc), # Use timezone aware
            valid_until=valid_until_datetime,
            access_count_total=access_count_total,
            access_count_remaining=access_count_total, # Initially same as total
            status=ConsentStatus.ACTIVE
        )
        db.session.add(new_consent_grant)
        # Must flush to get new_consent_grant.id for ConsentedField, or use relationship append
        # db.session.flush()

        for field_name in actual_consented_fields_for_grant:
            consented_field_entry = ConsentedField(field_name=field_name)
            new_consent_grant.consented_fields.append(consented_field_entry)
            # db.session.add(consented_field_entry) # If not using append to relationship

        created_consent_grant = new_consent_grant

        try:
            db.session.commit()
            return consent_request, created_consent_grant, None
        except Exception as e:
            db.session.rollback()
            # Log error e
            return None, None, f"Database error while creating consent grant: {str(e)}"
