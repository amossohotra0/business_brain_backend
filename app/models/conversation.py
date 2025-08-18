from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"

class SearchType(str, Enum):
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"

# Request Models
class ConversationCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=255, description="Conversation title (auto-generated if not provided)")

class ConversationUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="New conversation title")

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, description="User message content")
    search_type: Optional[SearchType] = Field(SearchType.HYBRID, description="Type of search to perform")

# Response Models
class ConversationResponse(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: Optional[int] = Field(None, description="Total number of messages in conversation")
    last_message: Optional[str] = Field(None, description="Preview of the last message")
    last_message_at: Optional[datetime] = Field(None, description="Timestamp of last message")

    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    user_id: str
    role: MessageRole
    content: str
    search_query: Optional[str] = None
    search_type: Optional[SearchType] = None
    search_response: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ConversationWithMessages(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse]

    class Config:
        from_attributes = True

# List Response Models
class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]
    total: int

class MessageListResponse(BaseModel):
    messages: List[MessageResponse]
    total: int
    conversation_id: str

# Chat Search Response (extends existing search response)
class ChatSearchResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    search_results: Dict[str, Any]  # This will contain the existing search response format