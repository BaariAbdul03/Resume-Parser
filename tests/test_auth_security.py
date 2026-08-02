"""
Auth security regression tests: sandbox OAuth gating and login rate limiting.
"""

from app import create_app
from app.config import TestingConfig
from app.extensions import db, limiter


def test_sandbox_login_blocked_in_production(client):
    """POST /auth/oauth/sandbox must not exist in production."""
    client.application.config["ENV"] = "production"
    response = client.post("/auth/oauth/sandbox")
    assert response.status_code == 404


def test_sandbox_login_allowed_in_dev(client):
    """Sandbox login stays available for frictionless dev/test login."""
    response = client.post("/auth/oauth/sandbox")
    assert response.status_code == 302  # redirects to the workspace


def test_login_google_fallback_blocked_in_production(client):
    """Without Google keys, prod must not render the sandbox login page."""
    client.application.config["ENV"] = "production"
    response = client.get("/auth/oauth/google")
    assert response.status_code == 302  # redirected to regular login


def test_login_rate_limited():
    """Login POSTs are limited to 10 per minute per client."""
    class RateLimitedTestingConfig(TestingConfig):
        RATELIMIT_ENABLED = True
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    app = create_app(RateLimitedTestingConfig)
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
    })
    with app.app_context():
        db.create_all()

    client = app.test_client()
    try:
        for _ in range(10):
            response = client.post(
                "/auth/login",
                data={"email": "recruiter@example.com", "password": "wrong-password"},
            )
            assert response.status_code == 200  # invalid creds re-render the form
        response = client.post(
            "/auth/login",
            data={"email": "recruiter@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.get_json()["error"]
    finally:
        # Restore the shared limiter for the rest of the test session.
        limiter.enabled = False
