from pydantic import BaseModel
from typing import List, Optional, Literal
from app.models.document import DocumentResponse

class DocumentSearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 10
    search_type: Optional[Literal["semantic", "keyword", "hybrid"]] = "semantic"

class DocumentSearchResponse(BaseModel):
    query: str
    search_type: str  # Add this line
    documents_found: int
    relevant_documents: List[dict]
    ai_response: Optional[str] = None

class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int

class SearchComparisonResponse(BaseModel):  # Add this new model
    query: str
    semantic_search: DocumentSearchResponse
    keyword_search: DocumentSearchResponse
    hybrid_search: DocumentSearchResponse