import logging

from flask import Blueprint, render_template, jsonify, request
from flask_login import current_user
from sqlalchemy import text
from app.services.role_library import RoleLibrary
from app.models import Analysis, RoleTemplate
from app.extensions import db

logger = logging.getLogger(__name__)

web_bp = Blueprint('web', __name__)


@web_bp.route('/healthz')
def healthz():
    """Lightweight health check for Render and uptime monitors."""
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok", "database": "ok"})
    except Exception:
        return jsonify({"status": "degraded", "database": "error"}), 503

@web_bp.route('/')
def index():
    """Serves the stunning landing page or the workspace if authenticated."""
    # Discard flashed messages so they don't linger in session cookies
    from flask import get_flashed_messages
    get_flashed_messages()
    if current_user.is_authenticated:
        return render_template('index.html')
    return render_template('landing.html')


@web_bp.route('/home')
def home():
    """Serves the stunning landing page always."""
    from flask import get_flashed_messages
    get_flashed_messages()
    return render_template('landing.html')


@web_bp.route('/workspace')
def workspace():
    """Serves the direct Recruiters' workspace panel."""
    # Discard flashed messages
    from flask import get_flashed_messages
    get_flashed_messages()
    return render_template('index.html')


@web_bp.route('/roles', methods=['GET', 'POST'])
def manage_roles():
    """
    GET: Returns a list of all curated roles (global default templates + user's custom templates).
    POST: Saves a new custom target position template for the recruiter.
    """
    if request.method == 'POST':
        if not current_user.is_authenticated:
            return jsonify({"error": "Please sign in to save custom job templates."}), 401
            
        try:
            data = request.get_json() or {}
            role_name = data.get("role_name", "").strip()
            jd_text = data.get("job_description", "").strip()
            
            if not role_name or not jd_text:
                return jsonify({"error": "Role name and job description text are required."}), 400
                
            if len(jd_text) > 5000:
                return jsonify({"error": "Job description template exceeds maximum allowed length of 5000 characters."}), 400
                
            # Check if template already exists for this user
            existing = RoleTemplate.query.filter_by(user_id=current_user.id, role_name=role_name).first()
            if existing:
                existing.job_description = jd_text
            else:
                new_template = RoleTemplate(
                    user_id=current_user.id,
                    role_name=role_name,
                    job_description=jd_text
                )
                db.session.add(new_template)
                
            db.session.commit()
            return jsonify({"success": True, "message": f"Template for '{role_name}' saved successfully!"})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to save role template: {e}", exc_info=True)
            return jsonify({"error": "Failed to save role template."}), 500

    # GET Request
    global_list = RoleLibrary.get_list()
    custom_list = []
    
    if current_user.is_authenticated:
        try:
            custom_templates = RoleTemplate.query.filter_by(user_id=current_user.id).order_by(RoleTemplate.role_name).all()
            # Mark custom templates clearly with a star badge so UI displays them elevated
            custom_list = [f"★ {t.role_name}" for t in custom_templates]
        except Exception:
            pass
            
    return jsonify(global_list + custom_list)


@web_bp.route('/roles/template')
@web_bp.route('/roles/<string:role_name>')
def get_role_template(role_name=None):
    """
    Returns the job description template for a specific role.
    Checks user's custom templates first (stripping the star badge prefix if present),
    then falls back to system global templates.
    Supports role name passed as path parameter or query parameter 'role_name'.
    """
    if not role_name:
        role_name = request.args.get("role_name", "").strip()
        
    clean_name = role_name.lstrip("★ ").strip()
    
    # Check user's custom templates if authenticated
    if current_user.is_authenticated:
        try:
            custom_t = RoleTemplate.query.filter_by(user_id=current_user.id, role_name=clean_name).first()
            if custom_t:
                return jsonify({"role": role_name, "template": custom_t.job_description})
        except Exception:
            pass
            
    # Fallback to system library
    template = RoleLibrary.get_template(clean_name)
    if not template:
        return jsonify({"error": "Role template not found."}), 404
    return jsonify({"role": role_name, "template": template})


@web_bp.route('/archives')
def get_archives():
    """Lists saved candidate analyses for the logged-in user."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Unauthorized. Please login to access archives."}), 401
        
    analyses = Analysis.query.filter_by(user_id=current_user.id).order_by(Analysis.created_at.desc()).all()
    return jsonify([a.to_dict() for a in analyses])


@web_bp.route('/archives/<int:analysis_id>', methods=['GET', 'DELETE'])
def manage_archive(analysis_id):
    """Retrieves or deletes a specific analysis from candidate archives."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Unauthorized"}), 401
        
    analysis = Analysis.query.get_or_404(analysis_id)
    
    if analysis.user_id != current_user.id:
        return jsonify({"error": "Forbidden"}), 403
        
    if request.method == 'DELETE':
        try:
            db.session.delete(analysis)
            db.session.commit()
            return jsonify({"success": True, "message": "Analysis deleted from archives."})
        except Exception:
            db.session.rollback()
            return jsonify({"error": "Failed to delete analysis record."}), 500
            
    return jsonify(analysis.to_dict())
