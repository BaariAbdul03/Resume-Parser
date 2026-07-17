import json
from unittest.mock import MagicMock, patch
import pytest
from google.api_core.exceptions import GoogleAPIError
from app.services.ai_service import GeminiService, AIService


@pytest.fixture
def gemini_service():
    """Create a test gemini service instance with mock setup."""
    svc = GeminiService()
    svc._configured = True
    return svc


def test_analyze_resume_success(gemini_service):
    """Verify successful parsing returns parsed JSON dictionary."""
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1 234 567",
        "github_url": "https://github.com/janedoe",
        "linkedin_url": "https://linkedin.com/in/janedoe",
        "education": ["B.Tech — CS, MIT, 2022"],
        "skills": ["Python", "Flask"],
        "match_percentage": 85,
        "detected_role": "Full Stack Dev",
        "missing_keywords": ["SQL"],
        "profile_summary": "Summary...",
        "scoring_reasoning": "Started at 100. Deducted 15 for missing SQL. Final: 85."
    })
    
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    
    with patch.object(gemini_service, "_call", return_value=json.loads(mock_response.text)):
        results = gemini_service.analyze("Resume content...", "JD...")
        assert results["name"] == "Jane Doe"
        assert results["match_percentage"] == 85
        assert "jane@example.com" in results["email"]


def test_gemini_resiliency_backoff_success(gemini_service):
    """Verify service retries on transient errors and succeeds."""
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1 234 567",
        "github_url": "https://github.com/janedoe",
        "linkedin_url": "https://linkedin.com/in/janedoe",
        "education": ["B.Tech — CS, MIT, 2022"],
        "skills": ["Python", "Flask"],
        "match_percentage": 90,
        "detected_role": "Full Stack Dev",
        "missing_keywords": [],
        "profile_summary": "Summary...",
        "scoring_reasoning": "Started at 100. Deducted 10 for vague metrics. Final: 90."
    })
    
    # Mocking _call to throw exception twice, then return success on 3rd attempt
    mock_call = MagicMock(side_effect=[
        GoogleAPIError("Quota exceeded"),
        GoogleAPIError("Temporary unavailable"),
        json.loads(mock_response.text)
    ])
    
    with patch.object(gemini_service, "_call", mock_call):
        with patch("app.services.ai_service.time.sleep") as mock_sleep: # Fast mock sleep
            results = gemini_service.analyze("Resume content...", "JD...")
            assert results["name"] == "Jane Doe"
            assert mock_sleep.call_count == 2


def test_gemini_fallback_model(gemini_service):
    """Verify primary model total failure triggers the fallback model."""
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1 234 567",
        "github_url": "https://github.com/janedoe",
        "linkedin_url": "https://linkedin.com/in/janedoe",
        "education": ["B.Tech — CS, MIT, 2022"],
        "skills": ["Python", "Flask"],
        "match_percentage": 75,
        "detected_role": "Full Stack Dev",
        "missing_keywords": [],
        "profile_summary": "Summary...",
        "scoring_reasoning": "Started at 100. Deducted 25. Final: 75."
    })
    
    def mock_call(prompt, model_name):
        if model_name == gemini_service.PRIMARY_MODEL:
            raise GoogleAPIError("Unavailable")
        return json.loads(mock_response.text)

    with patch.object(gemini_service, "_call", side_effect=mock_call):
        with patch("app.services.ai_service.time.sleep"):
            results = gemini_service.analyze("Resume content...", "JD...")
            assert results["name"] == "Jane Doe"
            assert results["match_percentage"] == 75


def test_ai_service_facade_fallback():
    """Verify AIService runs Groq primary, and falls back to Gemini on error."""
    ai_service = AIService()
    
    mock_result = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1 234 567",
        "github_url": "https://github.com/janedoe",
        "linkedin_url": "https://linkedin.com/in/janedoe",
        "education": ["B.Tech — CS, MIT, 2022"],
        "skills": ["Python", "Flask"],
        "match_percentage": 95,
        "detected_role": "Full Stack Dev",
        "missing_keywords": [],
        "profile_summary": "Summary...",
        "scoring_reasoning": "Started at 100. Deducted 5. Final: 95."
    }

    # Case 1: Groq succeeds
    with patch.object(ai_service._groq, "analyze", return_value=mock_result) as mock_groq:
        with patch.object(ai_service._gemini, "analyze") as mock_gemini:
            res = ai_service.analyze_resume("Resume...", "JD...")
            assert res["name"] == "Jane Doe"
            assert res["match_percentage"] == 95
            mock_groq.assert_called_once()
            mock_gemini.assert_not_called()

    # Case 2: Groq fails, falls back to Gemini
    with patch.object(ai_service._groq, "analyze", side_effect=Exception("Groq offline")):
        with patch.object(ai_service._gemini, "analyze", return_value=mock_result) as mock_gemini:
            res = ai_service.analyze_resume("Resume...", "JD...")
            assert res["name"] == "Jane Doe"
            assert res["match_percentage"] == 95
            mock_gemini.assert_called_once()
