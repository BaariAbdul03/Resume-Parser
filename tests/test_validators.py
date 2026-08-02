import io
import pytest
from pydantic import ValidationError
from app.utils.validators import sanitize_text, validate_pdf_mime, validate_ai_output

def test_sanitize_text():
    """Verify text is correctly sanitized by stripping null bytes and non-printable controls."""
    # Standard text
    assert sanitize_text("Hello World") == "Hello World"
    
    # Null bytes
    assert sanitize_text("Hello\x00World") == "HelloWorld"
    
    # Control characters but keeping standard tabs and newlines
    dirty_text = "Line 1\nLine 2\t\x07Text\x1b"
    assert sanitize_text(dirty_text) == "Line 1\nLine 2\tText"
    
    # Empty cases
    assert sanitize_text("") == ""
    assert sanitize_text(None) == ""

def test_validate_pdf_mime_real_pdf():
    """Verify MIME checker correctly recognizes valid PDF signature headers."""
    # Real PDF files start with %PDF- signature
    valid_pdf_stream = io.BytesIO(b"%PDF-1.5\n%EOF")
    assert validate_pdf_mime(valid_pdf_stream) is True

def test_validate_pdf_mime_invalid():
    """Verify MIME checker correctly rejects spoofed plain text files."""
    spoofed_stream = io.BytesIO(b"Hello World, I am a plain text file")
    assert validate_pdf_mime(spoofed_stream) is False

def test_validate_ai_output_valid():
    data = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "123-456-7890",
        "github_url": "https://github.com/janedoe",
        "linkedin_url": "https://linkedin.com/in/janedoe",
        "education": ["Bachelor of Science, Stanford, 2020"],
        "skills": ["Python", "Flask"],
        "match_percentage": 54,
        "detected_role": "Software Engineer",
        "missing_keywords": ["SQL"],
        "profile_summary": "Strong candidate.",
        "scoring_reasoning": "D1 Skills: 32/40. D2 Seniority: 2/30 [ENTRY vs SENIOR]. D3 Impact: 12/20. D4 Education: 8/10. Final: 54."
    }
    validated = validate_ai_output(data)
    assert validated["name"] == "Jane Doe"
    assert validated["match_percentage"] == 54

def test_validate_ai_output_dimension_arithmetic_mismatch():
    """D1+D2+D3+D4 sum != Final should raise."""
    data = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "123-456-7890",
        "github_url": "https://github.com/janedoe",
        "linkedin_url": "https://linkedin.com/in/janedoe",
        "education": ["Bachelor of Science, Stanford, 2020"],
        "skills": ["Python", "Flask"],
        "match_percentage": 60,
        "detected_role": "Software Engineer",
        "missing_keywords": ["SQL"],
        "profile_summary": "Strong candidate.",
        # D1+D2+D3+D4 = 32+2+12+8 = 54, but Final says 60
        "scoring_reasoning": "D1 Skills: 32/40. D2 Seniority: 2/30. D3 Impact: 12/20. D4 Education: 8/10. Final: 60."
    }
    with pytest.raises(ValidationError):
        validate_ai_output(data)

def test_validate_ai_output_coercion():
    data = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "123-456-7890",
        "github_url": "https://github.com/janedoe",
        "linkedin_url": "https://linkedin.com/in/janedoe",
        "education": "Bachelor of Science, Stanford, 2020",
        "skills": ["Python", None],
        "match_percentage": " 85% ",
        "detected_role": "Software Engineer",
        "missing_keywords": "SQL, Git",
        "profile_summary": "Strong candidate.",
        "scoring_reasoning": "D1 Skills: 40/40. D2 Seniority: 20/30 [MID vs SENIOR]. D3 Impact: 15/20. D4 Education: 10/10. Final: 85."
    }
    validated = validate_ai_output(data)
    assert validated["education"] == ["Bachelor of Science, Stanford, 2020"]
    assert validated["skills"] == ["Python"]
    assert validated["match_percentage"] == 85
    assert validated["missing_keywords"] == ["SQL", "Git"]

def test_validate_ai_output_mismatch():
    """match_percentage != Final in reasoning should raise."""
    data = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "123-456-7890",
        "github_url": "https://github.com/janedoe",
        "linkedin_url": "https://linkedin.com/in/janedoe",
        "education": ["Bachelor of Science, Stanford, 2020"],
        "skills": ["Python"],
        "match_percentage": 80,
        "detected_role": "Software Engineer",
        "missing_keywords": ["SQL"],
        "profile_summary": "Strong candidate.",
        "scoring_reasoning": "D1 Skills: 30/40. D2 Seniority: 30/30. D3 Impact: 15/20. D4 Education: 10/10. Final: 85."
    }
    with pytest.raises(ValidationError):
        validate_ai_output(data)

def test_validate_ai_output_urls():
    """Verify whitelisting and protocol safety rules for candidate links."""
    base_data = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "123-456-7890",
        "education": ["Stanford"],
        "skills": ["Python"],
        "match_percentage": 85,
        "detected_role": "Software Engineer",
        "missing_keywords": [],
        "profile_summary": "Summary.",
        "scoring_reasoning": "Final: 85"
    }

    # 1. Unsafe javascript URI scheme
    data1 = base_data.copy()
    data1["github_url"] = "javascript:alert(1)"
    data1["linkedin_url"] = "javascript:alert(1)"
    validated1 = validate_ai_output(data1)
    assert validated1["github_url"] == "Not Found"
    assert validated1["linkedin_url"] == "Not Found"

    # 2. Non-whitelisted domain URIs
    data2 = base_data.copy()
    data2["github_url"] = "http://evil.test/p"
    data2["linkedin_url"] = "https://evil.test/p"
    validated2 = validate_ai_output(data2)
    assert validated2["github_url"] == "Not Found"
    assert validated2["linkedin_url"] == "Not Found"

    # 3. Whitelisted domains but standard URLs
    data3 = base_data.copy()
    data3["github_url"] = "https://github.com/octocat"
    data3["linkedin_url"] = "https://www.linkedin.com/in/octocat"
    validated3 = validate_ai_output(data3)
    assert validated3["github_url"] == "https://github.com/octocat"
    assert validated3["linkedin_url"] == "https://www.linkedin.com/in/octocat"

    # 4. Username fallbacks auto-normalization
    data4 = base_data.copy()
    data4["github_url"] = "octocat"
    data4["linkedin_url"] = "octocat-handle"
    validated4 = validate_ai_output(data4)
    assert validated4["github_url"] == "https://github.com/octocat"
    assert validated4["linkedin_url"] == "https://linkedin.com/in/octocat-handle"
