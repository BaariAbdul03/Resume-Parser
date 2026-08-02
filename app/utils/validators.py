import re
import logging
from urllib.parse import urlparse
from typing import List
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# Make magic optional since OS-level libmagic is often missing in serverless/cloud environments
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False
    logger.warning("python-magic library could not find system libmagic. Falling back to native binary signature validation.")

def sanitize_text(text: str) -> str:
    """
    Sanitizes extracted PDF text before processing:
    - Strips null bytes
    - Strips control characters (except common whitespace like tabs, newlines, carriage returns)
    """
    if not text:
        return ""
    # Strip null bytes
    text = text.replace("\x00", "")
    # Strip control characters except whitespace (\t, \n, \r)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    return text.strip()

def validate_pdf_mime(file_stream) -> bool:
    """
    Validates a file stream's MIME type using magic number detection server-side.
    Avoids extension spoofing vulnerability.
    Uses native %PDF header check and falls back to python-magic if available.
    """
    try:
        # 1. High-speed, dependency-free binary header check
        header_4 = file_stream.read(4)
        file_stream.seek(0)  # Rewind the file stream immediately
        
        # Valid PDF files always start with %PDF
        if header_4 == b'%PDF':
            return True
            
        # 2. Fallback to magic check if the header is shifted or complex
        if HAS_MAGIC:
            header_2048 = file_stream.read(2048)
            file_stream.seek(0)  # Rewind
            mime = magic.from_buffer(header_2048, mime=True)
            logger.info(f"Magic detected MIME type: {mime}")
            return mime == 'application/pdf'
            
        logger.warning("Native signature mismatch and python-magic unavailable.")
        return False
    except Exception as e:
        logger.error(f"Error during MIME validation: {e}", exc_info=True)
        return False

# --- AI Output Validation ---

