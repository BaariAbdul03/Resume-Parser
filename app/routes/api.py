import logging
import secrets
import hashlib
from functools import wraps
from flask import Blueprint, request, jsonify, g
from app.extensions import db, limiter, csrf
from app.models import ApiKey, Analysis
from app.services.parsing import parse_single_resume_object, save_analysis_result

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__, url_prefix='/api')

def api_key_required(f):
    @wraps(f)
    def decorated_function(*gargs, **kwargs):
        # Retrieve key from Authorization header or X-API-Key header
        auth_header = request.headers.get("Authorization")
        api_key = None
        
        if auth_header and auth_header.startswith("Bearer "):
            api_key = auth_header.split(" ")[1].strip()
        else:
            api_key = request.headers.get("X-API-Key")
            
        if not api_key:
            return jsonify({"error": "Unauthorized. Please provide a valid SynapseCV API key."}), 401
            
        # Hash the API key and lookup in DB
        try:
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            db_key = ApiKey.query.filter_by(key_hash=key_hash).first()
            
            if not db_key:
                return jsonify({"error": "Unauthorized. The provided API key is invalid or revoked."}), 401
                
            # Bind authenticated user context to flask global context
            g.api_user = db_key.user
            g.api_key_name = db_key.name
        except Exception as err:
            logger.error(f"API key authentication error: {err}", exc_info=True)
            return jsonify({"error": "Unauthorized. Security validation failed."}), 401
            
        return f(*gargs, **kwargs)
    return decorated_function


