from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List
from app.services.notes_service import NotesService
from app.models.document import NoteCreate, NoteUpdate, NoteResponse
from app.core.security import verify_token

router = APIRouter(prefix="/notes", tags=["Notes"])
security = HTTPBearer()

async def get_current_user_email(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Extract user email from JWT token."""
    token = credentials.credentials
    payload = verify_token(token)
    email = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    return email

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_note(
    note_data: NoteCreate,
    current_user_email: str = Depends(get_current_user_email)
):
    """Create a new note."""
    
    note = await NotesService.create_note(current_user_email, note_data)
    
    return {
        "message": "Note created successfully",
        "note": note
    }

@router.get("/")
async def list_notes(current_user_email: str = Depends(get_current_user_email)):
    """Get all notes for the current user."""
    
    notes = await NotesService.get_user_notes(current_user_email)
    
    return {
        "notes": notes,
        "total": len(notes)
    }

@router.get("/{note_id}")
async def get_note(
    note_id: str,
    current_user_email: str = Depends(get_current_user_email)
):
    """Get a specific note."""
    
    note = await NotesService.get_note_by_id(note_id, current_user_email)
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    return note

@router.put("/{note_id}")
async def update_note(
    note_id: str,
    note_data: NoteUpdate,
    current_user_email: str = Depends(get_current_user_email)
):
    """Update an existing note."""
    
    updated_note = await NotesService.update_note(note_id, current_user_email, note_data)
    
    return {
        "message": "Note updated successfully",
        "note": updated_note
    }

@router.delete("/{note_id}")
async def delete_note(
    note_id: str,
    current_user_email: str = Depends(get_current_user_email)
):
    """Delete a note."""
    
    await NotesService.delete_note(note_id, current_user_email)
    
    return {"message": "Note deleted successfully"}