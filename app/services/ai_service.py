"""
Unified AI Resume Analysis Service
====================================
3-Tier resilient AI pipeline:
  1. Groq (Llama 4 Scout)      – Primary   – Free, fast, generous limits
  2. Gemini 2.5 Flash           – Secondary – Fallback if Groq unavailable
  3. Gemini 2.0 Flash           – Tertiary  – Last resort

The service automatically cascades down the chain on quota errors (429),
connection failures, or invalid JSON responses.
"""

import json
import logging
import time
import re

from flask import current_app, has_app_context
from app.utils.validators import validate_ai_output

logger = logging.getLogger(__name__)

MAX_RESUME_TEXT_CHARS = 30_000


# ---------------------------------------------------------------------------
# Shared prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(resume_text: str, jd_text: str) -> str:
    truncated = resume_text[:MAX_RESUME_TEXT_CHARS]
    if len(resume_text) > MAX_RESUME_TEXT_CHARS:
        truncated += "\n\n[Resume text truncated for processing safety.]"

    if jd_text.strip():
        # ── JD-AWARE MODE: Score the candidate against the specified role ────
        context_block = f"""RECRUITER'S TARGET ROLE & JOB DESCRIPTION:
\"\"\"
{jd_text.strip()}
\"\"\"

YOUR MISSION: Evaluate how well this candidate fits the TARGET ROLE described above.
- "detected_role" MUST be the TARGET ROLE extracted from the job description above — NOT the candidate's current job title.
- Score the candidate's skills and experience SPECIFICALLY against the requirements in the JD.
- Identify which required skills from the JD are MISSING from the resume as "missing_keywords"."""

        scoring_logic = """
SCORING ALGORITHM (JD-MATCHED PENALTY SYSTEM):
1. Start with a Base Score of 100.
2. The target role is DEFINED by the Job Description above — use it directly.
3. Apply Deductions based on gaps between the CANDIDATE'S RESUME and the JD REQUIREMENTS:
   - CRITICAL SKILL GAP (-25 pts each): The JD explicitly requires a skill that is completely absent from the resume.
     * Example: JD requires Python/R for Data Scientist role, candidate has none.
     * Example: JD requires React/TypeScript for Frontend Engineer, candidate has none.
   - EXPERIENCE GAP (-10 pts): Bullet points are vague, generic, or lack quantifiable metrics (numbers/%).
   - FORMATTING (-5 pts): Layout is messy or missing basic contact info.
4. Final Score = 100 - Total Deductions. (Minimum 0.)"""
    else:
        # ── INFERENCE MODE: No JD, detect role from resume content ──────────
        context_block = """NO JOB DESCRIPTION PROVIDED.
YOUR MISSION: Infer the candidate's target role from their resume content, skills, and experience.
- "detected_role" MUST be the role you infer from the resume content.
- Score the candidate against typical industry standards for their detected role.
- Identify commonly expected skills for that role that are missing as "missing_keywords"."""

        scoring_logic = """
SCORING ALGORITHM (INFERRED ROLE PENALTY SYSTEM):
1. Start with a Base Score of 100.
2. Infer the Target Role from the resume (job titles, skills, experience context).
3. Apply Deductions based on gaps for the INFERRED ROLE:
   - CRITICAL SKILL GAP (-25 pts): Missing a FOUNDATIONAL skill for their inferred role.
     * Example: 'Full Stack Dev' missing Databases (SQL/NoSQL).
     * Example: 'Data Scientist' missing Python/R.
   - EXPERIENCE GAP (-10 pts): Bullet points are vague, generic, or lack quantifiable metrics.
   - FORMATTING (-5 pts): Layout is messy or missing basic contact info.
4. Final Score = 100 - Total Deductions. (Minimum 0.)"""

    return f"""You are a senior technical recruiter and ruthless AI Resume Parser performing a precise candidate evaluation.

{context_block}

---
TASK 1: DATA EXTRACTION
Extract the following fields from the resume. Return "Not Found" if a field is absent.
- "name": Candidate's full name
- "email": Email address
- "phone": Phone number
- "github_url": GitHub profile URL (full URL like https://github.com/username). Return "Not Found" if absent.
- "linkedin_url": LinkedIn profile URL (full URL like https://linkedin.com/in/username). Return "Not Found" if absent.
- "education": List of strings, each formatted as: "Degree — Field of Study (Score%), Institution, Year"
- "skills": Complete list of all technical skills mentioned anywhere in the resume

---
TASK 2: JD-MATCHED EVALUATION
{scoring_logic}

MANDATORY CONSISTENCY RULE: The numeric value in "match_percentage" MUST EXACTLY EQUAL the final score
stated at the end of "scoring_reasoning". Example: if reasoning ends with "Final: 65", then match_percentage must be 65.
Any mismatch between these two fields is a critical error.

---
OUTPUT FORMAT (MANDATORY — return ONLY this JSON, no markdown, no extra text):
{{
    "name": "...",
    "email": "...",
    "phone": "...",
    "github_url": "...",
    "linkedin_url": "...",
    "education": ["Degree — Field (Score%), Institution, Year"],
    "skills": ["skill1", "skill2"],
    "match_percentage": 75,
    "detected_role": "EXACT TARGET ROLE from JD (or inferred role if no JD)",
    "missing_keywords": ["required skill from JD that is absent in resume"],
    "profile_summary": "2-3 sentence evaluation of candidate fit for the target role",
    "scoring_reasoning": "Started at 100. Deducted X for [specific gap]. Deducted Y for [specific gap]. Final: Z."
}}

---
RESUME TEXT TO ANALYSE:
{truncated}""".strip()


