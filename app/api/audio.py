from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, BackgroundTasks, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
from app.services.audio_service import AudioService
from app.models.document import AudioCreate, AudioResponse
from app.core.security import verify_token

router = APIRouter(prefix="/audio", tags=["Audio"])
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

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    language: str = Form("en"),
    current_user_email: str = Depends(get_current_user_email)
):
    """Upload audio file for transcription."""
    
    # Validate file
    AudioService.validate_audio_file(file)
    
    try:
        # Save file temporarily
        temp_file_path = await AudioService.save_audio_temporarily(file)
        
        # Get file size
        file_size = len(await file.read())
        await file.seek(0)  # Reset file pointer
        
        # Create audio record
        audio_record = await AudioService.create_audio_record(
            user_email=current_user_email,
            title=title,
            filename=file.filename,
            file_size=file_size,
            content_type=file.content_type,
            description=description
        )
        
        # Add transcription processing to background tasks
        background_tasks.add_task(
            AudioService.process_audio_transcription,
            audio_record['id'],
            temp_file_path,
            language
        )
        
        return {
            "message": "Audio uploaded successfully. Transcription processing started.",
            "audio": audio_record
        }
        
    except Exception as e:
        # Clean up temp file in case of error
        import os
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audio upload failed: {str(e)}"
        )

@router.get("/")
async def list_audio_recordings(current_user_email: str = Depends(get_current_user_email)):
    """Get all audio recordings for the current user."""
    
    recordings = await AudioService.get_user_audio_recordings(current_user_email)
    
    return {
        "recordings": recordings,
        "total": len(recordings)
    }

@router.get("/{audio_id}")
async def get_audio_recording(
    audio_id: str,
    current_user_email: str = Depends(get_current_user_email)
):
    """Get a specific audio recording with transcription."""
    
    # Get user's recordings to verify ownership
    user_recordings = await AudioService.get_user_audio_recordings(current_user_email)
    user_recording_ids = [recording['id'] for recording in user_recordings]
    
    if audio_id not in user_recording_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Find the specific recording
    recording = next((r for r in user_recordings if r['id'] == audio_id), None)
    
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio recording not found"
        )
    
    return recording

@router.post("/{audio_id}/retranscribe")
async def retranscribe_audio(
    audio_id: str,
    background_tasks: BackgroundTasks,
    language: str = Form("en"),
    current_user_email: str = Depends(get_current_user_email)
):
    """Retranscribe an audio recording (if original file still exists)."""
    
    # Note: Since we delete audio files after transcription, this endpoint 
    # would only work if we kept the original files. For now, return an error.
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Retranscription not available. Original audio files are not stored for privacy and storage optimization."
    )

@router.delete("/{audio_id}")
async def delete_audio_recording(
    audio_id: str,
    current_user_email: str = Depends(get_current_user_email)
):
    """Delete an audio recording."""
    
    try:
        # Get user's recordings to verify ownership
        user_recordings = await AudioService.get_user_audio_recordings(current_user_email)
        user_recording_ids = [recording['id'] for recording in user_recordings]
        
        if audio_id not in user_recording_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Delete the record
        result = supabase.table('documents').delete().eq('id', audio_id).execute()
        
        return {"message": "Audio recording deleted successfully"}
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete audio recording: {str(e)}"
        )