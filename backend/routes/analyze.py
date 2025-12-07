from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from backend.database import get_db

from backend.services.llm_service import evaluate_answer, generate_reference_answer
from backend.services.export_service import generate_pdf_report
import json
import time

router = APIRouter()



@router.post("/analyze/{session_id}")
async def analyze_session(session_id: str):
    """
    Analyzes all answers for a given session. For each unanswered score:
    1) Generates a reference (ideal) answer per question (cached per question_id).
    2) Evaluates the candidate transcript against the reference using evaluate_answer(...).
    Persists: score, feedback (JSON), model_answer (reference).
    """
    max_db_retries = 3
    retry_count = 0
    
    while retry_count < max_db_retries:
        try:
            with get_db() as conn:
                cursor = conn.cursor()

                # --- Fetch session ---
                cursor.execute("""
                    SELECT * FROM interview_sessions WHERE id = ?
                """, (session_id,))
                session_row = cursor.fetchone()

                if not session_row:
                    raise HTTPException(status_code=404, detail="Session not found")

                session = dict(session_row)

                # Parse questions JSON if needed
                if isinstance(session.get("questions"), str) and session["questions"]:
                    session["questions"] = json.loads(session["questions"])

                if not session.get("questions"):
                    # No questions -> mark analyzed and return success
                    cursor.execute("""
                        UPDATE interview_sessions 
                        SET status = 'analyzed'
                        WHERE id = ?
                    """, (session_id,))
                    return {"status": "success", "message": "Analysis complete"}

                # Try to get JD/Resume text if present; fall back to empty strings
                jd_text = (
                    session.get("job_description")
                    or session.get("jd")
                    or session.get("jd_text")
                    or ""
                )
                resume_text = (
                    session.get("resume_text")
                    or session.get("resume")
                    or session.get("resume_content")
                    or ""
                )

                # --- Fetch answers ---
                cursor.execute("""
                    SELECT * FROM interview_answers WHERE session_id = ?
                """, (session_id,))
                answer_rows = cursor.fetchall()
                answers = [dict(row) for row in answer_rows]

                # --- Cache to avoid regenerating the same reference answer per question ---
                reference_cache = {}  # {question_id: reference_answer}

                # Helper to get question text by id
                q_text_by_id = {q["id"]: q.get("text", "") for q in session["questions"]}

                # --- Evaluate answers that don't have scores yet ---
                for answer in answers:
                    # Skip if already scored or no transcript
                    if answer.get("score") is not None or not answer.get("transcript"):
                        continue

                    qid = answer.get("question_id")
                    question_text = q_text_by_id.get(qid, "")

                    if not question_text:
                        # Question not found in session questions; skip gracefully
                        continue

                    # Get or create the reference answer for this question
                    try:
                        if qid not in reference_cache:
                            # NOTE: Assumes you have implemented generate_reference_answer(question, jd, resume)
                            reference_cache[qid] = generate_reference_answer(
                                question=question_text,
                                jd=jd_text,
                                resume=resume_text
                            )
                        reference_answer = reference_cache[qid]
                    except Exception as ref_err:
                        # If reference generation fails, skip evaluation for this answer
                        print(f"Error generating reference for question {qid}: {ref_err}")
                        continue

                    # Evaluate against reference
                    try:
                        # NOTE: Assumes your updated evaluate_answer(question, transcript, reference_answer)
                        evaluation = evaluate_answer(
                            question=question_text,
                            transcript=answer["transcript"],
                            reference_answer=reference_answer
                        )

                        if not isinstance(evaluation, dict):
                            raise ValueError(f"Invalid evaluation response: {evaluation}")

                        # Prefer 'total_score' if provided, else fallback to 'score'
                        score = evaluation.get("total_score")
                        if score is None:
                            score = evaluation.get("score")

                        # Ensure feedback is a list
                        feedback = evaluation.get("feedback", [])
                        if not isinstance(feedback, list):
                            feedback = [feedback] if feedback else []

                        # Store the reference (ideal) answer in model_answer column
                        model_answer = reference_answer or evaluation.get("model_answer", "")

                        cursor.execute("""
                            UPDATE interview_answers
                            SET score = ?, feedback = ?, model_answer = ?
                            WHERE id = ?
                        """, (
                            score,
                            json.dumps(feedback, ensure_ascii=False),
                            model_answer,
                            answer["id"]
                        ))

                    except Exception as eval_error:
                        # Log and continue with other answers
                        print(f"Error evaluating answer {answer.get('id')}: {str(eval_error)}")
                        continue

                # --- Update session status (after all answers processed) ---
                cursor.execute("""
                    UPDATE interview_sessions
                    SET status = 'analyzed'
                    WHERE id = ?
                """, (session_id,))
            
            # Success - break out of retry loop
            return {"status": "success", "message": "Analysis complete"}
            
        except Exception as db_error:
            retry_count += 1
            if retry_count >= max_db_retries:
                # If it's an HTTPException, re-raise it
                if isinstance(db_error, HTTPException):
                    raise db_error
                raise HTTPException(
                    status_code=500,
                    detail=f"Database error during analysis after {max_db_retries} retries: {str(db_error)}"
                )
            # Wait before retrying (exponential backoff)
            time.sleep(0.2 * retry_count)
    
    # Should not reach here, but just in case
    raise HTTPException(status_code=500, detail="Analysis failed after retries")




@router.get("/export-pdf/{session_id}")
async def export_pdf(session_id: str):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get session
            cursor.execute("""
                SELECT * FROM interview_sessions WHERE id = ?
            """, (session_id,))
            session_row = cursor.fetchone()
            
            if not session_row:
                raise HTTPException(status_code=404, detail="Session not found")
            
            session = dict(session_row)

            if isinstance(session.get("questions"), str):
                session["questions"] = json.loads(session["questions"])

            # Get answers
            cursor.execute("""
                SELECT * FROM interview_answers WHERE session_id = ?
            """, (session_id,))
            answer_rows = cursor.fetchall()
            
            answers = [dict(row) for row in answer_rows]

            for answer in answers:
                if isinstance(answer.get("feedback"), str):
                    answer["feedback"] = json.loads(answer["feedback"])

        pdf_bytes = generate_pdf_report(session, answers)

        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=interview_results_{session_id[:8]}.pdf"}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
