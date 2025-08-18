from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.notes import router as notes_router
from app.api.audio import router as audio_router
from app.api.conversations import router as conversations_router
from app.api.google_gmail import router as gmail_router  # Updated import name


app = FastAPI(
    title="Document Intelligence API",
    description="API for document upload, OCR, note-taking, audio transcription, semantic search, conversation management, and Gmail integration",  # Updated description
    version="1.2.0"  # Updated version
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(notes_router, prefix="/api/v1")
app.include_router(audio_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(gmail_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "message": "Document Intelligence API with Gmail Integration is running!",
        "features": [
            "Document upload and OCR",
            "Audio transcription", 
            "Note management",
            "Semantic search",
            "Conversation threads",
            "Chat-based document search",
            "Gmail inbox integration",
            "Real-time email notifications"
        ]
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.2.0"}