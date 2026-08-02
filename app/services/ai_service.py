"""
Unified AI Resume Analysis Service
====================================
3-Tier resilient AI pipeline:
  1. Groq (Llama 3.3 70B)          – Primary   – Free, fast, generous limits
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
SCORING RUBRIC — 4 DIMENSIONS, MAX 100 POINTS TOTAL:
Do NOT start from 100 and deduct. Instead EARN points across 4 dimensions:

D1 — SKILLS MATCH (max 40 pts)
  Count the EXPLICIT required skills listed in the Job Description above.
  Points = (skills_present_in_resume / total_required_skills_in_JD) × 40.
  Round to nearest integer.
  CRITICAL DOMAIN RULE: Do NOT award D1 points for generic skills (like HTML/CSS/Python) if the role requires specialized domain tools (e.g. Figma/wireframing for UX/UI, CRM/Salesforce for Sales, Terraform/Kubernetes for DevOps, PyTorch/Tableau for Data Science).
  If the candidate lacks ALL specialized domain tools/skills required by the role, D1 MUST BE 0/40.

D2 — SENIORITY / EXPERIENCE MATCH (max 30 pts) — THE HARDEST GATE
  Step 1: Determine REQUIRED seniority from the JD title and language:
    - “Intern / Fresher / Graduate / Trainee / Entry-Level” → ENTRY (0–2 yr expected)
    - “Junior / Associate” → JUNIOR (1–3 yr expected)
    - “Mid-Level / Intermediate / (no modifier)” → MID (3–5 yr expected)
    - “Senior / Staff / Principal” → SENIOR (5+ yr expected)
    - “Lead / Architect / Director / VP” → LEAD (8+ yr expected)
  Step 2: Assess CANDIDATE’S actual experience level from resume dates/context:
    - Still in college / graduation year ≥ current year → ENTRY
    - Graduated ≤ 2 years ago AND first real job → JUNIOR
    - 2–5 years of professional work history → MID
    - 5+ years of professional work history → SENIOR
    - 8+ years or explicit leadership/architecture roles → LEAD
  Step 3: Award D2 points:
    | Gap (Required vs Candidate)       | D2 Points |
    | Exact match or overqualified      |     30    |
    | 1 level below required            |     18    |
    | 2 levels below required           |      8    |
    | 3+ levels below (e.g. ENTRY → SENIOR) |  2    |

D3 — IMPACT / PROJECT QUALITY (max 20 pts)
  Assess evidence of real-world contribution:
    - Multiple quantified achievements using numbers/%, AND professional work (not just courses):→ 18–20 pts
    - Some quantified results OR one significant professional project with metrics:→ 12–15 pts
    - Only academic / personal projects, no production scale, no metrics:→ 5–8 pts
    - Pure skills list or course certifications only, no evidence of building anything:→ 0–2 pts

D4 — EDUCATION FIT (max 10 pts)
  - Degree directly relevant to the role (CS/EE for Engineering, etc.):→ 9–10 pts
  - Related field or ongoing relevant degree:→ 6–8 pts
  - Unrelated degree but relevant certifications present:→ 3–5 pts
  - No degree and no relevant certs:→ 0–2 pts

FINAL SCORE = D1 + D2 + D3 + D4  (must be between 0 and 100)"""

    else:
        # ── INFERENCE MODE: No JD, detect role from resume content ──────────
        context_block = """NO JOB DESCRIPTION PROVIDED.
YOUR MISSION: Infer the candidate's target role from their resume content, skills, and experience.
- "detected_role" MUST be the role you infer from the resume content (include realistic seniority, e.g. "Junior Frontend Engineer" or "Mid-Level Data Scientist").
- Score the candidate against TYPICAL INDUSTRY STANDARDS for their inferred role AND their inferred seniority level.
- Identify commonly expected skills for that role that are missing as "missing_keywords"."""

        scoring_logic = """
SCORING RUBRIC — 4 DIMENSIONS, MAX 100 POINTS TOTAL:
Do NOT start from 100 and deduct. Instead EARN points across 4 dimensions:

D1 — SKILLS MATCH (max 40 pts)
  Identify the foundational skills typically required for the inferred role.
  Points = (skills_present_in_resume / typical_required_skills_for_role) × 40. Cap at 40.
  CRITICAL DOMAIN RULE: Candidate MUST possess specialized domain tools for the role to get D1 points. If candidate lacks core domain tools, D1 MUST BE 0/40.

D2 — SENIORITY / EXPERIENCE MATCH (max 30 pts)
  Step 1: Assess candidate's actual experience level from resume:
    - Still in college / graduation year ≥ current year → ENTRY
    - Graduated ≤ 2 years ago, first real job → JUNIOR
    - 2–5 years professional history → MID
    - 5+ years professional history → SENIOR
    - 8+ years or explicit leadership/architecture roles → LEAD
  Step 2: The inferred "detected_role" MUST reflect this assessed level.
  Step 3: Since the detected role matches assessed level by definition, D2 should be 24–30
    (slight deduction only if the skills tell a different seniority story than the years).

D3 — IMPACT / PROJECT QUALITY (max 20 pts)
    - Multiple quantified achievements in professional roles: 18–20 pts
    - Some metrics OR significant professional project: 12–15 pts
    - Only academic/personal projects, no metrics: 5–8 pts
    - Pure skills list, no evidence of building: 0–2 pts

D4 — EDUCATION FIT (max 10 pts)
  - Degree relevant to inferred role: 9–10 pts
  - Related field or in-progress degree: 6–8 pts
  - Unrelated degree + certs: 3–5 pts
  - No degree, no certs: 0–2 pts

FINAL SCORE = D1 + D2 + D3 + D4  (must be between 0 and 100)"""

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

