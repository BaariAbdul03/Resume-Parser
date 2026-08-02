"""
Resume parsing worker and archive persistence helpers.
=======================================================

`parse_single_resume_object` may be executed inside a ThreadPoolExecutor
worker thread that has no Flask request context. In that case the caller must
pass the Flask app object (`_app`) so the worker can push an app context —
the AI service resolves provider API keys from the app config, which is only
reachable when an app context is active.
"""

import logging

from flask import current_app

from app.extensions import db
from app.models import Analysis
from app.services.ai_service import AIService
from app.services.pdf_service import extract_text_from_pdf
from app.utils.validators import validate_pdf_mime

logger = logging.getLogger(__name__)

# Initialize the unified 3-tier AI service (Groq → Gemini 2.5 → Gemini 2.0)
ai_service = AIService()


def parse_single_resume_object(filename, stream, jd_text, _app=None):
    """
    Worker function executed in a concurrent thread.
    Performs PDF extraction and calls the AI service safely.

    `_app` (the Flask app object) must be supplied when this runs outside a
    request context (batch mode) so the AI service can read provider keys.
    """
    try:
        # Validate MIME signature
        stream.seek(0)
        if not validate_pdf_mime(stream):
            return {"filename": filename, "error": "Invalid file content. Not a valid PDF."}

        stream.seek(0)
        resume_text = extract_text_from_pdf(stream)
        if not resume_text:
            return {"filename": filename, "error": "Failed to read or extract printable text from PDF."}

        # Call unified AI service (Groq → Gemini fallback chain) under an app
        # context, which is required to resolve provider API keys from config.
        app = _app or current_app._get_current_object()
        with app.app_context():
            extracted_data = ai_service.analyze_resume(resume_text, jd_text)
        if not extracted_data:
            return {"filename": filename, "error": "AI model failed to analyze resume contents."}

        extracted_data["filename"] = filename
        return extracted_data
    except Exception as e:
        logger.error(f"Error parsing resume {filename}: {e}", exc_info=True)
        # Do not leak internal exception details to clients.
        return {"filename": filename, "error": "Internal parser error. Please try again."}


def save_analysis_result(user_id, result, target_role):
    """Persist a parse result as an Analysis row for `user_id`.

    Returns the new row id, or None when persistence fails (the parse result
    is still returned to the client either way — archiving is best-effort).
    """
    try:
        analysis = Analysis(
            user_id=user_id,
            candidate_name=result.get("name"),
            target_role=target_role or result.get("detected_role"),
            detected_role=result.get("detected_role"),
            match_percentage=result.get("match_percentage"),
            email=result.get("email"),
            phone=result.get("phone"),
            github_url=result.get("github_url"),
            linkedin_url=result.get("linkedin_url"),
            education=result.get("education"),
            skills=result.get("skills"),
            missing_keywords=result.get("missing_keywords"),
            profile_summary=result.get("profile_summary"),
            scoring_reasoning=result.get("scoring_reasoning")
        )
        db.session.add(analysis)
        db.session.commit()
        return analysis.id
    except Exception as db_err:
        db.session.rollback()
        logger.error(f"Database archive failed: {db_err}", exc_info=True)
        return None
