from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from app.db.supabase_client import supabase
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.user import UserCreate, UserLogin
from datetime import timedelta
from app.core.config import settings

class AuthService:
    
    @staticmethod
    async def create_user(user_data: UserCreate) -> Dict[str, Any]:
        """Create a new user in the database."""
        try:
            # Check if user already exists
            existing_user = supabase.table('users').select('email').eq('email', user_data.email).execute()
            
            if existing_user.data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            
            # Hash the password
            hashed_password = get_password_hash(user_data.password)
            
            # Create user data
            user_dict = {
                'email': user_data.email,
                'full_name': user_data.full_name,
                'hashed_password': hashed_password,
                'is_active': True
            }
            
            # Insert user into database
            result = supabase.table('users').insert(user_dict).execute()
            
            if result.data:
                user = result.data[0]
                # Remove hashed_password from response
                user.pop('hashed_password', None)
                return user
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user"
                )
                
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {str(e)}"
            )
    
    @staticmethod
    async def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user and return user data if valid."""
        try:
            # Get user from database
            result = supabase.table('users').select('*').eq('email', email).execute()
            
            if not result.data:
                return None
            
            user = result.data[0]
            
            # Verify password
            if not verify_password(password, user['hashed_password']):
                return None
            
            # Remove hashed_password from user data
            user.pop('hashed_password', None)
            return user
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Authentication error: {str(e)}"
            )
    
    @staticmethod
    async def login_user(user_data: UserLogin) -> Dict[str, Any]:
        """Login user and return access token."""
        user = await AuthService.authenticate_user(user_data.email, user_data.password)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user['email']}, 
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user
        }
    
    @staticmethod
    async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
        """Get user by email."""
        try:
            result = supabase.table('users').select('*').eq('email', email).execute()
            
            if result.data:
                user = result.data[0]
                user.pop('hashed_password', None)
                return user
            return None
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {str(e)}"
            )