# ==========================================================================
# 1. API Token Generation & Listing (Session-Authenticated UI endpoints)
# ==========================================================================
@api_bp.route('/v1/keys', methods=['POST'])
def generate_key():
    """
    Generates a new API key for the logged-in session user.
    Plaintext key is shown ONLY once.
    """
    from flask_login import current_user
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required."}), 401
        
    try:
        data = request.get_json() or {}
        key_name = data.get("name", "Production API Key").strip()
        if not key_name:
            key_name = "Production API Key"
            
        # Generate Stripe-like key format: scv_live_[32 characters]
        token = secrets.token_hex(16)
        plaintext_key = f"scv_live_{token}"
        
        key_prefix = "scv_live_" + token[:4]
        key_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
        
        new_key = ApiKey(
            user_id=current_user.id,
            name=key_name,
            key_prefix=key_prefix,
            key_hash=key_hash
        )
        db.session.add(new_key)
        db.session.commit()
        
        return jsonify({
            "id": new_key.id,
            "name": new_key.name,
            "key_prefix": new_key.key_prefix + "...",
            "plaintext_key": plaintext_key,
            "created_at": new_key.created_at.isoformat()
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to generate API Key: {e}", exc_info=True)
        return jsonify({"error": "Failed to generate API credentials."}), 500


@api_bp.route('/v1/keys', methods=['GET'])
def list_keys():
    """Lists active API key prefixes for the session user."""
    from flask_login import current_user
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required."}), 401
        
    try:
        keys = ApiKey.query.filter_by(user_id=current_user.id).order_by(ApiKey.created_at.desc()).all()
        return jsonify([{
            "id": k.id,
            "name": k.name,
            "key_prefix": k.key_prefix + "...",
            "created_at": k.created_at.isoformat()
        } for k in keys])
    except Exception as e:
        logger.error(f"Failed to list API Keys: {e}", exc_info=True)
        return jsonify({"error": "Failed to list credentials."}), 500


@api_bp.route('/v1/keys/<int:key_id>', methods=['DELETE'])
def revoke_key(key_id):
    """Revokes (deletes) an API key."""
    from flask_login import current_user
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required."}), 401
        
    try:
        key = ApiKey.query.filter_by(id=key_id, user_id=current_user.id).first()
        if not key:
            return jsonify({"error": "API Key not found or access denied."}), 404
            
        db.session.delete(key)
        db.session.commit()
        return jsonify({"success": "API key revoked successfully."})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to revoke API Key: {e}", exc_info=True)
        return jsonify({"error": "Failed to revoke credentials."}), 500


# ==========================================================================
# 2. Public REST API Endpoints (API Key-Authenticated)
# ==========================================================================
@api_bp.route('/v1/parse', methods=['POST'])
@limiter.limit("10 per minute")
@api_key_required
@csrf.exempt
def api_parse_resume():
    """
    Public API endpoint to parse a single resume PDF.
    Expects multipart/form-data with a file 'resume' and string 'job_description'.
    """
    try:
        if 'resume' not in request.files:
            return jsonify({"error": "No resume file provided in 'resume' field."}), 400
            
        file = request.files['resume']
        jd_text = request.form.get('job_description', '').strip()
        
        if not file or file.filename == '':
            return jsonify({"error": "No selected file."}), 400
            
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({"error": "Invalid format. Only PDF files are supported."}), 400
            
        # Parse PDF using worker helper
        result = parse_single_resume_object(file.filename, file, jd_text)
        
        if "error" in result:
            return jsonify({"error": result["error"]}), 400
            
        # Save to database under the API key user's account (best-effort)
        target_role = request.form.get('target_role', '').strip() or request.form.get('selected_role', '').strip()
        db_id = save_analysis_result(g.api_user.id, result, target_role)
        if db_id is not None:
            result["db_id"] = db_id

        return jsonify(result)
        
    except Exception as e:
        logger.error(f"API parse error: {e}", exc_info=True)
        return jsonify({"error": "Internal Server Error"}), 500


@api_bp.route('/v1/results/<int:result_id>', methods=['GET'])
@api_key_required
def api_get_result(result_id):
    """Retrieves an archived analysis record by ID."""
    try:
        analysis = Analysis.query.filter_by(id=result_id, user_id=g.api_user.id).first()
        if not analysis:
            return jsonify({"error": "Analysis record not found or access denied."}), 404
            
        return jsonify(analysis.to_dict())
    except Exception as e:
        logger.error(f"API get result error: {e}", exc_info=True)
        return jsonify({"error": "Internal Server Error"}), 500


@api_bp.route('/docs')
@api_bp.route('/docs/')
def api_docs():
    """Serves the interactive Swagger UI API documentation page."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>SynapseCV REST API Documentation</title>
        <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css" />
        <style>
            html { box-sizing: border-box; overflow-y: scroll; }
            *, *:before, *:after { box-sizing: inherit; }
            body { margin:0; background: #060609; }
            .swagger-ui { filter: invert(90%) hue-rotate(180deg); }
            .swagger-ui .topbar { display: none; }
            .swagger-ui .info .title { color: #ffffff !important; }
            .swagger-ui .scheme-container { background: #12121a !important; }
        </style>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js"></script>
        <script>
            window.onload = function() {
                const ui = SwaggerUIBundle({
                    url: "/api/v1/openapi.json",
                    dom_id: '#swagger-ui',
                    deepLinking: true,
                    presets: [
                        SwaggerUIBundle.presets.apis,
                        SwaggerUIBundle.presets.swaggerUiConfig
                    ]
                });
                window.ui = ui;
            };
        </script>
    </body>
    </html>
    """


@api_bp.route('/v1/openapi.json')
def openapi_json():
    """Returns the OpenAPI 3.0 JSON specification for SynapseCV REST APIs."""
    return jsonify({
        "openapi": "3.0.0",
        "info": {
            "title": "SynapseCV Developer REST APIs",
            "version": "1.0.0",
            "description": "Enterprise-grade endpoints to scan resume PDFs concurrently and query candidates."
        },
        "servers": [{"url": "/api"}],
        "paths": {
            "/v1/parse": {
                "post": {
                    "summary": "Parse a single resume PDF",
                    "description": "Upload a candidate's resume PDF and score it against an optional job description.",
                    "parameters": [
                        {
                            "name": "X-API-Key",
                            "in": "header",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Stripe-style API key (e.g. scv_live_...)"
                        }
                    ],
                    "requestBody": {
                        "content": {
                            "multipart/form-data": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "resume": {"type": "string", "format": "binary", "description": "Candidate's resume PDF"},
                                        "job_description": {"type": "string", "description": "Target job description constraints"},
                                        "target_role": {"type": "string", "description": "Optional specific target role name (e.g. Frontend Engineer)"}
                                    },
                                    "required": ["resume"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "Parsing completed successfully"},
                        "400": {"description": "Validation error or invalid file structure"},
                        "401": {"description": "Unauthorized access"}
                    }
                }
            },
            "/v1/results/{result_id}": {
                "get": {
                    "summary": "Retrieve an archived analysis result",
                    "parameters": [
                        {
                            "name": "X-API-Key",
                            "in": "header",
                            "required": True,
                            "schema": {"type": "string"}
                        },
                        {
                            "name": "result_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"}
                        }
                    ],
                    "responses": {
                        "200": {"description": "Archive retrieved"},
                        "404": {"description": "Analysis record not found"},
                        "401": {"description": "Unauthorized"}
                    }
                }
            }
        }
    })
