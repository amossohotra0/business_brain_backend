import os
import asyncio
from typing import Optional, List
from PIL import Image
from pdf2image import convert_from_path
import pytesseract
from fastapi import HTTPException, status
from app.db.supabase_client import supabase
from app.models.document import OCRStatus
from app.services.embedding_service import EmbeddingService  # Add this import

class OCRService:
    
    @staticmethod
    async def extract_text_from_pdf(file_path: str) -> str:
        """Extract text from PDF using OCR."""
        try:
            # Convert PDF to images
            images = convert_from_path(file_path)
            
            extracted_text = []
            
            # Process each page
            for i, image in enumerate(images):
                # Use OCR to extract text from image
                text = pytesseract.image_to_string(image, lang='eng')
                
                if text.strip():  # Only add non-empty text
                    extracted_text.append(f"--- Page {i + 1} ---\n{text.strip()}")
            
            # Combine all text
            full_text = "\n\n".join(extracted_text)
            
            return full_text if full_text.strip() else "No text found in document"
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"OCR processing failed: {str(e)}"
            )
    
    @staticmethod
    async def update_document_ocr_status(document_id: str, status: OCRStatus, ocr_text: Optional[str] = None):
        """Update document OCR status and text in database."""
        try:
            update_data = {
                'ocr_status': status.value,
                'updated_at': 'NOW()'
            }
            
            if ocr_text is not None:
                update_data['ocr_text'] = ocr_text
            
            result = supabase.table('documents').update(update_data).eq('id', document_id).execute()
            
            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found"
                )
            
            return result.data[0]
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update document status: {str(e)}"
            )
    
    @staticmethod
    async def process_document_ocr(document_id: str, file_path: str):
        """Process OCR for a single document."""
        try:
            # Update status to processing
            await OCRService.update_document_ocr_status(document_id, OCRStatus.PROCESSING)
            
            # Extract text from PDF
            extracted_text = await OCRService.extract_text_from_pdf(file_path)
            
            # Update document with extracted text and completed status
            await OCRService.update_document_ocr_status(
                document_id, 
                OCRStatus.COMPLETED, 
                extracted_text
            )
            
            # Generate embedding for the extracted text
            try:
                await EmbeddingService.process_document_embedding(document_id, extracted_text)
                print(f"✅ Embedding generated for document {document_id}")
            except Exception as e:
                print(f"⚠️ Embedding generation failed for document {document_id}: {str(e)}")
                # Continue even if embedding fails
            
            # Clean up temporary file
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return extracted_text
            
        except Exception as e:
            # Update status to failed
            try:
                await OCRService.update_document_ocr_status(document_id, OCRStatus.FAILED)
            except:
                pass  # Don't let status update failure mask original error
            
            # Clean up temporary file
            if os.path.exists(file_path):
                os.remove(file_path)
            
            raise e
    
    @staticmethod
    async def process_multiple_documents_ocr(documents: List[dict]):
        """Process OCR for multiple documents."""
        results = []
        
        for doc in documents:
            try:
                result = await OCRService.process_document_ocr(doc['id'], doc['file_path'])
                results.append({
                    'document_id': doc['id'],
                    'status': 'success',
                    'text_length': len(result)
                })
            except Exception as e:
                results.append({
                    'document_id': doc['id'],
                    'status': 'failed',
                    'error': str(e)
                })
        
        return results
    
    @staticmethod
    async def get_document_by_id(document_id: str) -> Optional[dict]:
        """Get document by ID."""
        try:
            result = supabase.table('documents').select('*').eq('id', document_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching document: {str(e)}"
            )