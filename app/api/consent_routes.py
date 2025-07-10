from flask import request, jsonify
from datetime import timedelta # Import timedelta
from . import bp  # The API blueprint
from app.services.consent_service import ConsentService
from app.models import ConsentRequest, ConsentRequestStatus, RequestedField, User, Document, DocumentType, Consent, ConsentedField, ConsentStatus # Import Consent, ConsentedField, ConsentStatus
from .document_routes import serialize_document # For embedding document info
from .document_type_routes import serialize_document_type, serialize_field # For document type info in document

# Helpers for serializing User and other nested objects if not fully embedding
def serialize_user_simple(user: User):
    if not user: return None
    return {
        "id": user.id,
        "username": user.username
    }

def serialize_requested_field(req_field: RequestedField):
    return {
        "id": req_field.id,
        "field_name": req_field.field_name
    }

def serialize_consent_request(cr: ConsentRequest):
    data = {
        "id": cr.id,
        "document_id": cr.document_id,
        "requester_id": cr.requester_id,
        "requested_at": cr.requested_at.isoformat() if cr.requested_at else None,
        "status": cr.status.value if cr.status else None,
        "request_message": cr.request_message,
        "owner_message": cr.owner_message,
        "requested_fields": [serialize_requested_field(rf) for rf in cr.requested_fields] if cr.requested_fields else []
    }
    if cr.requester:
        data["requester"] = serialize_user_simple(cr.requester)
    if cr.document:
        # Serialize document, which can in turn serialize its document_type
        data["document"] = serialize_document(cr.document)
        # Ensure owner is serialized if document is present
        if cr.document.owner:
             data["document"]["owner"] = serialize_user_simple(cr.document.owner)

    # The consent_grant relationship is not serialized here by default,
    # it will be part of the Consent object serialization when that's built.
    return data


@bp.route('/consent-requests', methods=['POST'])
def create_consent_request_route():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    requester_id = data.get('requester_id') # Assuming requester_id is passed (e.g. from authenticated user context later)
    document_id = data.get('document_id')
    requested_field_names = data.get('requested_field_names') # List of strings
    request_message = data.get('request_message')

    if not all([isinstance(requester_id, int), isinstance(document_id, int), isinstance(requested_field_names, list)]):
        return jsonify({"error": "Missing or invalid type for required fields: requester_id (int), document_id (int), requested_field_names (list)"}), 400

    if not requested_field_names:
        return jsonify({"error": "requested_field_names cannot be empty"}), 400

    consent_request, error = ConsentService.create_consent_request(
        requester_id=requester_id,
        document_id=document_id,
        requested_field_names=requested_field_names,
        request_message=request_message
    )

    if error:
        # Specific error codes can be useful here (404 for not found, 403 for forbidden, 400/422 for validation)
        if "not found" in error.lower():
            return jsonify({"error": error}), 404
        if "cannot request consent for your own document" in error.lower() or "cannot be requested" in error.lower():
            return jsonify({"error": error}), 403 # Or 400, depending on policy
        return jsonify({"error": error}), 400

    return jsonify(serialize_consent_request(consent_request)), 201


@bp.route('/consent-requests/<int:request_id>', methods=['GET'])
def get_consent_request_route(request_id):
    # Future: Add permission check: only requester or document owner should view.
    consent_request = ConsentService.get_consent_request_by_id(request_id)
    if not consent_request:
        return jsonify({"error": "Consent request not found"}), 404
    return jsonify(serialize_consent_request(consent_request)), 200


