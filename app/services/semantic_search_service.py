from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from app.db.supabase_client import supabase
from app.services.embedding_service import EmbeddingService
from app.services.search_service import SearchService

class SemanticSearchService:
    
    @staticmethod
    async def get_user_id_from_email(user_email: str) -> str:
        """Get user ID from email."""
        try:
            user_result = supabase.table('users').select('id').eq('email', user_email).execute()
            if not user_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            return user_result.data[0]['id']
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching user: {str(e)}"
            )
    
    @staticmethod
    async def semantic_search(user_email: str, query: str, limit: int = 10, threshold: float = 0.2) -> List[Dict[str, Any]]:
        """Perform semantic search using vector similarity."""
        try:
            # Get user ID
            user_id = await SemanticSearchService.get_user_id_from_email(user_email)
            print(f"🔍 User ID: {user_id}")
            
            # Generate embedding for the query
            query_embedding = await EmbeddingService.generate_embedding(query)
            print(f"🔍 Query: '{query}' - Generated embedding with {len(query_embedding)} dimensions")
            
            # Perform similarity search using the database function
            result = supabase.rpc('match_documents', {
                'query_embedding': query_embedding,
                'match_threshold': threshold,
                'match_count': limit,
                'user_id_param': user_id
            }).execute()
            
            print(f"🔍 Supabase RPC result: {result.data}")
            print(f"🔍 Number of results: {len(result.data) if result.data else 0}")
            
            return result.data or []
            
        except Exception as e:
            print(f"❌ Semantic search error: {str(e)}")
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Semantic search failed: {str(e)}"
            )
    
    @staticmethod
    async def keyword_search(user_email: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Perform keyword search (existing logic)."""
        try:
            # Use existing keyword search logic
            return await SearchService.search_documents(user_email, query, limit)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Keyword search failed: {str(e)}"
            )
    
    @staticmethod
    async def hybrid_search(user_email: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Combine semantic and keyword search for best results."""
        try:
            # Perform both searches
            semantic_results = await SemanticSearchService.semantic_search(user_email, query, limit)
            keyword_results = await SemanticSearchService.keyword_search(user_email, query, limit)
            
            # Create a dictionary to merge results by document ID
            combined_results = {}
            
            # Add semantic results
            for doc in semantic_results:
                doc_id = doc['id']
                combined_results[doc_id] = {
                    **doc,
                    'semantic_score': doc.get('similarity', 0),
                    'keyword_score': 0,
                    'search_type': 'semantic'
                }
            
            # Add keyword results and merge scores
            for doc in keyword_results:
                doc_id = doc['id']
                if doc_id in combined_results:
                    # Document found in both searches - combine scores
                    combined_results[doc_id]['keyword_score'] = doc.get('relevance_score', 0)
                    combined_results[doc_id]['search_type'] = 'hybrid'
                else:
                    # Document only found in keyword search
                    combined_results[doc_id] = {
                        **doc,
                        'semantic_score': 0,
                        'keyword_score': doc.get('relevance_score', 0),
                        'search_type': 'keyword'
                    }
            
            # Calculate combined score (weighted average)
            for doc_id, doc in combined_results.items():
                semantic_weight = 0.7
                keyword_weight = 0.3
                
                # Normalize scores (semantic is 0-1, keyword can be higher)
                normalized_semantic = doc['semantic_score']
                normalized_keyword = min(doc['keyword_score'] / 100, 1.0) if doc['keyword_score'] > 0 else 0
                
                combined_score = (
                    semantic_weight * normalized_semantic + 
                    keyword_weight * normalized_keyword
                )
                
                combined_results[doc_id]['combined_score'] = combined_score
            
            # Sort by combined score and return top results
            sorted_results = sorted(
                combined_results.values(), 
                key=lambda x: x['combined_score'], 
                reverse=True
            )
            
            return sorted_results[:limit]
            
        except Exception as e:
            # Fallback to keyword search if semantic search fails
            print(f"Hybrid search failed, falling back to keyword search: {str(e)}")
            return await SemanticSearchService.keyword_search(user_email, query, limit)
    
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
    
    @staticmethod
    async def search_and_respond(user_email: str, query: str, limit: int = 10, search_type: str = "hybrid") -> Dict[str, Any]:
        """Search documents and generate AI response."""
        try:
            # Choose search method
            if search_type == "semantic":
                documents = await SemanticSearchService.semantic_search(user_email, query, limit)
            elif search_type == "keyword":
                documents = await SemanticSearchService.keyword_search(user_email, query, limit)
            else:  # hybrid (default)
                documents = await SemanticSearchService.hybrid_search(user_email, query, limit)
            
            # Generate AI response using existing logic
            ai_response = await SearchService.generate_ai_response(query, documents)
            
            return {
                "query": query,
                "search_type": search_type,
                "documents_found": len(documents),
                "relevant_documents": [
                    {
                        "id": doc["id"],
                        "title": doc.get("title") or doc.get("filename", "Untitled"),
                        "document_type": doc.get("document_type", "unknown"),
                        "filename": doc.get("filename"),  # Will be None for notes
                        "semantic_score": doc.get("semantic_score", 0),
                        "keyword_score": doc.get("keyword_score", 0),
                        "combined_score": doc.get("combined_score", doc.get("similarity", doc.get("relevance_score", 0))),
                        "search_type": doc.get("search_type", "unknown"),
                        "preview": SemanticSearchService._get_document_preview(doc)
                    }
                    for doc in documents
                ],
                "ai_response": ai_response
            }
            
        except Exception as e:
            print(f"❌ Search and respond error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Search and response failed: {str(e)}"
            )