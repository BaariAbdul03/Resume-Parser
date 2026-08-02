import os

class Config:
    """Base Configuration class."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "default-synapse-cv-secret-key-change-in-prod")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    
    # Flask settings
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB limit
    
    # Gemini API settings
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    GEMINI_TIMEOUT = float(os.environ.get("GEMINI_TIMEOUT", "30.0"))  # seconds
    GEMINI_RETRIES = int(os.environ.get("GEMINI_RETRIES", "2"))
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-2.0-flash")
    
    # Database (Supabase / SQLite)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///synapsecv.db")
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
        
    # Rate Limiting defaults
    RATELIMIT_DEFAULT = "100 per day"
    RATELIMIT_STORAGE_URI = "memory://"

    # CORS: comma-separated list of allowed origins (default: same-origin only)
    CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
    
    # OAuth configuration (Google)
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
    
    # Groq AI configuration (primary AI provider)
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    ENV = "development"
    # Local dev defaults
    RATELIMIT_ENABLED = False  # Disable rate limit for dev convenience

class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    ENV = "production"
    RATELIMIT_ENABLED = True
    PREFERRED_URL_SCHEME = "https"
    SESSION_COOKIE_SECURE = True
    
    # Configure NullPool to prevent connection pooling issues with Supabase transaction pooler
    from sqlalchemy.pool import NullPool
    SQLALCHEMY_ENGINE_OPTIONS = {
        "poolclass": NullPool,
    }
    
    # Talisman CSP configurations
    CSP_POLICY = {
        'default-src': '\'self\'',
        'script-src': [
            '\'self\'',
            '\'unsafe-inline\'',
            'https://cdnjs.cloudflare.com',
            'https://fonts.googleapis.com',
            'https://unpkg.com'
        ],
        'style-src': [
            '\'self\'',
            '\'unsafe-inline\'',
            'https://fonts.googleapis.com',
            'https://cdnjs.cloudflare.com'
        ],
        'font-src': [
            '\'self\'',
            'https://fonts.gstatic.com'
        ],
        'img-src': [
            '\'self\'',
            'data:',
            'https://images.unsplash.com'
        ],
        'connect-src': [
            '\'self\'',
            'https://cdnjs.cloudflare.com',
            'https://unpkg.com'
        ],
        'worker-src': [
            '\'self\'',
            'blob:'
        ]
    }

class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    RATELIMIT_ENABLED = False
    PRESERVE_CONTEXT_ON_EXCEPTION = False

def validate_production_config(config):
    """
    Validates required settings for production environment.
    """
    import os
    
    # 1. SECRET_KEY validation
    secret_key = config.get("SECRET_KEY")
    if not secret_key or secret_key == "default-synapse-cv-secret-key-change-in-prod":
        raise ValueError("Production Error: SECRET_KEY must be set to a secure, custom value in production.")
        
    # 2. Database URL validation
    db_uri = config.get("SQLALCHEMY_DATABASE_URI")
    if not db_uri or db_uri.startswith("sqlite://") or not os.environ.get("DATABASE_URL"):
        raise ValueError("Production Error: DATABASE_URL must be configured with a production database in production.")
        
    # 3. OAuth secrets if OAuth is required
    oauth_required = os.environ.get("OAUTH_REQUIRED", "false").lower() == "true"
    if oauth_required:
        if not config.get("GOOGLE_CLIENT_ID") or not config.get("GOOGLE_CLIENT_SECRET"):
            raise ValueError("Production Error: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be configured when OAuth is required.")
            
    # 4. At least one AI provider key
    if not config.get("GROQ_API_KEY") and not config.get("GEMINI_API_KEY"):
        raise ValueError("Production Error: At least one AI provider API key (GROQ_API_KEY or GEMINI_API_KEY) must be configured in production.")

