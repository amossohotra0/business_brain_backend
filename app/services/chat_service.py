from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from app.services.conversation_service import ConversationService
from app.services.semantic_search_service import SemanticSearchService
from app.models.conversation import MessageCreate
import re

class ChatService:
    
    @staticmethod
    async def send_message_to_conversation(
        conversation_id: str,
        user_email: str,
        message_data: MessageCreate
    ) -> Dict[str, Any]:
        """Send a message to a conversation and get AI response with document search."""
        try:
            # Verify conversation exists and user owns it
            conversation = await ConversationService.get_conversation_by_id(conversation_id, user_email)
            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found"
                )
            
            # Save user message
            user_message = await ConversationService.save_message(
                conversation_id=conversation_id,
                user_email=user_email,
                role="user",
                content=message_data.content,
                search_query=message_data.content,
                search_type=message_data.search_type
            )
            
            # Perform document search using existing SemanticSearchService
            search_result = await SemanticSearchService.search_and_respond(
                user_email=user_email,
                query=message_data.content,
                limit=10,
                search_type=message_data.search_type
            )
            
            # Generate enhanced AI response with conversation context
            enhanced_response = await ChatService._enhance_response_with_context(
                conversation_id=conversation_id,
                user_email=user_email,
                original_response=search_result.get('ai_response', ''),
                search_results=search_result
            )
            
            # Save assistant message
            assistant_message = await ConversationService.save_message(
                conversation_id=conversation_id,
                user_email=user_email,
                role="assistant",
                content=enhanced_response,
                search_query=message_data.content,
                search_type=message_data.search_type,
                search_response=search_result
            )
            
            # Update conversation title if it's the first message
            if conversation['title'] == "New Conversation":
                auto_title = ChatService._generate_title_from_query(message_data.content)
                await ConversationService.update_conversation(
                    conversation_id=conversation_id,
                    user_email=user_email,
                    title=auto_title
                )
                conversation['title'] = auto_title
            
            # Get updated conversation info
            updated_conversation = await ConversationService.get_conversation_by_id(conversation_id, user_email)
            
            return {
                "conversation": updated_conversation,
                "user_message": user_message,
                "assistant_message": assistant_message,
                "search_results": search_result
            }
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Chat error: {str(e)}"
            )
    
    @staticmethod
    async def _enhance_response_with_context(
        conversation_id: str,
        user_email: str,
        original_response: str,
        search_results: Dict[str, Any]
    ) -> str:
        """Enhance AI response by considering conversation context."""
        try:
            # Get recent messages for context (last 5 messages)
            messages = await ConversationService.get_conversation_messages(conversation_id, user_email)
            recent_messages = messages[-5:] if len(messages) > 5 else messages
            
            # If this is the first message or no context, return original response
            if len(recent_messages) <= 1:  # Only the current user message
                return original_response
            
            # Build context from recent conversation
            context_parts = []
            for msg in recent_messages[:-1]:  # Exclude the current user message
                if msg['role'] == 'user':
                    context_parts.append(f"Previous question: {msg['content']}")
                elif msg['role'] == 'assistant':
                    # Only include a brief snippet of previous responses
                    snippet = msg['content'][:200] + "..." if len(msg['content']) > 200 else msg['content']
                    context_parts.append(f"Previous answer: {snippet}")
            
            # If we have context, enhance the response
            if context_parts:
                enhanced_response = f"{original_response}\n\n💡 *This response builds on our previous conversation about your documents.*"
                # return enhanced_response
            
            return original_response
            
        except Exception as e:
            # If context enhancement fails, return original response
            print(f"Context enhancement failed: {str(e)}")
            return original_response
    
    @staticmethod
    def _generate_title_from_query(query: str) -> str:
        """Generate a conversation title from the first user query."""
        try:
            # Clean and truncate the query
            cleaned_query = re.sub(r'[^\w\s]', '', query)  # Remove special characters
            words = cleaned_query.split()
            
            # Take first 4-6 words and capitalize appropriately
            if len(words) <= 3:
                title = ' '.join(words).title()
            elif len(words) <= 6:
                title = ' '.join(words[:4]).title() + "..."
            else:
                title = ' '.join(words[:3]).title() + "..."
            
            # Ensure title is not empty and has reasonable length
            if not title or title == "...":
                title = "Document Search"
            elif len(title) > 50:
                title = title[:47] + "..."
            
            return title
            
        except Exception:
            return "Document Search"
    
    @staticmethod
    async def create_conversation_with_first_message(
        user_email: str,
        message_data: MessageCreate
    ) -> Dict[str, Any]:
        """Create a new conversation and send the first message."""
        try:
            # Generate title from the first message
            auto_title = ChatService._generate_title_from_query(message_data.content)
            
            # Create conversation
            from app.models.conversation import ConversationCreate
            conversation_create = ConversationCreate(title=auto_title)
            conversation = await ConversationService.create_conversation(user_email, conversation_create)
            
            # Send the first message
            result = await ChatService.send_message_to_conversation(
                conversation_id=conversation['id'],
                user_email=user_email,
                message_data=message_data
            )
            
            return result
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create conversation with message: {str(e)}"
            )
    
    @staticmethod
    async def delete_message(message_id: str, user_email: str) -> bool:
        """Delete a specific message (optional feature)."""
        try:
            from app.db.supabase_client import supabase
            
            # Get user ID
            user_result = supabase.table('users').select('id').eq('email', user_email).execute()
            if not user_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            user_id = user_result.data[0]['id']
            
            # Verify message exists and user owns it
            message_result = supabase.table('chat_messages').select('*').eq('id', message_id).eq('user_id', user_id).execute()
            if not message_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Message not found"
                )
            
            # Delete message
            supabase.table('chat_messages').delete().eq('id', message_id).execute()
            
            return True
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Delete message error: {str(e)}"
            )