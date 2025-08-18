from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List
from app.services.conversation_service import ConversationService
from app.services.chat_service import ChatService
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationUpdateRequest,
    MessageSendRequest,
    ConversationSchema,
    ConversationListSchema,
    MessageListSchema,
    ChatResponseSchema,
    ConversationCreateResponse,
    ConversationUpdateResponse,
    ConversationDeleteResponse,
    MessageResponse
)
from app.core.security import verify_token

router = APIRouter(prefix="/conversations", tags=["Conversations"])
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

# Conversation Management Routes

@router.post("/", response_model=ConversationCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation_data: ConversationCreateRequest,
    current_user_email: str = Depends(get_current_user_email)
):
    """Create a new conversation."""
    from app.models.conversation import ConversationCreate
    
    conversation_create = ConversationCreate(title=conversation_data.title)
    conversation = await ConversationService.create_conversation(current_user_email, conversation_create)
    
    return ConversationCreateResponse(
        message="Conversation created successfully",
        conversation=ConversationSchema(**conversation)
    )

@router.get("/", response_model=ConversationListSchema)
async def list_conversations(current_user_email: str = Depends(get_current_user_email)):
    """Get all conversations for the current user."""
    conversations = await ConversationService.get_user_conversations(current_user_email)
    
    return ConversationListSchema(
        conversations=[ConversationSchema(**conv) for conv in conversations],
        total=len(conversations)
    )

@router.get("/{conversation_id}", response_model=ConversationSchema)
async def get_conversation(
    conversation_id: str,
    current_user_email: str = Depends(get_current_user_email)
):
    """Get a specific conversation."""
    conversation = await ConversationService.get_conversation_by_id(conversation_id, current_user_email)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    return ConversationSchema(**conversation)

@router.put("/{conversation_id}", response_model=ConversationUpdateResponse)
async def update_conversation(
    conversation_id: str,
    conversation_data: ConversationUpdateRequest,
    current_user_email: str = Depends(get_current_user_email)
):
    """Update conversation title."""
    updated_conversation = await ConversationService.update_conversation(
        conversation_id, current_user_email, conversation_data.title
    )
    
    return ConversationUpdateResponse(
        message="Conversation updated successfully",
        conversation=ConversationSchema(**updated_conversation)
    )

@router.delete("/{conversation_id}", response_model=ConversationDeleteResponse)
async def delete_conversation(
    conversation_id: str,
    current_user_email: str = Depends(get_current_user_email)
):
    """Delete a conversation and all its messages."""
    await ConversationService.delete_conversation(conversation_id, current_user_email)
    
    return ConversationDeleteResponse(message="Conversation deleted successfully")

# Message Management Routes

@router.get("/{conversation_id}/messages", response_model=MessageListSchema)
async def get_conversation_messages(
    conversation_id: str,
    current_user_email: str = Depends(get_current_user_email)
):
    """Get all messages for a conversation."""
    messages = await ConversationService.get_conversation_messages(conversation_id, current_user_email)
    
    return MessageListSchema(
        messages=messages,
        total=len(messages),
        conversation_id=conversation_id
    )

@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: str,
    message_data: MessageSendRequest,
    current_user_email: str = Depends(get_current_user_email)
):
    """Send a message to a conversation and get AI response."""
    from app.models.conversation import MessageCreate
    
    message_create = MessageCreate(
        content=message_data.content,
        search_type=message_data.search_type
    )
    
    result = await ChatService.send_message_to_conversation(
        conversation_id=conversation_id,
        user_email=current_user_email,
        message_data=message_create
    )
    
    return MessageResponse(
        message="Message sent successfully",
        data=ChatResponseSchema(**result)
    )

# Quick Chat Route (Create conversation + send first message)

@router.post("/quick-chat", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def quick_chat(
    message_data: MessageSendRequest,
    current_user_email: str = Depends(get_current_user_email)
):
    """Create a new conversation and send the first message in one request."""
    from app.models.conversation import MessageCreate
    
    message_create = MessageCreate(
        content=message_data.content,
        search_type=message_data.search_type
    )
    
    result = await ChatService.create_conversation_with_first_message(
        user_email=current_user_email,
        message_data=message_create
    )
    
    return MessageResponse(
        message="Conversation created and message sent successfully",
        data=ChatResponseSchema(**result)
    )

# Enhanced Search Route (Legacy compatibility)

@router.post("/{conversation_id}/search")
async def search_in_conversation(
    conversation_id: str,
    search_request: MessageSendRequest,
    current_user_email: str = Depends(get_current_user_email)
):
    """
    Legacy route for search functionality - redirects to send_message.
    Maintains backward compatibility with existing search API.
    """
    from app.models.conversation import MessageCreate
    
    message_create = MessageCreate(
        content=search_request.content,
        search_type=search_request.search_type
    )
    
    result = await ChatService.send_message_to_conversation(
        conversation_id=conversation_id,
        user_email=current_user_email,
        message_data=message_create
    )
    
    # Return in the format similar to the original search API
    return {
        "query": search_request.content,
        "search_type": search_request.search_type,
        "documents_found": result["search_results"].get("documents_found", 0),
        "relevant_documents": result["search_results"].get("relevant_documents", []),
        "ai_response": result["assistant_message"]["content"],
        "conversation_id": conversation_id,
        "user_message_id": result["user_message"]["id"],
        "assistant_message_id": result["assistant_message"]["id"]
    }

# Message Operations

@router.delete("/messages/{message_id}", response_model=dict)
async def delete_message(
    message_id: str,
    current_user_email: str = Depends(get_current_user_email)
):
    """Delete a specific message."""
    success = await ChatService.delete_message(message_id, current_user_email)
    
    if success:
        return {"message": "Message deleted successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete message"
        )