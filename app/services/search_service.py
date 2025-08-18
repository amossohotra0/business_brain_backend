from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from openai import OpenAI
from app.db.supabase_client import supabase
from app.core.config import settings

# Configure OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)

class SearchService:
    
    @staticmethod
    async def search_documents(user_email: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search documents by content using text similarity."""
        try:
            # Get user ID
            user_result = supabase.table('users').select('id').eq('email', user_email).execute()
            if not user_result.data:
                return []
            
            user_id = user_result.data[0]['id']
            
            # Search for documents with OCR text or notes with description containing query terms
            result = supabase.table('documents').select('*').eq('user_id', user_id).execute()
            
            if not result.data:
                return []
            
            # Filter documents that contain query terms
            query_lower = query.lower()
            matching_documents = []
            
            for doc in result.data:
                # Get searchable content based on document type
                searchable_content = ""
                
                if doc.get('document_type') == 'note':
                    # For notes, search in title and description
                    title = doc.get('title', '')
                    description = doc.get('description', '')
                    searchable_content = f"{title} {description}".lower()
                else:
                    # For PDFs, search in OCR text (only if completed)
                    if doc.get('ocr_status') == 'completed' and doc.get('ocr_text'):
                        searchable_content = doc['ocr_text'].lower()
                
                if searchable_content:
                    # Simple text matching - check if query words are in document
                    query_words = query_lower.split()
                    
                    # Calculate relevance score
                    score = 0
                    for word in query_words:
                        if word in searchable_content:
                            score += searchable_content.count(word)
                    
                    if score > 0:
                        doc['relevance_score'] = score
                        matching_documents.append(doc)
            
            # Sort by relevance score (highest first)
            matching_documents.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            return matching_documents[:limit]
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Search failed: {str(e)}"
            )
    
    @staticmethod
    async def generate_ai_response(query: str, documents: List[Dict[str, Any]]) -> str:
        """Generate AI response based on query and relevant documents."""
        try:
            if not documents:
                return "I couldn't find any relevant documents or notes to answer your question. Please make sure you have uploaded documents with OCR processing completed or created some notes."
            
            # Prepare context from documents
            context_parts = []
            for i, doc in enumerate(documents[:3]):  # Use top 3 most relevant documents
                doc_type = doc.get('document_type', 'document')
                title = doc.get('title') or doc.get('filename', f'Document {i+1}')
                
                # Get content based on document type
                if doc_type == 'note':
                    content = doc.get('description', '')
                else:
                    content = doc.get('ocr_text', '')
                
                # Limit content length
                limited_content = content[:1000] + "..." if len(content) > 1000 else content
                
                context_parts.append(f"{doc_type.title()} {i+1} ({title}):\n{limited_content}")
            
            context = "\n\n".join(context_parts)
            
            # Create prompt for OpenAI
            prompt = f"""
            You are a professional yet approachable AI assistant that helps the user find information 
            from their uploaded documents, meeting notes, and related files.

            ## Your role:
            - Respond in a natural, human-like way while keeping answers clear, concise, and professional.
            - Base all responses only on the information in the CONTENT section.
            - If the answer is incomplete because the documents don’t cover it, gently tell the users about it. 
            (e.g., "The documents don’t define X directly, but they do mention...").
            - If multiple documents contribute, reference them conversationally (e.g., "Both the project plan and meeting summary mention...").
            - Organize complex answers with short paragraphs or bullet points for readability.
            **Citations**: When you provide an answer, reference the specific document(s) or note(s) you are using. Use a format like: *(Source: Document Name)*.

            ## CONTENT:
            {context}

            ## USER QUESTION:
            {query}

            ## Task:
            Answer the question in a natural, conversational, and helpful tone that feels like a knowledgeable colleague explaining the answer. 
            Where possible, weave source mentions naturally into the sentences instead of listing them mechanically at the end.
            """

            # Call OpenAI API using the new v1.x format
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that answers questions based on provided documents and notes. Always be accurate and cite your sources."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.1
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            # Handle OpenAI errors more generically since the error structure changed
            if "openai" in str(type(e)).lower():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"OpenAI API error: {str(e)}"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"AI response generation failed: {str(e)}"
                )
    
    @staticmethod
    async def search_and_respond(user_email: str, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search documents and generate AI response."""
        
        # Search for relevant documents
        documents = await SearchService.search_documents(user_email, query, limit)
        
        # Generate AI response
        ai_response = await SearchService.generate_ai_response(query, documents)
        
        return {
            "query": query,
            "documents_found": len(documents),
            "relevant_documents": [
                {
                    "id": doc["id"],
                    "title": doc.get("title") or doc.get("filename", "Untitled"),
                    "document_type": doc.get("document_type", "unknown"),
                    "filename": doc.get("filename"),
                    "relevance_score": doc.get("relevance_score", 0),
                    "preview": SearchService._get_document_preview(doc)
                }
                for doc in documents
            ],
            "ai_response": ai_response
        }
    
    @staticmethod
    def _get_document_preview(doc: Dict[str, Any]) -> str:
        """Get preview text for a document (PDF or note)."""
        if doc.get("document_type") == "note":
            # For notes, use description
            description = doc.get("description", "")
            return description[:200] + "..." if len(description) > 200 else description
        else:
            # For PDFs, use ocr_text
            ocr_text = doc.get("ocr_text", "")
            return ocr_text[:200] + "..." if len(ocr_text) > 200 else ocr_text