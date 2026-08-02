import io
import logging
from concurrent.futures import ThreadPoolExecutor

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user

from app.extensions import limiter
from app.services.parsing import parse_single_resume_object, save_analysis_result

logger = logging.getLogger(__name__)
parse_bp = Blueprint('parse', __name__)


def ensure_ai_configured():
    """Verify that at least one AI provider key is set before processing."""
    groq_key = current_app.config.get("GROQ_API_KEY")
    gemini_key = current_app.config.get("GEMINI_API_KEY")
    return bool(groq_key or gemini_key)


@parse_bp.route('/parse', methods=['POST'])
@limiter.limit("10 per minute")
def parse_resume():
    """
    Parses single or batch uploaded resumes against a job description.
    Supports up to 10 files concurrently using ThreadPoolExecutor.
    """
    try:
        if not ensure_ai_configured():
            return jsonify({
                "error": "AI parser is not configured. Please set GROQ_API_KEY or GEMINI_API_KEY in your environment."
            }), 503

        # P1.1: File presence validation
        if 'resume' not in request.files:
            return jsonify({"error": "No resume file provided"}), 400

        files = request.files.getlist("resume")
        jd_text = request.form.get('job_description', '').strip()
        selected_role = request.form.get('selected_role', '').strip()  # The role chosen from dropdown

        # P1.1: Enforce JD max character limit
        if len(jd_text) > 5000:
            return jsonify({"error": "Job description exceeds maximum allowed length of 5000 characters."}), 400

        # Read streams into memory buffers for thread safety
        file_payloads = []
        for file in files:
            if file and file.filename != '':
                if not file.filename.lower().endswith('.pdf'):
                    return jsonify({"error": f"Invalid format for '{file.filename}'. Only PDF files are accepted."}), 400

                # Buffer the stream in memory
                buffered_stream = io.BytesIO(file.read())
                file_payloads.append((file.filename, buffered_stream))

        if not file_payloads:
            return jsonify({"error": "No selected files detected"}), 400

        if len(file_payloads) > 10:
            return jsonify({"error": "Batch parsing is limited to a maximum of 10 resumes per scan."}), 400

        # Determine single vs batch execution path
        if len(file_payloads) == 1:
            filename, stream = file_payloads[0]
            result = parse_single_resume_object(filename, stream, jd_text)

            if "error" in result:
                return jsonify({"error": result["error"]}), 400

            # Save single record to database if authenticated
            if current_user.is_authenticated:
                db_id = save_analysis_result(current_user.id, result, selected_role)
                if db_id is not None:
                    result["db_id"] = db_id

            return jsonify(result)

        else:
            # Concurrently parse batch payloads using a bounded ThreadPoolExecutor.
            # Worker threads have no request context, so capture the app object and
            # hand it to each worker — it pushes its own app context for the AI call.
            app = current_app._get_current_object()
            completed_results = []
            with ThreadPoolExecutor(max_workers=min(len(file_payloads), 5)) as executor:
                futures = [
                    executor.submit(parse_single_resume_object, filename, stream, jd_text, app)
                    for filename, stream in file_payloads
                ]
                for future in futures:
                    completed_results.append(future.result())

            # Sequentially save successful analyses to the database in the main thread to avoid SQLite locking
            saved_count = 0
            if current_user.is_authenticated:
                for res in completed_results:
                    if "error" not in res:
                        db_id = save_analysis_result(current_user.id, res, selected_role)
                        if db_id is not None:
                            res["db_id"] = db_id
                            saved_count += 1

            # Sort batch results by match percentage descending (Ranked Leaderboard)
            successful_parses = [r for r in completed_results if "error" not in r]
            failed_parses = [r for r in completed_results if "error" in r]

            successful_parses.sort(key=lambda x: x.get("match_percentage", 0), reverse=True)

            # Form ranked list
            ranked_results = successful_parses + failed_parses

            return jsonify({
                "is_batch": True,
                "results": ranked_results,
                "total_processed": len(file_payloads),
                "successful_count": len(successful_parses),
                "failed_count": len(failed_parses)
            })

    except Exception as e:
        logger.error(f"Error parsing resume: {e}", exc_info=True)
        return jsonify({"error": "Internal Server Error"}), 500
