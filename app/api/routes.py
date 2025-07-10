# app/api/routes.py
from . import bp
from flask import jsonify

@bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'message': 'API is running!'})