MANDATORY CONSISTENCY & ARITHMETIC RULE:
1. Compute D1, D2, D3, D4 scores. Add them: TOTAL = D1 + D2 + D3 + D4.
2. Set "match_percentage" = TOTAL. Do NOT choose match_percentage independently — it MUST be the arithmetic sum.
3. Show all dimension scores in "scoring_reasoning" in this exact format:
   "D1 Skills: X/40. D2 Seniority: Y/30 [candidate-level vs required-level]. D3 Impact: Z/20. D4 Education: W/10. Final: TOTAL."
4. Final in scoring_reasoning MUST equal TOTAL which MUST equal match_percentage. All three must be identical.
Any mismatch is a critical error — recompute before outputting.

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
    "scoring_reasoning": "D1 Skills: 38/40. D2 Seniority: 2/30 [ENTRY vs SENIOR required]. D3 Impact: 6/20. D4 Education: 8/10. Final: 54."
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
    """Groq-backed resume analysis using Llama 3.3 70B with JSON mode."""

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
    """Gemini-backed resume analysis (secondary / tertiary fallback).

    Model names, retry count, and timeout are read from app config at call
    time (GEMINI_MODEL, GEMINI_FALLBACK_MODEL, GEMINI_RETRIES, GEMINI_TIMEOUT),
    falling back to the defaults below when no app context is active.
    """

    PRIMARY_MODEL = "gemini-2.5-flash"
    FALLBACK_MODEL = "gemini-2.0-flash"
    DEFAULT_RETRIES = 2

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
        if has_app_context():
            primary = current_app.config.get("GEMINI_MODEL") or self.PRIMARY_MODEL
            fallback = current_app.config.get("GEMINI_FALLBACK_MODEL") or self.FALLBACK_MODEL
            retries = int(current_app.config.get("GEMINI_RETRIES") or self.DEFAULT_RETRIES)
        else:
            primary, fallback, retries = self.PRIMARY_MODEL, self.FALLBACK_MODEL, self.DEFAULT_RETRIES

        model = model_name or primary
        prompt = _build_prompt(resume_text, jd_text)
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
        if model == primary:
            logger.warning(f"[Gemini] Switching to fallback model {fallback}")
            return self.analyze(resume_text, jd_text, model_name=fallback)

        raise last_error


# ---------------------------------------------------------------------------
# Unified Facade  ← this is what the rest of the app imports
# ---------------------------------------------------------------------------

class AIService:
    """
    3-Tier AI facade:
      Tier 1 → Groq (Llama 3.3 70B)     [primary, fastest, free quota]
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
        groq_err_for_log = None
        try:
            result = self._groq.analyze(resume_text, jd_text)
            validated = validate_ai_output(result)
            logger.info("[AIService] Analysis completed via Groq (Tier 1).")
            return validated
        except Exception as groq_err:
            groq_err_for_log = groq_err
            logger.warning(f"[AIService] Groq failed or output invalid: {groq_err}. Falling back to Gemini.")

        # ── Tier 2 + 3: Gemini (handles its own internal fallback) ──────────
        try:
            result = self._gemini.analyze(resume_text, jd_text)
            validated = validate_ai_output(result)
            logger.info("[AIService] Analysis completed via Gemini (Tier 2/3).")
            # Surface that a fallback occurred so callers can observe it in logs/responses.
            validated["_validation_fallback"] = True
            validated["_fallback_reason"] = str(groq_err_for_log)
            return validated
        except Exception as gemini_err:
            logger.error(f"[AIService] All AI providers exhausted or invalid. Final error: {gemini_err}", exc_info=True)
            raise RuntimeError(
                f"All AI providers are currently unavailable or returned invalid schemas. Please try again later. "
                f"Last error: {gemini_err}"
            )
