from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from backend.database import get_db
from backend.services.pdf_service import extract_text_from_pdf
from backend.services.llm_service import generate_questions
import json
import uuid

router = APIRouter()

@router.post("/create-session")
async def create_session(
    job_description: str = Form(...),
    resume: UploadFile = File(...),
    duration: int = Form(...)
):
    try:
        resume_bytes = await resume.read()
        resume_text = extract_text_from_pdf(resume_bytes)

        questions = generate_questions(job_description, resume_text, duration)

        session_id = str(uuid.uuid4())
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO interview_sessions 
                (id, job_description, resume_text, duration_seconds, questions, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                job_description,
                resume_text,
                duration,
                json.dumps(questions),
                "created"
            ))

        return {
            "session_id": session_id,
            "questions": questions,
            "duration_seconds": duration
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session/{session_id}")
async def get_session(session_id: str):
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
            
            # Convert row to dict
            session = dict(session_row)
            
            # Parse questions JSON
            if isinstance(session.get("questions"), str):
                session["questions"] = json.loads(session["questions"])
            
            # Get answers
            cursor.execute("""
                SELECT * FROM interview_answers WHERE session_id = ?
            """, (session_id,))
            answer_rows = cursor.fetchall()
            
            answers = [dict(row) for row in answer_rows]
            
            # Parse feedback JSON for each answer
            for answer in answers:
                if isinstance(answer.get("feedback"), str):
                    answer["feedback"] = json.loads(answer["feedback"])

        return {
            "session": session,
            "answers": answers
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
