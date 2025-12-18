import os
import json
import pdfplumber
import logging
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import google.generativeai as genai

# --- Setup and Configuration ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# --- Gemini Model Initialization ---
API_KEY = os.getenv("GEMINI_API_KEY")
model = None

if not API_KEY:
    logging.error("FATAL: GEMINI_API_KEY not found in .env file.")
else:
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        logging.info("Successfully initialized Gemini 1.5 Flash model.")
    except Exception as e:
        logging.error(f"FATAL: Failed to configure Gemini API. Error: {e}")

# --- Core Functions ---
def extract_text_from_pdf(file_stream):
    """Safely extracts text from a PDF file stream."""
    try:
        with pdfplumber.open(file_stream) as pdf:
            return "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
    except Exception as e:
        logging.error(f"Error during PDF extraction: {e}")
        return None

def get_gemini_response(resume_text, jd_text):
    """
    Analyzes resume using a STRICT 'Penalty-Based' protocol to ensure realistic scoring.
    """
    if not model:
        return None

    # Logic: Universal Detection + Strict Penalties
    scoring_logic = """
    SCORING ALGORITHM (STRICT PENALTY SYSTEM):
    1. **Start with a Base Score of 100.**
    2. **Detect the Target Role** (inferred from resume or provided JD).
    3. **Apply Deductions (The 'Deal Breakers'):**
       - **CRITICAL SKILL GAP (-25 points):** If the candidate is missing a FOUNDATIONAL skill for their specific role.
         * Example: 'Full Stack Dev' missing Databases (SQL/NoSQL).
         * Example: 'Data Scientist' missing Python/R.
         * Example: 'Marketer' missing SEO/Analytics.
       - **EXPERIENCE GAP (-10 points):** If bullet points are vague, generic, or lack quantifiable metrics (numbers/%).
       - **FORMATTING (-5 points):** If the layout is messy or missing basic contact info.
    4. **Final Calculation:** Score = 100 - Total Deductions. (Minimum 0).
    """

    if jd_text.strip():
        context = f"CONTEXT: Analyze the resume against this JOB DESCRIPTION: '{jd_text}'"
    else:
        context = "CONTEXT: No Job Description provided. INFER the target role from the resume content first."

    prompt = f"""
    You are a ruthless, industry-standard AI Resume Parser. 
    You have TWO mandatory tasks.

    {context}

    ---
    TASK 1: EXTRACTION
    Extract these exact details. Return "Not Found" if missing.
    - "name": Full Name
    - "email": Email Address
    - "phone": Phone Number
    - "education": List of strings (e.g., ["B.Tech CS, 2024"])
    - "skills": List of strings (All technical skills found)

    ---
    TASK 2: EVALUATION
    {scoring_logic}

    ---
    OUTPUT FORMAT (MANDATORY):
    Return ONLY a valid JSON object. Do not add markdown blocks.
    {{
        "name": "...",
        "email": "...",
        "phone": "...",
        "education": ["..."],
        "skills": ["..."],
        "match_percentage": 0,
        "detected_role": "...",
        "missing_keywords": ["..."],
        "profile_summary": "...",
        "scoring_reasoning": "Started at 100. Deducted 25 for missing SQL. Deducted 10 for vague metrics. Final: 65."
    }}

    ---
    RESUME TEXT:
    {resume_text}
    """

    try:
        # Temperature 0.0 forces consistency
        response = model.generate_content(prompt, generation_config={"temperature": 0.0})
        cleaned_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        return json.loads(cleaned_text)
    except Exception as e:
        logging.error(f"Gemini processing failed: {e}")
        return None

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/parse', methods=['POST'])
def parse_resume():
    try:
        if 'resume' not in request.files:
            return jsonify({"error": "No resume file provided"}), 400
        
        file = request.files['resume']
        jd_text = request.form.get('job_description', '')

        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        resume_text = extract_text_from_pdf(file)
        if not resume_text:
            return jsonify({"error": "Failed to read PDF"}), 400

        extracted_data = get_gemini_response(resume_text, jd_text)
        
        if not extracted_data:
            return jsonify({"error": "AI failed to process resume"}), 500

        return jsonify(extracted_data)

    except Exception as e:
        logging.error(f"Server Error: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

if __name__ == '__main__':
    app.run(debug=True)