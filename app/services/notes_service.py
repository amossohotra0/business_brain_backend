from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from app.db.supabase_client import supabase
from app.models.document import NoteCreate, NoteUpdate, DocumentType
from app.services.embedding_service import EmbeddingService

class NotesService:
    
    @staticmethod
    async def create_note(user_email: str, note_data: NoteCreate) -> Dict[str, Any]:
        """Create a new note."""
        try:
            # Get user ID from email
            user_result = supabase.table('users').select('id').eq('email', user_email).execute()
            if not user_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            user_id = user_result.data[0]['id']
            
            # Create note record
            note_record = {
                'user_id': user_id,
                'title': note_data.title,
                'description': note_data.description,
                'document_type': DocumentType.NOTE.value,
                'ocr_status': 'completed'  # Notes are immediately "completed"
            }
            
            # Insert note into database
            result = supabase.table('documents').insert(note_record).execute()
            
            if result.data:
                note = result.data[0]
                
                # Generate embedding for the note content (title + description)
                try:
                    content_for_embedding = f"{note_data.title}\n\n{note_data.description}"
                    await EmbeddingService.process_document_embedding(
                        note['id'], 
                        content_for_embedding
                    )
                    print(f"✅ Embedding generated for note {note['id']}")
                except Exception as e:
                    print(f"⚠️ Embedding generation failed for note {note['id']}: {str(e)}")
                    # Continue even if embedding fails
                
                return note
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create note"
                )
                
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {str(e)}"
            )
    
    @staticmethod
    async def get_user_notes(user_email: str) -> List[Dict[str, Any]]:
        """Get all notes for a user."""
        try:
            # Get user ID
            user_result = supabase.table('users').select('id').eq('email', user_email).execute()
            if not user_result.data:
                return []
            
            user_id = user_result.data[0]['id']
            
            # Get notes
            result = supabase.table('documents').select('*').eq('user_id', user_id).eq('document_type', 'note').order('created_at', desc=True).execute()
            return result.data or []
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching notes: {str(e)}"
            )
    
    @staticmethod
    async def get_note_by_id(note_id: str, user_email: str) -> Optional[Dict[str, Any]]:
        """Get a specific note by ID."""
        try:
            # Get user ID
            user_result = supabase.table('users').select('id').eq('email', user_email).execute()
            if not user_result.data:
                return None
            
            user_id = user_result.data[0]['id']
            
            # Get note
            result = supabase.table('documents').select('*').eq('id', note_id).eq('user_id', user_id).eq('document_type', 'note').execute()
            return result.data[0] if result.data else None
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching note: {str(e)}"
            )
    
    @staticmethod
    async def update_note(note_id: str, user_email: str, note_data: NoteUpdate) -> Dict[str, Any]:
        """Update an existing note."""
        try:
            # Verify note exists and user owns it
            existing_note = await NotesService.get_note_by_id(note_id, user_email)
            if not existing_note:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Note not found"
                )
            
            # Prepare update data
            update_data = {'updated_at': 'NOW()'}
            
            if note_data.title is not None:
                update_data['title'] = note_data.title
            
            if note_data.description is not None:
                update_data['description'] = note_data.description
            
            # Update note
            result = supabase.table('documents').update(update_data).eq('id', note_id).execute()
            
            if result.data:
                updated_note = result.data[0]
                
                # Regenerate embedding if content changed
                if note_data.title is not None or note_data.description is not None:
                    try:
                        content_for_embedding = f"{updated_note['title']}\n\n{updated_note['description']}"
                        await EmbeddingService.process_document_embedding(
                            note_id, 
                            content_for_embedding
                        )
                        print(f"✅ Embedding updated for note {note_id}")
                    except Exception as e:
                        print(f"⚠️ Embedding update failed for note {note_id}: {str(e)}")
                
                return updated_note
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update note"
                )
                
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Update error: {str(e)}"
            )
    
    @staticmethod
    async def delete_note(note_id: str, user_email: str) -> bool:
        """Delete a note."""
        try:
            # Verify note exists and user owns it
            existing_note = await NotesService.get_note_by_id(note_id, user_email)
            if not existing_note:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Note not found"
                )
            
            # Delete note
            result = supabase.table('documents').delete().eq('id', note_id).execute()
            
            return True
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Delete error: {str(e)}"
            )