@bp.route('/consent-requests', methods=['GET'])
def list_consent_requests_route():
    # Future: This needs to be heavily permissioned.
    # For now, allow filtering by requester_id or owner_id (of the document).
    # This assumes user ID is passed as query param for demonstration.
    # In a real app, this would come from authenticated user context.

    requester_id = request.args.get('requester_id', type=int)
    owner_id = request.args.get('owner_id', type=int) # This implies fetching docs by owner, then their requests
    status_str = request.args.get('status')

    status_enum = None
    if status_str:
        try:
            status_enum = ConsentRequestStatus[status_str.upper()]
        except KeyError:
            valid_statuses = [s.value for s in ConsentRequestStatus]
            return jsonify({"error": f"Invalid status. Valid statuses are: {valid_statuses}"}), 400

    requests_list = []
    if requester_id:
        requests_list = ConsentService.get_consent_requests_by_requester(requester_id, status=status_enum)
    elif owner_id:
        requests_list = ConsentService.get_consent_requests_for_owner(owner_id, status=status_enum)
    else:
        # Potentially list all for an admin, or return error if no filter for non-admin
        # For now, let's restrict: must provide either requester_id or owner_id
        return jsonify({"error": "Must provide either requester_id or owner_id to list consent requests"}), 400
        # requests_list = ConsentRequest.query.all() # Too broad without auth

    return jsonify([serialize_consent_request(cr) for cr in requests_list]), 200


# --- Helper to serialize Consent Grant ---
def serialize_consented_field(cons_field: ConsentedField):
    return {
        "id": cons_field.id,
        "field_name": cons_field.field_name
    }

def serialize_consent_grant(grant: Consent):
    if not grant: return None
    return {
        "id": grant.id,
        "consent_request_id": grant.consent_request_id,
        "owner_id": grant.owner_id,
        "granted_at": grant.granted_at.isoformat() if grant.granted_at else None,
        "valid_until": grant.valid_until.isoformat() if grant.valid_until else None,
        "access_count_total": grant.access_count_total,
        "access_count_remaining": grant.access_count_remaining,
        "status": grant.status.value if grant.status else None,
        "consented_fields": [serialize_consented_field(cf) for cf in grant.consented_fields] if grant.consented_fields else []
    }
# --- End Helper ---