class AIAnalysisResult(BaseModel):
    name: str = Field(default="Not Found")
    email: str = Field(default="Not Found")
    phone: str = Field(default="Not Found")
    github_url: str = Field(default="Not Found")
    linkedin_url: str = Field(default="Not Found")
    education: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    match_percentage: int = Field(default=0, ge=0, le=100)
    detected_role: str = Field(default="Unknown Role")
    missing_keywords: List[str] = Field(default_factory=list)
    profile_summary: str = Field(default="")
    scoring_reasoning: str = Field(default="")

    @field_validator("github_url", mode="before")
    @classmethod
    def validate_github_url(cls, v):
        if v is None:
            return "Not Found"
        v_str = str(v).strip()
        if not v_str or v_str.lower() in ('not found', 'none', ''):
            return "Not Found"
        
        # Prevent javascript / data / vbscript protocols
        if any(v_str.lower().startswith(proto) for proto in ('javascript:', 'data:', 'vbscript:')):
            return "Not Found"
            
        url_to_parse = v_str
        if not (url_to_parse.startswith('http://') or url_to_parse.startswith('https://')):
            # If it's just a username/handle (letters, numbers, hyphens)
            if re.match(r'^[a-zA-Z0-9\-]+$', url_to_parse):
                return f"https://github.com/{url_to_parse}"
            url_to_parse = 'https://' + url_to_parse
            
        try:
            parsed = urlparse(url_to_parse)
            netloc = parsed.netloc.lower()
            if not netloc:
                return "Not Found"
            # Whitelist github.com and www.github.com
            if netloc in ('github.com', 'www.github.com'):
                return url_to_parse
            return "Not Found"
        except Exception:
            return "Not Found"

    @field_validator("linkedin_url", mode="before")
    @classmethod
    def validate_linkedin_url(cls, v):
        if v is None:
            return "Not Found"
        v_str = str(v).strip()
        if not v_str or v_str.lower() in ('not found', 'none', ''):
            return "Not Found"
            
        # Prevent javascript / data / vbscript protocols
        if any(v_str.lower().startswith(proto) for proto in ('javascript:', 'data:', 'vbscript:')):
            return "Not Found"
            
        url_to_parse = v_str
        if not (url_to_parse.startswith('http://') or url_to_parse.startswith('https://')):
            # If it's just a username/handle (letters, numbers, hyphens, underscores)
            if re.match(r'^[a-zA-Z0-9\-_]+$', url_to_parse):
                return f"https://linkedin.com/in/{url_to_parse}"
            url_to_parse = 'https://' + url_to_parse
            
        try:
            parsed = urlparse(url_to_parse)
            netloc = parsed.netloc.lower()
            if not netloc:
                return "Not Found"
            # Whitelist linkedin.com, www.linkedin.com, and regional/subdomains
            if netloc == 'linkedin.com' or netloc.endswith('.linkedin.com'):
                return url_to_parse
            return "Not Found"
        except Exception:
            return "Not Found"

    @field_validator("match_percentage", mode="before")
    @classmethod
    def parse_match_percentage(cls, v):
        if v is None:
            return 0
        if isinstance(v, str):
            v = v.replace("%", "").strip()
            match = re.search(r'\d+', v)
            if match:
                return max(0, min(100, int(match.group())))
            return 0
        try:
            # Clamp instead of raising — prevents cascading fallback for off-by-one LLM outputs
            return max(0, min(100, int(v)))
        except (ValueError, TypeError):
            return 0

    @field_validator("skills", "missing_keywords", mode="before")
    @classmethod
    def parse_list_with_split(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            if "," in v:
                return [item.strip() for item in v.split(",") if item.strip()]
            return [v.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v if item is not None]
        return []

    @field_validator("education", mode="before")
    @classmethod
    def parse_education_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            if ";" in v:
                return [item.strip() for item in v.split(";") if item.strip()]
            if "\n" in v:
                return [item.strip() for item in v.split("\n") if item.strip()]
            return [v.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v if item is not None]
        return []

    @field_validator("scoring_reasoning")
    @classmethod
    def validate_scoring_reasoning(cls, v, info):
        match_percentage = info.data.get("match_percentage")
        if not (match_percentage is not None and v):
            return v

        # ── Extract "Final: N" (last occurrence) ──────────────────────────────
        final_matches = re.findall(
            r'(?:Final(?:\s+Score)?):\s*(\d+)',
            v, re.IGNORECASE
        )
        if not final_matches:
            logger.warning(
                "validate_scoring_reasoning: no 'Final: N' pattern found. "
                "Consistency check skipped. reasoning=%r, match_percentage=%s",
                v[:120], match_percentage
            )
            return v

        final_val = int(final_matches[-1])
        if final_val != match_percentage:
            raise ValueError(
                f"Scoring consistency mismatch: match_percentage={match_percentage} "
                f"but Final in reasoning={final_val}"
            )

        # ── NEW FORMAT: D1 X/40, D2 Y/30, D3 Z/20, D4 W/10 ──────────────────
        # Pattern: "D1 Skills: 38/40" or "D1 Skills: 38"
        dim_matches = re.findall(
            r'D[1-4][^:]*:\s*(\d+)(?:/\d+)?',
            v, re.IGNORECASE
        )
        if len(dim_matches) == 4:
            dim_vals = [int(x) for x in dim_matches]
            dim_sum = sum(dim_vals)
            if dim_sum != final_val:
                raise ValueError(
                    f"Scoring arithmetic error: D1+D2+D3+D4 = {dim_vals} = {dim_sum}, "
                    f"but Final stated as {final_val}"
                )
            return v  # dimension-based check passed

        # ── LEGACY FALLBACK: Deducted N patterns (for backward compat) ────────
        deduction_matches = re.findall(
            r'(?:Deduct(?:ed)?|penalty)\s+(\d+)|-\s*(\d+)\s*(?:pts|points)',
            v, re.IGNORECASE
        )
        if deduction_matches:
            deductions = [int(m[0] or m[1]) for m in deduction_matches if (m[0] or m[1])]
            if deductions:
                expected_score = max(0, 100 - sum(deductions))
                if final_val != expected_score:
                    raise ValueError(
                        f"Scoring arithmetic error: deductions {deductions} sum={sum(deductions)}, "
                        f"expected score={expected_score}, but reasoning stated Final={final_val}"
                    )

        return v


def validate_ai_output(data: dict) -> dict:
    """
    Validates and normalizes AI analysis JSON using Pydantic.
    Raises ValidationError or ValueError if data does not conform.
    """
    validated = AIAnalysisResult(**data)
    return validated.model_dump()
