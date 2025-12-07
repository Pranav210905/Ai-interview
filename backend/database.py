import sqlite3
import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# Database file path
DB_PATH = Path("interview.db")

def get_db_connection():
    """Get a SQLite database connection."""
    # Increased timeout to prevent "database is locked" errors during concurrent writes.
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn

@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_database():
    """Initialize the database with required tables."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Create interview_sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interview_sessions (
                id TEXT PRIMARY KEY,
                job_description TEXT NOT NULL,
                resume_text TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL,
                questions TEXT NOT NULL,
                status TEXT DEFAULT 'created',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create interview_answers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interview_answers (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                audio_path TEXT,
                transcript TEXT,
                score INTEGER,
                feedback TEXT,
                model_answer TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES interview_sessions(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_answers_session_id 
            ON interview_answers(session_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_status 
            ON interview_sessions(status)
        """)
        
        conn.commit()

# Initialize database on import
init_database()
