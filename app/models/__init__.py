# app/models/__init__.py
# This file will import all models so they are registered with SQLAlchemy

from .user import User
from .document_type import DocumentType
from .document_field import DocumentField, FieldClassification
from .document import Document
from .consent_request import ConsentRequest, ConsentRequestStatus
from .requested_field import RequestedField
from .consent import Consent, ConsentStatus
from .consented_field import ConsentedField
from .audit_log import AuditLog

# You can also define a helper function or variable to list all models if needed elsewhere.
__all__ = [
    'User',
    'DocumentType',
    'DocumentField', 'FieldClassification',
    'Document',
    'ConsentRequest', 'ConsentRequestStatus',
    'RequestedField',
    'Consent', 'ConsentStatus',
    'ConsentedField',
    'AuditLog'
]
