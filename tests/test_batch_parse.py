"""
Regression tests for the /parse endpoint, especially batch mode.

Batch parsing runs workers in a ThreadPoolExecutor (no Flask request context).
The regression guard below asserts the worker pushes a Flask app context before
calling the AI service — without the fix, provider API keys resolve to None and
every batch result fails.
"""

import io
from pathlib import Path
from unittest.mock import patch

from flask import has_app_context

SAMPLE_PDF = (Path(__file__).parent / "sample_resume.pdf").read_bytes()

FAKE_ANALYSIS = {
    "name": "Test Candidate",
    "email": "candidate@example.com",
    "phone": "555-1234",
    "github_url": "https://github.com/test",
    "linkedin_url": "https://linkedin.com/in/test",
    "education": ["BSc Computer Science"],
    "skills": ["Python", "SQL"],
    "missing_keywords": ["Go"],
    "match_percentage": 85,
    "detected_role": "Backend Engineer",
    "profile_summary": "Good fit for the target role.",
    "scoring_reasoning": "Started at 100. Deducted 15 for skill gaps. Final: 85.",
}


def _parse_request(client, resume_files, jd_text=""):
    return client.post(
        "/parse",
        data={"resume": resume_files, "job_description": jd_text},
        content_type="multipart/form-data",
    )


def test_batch_parse_runs_ai_inside_app_context(client):
    """Workers must see a Flask app context so the AI service can resolve keys."""

    def fake_analyze(resume_text, jd_text):
        assert has_app_context(), "Worker thread has no Flask app context!"
        return dict(FAKE_ANALYSIS)

    with patch("app.routes.parse.ensure_ai_configured", return_value=True), \
         patch("app.services.parsing.extract_text_from_pdf", return_value="Jane Doe\nPython, SQL"), \
         patch("app.services.parsing.ai_service.analyze_resume", side_effect=fake_analyze) as mock_ai:
        response = _parse_request(
            client,
            [(io.BytesIO(SAMPLE_PDF), "alice.pdf"), (io.BytesIO(SAMPLE_PDF), "bob.pdf")],
            "Backend Engineer",
        )

    assert response.status_code == 200
    assert mock_ai.call_count == 2

    body = response.get_json()
    assert body["is_batch"] is True
    assert body["total_processed"] == 2
    assert body["successful_count"] == 2
    assert body["failed_count"] == 0
    assert len(body["results"]) == 2
    # Ranked leaderboard: sorted by match_percentage descending
    scores = [r["match_percentage"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)


def test_single_parse_success(client):
    """Single-file path still works through the shared worker."""
    with patch("app.routes.parse.ensure_ai_configured", return_value=True), \
         patch("app.services.parsing.extract_text_from_pdf", return_value="Jane Doe\nPython, SQL"), \
         patch("app.services.parsing.ai_service.analyze_resume", return_value=dict(FAKE_ANALYSIS)) as mock_ai:
        response = _parse_request(client, [(io.BytesIO(SAMPLE_PDF), "alice.pdf")], "Backend Engineer")

    assert response.status_code == 200
    assert mock_ai.call_count == 1
    assert "error" not in response.get_json()


def test_parse_error_does_not_leak_internals(client):
    """Internal exception details must never reach the client."""
    with patch("app.routes.parse.ensure_ai_configured", return_value=True), \
         patch("app.services.parsing.extract_text_from_pdf", return_value="Jane Doe"), \
         patch("app.services.parsing.ai_service.analyze_resume", side_effect=RuntimeError("db:secret@host leak")):
        response = _parse_request(client, [(io.BytesIO(SAMPLE_PDF), "alice.pdf")])

    assert response.status_code == 400
    error = response.get_json()["error"]
    assert "leak" not in error
    assert error == "Internal parser error. Please try again."
