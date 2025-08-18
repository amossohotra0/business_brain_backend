from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, BackgroundTasks, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Dict, Any, Literal, Optional
from app.services.document_service import DocumentService
from app.services.ocr_service import OCRService
import os
import uuid
import logging
from datetime import datetime
from app.services.search_service import SearchService
from app.schemas.document import DocumentListResponse, DocumentSearchRequest, DocumentSearchResponse
from app.models.document import (
    DocumentUploadResponse, 
    DocumentResponse, 
    DocumentType, 
    OCRStatus
)
from app.core.security import verify_token
from app.services.semantic_search_service import SemanticSearchService
from app.schemas.document import DocumentListResponse, DocumentSearchRequest, DocumentSearchResponse, SearchComparisonResponse
from app.db.supabase_client import supabase  # Add this import

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

# SEARCH ENDPOINTS FIRST (more specific routes)
@router.post("/search", response_model=DocumentSearchResponse)
async def search_documents_post(
    search_request: DocumentSearchRequest,
    current_user_email: str = Depends(get_current_user_email)
):
    """Search documents with semantic understanding and get AI-powered response."""
    
    result = await SemanticSearchService.search_and_respond(
        user_email=current_user_email,
        query=search_request.query,
        limit=search_request.limit or 10,
        search_type=search_request.search_type or "hybrid"  # Use the search_type from request
    )
    
    return result

@router.get("/search", response_model=DocumentSearchResponse)
async def search_documents_get(
    q: str,
    limit: int = 10,
    search_type: Literal["semantic", "keyword", "hybrid"] = "hybrid",  # This will show as dropdown in Swagger
    current_user_email: str = Depends(get_current_user_email)
):
    """Search documents via GET request with semantic understanding."""
    
    result = await SemanticSearchService.search_and_respond(
        user_email=current_user_email,
        query=q,
        limit=limit,
        search_type=search_type
    )
    
    return result

@router.get("/search/compare", response_model=SearchComparisonResponse)
async def compare_search_types(
    q: str,
    limit: int = 5,
    current_user_email: str = Depends(get_current_user_email)
):
    """Compare semantic, keyword, and hybrid search results."""
    
    try:
        semantic_results = await SemanticSearchService.search_and_respond(
            user_email=current_user_email,
            query=q,
            limit=limit,
            search_type="semantic"
        )
        
        keyword_results = await SemanticSearchService.search_and_respond(
            user_email=current_user_email,
            query=q,
            limit=limit,
            search_type="keyword"
        )
        
        hybrid_results = await SemanticSearchService.search_and_respond(
            user_email=current_user_email,
            query=q,
            limit=limit,
            search_type="hybrid"
        )
        
        return SearchComparisonResponse(
            query=q,
            semantic_search=semantic_results,
            keyword_search=keyword_results,
            hybrid_search=hybrid_results
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search comparison failed: {str(e)}"
        )

# UPLOAD ENDPOINT
# @router.post("/upload", status_code=status.HTTP_201_CREATED)
# async def upload_documents(
#     background_tasks: BackgroundTasks,
#     files: List[UploadFile] = File(...),
#     current_user_email: str = Depends(get_current_user_email)
# ):
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


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    current_user_email: str = Depends(get_current_user_email)
):
    """Upload documents and extract text"""
    
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    uploaded_documents = []
    temp_files = []
    
    try:
        for file in files:
            # Validate file type
            if not file.content_type or not file.content_type.startswith('application/pdf'):
                raise HTTPException(
                    status_code=400, 
                    detail=f"File {file.filename} is not a PDF"
                )
            
            # Save file temporarily
            temp_file_path = await DocumentService.save_file_temporarily(file)
            temp_files.append(temp_file_path)
            
            # Get file size
            file_size = len(await file.read())
            await file.seek(0)  # Reset file pointer
            
            # Generate title from original filename
            title = file.filename.rsplit('.', 1)[0] if '.' in file.filename else file.filename
            title = title.replace('_', ' ').replace('-', ' ')
            title = ' '.join(word.capitalize() for word in title.split())
            
            # Create document record with title
            document = await DocumentService.create_document_record(
                user_email=current_user_email,
                filename=file.filename,
                file_path=temp_file_path,
                file_size=file_size,
                content_type=file.content_type,
                title=title
            )
            
            uploaded_documents.append(document)
        
        # Add OCR processing to background tasks
        background_tasks.add_task(
            OCRService.process_multiple_documents_ocr, 
            uploaded_documents
        )

        return DocumentUploadResponse(
            message=f"Successfully uploaded {len(uploaded_documents)} document(s)",
            documents=uploaded_documents,
            total_uploaded=len(uploaded_documents)
        )
        
    except Exception as e:
        # Clean up temp files in case of error
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


# SPECIFIC DOCUMENT ENDPOINTS (more specific before general)
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

# GENERAL LIST ENDPOINT (least specific, comes last)
@router.get("/", response_model=DocumentListResponse)
async def list_documents(current_user_email: str = Depends(get_current_user_email)):
    """Get all documents for the current user."""
    documents = await DocumentService.get_user_documents(current_user_email)
    
    return DocumentListResponse(
        documents=documents,
        total=len(documents)
    )

@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user_email: str = Depends(get_current_user_email)
):
    """Delete a document (PDF)."""
    
    try:
        # Get user's documents to verify ownership
        user_documents = await DocumentService.get_user_documents(current_user_email)
        user_doc_ids = [doc['id'] for doc in user_documents]
        
        if document_id not in user_doc_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get the specific document to check if it has a file to clean up
        document = next((doc for doc in user_documents if doc['id'] == document_id), None)
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Clean up temporary file if it still exists (for failed uploads)
        if document.get('file_path') and document.get('document_type') == 'pdf':
            import os
            if os.path.exists(document['file_path']):
                try:
                    os.remove(document['file_path'])
                    print(f"🗑️ Cleaned up file: {document['file_path']}")
                except Exception as e:
                    print(f"⚠️ Could not clean up file {document['file_path']}: {str(e)}")
        
        # Delete the document record from database
        from app.db.supabase_client import supabase
        result = supabase.table('documents').delete().eq('id', document_id).execute()
        
        return {
            "message": f"Document '{document.get('title', document.get('filename', 'Unknown'))}' deleted successfully"
        }
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        )
