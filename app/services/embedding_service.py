from typing import List, Optional
from fastapi import HTTPException, status
from openai import OpenAI
from app.core.config import settings
from app.db.supabase_client import supabase

# Configure OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)

class EmbeddingService:
    
    @staticmethod
    async def generate_embedding(text: str) -> List[float]:
        """Generate embedding for given text using OpenAI."""
        try:
            # Clean and truncate text if too long
            cleaned_text = text.strip()
            
            # OpenAI embedding model has token limits (~8192 tokens)
            # Truncate to ~6000 characters to be safe
            if len(cleaned_text) > 6000:
                cleaned_text = cleaned_text[:6000] + "..."
            
            # Generate embedding
            response = client.embeddings.create(
                model="text-embedding-ada-002",
                input=cleaned_text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate embedding: {str(e)}"
            )
    
    @staticmethod
    async def update_document_embedding(document_id: str, embedding: List[float]):
        """Update document with generated embedding."""
        try:
            result = supabase.table('documents').update({
                'embedding': embedding
            }).eq('id', document_id).execute()
            
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
                detail=f"Failed to update document embedding: {str(e)}"
            )
    
    @staticmethod
    async def process_document_embedding(document_id: str, ocr_text: str):
        """Generate and store embedding for a document."""
        try:
            # Generate embedding
            embedding = await EmbeddingService.generate_embedding(ocr_text)
            
            # Update document with embedding
            await EmbeddingService.update_document_embedding(document_id, embedding)
            
            return embedding
            
        except Exception as e:
            print(f"Error processing embedding for document {document_id}: {str(e)}")
            # Don't fail OCR if embedding fails
            return None