def _clean_json_response(text: str) -> dict:
    """Strip markdown fences and parse JSON robustly."""
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ``` fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    return json.loads(text)


# ---------------------------------------------------------------------------
# Tier 1 – Groq (Llama)
# ---------------------------------------------------------------------------

class GroqService:
    """Groq-backed resume analysis using Llama 4 Scout with JSON mode."""

    PRIMARY_MODEL = "llama-3.3-70b-versatile"
    FALLBACK_MODEL = "llama-3.1-8b-instant"

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client:
            return self._client
        try:
            from groq import Groq  # lazy import — only needed if Groq is configured
        except ImportError:
            raise RuntimeError("groq package is not installed. Add 'groq' to requirements.txt.")

        api_key = None
        if has_app_context():
            api_key = current_app.config.get("GROQ_API_KEY")

        if not api_key:
            raise ValueError("GROQ_API_KEY is not configured.")

        self._client = Groq(api_key=api_key)
        return self._client

    def _call(self, prompt: str, model: str) -> dict:
        client = self._get_client()
        logger.info(f"[Groq] Calling model={model}")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert AI resume parser and senior technical recruiter. "
                        "You evaluate candidate resumes against specific job descriptions. "
                        "CRITICAL RULE: When a Job Description is provided, the 'detected_role' field in your JSON "
                        "output MUST contain the TARGET ROLE from the job description — never the candidate's current job title. "
                        "Always respond with a single valid JSON object matching the schema given by the user. "
                        "Never add commentary, markdown fences, or extra text outside the JSON object."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        raw = response.choices[0].message.content
        return _clean_json_response(raw)


    def analyze(self, resume_text: str, jd_text: str) -> dict:
        prompt = _build_prompt(resume_text, jd_text)
        try:
            return self._call(prompt, self.PRIMARY_MODEL)
        except Exception as e:
            logger.warning(f"[Groq] Primary model failed ({e}). Trying fallback.")
            return self._call(prompt, self.FALLBACK_MODEL)


# ---------------------------------------------------------------------------
# Tier 2 & 3 – Gemini
# ---------------------------------------------------------------------------

class GeminiService:
    """Gemini-backed resume analysis (secondary / tertiary fallback)."""

    PRIMARY_MODEL = "gemini-2.5-flash-preview-05-20"
    FALLBACK_MODEL = "gemini-2.0-flash"

    def __init__(self):
        self._configured = False

    def _ensure_configured(self):
        if self._configured:
            return
        try:
            import google.generativeai as genai  # noqa
        except ImportError:
            raise RuntimeError("google-generativeai is not installed.")

        api_key = None
        if has_app_context():
            api_key = current_app.config.get("GEMINI_API_KEY")

        if not api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")

        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._configured = True

    def _call(self, prompt: str, model_name: str) -> dict:
        import google.generativeai as genai
        self._ensure_configured()
        logger.info(f"[Gemini] Calling model={model_name}")

        timeout = 30.0
        if has_app_context():
            timeout = float(current_app.config.get("GEMINI_TIMEOUT", 30.0))

        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.0},
            request_options={"timeout": timeout},
        )
        if not response or not response.text:
            raise ValueError("Empty response from Gemini API.")
        return _clean_json_response(response.text)

    def analyze(self, resume_text: str, jd_text: str, model_name: str = None) -> dict:
        model = model_name or self.PRIMARY_MODEL
        prompt = _build_prompt(resume_text, jd_text)
        retries = 2
        delay = 1.0
        last_error = None

        for attempt in range(retries + 1):
            try:
                return self._call(prompt, model)
            except Exception as e:
                last_error = e
                logger.warning(f"[Gemini] model={model} attempt {attempt + 1} failed: {e}")
                if attempt < retries:
                    time.sleep(delay)
                    delay *= 2.0

        # Try fallback Gemini model if primary failed
        if model == self.PRIMARY_MODEL:
            logger.warning(f"[Gemini] Switching to fallback model {self.FALLBACK_MODEL}")
            return self.analyze(resume_text, jd_text, model_name=self.FALLBACK_MODEL)

        raise last_error


# ---------------------------------------------------------------------------
# Unified Facade  ← this is what the rest of the app imports
# ---------------------------------------------------------------------------

class AIService:
    """
    3-Tier AI facade:
      Tier 1 → Groq (Llama 4 Scout)     [primary, fastest, free quota]
      Tier 2 → Gemini 2.5 Flash          [secondary]
      Tier 3 → Gemini 2.0 Flash          [last resort]

    Falls back automatically on any error.
    """

    def __init__(self):
        self._groq = GroqService()
        self._gemini = GeminiService()

    def analyze_resume(self, resume_text: str, jd_text: str = "") -> dict:
        """Public entry point — tries Groq first, cascades to Gemini on failure."""

        # ── Tier 1: Groq ────────────────────────────────────────────────────
        try:
            result = self._groq.analyze(resume_text, jd_text)
            validated = validate_ai_output(result)
            logger.info("[AIService] Analysis completed via Groq (Tier 1).")
            return validated
        except Exception as groq_err:
            logger.warning(f"[AIService] Groq failed or output invalid: {groq_err}. Falling back to Gemini.")

        # ── Tier 2 + 3: Gemini (handles its own internal fallback) ──────────
        try:
            result = self._gemini.analyze(resume_text, jd_text)
            validated = validate_ai_output(result)
            logger.info("[AIService] Analysis completed via Gemini (Tier 2/3).")
            return validated
        except Exception as gemini_err:
            logger.error(f"[AIService] All AI providers exhausted or invalid. Final error: {gemini_err}", exc_info=True)
            raise RuntimeError(
                f"All AI providers are currently unavailable or returned invalid schemas. Please try again later. "
                f"Last error: {gemini_err}"
            )
