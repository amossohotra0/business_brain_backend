from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth_service import AuthService
from app.models.user import UserCreate, UserLogin
from app.schemas.auth import SignupRequest, LoginRequest, AuthResponse, MessageResponse
from app.core.security import verify_token

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()

@router.post("/signup", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def signup(user_data: SignupRequest):
    """Register a new user."""
    user_create = UserCreate(**user_data.dict())
    user = await AuthService.create_user(user_create)
    
    return MessageResponse(message="User created successfully")

@router.post("/login", response_model=AuthResponse)
async def login(user_data: LoginRequest):
    """Login user and return access token."""
    user_login = UserLogin(**user_data.dict())
    result = await AuthService.login_user(user_login)
    
    return AuthResponse(
        access_token=result["access_token"],
        token_type=result["token_type"],
        user=result["user"]
    )

@router.get("/me", response_model=dict)
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user information."""
    token = credentials.credentials
    payload = verify_token(token)
    
    email = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    user = await AuthService.get_user_by_email(email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user

@router.post("/logout", response_model=MessageResponse)
async def logout():
    """Logout user (client-side token removal)."""
    return MessageResponse(message="Successfully logged out")