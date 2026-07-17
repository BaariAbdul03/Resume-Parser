import os
import structlog
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from werkzeug.exceptions import HTTPException

from app.config import DevelopmentConfig, ProductionConfig, TestingConfig
from app.extensions import limiter, talisman, cors, db, migrate, login_manager, oauth, csrf

# Ensure environment variables are loaded early
load_dotenv()

def create_app(config_class=None):
    """
    Application Factory Pattern for initializing the Flask app.
    Loads configurations based on the FLASK_ENV setting.
    """
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    
    # Apply ProxyFix middleware in production to trust reverse-proxy headers (like Render's SSL terminator)
    is_prod_env = os.environ.get("FLASK_ENV", "development").lower() == "production" or os.environ.get("RENDER") is not None
    if is_prod_env:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
    
    # 1. Determine environment and load configuration
    if config_class is None:
        env = os.environ.get("FLASK_ENV", "development").lower()
        if env == "production" or os.environ.get("RENDER") is not None:
            config_class = ProductionConfig
        elif env == "testing":
            config_class = TestingConfig
        else:
            config_class = DevelopmentConfig
            
    app.config.from_object(config_class)
    
    # Enforce production validation if in production config
    if config_class == ProductionConfig or app.config.get("ENV") == "production":
        from app.config import validate_production_config
        validate_production_config(app.config)
    
    # 2. Configure Structured Logging
    from app.utils.logging import setup_logger
    setup_logger(app)
    
    # 3. Initialize Extensions
    limiter.init_app(app)
    cors.init_app(app)
    csrf.init_app(app)
    
    # Talisman only active/strict in production to avoid local HTTPS hassles
    if not app.debug and not app.testing:
        talisman.init_app(
            app,
            force_https=True,
            content_security_policy=app.config.get("CSP_POLICY"),
            session_cookie_secure=True
        )
    else:
        # Dummy or lenient talisman initialization for dev
        talisman.init_app(
            app,
            force_https=False,
            content_security_policy=None
        )
        
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Zero-configuration Database Initialization
    with app.app_context():
        try:
            # Log the parsed URI (obscuring password) for easy production debugging
            db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
            obscured_uri = db_uri
            if "@" in db_uri:
                try:
                    prefix, rest = db_uri.split("@", 1)
                    scheme_creds = prefix.split("://", 1)
                    if len(scheme_creds) == 2:
                        scheme, creds = scheme_creds
                        user_pass = creds.split(":", 1)
                        user = user_pass[0]
                        obscured_uri = f"{scheme}://{user}:****@{rest}"
                except Exception:
                    obscured_uri = "postgresql://user:****@host..."
            structlog.get_logger(__name__).info(f"Database URI loaded: {obscured_uri}")

            from app.models import User, Analysis, ApiKey, RoleTemplate  # noqa: F401
            from app.utils.database import ensure_database_compatibility
            db.create_all()
            ensure_database_compatibility()
            
            # Keep a demo account local without creating public default credentials.
            if app.config.get("ENV") != "production":
                admin_email = "recruiter@example.com"
                admin = User.query.filter_by(email=admin_email).first()
                if not admin:
                    structlog.get_logger(__name__).info("Pre-seeding default Recruiter Admin account...")
                    admin = User(email=admin_email, name="Recruiter Admin")
                    admin.set_password("SecurePassword123")
                    db.session.add(admin)
                    db.session.commit()
        except Exception as e:
            structlog.get_logger(__name__).error(f"Failed to auto-create database tables: {e}", exc_info=True)
    
    # Configure Flask-Login loader
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to access SynapseCV archives."
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        try:
            return User.query.get(int(user_id))
        except Exception as e:
            structlog.get_logger(__name__).error(f"Database query failed in user_loader callback: {e}")
            return None
        
    oauth.init_app(app)
    from app.routes.auth import configure_oauth_clients
    configure_oauth_clients(app)
    
    # 4. Register Blueprints
    from app.routes.web import web_bp
    from app.routes.parse import parse_bp
    from app.routes.auth import auth_bp
    from app.routes.api import api_bp
    
    app.register_blueprint(web_bp)
    app.register_blueprint(parse_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    
    # 5. Error Handlers
    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({
            "error": "Rate limit exceeded. Please slow down.",
            "retry_after": getattr(e, "description", "60 seconds")
        }), 429

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return jsonify({
            "error": "File size exceeds the maximum limit of 5MB."
        }), 413

    @app.errorhandler(Exception)
    def unhandled_error(e):
        if isinstance(e, HTTPException):
            status_code = e.code or 500
            message = e.description
        else:
            status_code = 500
            message = "Internal Server Error"
            structlog.get_logger(__name__).error("Unhandled application error", exc_info=True)

        expects_json = (
            request.path.startswith("/api/")
            or request.path == "/parse"
            or request.accept_mimetypes.best == "application/json"
        )
        if expects_json:
            return jsonify({"error": message}), status_code
        if isinstance(e, HTTPException):
            return e
        return jsonify({"error": message}), status_code
        
    # 6. Global Security Headers and Cleanup Hooks
    @app.after_request
    def apply_security_filters(response):
        # Override Server header to obscure details
        response.headers['Server'] = 'SynapseCV'
        # Prevent search engine indexing of processed results (GDPR compliance)
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        return response
        
    # 7. Start Supabase Keep-Alive Database Ping Daemon in Production
    if app.config.get("ENV") == "production":
        try:
            from app.utils.keep_alive import start_keep_alive
            start_keep_alive(app)
        except Exception as e:
            app.logger.error(f"Failed to start Database Keep-Alive Daemon: {e}")
            
    return app
