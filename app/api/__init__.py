# app/api/__init__.py
from flask import Blueprint

bp = Blueprint('api', __name__)

# Import modules to register routes
from . import routes # General routes like health check
from . import document_type_routes
from . import document_routes
from . import consent_routes # Add consent routes
# from . import user_routes