@bp.route('/consent-requests/<int:request_id>/action', methods=['POST'])
def action_consent_request_route(request_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    owner_id = data.get('owner_id') # Assuming owner_id is passed (e.g. from authenticated user context later)
    approved_field_names = data.get('approved_field_names') # list of strings or None
    overall_status_str = data.get('overall_status') # "APPROVED", "DENIED", "PARTIALLY_APPROVED"
    owner_message = data.get('owner_message')

    valid_until_days = data.get('valid_until_days') # Optional: number of days from now
    access_count_total = data.get('access_count_total') # Optional: integer

    if not isinstance(owner_id, int) or not overall_status_str:
        return jsonify({"error": "Missing or invalid type for required fields: owner_id (int), overall_status (string)"}), 400

    try:
        overall_status_enum = ConsentRequestStatus[overall_status_str.upper()]
    except KeyError:
        valid_statuses = [s.value for s in [ConsentRequestStatus.APPROVED, ConsentRequestStatus.DENIED, ConsentRequestStatus.PARTIALLY_APPROVED]]
        return jsonify({"error": f"Invalid overall_status. Must be one of: {valid_statuses}"}), 400

    if overall_status_enum not in [ConsentRequestStatus.APPROVED, ConsentRequestStatus.DENIED, ConsentRequestStatus.PARTIALLY_APPROVED]:
        return jsonify({"error": "overall_status for action must be APPROVED, DENIED, or PARTIALLY_APPROVED."}), 400


    valid_until_delta = None
    if valid_until_days is not None:
        if not isinstance(valid_until_days, int) or valid_until_days <= 0:
            return jsonify({"error": "valid_until_days must be a positive integer."}), 400
        valid_until_delta = timedelta(days=valid_until_days)

    if access_count_total is not None and (not isinstance(access_count_total, int) or access_count_total < 0):
        return jsonify({"error": "access_count_total must be a non-negative integer."}), 400

    if approved_field_names is not None and not isinstance(approved_field_names, list):
        return jsonify({"error": "approved_field_names must be a list of strings."}), 400

    if overall_status_enum == ConsentRequestStatus.PARTIALLY_APPROVED and not approved_field_names:
        return jsonify({"error": "For PARTIALLY_APPROVED status, approved_field_names list must be provided (even if empty to deny all)."}), 400


    updated_request, new_grant, error = ConsentService.action_consent_request(
        consent_request_id=request_id,
        owner_id=owner_id,
        approved_field_names=approved_field_names,
        overall_status=overall_status_enum,
        owner_message=owner_message,
        valid_until_delta=valid_until_delta,
        access_count_total=access_count_total
    )

    if error:
        if "not found" in error.lower():
            return jsonify({"error": error}), 404
        if "not the owner" in error.lower() or "not in a pending state" in error.lower():
            return jsonify({"error": error}), 403
        return jsonify({"error": error}), 400 # Other validation errors from service

    response_data = {
        "consent_request": serialize_consent_request(updated_request),
        "consent_grant": serialize_consent_grant(new_grant) if new_grant else None
    }
    return jsonify(response_data), 200

# --- Routes for managing Consent Grants directly ---

@bp.route('/consents/<int:grant_id>', methods=['GET'])
def get_consent_grant_route(grant_id):
    # Permission: Requester of original request, or Owner of the document.
    # This requires getting the grant, then checking its consent_request.requester_id
    # or consent_request.document.owner_id against the authenticated user.
    # For now, not implementing this complex permission, assuming admin/direct ID access.
    grant = ConsentService.get_consent_grant_by_id(grant_id)
    if not grant:
        return jsonify({"error": "Consent grant not found"}), 404

    # Enrich serialization if needed, e.g. by adding more document/requester details
    # The `serialize_consent_grant` helper already includes consented_fields.
    # We might want to add the full ConsentRequest object or more details from it.
    serialized_grant = serialize_consent_grant(grant)
    # Add full consent request to the grant serialization for context
    if grant.consent_request:
        serialized_grant['consent_request_details'] = serialize_consent_request(grant.consent_request)

    return jsonify(serialized_grant), 200


@bp.route('/consents', methods=['GET'])
def list_consent_grants_route():
    # Filters based on ConsentService.list_consent_grants method
    document_id = request.args.get('document_id', type=int)
    owner_id = request.args.get('owner_id', type=int) # Owner of the grant (who approved it)
    requester_id = request.args.get('requester_id', type=int) # Requester from original ConsentRequest
    status_str = request.args.get('status')

    status_enum = None
    if status_str:
        try:
            status_enum = ConsentStatus[status_str.upper()]
        except KeyError:
            valid_statuses = [s.value for s in ConsentStatus]
            return jsonify({"error": f"Invalid status. Valid statuses are: {valid_statuses}"}), 400

    # Permission considerations:
    # - If owner_id is passed, it's likely the owner querying their grants.
    # - If requester_id is passed, it's likely the requester querying grants they received.
    # - document_id might be used by either.
    # - Unfiltered list should probably be admin-only.
    # For now, allow if at least one filter is provided, or it's an admin (not implemented).
    if not document_id and not owner_id and not requester_id and not status_enum:
         return jsonify({"error": "At least one filter (document_id, owner_id, requester_id, status) must be provided to list consent grants, or admin privileges required."}), 400

    grants = ConsentService.list_consent_grants(
        document_id=document_id,
        owner_id=owner_id,
        requester_id=requester_id,
        status=status_enum
    )
    return jsonify([serialize_consent_grant(g) for g in grants]), 200


@bp.route('/consents/<int:grant_id>/revoke', methods=['POST'])
def revoke_consent_grant_route(grant_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    revoking_user_id = data.get('revoking_user_id') # ID of user performing revocation (e.g. owner)
                                                 # In real app, this comes from auth token.
    if not isinstance(revoking_user_id, int):
        return jsonify({"error": "revoking_user_id (integer) is required in payload."}), 400

    grant, error = ConsentService.revoke_consent_grant(grant_id, revoking_user_id)
    if error:
        if "not found" in error:
            return jsonify({"error": error}), 404
        if "permission" in error or "not currently active" in error:
            return jsonify({"error": error}), 403
        return jsonify({"error": error}), 400

    # AuditService.log_action("CONSENT_REVOKED", user_id=revoking_user_id, target_resource_type="Consent", target_resource_id=grant_id)
    # The service method itself should ideally log this. (Added a commented out line there)
    # For now, let's assume service handles logging or we add it here if service doesn't.
    # Let's add it to the service as it's a direct action on the consent.

    return jsonify({"message": "Consent grant revoked successfully.", "consent_grant": serialize_consent_grant(grant)}), 200
