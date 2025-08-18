from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List
from app.services.document_service import DocumentService
from app.services.ocr_service import OCRService  # Add this import
from app.schemas.document import DocumentListResponse
from app.models.document import DocumentResponse
from app.core.security import verify_token
from typing import List, Dict, Any


router = APIRouter(prefix="/documents", tags=["Documents"])
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
async def upload_documents(
    background_tasks: BackgroundTasks,  # Add this parameter
    files: List[UploadFile] = File(...),
    current_user_email: str = Depends(get_current_user_email)
):
    """Upload PDF documents (max 5 files)."""
    
    # Validate number of files
    if len(files) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 5 files allowed per upload"
        )
    
    if len(files) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided"
        )
    
    uploaded_documents = []
    temp_files = []
    
    try:
        for file in files:
            # Validate file
            DocumentService.validate_file(file)
            
            # Save file temporarily
            temp_file_path = await DocumentService.save_file_temporarily(file)
            temp_files.append(temp_file_path)
            
            # Get file size
            file_size = len(await file.read())
            await file.seek(0)  # Reset file pointer
            
            # Create document record
            document = await DocumentService.create_document_record(
                user_email=current_user_email,
                filename=file.filename,
                file_path=temp_file_path,
                file_size=file_size,
                content_type=file.content_type
            )
            
            uploaded_documents.append(document)
        
        # Add OCR processing to background tasks
        background_tasks.add_task(
            OCRService.process_multiple_documents_ocr, 
            uploaded_documents
        )
        
        return {
            "message": f"Successfully uploaded {len(uploaded_documents)} documents. OCR processing started.",
            "documents": uploaded_documents,
            "total_uploaded": len(uploaded_documents)
        }
    
    except Exception as e:
        # Clean up temp files in case of error
        import os
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )

@router.get("/", response_model=DocumentListResponse)
async def list_documents(current_user_email: str = Depends(get_current_user_email)):
    """Get all documents for the current user."""
    documents = await DocumentService.get_user_documents(current_user_email)
    
    return DocumentListResponse(
        documents=documents,
        total=len(documents)
    )

# Add new endpoints for OCR management
@router.post("/{document_id}/process-ocr")
async def process_document_ocr(
    document_id: str,
    background_tasks: BackgroundTasks,
    current_user_email: str = Depends(get_current_user_email)
):
    """Manually trigger OCR processing for a specific document."""
    
    # Get document and verify ownership
    document = await OCRService.get_document_by_id(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Verify user owns this document
    user_documents = await DocumentService.get_user_documents(current_user_email)
    user_doc_ids = [doc['id'] for doc in user_documents]
    
    if document_id not in user_doc_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Add OCR processing to background task
    background_tasks.add_task(
        OCRService.process_document_ocr,
        document_id,
        document['file_path']
    )
    
    return {"message": "OCR processing started for document"}

@router.get("/{document_id}")
async def get_document(
    document_id: str,
    current_user_email: str = Depends(get_current_user_email)
):
    """Get a specific document with OCR text."""
    
    # Verify user owns this document
    user_documents = await DocumentService.get_user_documents(current_user_email)
    user_doc_ids = [doc['id'] for doc in user_documents]
    
    if document_id not in user_doc_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    document = await OCRService.get_document_by_id(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return document

# Add these imports at the top
from app.services.search_service import SearchService
from app.schemas.document import DocumentSearchRequest, DocumentSearchResponse

# Add these new endpoints at the end of the file

@router.post("/search", response_model=Dict)
async def search_documents(
    search_request: DocumentSearchRequest,
    current_user_email: str = Depends(get_current_user_email)
):
    """Search documents and get AI-powered response."""
    
    result = await SearchService.search_and_respond(
        user_email=current_user_email,
        query=search_request.query,
        limit=search_request.limit or 10
    )
    
    return result

@router.get("/search")
async def search_documents_get(
    q: str,
    limit: int = 10,
    current_user_email: str = Depends(get_current_user_email)
):
    """Search documents via GET request."""
    
    result = await SearchService.search_and_respond(
        user_email=current_user_email,
        query=q,
        limit=limit
    )
    
    return result