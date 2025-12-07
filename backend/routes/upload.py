from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.database import get_db
from backend.services.transcription_service import transcribe_audio
from pathlib import Path
import os
import uuid
import shutil
import time

# Get project root directory
project_root = Path(__file__).parent.parent.parent
uploads_dir = project_root / "uploads"

router = APIRouter()

@router.post("/upload-answer/{session_id}/{question_id}")
async def upload_answer(
    session_id: str,
    question_id: str,
    audio: UploadFile = File(...)
):
    file_path = None
    temp_file_path = None
    
    try:
        # Ensure uploads directory exists
        os.makedirs(str(uploads_dir), exist_ok=True)

        # Read audio content first
        content = await audio.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty audio file received")

        # Write to temporary file first to avoid partial writes
        file_extension = audio.filename.split(".")[-1] if "." in audio.filename else "webm"
        filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = uploads_dir / filename
        
        # Use temporary file to ensure atomic write
        temp_file_path = uploads_dir / f"{filename}.tmp"
        
        try:
            with open(str(temp_file_path), "wb") as f:
                f.write(content)
            
            # Atomic move (rename) - this is safer on Windows
            if os.path.exists(str(file_path)):
                os.remove(str(file_path))
            shutil.move(str(temp_file_path), str(file_path))
            temp_file_path = None  # Mark as successfully moved
        except (IOError, OSError) as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to save audio file: {str(e)}"
            )

        # Transcribe audio
        try:
            transcript = transcribe_audio(str(file_path))
        except Exception as e:
            # If transcription fails, still save the audio but with empty transcript
            transcript = ""
            print(f"Transcription failed for {file_path}: {str(e)}")

        # Store relative path for web access (just the filename)
        audio_path_relative = f"uploads/{filename}"

        # Database operations with retry logic
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    
                    # Check if answer already exists
                    cursor.execute("""
                        SELECT id FROM interview_answers 
                        WHERE session_id = ? AND question_id = ?
                    """, (session_id, question_id))
                    existing = cursor.fetchone()

                    if existing:
                        # Update existing answer
                        cursor.execute("""
                            UPDATE interview_answers 
                            SET audio_path = ?, transcript = ?
                            WHERE id = ?
                        """, (audio_path_relative, transcript, existing["id"]))
                    else:
                        # Insert new answer
                        answer_id = str(uuid.uuid4())
                        cursor.execute("""
                            INSERT INTO interview_answers 
                            (id, session_id, question_id, audio_path, transcript)
                            VALUES (?, ?, ?, ?, ?)
                        """, (answer_id, session_id, question_id, audio_path_relative, transcript))

                    # Update session status
                    cursor.execute("""
                        UPDATE interview_sessions 
                        SET status = 'in_progress'
                        WHERE id = ?
                    """, (session_id,))
                
                # Success - break out of retry loop
                break
                
            except Exception as db_error:
                retry_count += 1
                if retry_count >= max_retries:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Database error after {max_retries} retries: {str(db_error)}"
                    )
                # Wait a bit before retrying (exponential backoff)
                time.sleep(0.1 * retry_count)

        return {
            "transcript": transcript,
            "audio_path": audio_path_relative
        }

    except HTTPException:
        raise
    except Exception as e:
        # Clean up files on error
        if temp_file_path and os.path.exists(str(temp_file_path)):
            try:
                os.remove(str(temp_file_path))
            except:
                pass
        if file_path and os.path.exists(str(file_path)):
            try:
                os.remove(str(file_path))
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
