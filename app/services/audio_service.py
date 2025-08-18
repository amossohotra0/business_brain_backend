import os
import uuid
import aiofiles
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, UploadFile
from openai import OpenAI
from app.db.supabase_client import supabase
from app.core.config import settings
from app.services.embedding_service import EmbeddingService

# Configure OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)

class AudioService:
    
    # Maximum file size (25MB - Whisper API limit)
    MAX_FILE_SIZE = 25 * 1024 * 1024
    
    # Allowed audio content types
    ALLOWED_CONTENT_TYPES = [
        "audio/mpeg",       # MP3
        "audio/wav",        # WAV
        "audio/mp4",        # M4A
        "audio/m4a",        # M4A alternative
        "audio/webm",       # WebM
        "audio/ogg",        # OGG
        "audio/flac",       # FLAC
    ]
    
    # Allowed file extensions
    ALLOWED_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.webm', '.ogg', '.flac']
    
    @staticmethod
    def validate_audio_file(file: UploadFile) -> None:
        """Validate uploaded audio file."""
        # Check content type
        if file.content_type not in AudioService.ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Audio format not supported. Allowed formats: MP3, WAV, M4A, WebM, OGG, FLAC"
            )
        
        # Check file extension
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in AudioService.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension not allowed. Allowed extensions: {', '.join(AudioService.ALLOWED_EXTENSIONS)}"
            )
    
    @staticmethod
    async def save_audio_temporarily(file: UploadFile) -> str:
        """Save uploaded audio file temporarily and return file path."""
        try:
            # Create temp directory if it doesn't exist
            temp_dir = "temp_audio"
            os.makedirs(temp_dir, exist_ok=True)
            
            # Generate unique filename
            file_id = str(uuid.uuid4())
            file_extension = os.path.splitext(file.filename)[1].lower()
            temp_file_path = os.path.join(temp_dir, f"{file_id}{file_extension}")
            
            # Save file
            async with aiofiles.open(temp_file_path, 'wb') as f:
                content = await file.read()
                
                # Check file size
                if len(content) > AudioService.MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File size exceeds maximum limit of {AudioService.MAX_FILE_SIZE // (1024*1024)}MB"
                    )
                
                await f.write(content)
            
            return temp_file_path
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error saving audio file: {str(e)}"
            )
    
    @staticmethod
    async def transcribe_audio(file_path: str, language: Optional[str] = "en") -> str:
        """Transcribe audio using OpenAI Whisper."""
        try:
            with open(file_path, "rb") as audio_file:
                # Call OpenAI Whisper API
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    response_format="text"
                )
                
                return transcript.strip() if transcript else "No speech detected in audio"
                
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Audio transcription failed: {str(e)}"
            )
    
    @staticmethod
    async def create_audio_record(
        user_email: str,
        title: str,
        filename: str,
        file_size: int,
        content_type: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create audio record in database."""
        try:
            # Get user ID from email
            user_result = supabase.table('users').select('id').eq('email', user_email).execute()
            if not user_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            user_id = user_result.data[0]['id']
            
            # Create audio record
            audio_data = {
                'user_id': user_id,
                'title': title,
                'filename': filename,
                'file_size': file_size,
                'content_type': content_type,
                'document_type': 'audio',
                'transcription_status': 'pending',
                'description': description
            }
            
            result = supabase.table('documents').insert(audio_data).execute()
            
            if result.data:
                return result.data[0]
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create audio record"
                )
                
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {str(e)}"
            )
    
    @staticmethod
    async def update_transcription_status(audio_id: str, status: str, transcribed_text: Optional[str] = None):
        """Update audio transcription status and text."""
        try:
            update_data = {
                'transcription_status': status,
                'updated_at': 'NOW()'
            }
            
            if transcribed_text is not None:
                update_data['ocr_text'] = transcribed_text  # Using ocr_text field for consistency
            
            result = supabase.table('documents').update(update_data).eq('id', audio_id).execute()
            
            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Audio record not found"
                )
            
            return result.data[0]
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update transcription status: {str(e)}"
            )
    
    @staticmethod
    async def process_audio_transcription(audio_id: str, file_path: str, language: Optional[str] = "en"):
        """Process audio transcription and generate embeddings."""
        try:
            # Update status to processing
            await AudioService.update_transcription_status(audio_id, 'processing')
            
            # Transcribe audio
            transcribed_text = await AudioService.transcribe_audio(file_path, language)
            
            # Update with transcribed text and completed status
            await AudioService.update_transcription_status(audio_id, 'completed', transcribed_text)
            
            # Generate embedding for the transcribed text
            try:
                await EmbeddingService.process_document_embedding(audio_id, transcribed_text)
                print(f"✅ Embedding generated for audio {audio_id}")
            except Exception as e:
                print(f"⚠️ Embedding generation failed for audio {audio_id}: {str(e)}")
                # Continue even if embedding fails
            
            # Clean up temporary file
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️ Cleaned up temporary audio file: {file_path}")
            
            return transcribed_text
            
        except Exception as e:
            # Update status to failed
            try:
                await AudioService.update_transcription_status(audio_id, 'failed')
            except:
                pass  # Don't let status update failure mask original error
            
            # Clean up temporary file
            if os.path.exists(file_path):
                os.remove(file_path)
            
            raise e
    
    @staticmethod
    async def get_user_audio_recordings(user_email: str):
        """Get all audio recordings for a user."""
        try:
            # Get user ID
            user_result = supabase.table('users').select('id').eq('email', user_email).execute()
            if not user_result.data:
                return []
            
            user_id = user_result.data[0]['id']
            
            # Get audio recordings
            result = supabase.table('documents').select('*').eq('user_id', user_id).eq('document_type', 'audio').order('created_at', desc=True).execute()
            return result.data or []
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching audio recordings: {str(e)}"
            )