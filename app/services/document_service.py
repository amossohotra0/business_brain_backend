import os
import uuid
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status, UploadFile
from app.db.supabase_client import supabase
from app.models.document import DocumentCreate, OCRStatus
import aiofiles
import magic

class DocumentService:
    
    # Maximum file size (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    # Allowed content types
    ALLOWED_CONTENT_TYPES = [
        "application/pdf"
    ]
    
    @staticmethod
    def validate_file(file: UploadFile) -> None:
        """Validate uploaded file."""
        # Check content type
        if file.content_type not in DocumentService.ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Only PDF files are supported."
            )
        
        # Check file extension
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must have .pdf extension"
            )
    
    @staticmethod
    async def save_file_temporarily(file: UploadFile) -> str:
        """Save uploaded file temporarily and return file path."""
        try:
            # Create temp directory if it doesn't exist
            temp_dir = "temp_uploads"
            os.makedirs(temp_dir, exist_ok=True)
            
            # Generate unique filename
            file_id = str(uuid.uuid4())
            temp_file_path = os.path.join(temp_dir, f"{file_id}_{file.filename}")
            
            # Save file
            async with aiofiles.open(temp_file_path, 'wb') as f:
                content = await file.read()
                
                # Check file size
                if len(content) > DocumentService.MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File size exceeds maximum limit of {DocumentService.MAX_FILE_SIZE // (1024*1024)}MB"
                    )
                
                await f.write(content)
            
            # Verify file is actually a PDF using python-magic
            file_type = magic.from_file(temp_file_path, mime=True)
            if file_type != 'application/pdf':
                os.remove(temp_file_path)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File is not a valid PDF"
                )
            
            return temp_file_path
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error saving file: {str(e)}"
            )
    
    # @staticmethod
    # async def create_document_record(
    #     user_email: str, 
    #     filename: str, 
    #     file_path: str, 
    #     file_size: int, 
    #     content_type: str
    # ) -> Dict[str, Any]:
    #     """Create document record in database."""
    #     try:
    #         # Get user ID from email
    #         user_result = supabase.table('users').select('id').eq('email', user_email).execute()
    #         if not user_result.data:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail="User not found"
    #             )
            
    #         user_id = user_result.data[0]['id']
            
    #         # Create document record
    #         document_data = {
    #             'user_id': user_id,
    #             'filename': filename,
    #             'file_path': file_path,
    #             'file_size': file_size,
    #             'content_type': content_type,
    #             'ocr_status': OCRStatus.PENDING.value
    #         }
            
    #         result = supabase.table('documents').insert(document_data).execute()
            
    #         if result.data:
    #             return result.data[0]
    #         else:
    #             raise HTTPException(
    #                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #                 detail="Failed to create document record"
    #             )
                
    #     except Exception as e:
    #         if isinstance(e, HTTPException):
    #             raise e
    #         raise HTTPException(
    #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #             detail=f"Database error: {str(e)}"
    #         )
    
    @staticmethod
    async def create_document_record(
        user_email: str, 
        filename: str, 
        file_path: str, 
        file_size: int, 
        content_type: str,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create document record in database."""
        try:
            # Get user ID from email
            user_result = supabase.table('users').select('id').eq('email', user_email).execute()
            if not user_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            user_id = user_result.data[0]['id']
            
            # Generate title from filename if not provided
            if not title:
                title = filename.rsplit('.', 1)[0] if '.' in filename else filename
                title = title.replace('_', ' ').replace('-', ' ')
                title = ' '.join(word.capitalize() for word in title.split())
            
            # Create document record
            document_data = {
                'user_id': user_id,
                'title': title,  # Add this line
                'filename': filename,
                'file_path': file_path,
                'file_size': file_size,
                'content_type': content_type,
                'document_type': 'pdf',  # Add this line
                'ocr_status': OCRStatus.PENDING.value
            }
            
            result = supabase.table('documents').insert(document_data).execute()
            
            if result.data:
                return result.data[0]
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create document record"
                )
                
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {str(e)}"
            )
    
    @staticmethod
    async def get_user_documents(user_email: str) -> List[Dict[str, Any]]:
        """Get all documents for a user."""
        try:
            # Get user ID
            user_result = supabase.table('users').select('id').eq('email', user_email).execute()
            if not user_result.data:
                return []
            
            user_id = user_result.data[0]['id']
            
            # Get documents
            result = supabase.table('documents').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
            return result.data or []
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching documents: {str(e)}"
            )