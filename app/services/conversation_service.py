from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from app.db.supabase_client import supabase
from app.models.conversation import ConversationCreate, MessageCreate
import uuid
from datetime import datetime

class ConversationService:
    
    @staticmethod
    async def create_conversation(user_email: str, conversation_data: ConversationCreate) -> Dict[str, Any]:
        """Create a new conversation for the user."""
        try:
            # Get user ID from email
            user_result = supabase.table('users').select('id').eq('email', user_email).execute()
            if not user_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            user_id = user_result.data[0]['id']
            
            # Generate title if not provided
            title = conversation_data.title or "New Conversation"
            
            # Create conversation record
            conversation_record = {
                'user_id': user_id,
                'title': title
            }
            
            result = supabase.table('conversations').insert(conversation_record).execute()
            
            if result.data:
                conversation = result.data[0]
                # Add required fields for schema validation
                conversation['message_count'] = 0
                conversation['last_message'] = None
                conversation['last_message_at'] = None
                return conversation
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create conversation"
                )
                
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {str(e)}"
            )
    
    @staticmethod
    async def get_user_conversations(user_email: str) -> List[Dict[str, Any]]:
        """Get all conversations for a user with message counts and last message info."""
        try:
            # Get user ID
            user_result = supabase.table('users').select('id').eq('email', user_email).execute()
            if not user_result.data:
                return []
            
            user_id = user_result.data[0]['id']
            
            # Get conversations with message counts using a more complex query
            conversations_result = supabase.table('conversations').select('*').eq('user_id', user_id).order('updated_at', desc=True).execute()
            
            if not conversations_result.data:
                return []
            
            conversations = []
            for conv in conversations_result.data:
                # Get message count and last message for each conversation
                messages_result = supabase.table('chat_messages').select('content, created_at').eq('conversation_id', conv['id']).order('created_at', desc=True).limit(1).execute()
                
                message_count_result = supabase.table('chat_messages').select('id', count='exact').eq('conversation_id', conv['id']).execute()
                
                # Add computed fields
                conv['message_count'] = message_count_result.count or 0
                
                if messages_result.data:
                    last_msg = messages_result.data[0]
                    conv['last_message'] = last_msg['content'][:100] + '...' if len(last_msg['content']) > 100 else last_msg['content']
                    conv['last_message_at'] = last_msg['created_at']
                else:
                    conv['last_message'] = None
                    conv['last_message_at'] = None
                
                conversations.append(conv)
            
            return conversations
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching conversations: {str(e)}"
            )
    
    @staticmethod
    async def get_conversation_by_id(conversation_id: str, user_email: str) -> Optional[Dict[str, Any]]:
        """Get a specific conversation by ID with message count."""
        try:
            # Get user ID
            user_result = supabase.table('users').select('id').eq('email', user_email).execute()
            if not user_result.data:
                return None
            
            user_id = user_result.data[0]['id']
            
            # Get conversation
            result = supabase.table('conversations').select('*').eq('id', conversation_id).eq('user_id', user_id).execute()
            
            if result.data:
                conversation = result.data[0]
                
                # Add message count and last message info
                messages_result = supabase.table('chat_messages').select('content, created_at').eq('conversation_id', conversation_id).order('created_at', desc=True).limit(1).execute()
                message_count_result = supabase.table('chat_messages').select('id', count='exact').eq('conversation_id', conversation_id).execute()
                
                conversation['message_count'] = message_count_result.count or 0
                if messages_result.data:
                    last_msg = messages_result.data[0]
                    conversation['last_message'] = last_msg['content'][:100] + '...' if len(last_msg['content']) > 100 else last_msg['content']
                    conversation['last_message_at'] = last_msg['created_at']
                else:
                    conversation['last_message'] = None
                    conversation['last_message_at'] = None
                
                return conversation
            return None
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching conversation: {str(e)}"
            )
    
    @staticmethod
    async def update_conversation(conversation_id: str, user_email: str, title: str) -> Dict[str, Any]:
        """Update conversation title."""
        try:
            # Verify conversation exists and user owns it
            existing_conversation = await ConversationService.get_conversation_by_id(conversation_id, user_email)
            if not existing_conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found"
                )
            
            # Update conversation
            update_data = {
                'title': title,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            result = supabase.table('conversations').update(update_data).eq('id', conversation_id).execute()
            
            if result.data:
                updated_conv = result.data[0]
                # Add message count and last message info
                messages_result = supabase.table('chat_messages').select('content, created_at').eq('conversation_id', conversation_id).order('created_at', desc=True).limit(1).execute()
                message_count_result = supabase.table('chat_messages').select('id', count='exact').eq('conversation_id', conversation_id).execute()
                
                updated_conv['message_count'] = message_count_result.count or 0
                if messages_result.data:
                    last_msg = messages_result.data[0]
                    updated_conv['last_message'] = last_msg['content'][:100] + '...' if len(last_msg['content']) > 100 else last_msg['content']
                    updated_conv['last_message_at'] = last_msg['created_at']
                else:
                    updated_conv['last_message'] = None
                    updated_conv['last_message_at'] = None
                
                return updated_conv
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update conversation"
                )
                
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Update error: {str(e)}"
            )
    
    @staticmethod
    async def delete_conversation(conversation_id: str, user_email: str) -> bool:
        """Delete a conversation and all its messages."""
        try:
            # Verify conversation exists and user owns it
            existing_conversation = await ConversationService.get_conversation_by_id(conversation_id, user_email)
            if not existing_conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found"
                )
            
            # Delete conversation (messages will be deleted automatically due to CASCADE)
            result = supabase.table('conversations').delete().eq('id', conversation_id).execute()
            
            return True
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Delete error: {str(e)}"
            )
    
    @staticmethod
    async def get_conversation_messages(conversation_id: str, user_email: str) -> List[Dict[str, Any]]:
        """Get all messages for a conversation."""
        try:
            # Verify conversation exists and user owns it
            existing_conversation = await ConversationService.get_conversation_by_id(conversation_id, user_email)
            if not existing_conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found"
                )
            
            # Get messages
            result = supabase.table('chat_messages').select('*').eq('conversation_id', conversation_id).order('created_at', desc=False).execute()
            
            return result.data or []
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching messages: {str(e)}"
            )
    
    @staticmethod
    async def save_message(
        conversation_id: str, 
        user_email: str, 
        role: str, 
        content: str,
        search_query: Optional[str] = None,
        search_type: Optional[str] = None,
        search_response: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Save a message to a conversation."""
        try:
            # Get user ID
            user_result = supabase.table('users').select('id').eq('email', user_email).execute()
            if not user_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            user_id = user_result.data[0]['id']
            
            # Verify conversation exists and user owns it
            existing_conversation = await ConversationService.get_conversation_by_id(conversation_id, user_email)
            if not existing_conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found"
                )
            
            # Create message record
            message_record = {
                'conversation_id': conversation_id,
                'user_id': user_id,
                'role': role,
                'content': content,
                'search_query': search_query,
                'search_type': search_type,
                'search_response': search_response
            }
            
            result = supabase.table('chat_messages').insert(message_record).execute()
            
            if result.data:
                # Update conversation's updated_at timestamp
                supabase.table('conversations').update({
                    'updated_at': datetime.utcnow().isoformat()
                }).eq('id', conversation_id).execute()
                
                return result.data[0]
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to save message"
                )
                
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {str(e)}"
            )