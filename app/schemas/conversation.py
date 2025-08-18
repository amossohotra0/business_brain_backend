from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime

# Request Schemas
class ConversationCreateRequest(BaseModel):
    title: Optional[str] = Field(
        None, 
        max_length=255, 
        description="Conversation title. If not provided, will be auto-generated from first message"
    )

class ConversationUpdateRequest(BaseModel):
    title: str = Field(
        ..., 
        min_length=1, 
        max_length=255, 
        description="New conversation title"
    )

class MessageSendRequest(BaseModel):
    content: str = Field(
        ..., 
        min_length=1, 
        max_length=10000,
        description="Message content from user"
    )
    search_type: Optional[Literal["semantic", "keyword", "hybrid"]] = Field(
        "hybrid", 
        description="Type of document search to perform"
    )

# Response Schemas
class ConversationSchema(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = Field(description="Total number of messages in this conversation")
    last_message: Optional[str] = Field(None, description="Preview of the last message (first 100 chars)")
    last_message_at: Optional[datetime] = Field(None, description="Timestamp of the last message")

class MessageSchema(BaseModel):
    id: str
    conversation_id: str
    user_id: str
    role: Literal["user", "assistant"]
    content: str
    search_query: Optional[str] = None
    search_type: Optional[Literal["semantic", "keyword", "hybrid"]] = None
    search_response: Optional[Dict[str, Any]] = None
    created_at: datetime

class ConversationDetailSchema(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageSchema]

# List Response Schemas
class ConversationListSchema(BaseModel):
    conversations: List[ConversationSchema]
    total: int

class MessageListSchema(BaseModel):
    messages: List[MessageSchema]
    total: int
    conversation_id: str

# Chat Response Schema (for sending messages)
class ChatResponseSchema(BaseModel):
    conversation: ConversationSchema
    user_message: MessageSchema
    assistant_message: MessageSchema
    search_results: Dict[str, Any] = Field(description="Document search results and AI response")

# Standard API Response Schemas
class ConversationCreateResponse(BaseModel):
    message: str
    conversation: ConversationSchema

class ConversationUpdateResponse(BaseModel):
    message: str
    conversation: ConversationSchema

class ConversationDeleteResponse(BaseModel):
    message: str

class MessageResponse(BaseModel):
    message: str = "Message sent successfully"
    data: ChatResponseSchema