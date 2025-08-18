from pydantic import BaseModel, validator, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum

class OCRStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TranscriptionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DocumentType(str, Enum):
    PDF = "pdf"
    NOTE = "note"
    AUDIO = "audio"

class DocumentBase(BaseModel):
    title: str
    document_type: DocumentType

class DocumentCreate(DocumentBase):
    filename: Optional[str] = None
    file_size: Optional[int] = None
    content_type: Optional[str] = None

class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)

class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=1)

class AudioCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    language: Optional[str] = Field(default="en", description="Language code for transcription (e.g., 'en', 'es', 'fr')")

class DocumentResponse(BaseModel):
    id: str
    user_id: str
    title: str = Field(default="Untitled")
    document_type: DocumentType
    filename: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    content_type: Optional[str] = None
    ocr_text: Optional[str] = None
    description: Optional[str] = None
    ocr_status: Optional[OCRStatus] = OCRStatus.PENDING
    transcription_status: Optional[TranscriptionStatus] = None
    created_at: datetime
    updated_at: datetime
    
    @validator('title', pre=True, always=True)
    def validate_title(cls, v, values):
        """Ensure title is never None or empty, prefer filename over default"""
        # If title is None, empty, or "Untitled Document", try to use filename
        if v is None or v == "" or v == "Untitled Document" or v == "Untitled":
            filename = values.get('filename')
            if filename:
                # Remove file extension to get clean title
                title = filename.rsplit('.', 1)[0] if '.' in filename else filename
                # Clean up the title (replace underscores/hyphens with spaces, capitalize)
                title = title.replace('_', ' ').replace('-', ' ')
                # Capitalize first letter of each word for better readability
                title = ' '.join(word.capitalize() for word in title.split())
                return title
            return "Untitled Document"
        return v

    @validator('document_type', pre=True)
    def validate_document_type(cls, v):
        """Ensure document_type is valid"""
        if v is None:
            return DocumentType.PDF
        if isinstance(v, str):
            try:
                return DocumentType(v.lower())
            except ValueError:
                return DocumentType.PDF
        return v

    @validator('ocr_status', pre=True)
    def validate_ocr_status(cls, v):
        """Ensure ocr_status is valid"""
        if v is None:
            return OCRStatus.PENDING
        if isinstance(v, str):
            try:
                return OCRStatus(v.lower())
            except ValueError:
                return OCRStatus.PENDING
        return v
    
    class Config:
        from_attributes = True

class AudioResponse(BaseModel):
    id: str
    user_id: str
    title: str = Field(default="Untitled Audio")
    filename: str
    file_size: int
    content_type: str
    transcription_status: TranscriptionStatus = TranscriptionStatus.PENDING
    transcribed_text: Optional[str] = None
    description: Optional[str] = None
    document_type: str = "audio"
    created_at: datetime
    updated_at: datetime

    @validator('title', pre=True, always=True)
    def validate_title(cls, v, values):
        """Ensure title is never None or empty, prefer filename over default"""
        if v is None or v == "" or v == "Untitled Audio" or v == "Untitled":
            filename = values.get('filename')
            if filename:
                # Remove file extension to get clean title
                title = filename.rsplit('.', 1)[0] if '.' in filename else filename
                # Clean up the title
                title = title.replace('_', ' ').replace('-', ' ')
                title = ' '.join(word.capitalize() for word in title.split())
                return title
            return "Untitled Audio"
        return v

    @validator('transcription_status', pre=True)
    def validate_transcription_status(cls, v):
        """Ensure transcription_status is valid"""
        if v is None:
            return TranscriptionStatus.PENDING
        if isinstance(v, str):
            try:
                return TranscriptionStatus(v.lower())
            except ValueError:
                return TranscriptionStatus.PENDING
        return v

class DocumentUploadResponse(BaseModel):
    message: str
    documents: List[DocumentResponse]
    total_uploaded: int

class NoteResponse(BaseModel):
    id: str
    user_id: str
    title: str = Field(default="Untitled Note")
    description: str = Field(default="")
    document_type: str = "note"
    created_at: datetime
    updated_at: datetime

    @validator('title', pre=True)
    def validate_title(cls, v):
        """Ensure title is never None or empty"""
        if v is None or v == "":
            return "Untitled Note"
        return v

    @validator('description', pre=True)
    def validate_description(cls, v):
        """Ensure description is never None"""
        if v is None:
            return ""
        return v

# List response models
class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int

class AudioListResponse(BaseModel):
    recordings: List[AudioResponse]
    total: int

class NoteListResponse(BaseModel):
    notes: List[NoteResponse]
    total: int

# Legacy models for backward compatibility
class DocumentBase_Legacy(BaseModel):
    filename: str
    file_size: int
    content_type: str

class DocumentCreate_Legacy(DocumentBase_Legacy):
    pass