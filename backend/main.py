import os
import sys
from pathlib import Path

# Add project root to Python path when running directly
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.routes import session, upload, analyze

app = FastAPI(title="AI Interviewer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(analyze.router, prefix="/api")

# Use absolute paths
frontend_dir = project_root / "frontend"
uploads_dir = project_root / "uploads"

os.makedirs(uploads_dir, exist_ok=True)
os.makedirs(frontend_dir, exist_ok=True)

# Mount uploads directory for serving audio files
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# Mount frontend directory (must be last to catch all other routes)
app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
