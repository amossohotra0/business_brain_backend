from fastapi import APIRouter, Request, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import base64
import json
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from app.core.security import verify_token
from app.db.supabase_client import supabase
from app.core.config import settings
from app.schemas.gmail import (
    EmailResponse, EmailListResponse, EmailDetailResponse, 
    EmailStarResponse, EmailSyncResponse, GmailAuthResponse,
    GmailWatchResponse, WebhookResponse, ErrorResponse,
    EmailAttachment
)
import asyncio
import uuid
import logging

load_dotenv()
router = APIRouter(prefix="/gmail", tags=["Gmail"])
security = HTTPBearer()

# Setup logging
logger = logging.getLogger(__name__)

# WebSocket connections for real-time updates
websocket_connections: Dict[str, WebSocket] = {}

# Gmail OAuth scopes
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email"
]

# ===== Authentication Helper =====
async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Extract user ID from JWT token."""
    token = credentials.credentials
    payload = verify_token(token)
    user_id = payload.get("user_id") or payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    return user_id

# ===== Database Helper Functions =====
async def get_user_gmail_token(user_id: str) -> Optional[Dict]:
    """Get user's Gmail refresh token from database."""
    try:
        result = supabase.table('gmail_tokens').select('*').eq('user_id', user_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error getting Gmail token: {e}")
        return None

async def save_user_gmail_token(user_id: str, email_address: str, refresh_token: str, access_token: str = None, expires_at: datetime = None):
    """Save user's Gmail tokens to database."""
    try:
        token_data = {
            'user_id': user_id,
            'email_address': email_address,
            'refresh_token': refresh_token,
            'updated_at': datetime.utcnow().isoformat()
        }
        
        if access_token:
            token_data['access_token'] = access_token
        if expires_at:
            token_data['expires_at'] = expires_at.isoformat()
            
        result = supabase.table('gmail_tokens').upsert(token_data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error saving Gmail token: {e}")
        return None

async def save_email_to_db(user_id: str, email_data: Dict) -> Optional[Dict]:
    """Save email to database."""
    try:
        # Check if email already exists
        existing = supabase.table('emails').select('id').eq('gmail_id', email_data['id']).execute()
        if existing.data:
            print(f"Email {email_data['id']} already exists in database")
            return existing.data[0]

        # Prepare email data for database
        db_email_data = {
            'user_id': user_id,
            'gmail_id': email_data['id'],
            'thread_id': email_data.get('thread_id'),
            'subject': email_data.get('subject'),
            'from_email': email_data.get('from'),
            'to_email': email_data.get('to'),
            'cc_email': email_data.get('cc'),
            'bcc_email': email_data.get('bcc'),
            'date': email_data.get('date'),
            'readable_date': email_data.get('readable_date'),
            'message_id': email_data.get('message_id'),
            'snippet': email_data.get('snippet'),
            'body_text': email_data.get('body_text'),
            'body_html': email_data.get('body_html'),
            'attachments': email_data.get('attachments', []),
            'labels': email_data.get('labels', []),
            'headers': email_data.get('headers', {}),
            'size_estimate': email_data.get('size_estimate', 0),
            'is_read': False,
            'is_starred': False,
            'is_important': False
        }

        result = supabase.table('emails').insert(db_email_data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error saving email to database: {e}")
        return None

async def get_user_emails(user_id: str, limit: int = 20, offset: int = 0) -> Dict:
    """Get user's emails from database."""
    try:
        # Get emails with pagination
        emails_result = supabase.table('emails').select('*').eq('user_id', user_id).eq('is_deleted', False).order('readable_date', desc=True).range(offset, offset + limit - 1).execute()
        
        # Get total count
        total_result = supabase.table('emails').select('id', count='exact').eq('user_id', user_id).eq('is_deleted', False).execute()
        
        # Get unread count
        unread_result = supabase.table('emails').select('id', count='exact').eq('user_id', user_id).eq('is_read', False).eq('is_deleted', False).execute()

        return {
            'emails': emails_result.data or [],
            'total': total_result.count or 0,
            'unread_count': unread_result.count or 0
        }
    except Exception as e:
        print(f"Error getting user emails: {e}")
        return {'emails': [], 'total': 0, 'unread_count': 0}

async def get_email_by_id(user_id: str, email_id: str) -> Optional[Dict]:
    """Get specific email by ID."""
    try:
        result = supabase.table('emails').select('*').eq('user_id', user_id).eq('id', email_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error getting email by ID: {e}")
        return None

async def mark_email_as_read(user_id: str, email_id: str) -> bool:
    """Mark email as read."""
    try:
        result = supabase.table('emails').update({'is_read': True}).eq('user_id', user_id).eq('id', email_id).execute()
        return bool(result.data)
    except Exception as e:
        print(f"Error marking email as read: {e}")
        return False

# ===== Gmail Service Helper =====
async def get_gmail_service(user_id: str):
    """Get authenticated Gmail service for user."""
    try:
        token_data = await get_user_gmail_token(user_id)
        if not token_data:
            raise HTTPException(status_code=401, detail="User not authenticated with Gmail")

        if not token_data.get('refresh_token'):
            raise HTTPException(status_code=401, detail="No valid refresh token found")

        # Check if access token is still valid
        access_token = token_data.get('access_token')
        expires_at = token_data.get('expires_at')
        
        creds = Credentials(
            token=access_token,
            refresh_token=token_data['refresh_token'],
            token_uri=settings.GOOGLE_TOKEN_URI,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=GMAIL_SCOPES
        )
        
        # Check if token needs refresh
        needs_refresh = False
        if not access_token:
            needs_refresh = True
        elif expires_at:
            try:
                exp_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                needs_refresh = exp_time <= datetime.utcnow().replace(tzinfo=exp_time.tzinfo)
            except (ValueError, TypeError):
                needs_refresh = True
        
        if needs_refresh:
            try:
                creds.refresh(GoogleRequest())
                # Save updated tokens
                new_expires_at = datetime.utcnow() + timedelta(seconds=3600)  # 1 hour default
                await save_user_gmail_token(
                    user_id, 
                    token_data['email_address'], 
                    creds.refresh_token,
                    creds.token,
                    new_expires_at
                )
            except Exception as e:
                logger.error(f"Failed to refresh Gmail credentials for user {user_id}: {e}")
                raise HTTPException(
                    status_code=401, 
                    detail="Gmail authentication expired. Please reconnect your Gmail account."
                )
        
        return build("gmail", "v1", credentials=creds)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Gmail service for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to connect to Gmail service")

# ===== WebSocket for Real-time Updates =====
@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time email notifications.
    
    Args:
        websocket: WebSocket connection
        user_id: User ID for the connection
        
    WebSocket Message Format:
        {
            "type": "new_email",
            "data": {
                "id": "email_id",
                "subject": "Email subject",
                "from_email": "sender@example.com",
                "snippet": "Email preview..."
            }
        }
    """
    try:
        await websocket.accept()
        websocket_connections[user_id] = websocket
        logger.info(f"WebSocket connected for user: {user_id}")
        
        # Send connection confirmation
        await websocket.send_json({
            "type": "connection_established",
            "data": {"user_id": user_id, "timestamp": datetime.now().isoformat()}
        })
        
        while True:
            # Keep connection alive and handle ping/pong
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if message == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({
                    "type": "heartbeat",
                    "data": {"timestamp": datetime.now().isoformat()}
                })
    except WebSocketDisconnect:
        websocket_connections.pop(user_id, None)
        logger.info(f"WebSocket disconnected for user: {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        websocket_connections.pop(user_id, None)
        try:
            await websocket.close()
        except:
            pass

async def notify_new_email(user_id: str, email_data: Dict):
    """Send real-time notification to frontend."""
    if user_id in websocket_connections:
        try:
            await websocket_connections[user_id].send_json({
                "type": "new_email",
                "data": email_data
            })
        except Exception as e:
            print(f"Error sending WebSocket message: {e}")
            websocket_connections.pop(user_id, None)

# ===== OAuth Endpoints =====
@router.get("/auth", 
    summary="Start Gmail OAuth",
    description="Initiate Gmail OAuth flow for user authentication",
    responses={
        302: {"description": "Redirect to Google OAuth"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def google_auth(user_id: str = Depends(get_current_user_id)):
    """Start Gmail OAuth flow."""
    try:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
                    "auth_uri": settings.GOOGLE_AUTH_URI,
                    "token_uri": settings.GOOGLE_TOKEN_URI
                }
            },
            scopes=GMAIL_SCOPES
        )
        flow.redirect_uri = settings.GOOGLE_REDIRECT_URI

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            include_granted_scopes="true",
            state=user_id  # Pass user_id in state
        )
        return RedirectResponse(auth_url)
    except Exception as e:
        logger.error(f"Error starting Gmail OAuth: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start OAuth flow: {str(e)}")

@router.get("/oauth2callback", 
    response_model=GmailAuthResponse,
    summary="Gmail OAuth Callback",
    description="Handle Gmail OAuth callback and save user credentials",
    responses={
        200: {"model": GmailAuthResponse, "description": "Successfully authenticated"},
        400: {"model": ErrorResponse, "description": "Invalid callback parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def google_callback(
    code: str = Query(..., description="OAuth authorization code"),
    state: str = Query(..., description="User ID passed in OAuth state")
):
    """Handle Gmail OAuth callback."""
    try:
        user_id = state  # Get user_id from state
        
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID is required in state parameter")
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
                    "auth_uri": settings.GOOGLE_AUTH_URI,
                    "token_uri": settings.GOOGLE_TOKEN_URI
                }
            },
            scopes=GMAIL_SCOPES
        )
        flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
        flow.fetch_token(code=code)

        credentials = flow.credentials
        
        if not credentials.refresh_token:
            raise HTTPException(
                status_code=400, 
                detail="No refresh token received. Please revoke access and try again."
            )
        
        # Get Gmail profile and save tokens
        creds = Credentials(
            token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_uri=settings.GOOGLE_TOKEN_URI,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=GMAIL_SCOPES
        )
        
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        
        email_address = profile.get("emailAddress")
        if not email_address:
            raise HTTPException(status_code=500, detail="Could not retrieve email address from Gmail")
        
        # Calculate token expiration
        expires_at = datetime.utcnow() + timedelta(seconds=getattr(credentials, 'expires_in', 3600))
        
        # Save tokens to database
        await save_user_gmail_token(
            user_id, 
            email_address, 
            credentials.refresh_token,
            credentials.token,
            expires_at
        )
        
        # Start watching emails
        await start_gmail_watch(user_id)
        
        return GmailAuthResponse(
            status="success",
            email=email_address,
            message="Gmail connected successfully"
        )
    except HttpError as e:
        logger.error(f"Gmail API error in callback: {e}")
        raise HTTPException(status_code=400, detail=f"Gmail API error: {str(e)}")
    except Exception as e:
        logger.error(f"Error in Gmail callback: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to complete OAuth flow: {str(e)}")

# ===== Email Endpoints =====
@router.get("/emails", 
    response_model=EmailListResponse,
    summary="List User Emails",
    description="Get paginated list of user's emails from database",
    responses={
        200: {"model": EmailListResponse, "description": "Successfully retrieved emails"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def list_emails(
    limit: int = Query(20, ge=1, le=100, description="Number of emails to retrieve (1-100)"),
    offset: int = Query(0, ge=0, description="Number of emails to skip"),
    user_id: str = Depends(get_current_user_id)
):
    """Get user's emails from database."""
    try:
        data = await get_user_emails(user_id, limit, offset)
        
        emails = []
        for email in data['emails']:
            # Convert attachments to proper format
            attachments = []
            if email.get('attachments'):
                for att in email['attachments']:
                    if isinstance(att, dict):
                        attachments.append(EmailAttachment(
                            filename=att.get('filename', ''),
                            mime_type=att.get('mime_type', ''),
                            size=att.get('size', 0),
                            attachment_id=att.get('attachment_id')
                        ))
            
            emails.append(EmailResponse(
                id=email['id'],
                gmail_id=email['gmail_id'],
                thread_id=email['thread_id'],
                subject=email['subject'],
                from_email=email['from_email'],
                to_email=email['to_email'],
                date=email['date'],
                readable_date=email['readable_date'],
                snippet=email['snippet'],
                body_text=email['body_text'],
                body_html=email['body_html'],
                attachments=attachments,
                is_read=email['is_read'],
                is_starred=email['is_starred'],
                size_estimate=email['size_estimate'] or 0,
                created_at=email['created_at']
            ))
        
        return EmailListResponse(
            emails=emails,
            total=data['total'],
            unread_count=data['unread_count']
        )
    except Exception as e:
        logger.error(f"Error listing emails: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve emails: {str(e)}")

@router.get("/emails/{email_id}", response_model=EmailDetailResponse)
async def get_email_detail(
    email_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Get detailed email information."""
    email = await get_email_by_id(user_id, email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    # Mark as read when viewed
    await mark_email_as_read(user_id, email_id)
    
    return EmailDetailResponse(
        id=email['id'],
        gmail_id=email['gmail_id'],
        thread_id=email['thread_id'],
        subject=email['subject'],
        from_email=email['from_email'],
        to_email=email['to_email'],
        cc_email=email['cc_email'],
        bcc_email=email['bcc_email'],
        date=email['date'],
        readable_date=email['readable_date'],
        snippet=email['snippet'],
        body_text=email['body_text'],
        body_html=email['body_html'],
        attachments=email['attachments'] or [],
        headers=email['headers'] or {},
        labels=email['labels'] or [],
        is_read=True,  # Mark as read
        is_starred=email['is_starred'],
        size_estimate=email['size_estimate'] or 0,
        created_at=email['created_at']
    )

@router.post("/emails/{email_id}/star", 
    response_model=EmailStarResponse,
    summary="Star/Unstar Email",
    description="Toggle star status of an email",
    responses={
        200: {"model": EmailStarResponse, "description": "Successfully updated star status"},
        404: {"model": ErrorResponse, "description": "Email not found"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def star_email(
    email_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Star/unstar an email."""
    try:
        email = await get_email_by_id(user_id, email_id)
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        
        new_starred_status = not email['is_starred']
        result = supabase.table('emails').update({'is_starred': new_starred_status}).eq('user_id', user_id).eq('id', email_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to update email star status")
        
        return EmailStarResponse(
            starred=new_starred_status, 
            message=f"Email {'starred' if new_starred_status else 'unstarred'}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating email star status: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating email: {str(e)}")

@router.post("/sync", 
    response_model=EmailSyncResponse,
    summary="Sync Emails",
    description="Manually sync recent emails from Gmail",
    responses={
        200: {"model": EmailSyncResponse, "description": "Successfully synced emails"},
        401: {"model": ErrorResponse, "description": "Unauthorized or Gmail not connected"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def sync_emails(
    max_results: int = Query(20, ge=1, le=100, description="Maximum number of emails to sync (1-100)"),
    user_id: str = Depends(get_current_user_id)
):
    """Manually sync recent emails from Gmail."""
    try:
        service = await get_gmail_service(user_id)
        
        # Get latest messages
        results = service.users().messages().list(userId="me", maxResults=max_results).execute()
        messages = results.get("messages", [])
        
        synced_count = 0
        errors = []
        
        for msg in messages:
            try:
                msg_detail = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
                email_data = extract_complete_email_data(msg_detail)
                
                saved_email = await save_email_to_db(user_id, email_data)
                if saved_email:
                    synced_count += 1
            except Exception as e:
                logger.error(f"Error syncing email {msg.get('id', 'unknown')}: {e}")
                errors.append(str(e))
                continue
        
        message = f"Synced {synced_count} emails"
        if errors:
            message += f" with {len(errors)} errors"
        
        return EmailSyncResponse(message=message, synced_count=synced_count)
    except HTTPException:
        raise
    except HttpError as e:
        logger.error(f"Gmail API error during sync: {e}")
        raise HTTPException(status_code=500, detail=f"Gmail API error: {str(e)}")
    except Exception as e:
        logger.error(f"Error during email sync: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")

# ===== Webhook Endpoint =====
@router.post("/webhook", 
    response_model=WebhookResponse,
    summary="Gmail Webhook",
    description="Handle Gmail push notifications for new emails",
    responses={
        200: {"model": WebhookResponse, "description": "Successfully processed webhook"},
        400: {"model": ErrorResponse, "description": "Invalid webhook payload"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def gmail_webhook(request: Request):
    """Handle Gmail push notifications."""
    try:
        payload = await request.json()
        logger.info(f"Gmail push received: {payload}")

        message_data = payload.get("message", {}).get("data", "")
        if not message_data:
            return WebhookResponse(status="no_data")
            
        try:
            decoded_data = base64.urlsafe_b64decode(message_data).decode('utf-8')
            gmail_data = json.loads(decoded_data)
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error decoding webhook data: {e}")
            return WebhookResponse(status="decode_error", error=str(e))
        
        email_address = gmail_data.get("emailAddress")
        if not email_address:
            return WebhookResponse(status="no_email_address")
        
        logger.info(f"Decoded Gmail data: {gmail_data}")
        
        # Find user by email address
        token_result = supabase.table('gmail_tokens').select('user_id').eq('email_address', email_address).execute()
        if not token_result.data:
            logger.warning(f"No user found for email: {email_address}")
            return WebhookResponse(status="user_not_found")
        
        user_id = token_result.data[0]['user_id']
        service = await get_gmail_service(user_id)
        
        # Get the latest message
        results = service.users().messages().list(userId="me", maxResults=1).execute()
        messages = results.get("messages", [])
        
        if not messages:
            return WebhookResponse(status="no_messages")
        
        latest_msg = messages[0]
        msg_id = latest_msg["id"]
        
        # Check if email already exists in database
        existing = supabase.table('emails').select('id').eq('gmail_id', msg_id).execute()
        if existing.data:
            logger.info(f"Email {msg_id} already exists in database")
            return WebhookResponse(status="already_exists")
        
        # Get complete message details
        full_msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        email_data = extract_complete_email_data(full_msg)
        
        # Save to database
        saved_email = await save_email_to_db(user_id, email_data)
        if saved_email:
            logger.info(f"New email saved - ID: {saved_email['id']}, Gmail ID: {email_data['id']}, From: {email_data['from']}, Subject: {email_data['subject']}")
            
            # Send real-time notification to frontend
            await notify_new_email(user_id, saved_email)
            
            return WebhookResponse(
                status="received", 
                email_saved=True, 
                email_id=saved_email['id']
            )
        else:
            return WebhookResponse(status="save_failed")
            
    except HttpError as e:
        logger.error(f"Gmail API error in webhook: {e}")
        return WebhookResponse(status="gmail_api_error", error=str(e))
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return WebhookResponse(status="error", error=str(e))

# ===== Watch Setup =====
async def start_gmail_watch(user_id: str):
    """Start Gmail push notifications for user."""
    try:
        if not settings.GOOGLE_CLOUD_PROJECT:
            logger.warning("GOOGLE_CLOUD_PROJECT not set, skipping Gmail watch setup")
            return None
            
        service = await get_gmail_service(user_id)
        
        body = {
            "labelIds": ["INBOX"],
            "topicName": f"projects/{settings.GOOGLE_CLOUD_PROJECT}/topics/{settings.GMAIL_TOPIC_NAME}"
        }
        result = service.users().watch(userId="me", body=body).execute()
        logger.info(f"Gmail watch started for user {user_id}: {result}")
        return result
    except HttpError as e:
        logger.error(f"Gmail API error starting watch for user {user_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error starting Gmail watch for user {user_id}: {e}")
        return None

@router.post("/watch", 
    response_model=GmailWatchResponse,
    summary="Start Email Watch",
    description="Start watching emails for push notifications",
    responses={
        200: {"model": GmailWatchResponse, "description": "Successfully started watching emails"},
        401: {"model": ErrorResponse, "description": "Unauthorized or Gmail not connected"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def watch_emails(user_id: str = Depends(get_current_user_id)):
    """Start watching emails for push notifications."""
    try:
        result = await start_gmail_watch(user_id)
        if result:
            return GmailWatchResponse(
                status="watch_started", 
                expiration=result.get("expiration")
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to start email watching")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting email watch: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start email watching: {str(e)}")

# ===== Helper Functions =====
def extract_complete_email_data(full_msg):
    """Extract all email data including complete body, headers, and attachments."""
    headers = full_msg.get("payload", {}).get("headers", [])
    header_dict = {h["name"]: h["value"] for h in headers}
    
    subject = header_dict.get("Subject", "(No Subject)")
    from_email = header_dict.get("From", "(Unknown Sender)")
    to_email = header_dict.get("To", "")
    cc_email = header_dict.get("Cc", "")
    bcc_email = header_dict.get("Bcc", "")
    date = header_dict.get("Date", "")
    message_id = header_dict.get("Message-ID", "")
    
    body_text, body_html = get_complete_email_body(full_msg.get("payload", {}))
    attachments = get_attachment_info(full_msg.get("payload", {}))
    
    thread_id = full_msg.get("threadId", "")
    snippet = full_msg.get("snippet", "")
    internal_date = full_msg.get("internalDate", "")
    
    readable_date = None
    if internal_date:
        try:
            readable_date = datetime.fromtimestamp(int(internal_date) / 1000)
        except:
            pass
    
    return {
        "id": full_msg.get("id"),
        "thread_id": thread_id,
        "subject": subject,
        "from": from_email,
        "to": to_email,
        "cc": cc_email,
        "bcc": bcc_email,
        "date": date,
        "readable_date": readable_date.isoformat() if readable_date else None,
        "message_id": message_id,
        "snippet": snippet,
        "body_text": body_text,
        "body_html": body_html,
        "attachments": attachments,
        "labels": full_msg.get("labelIds", []),
        "headers": header_dict,
        "size_estimate": full_msg.get("sizeEstimate", 0)
    }

def get_complete_email_body(payload):
    """Extract both plain text and HTML body content recursively."""
    plain_text = ""
    html_content = ""
    
    def extract_body_recursive(part):
        nonlocal plain_text, html_content
        mime_type = part.get("mimeType", "")
        
        if "body" in part and "data" in part["body"] and part["body"]["data"]:
            try:
                decoded_data = base64.urlsafe_b64decode(part["body"]["data"]).decode(errors="ignore")
                if mime_type == "text/plain":
                    plain_text += decoded_data + "\n"
                elif mime_type == "text/html":
                    html_content += decoded_data + "\n"
                elif "text/" in mime_type:
                    plain_text += decoded_data + "\n"
            except Exception as e:
                print(f"❌ Error decoding body part: {e}")
        
        if "parts" in part:
            for subpart in part["parts"]:
                extract_body_recursive(subpart)
    
    extract_body_recursive(payload)
    return plain_text.strip(), html_content.strip()

def get_attachment_info(payload):
    """Extract attachment information."""
    attachments = []
    
    def extract_attachments_recursive(part):
        nonlocal attachments
        if part.get("filename"):
            attachment_info = {
                "filename": part.get("filename"),
                "mime_type": part.get("mimeType"),
                "size": part.get("body", {}).get("size", 0),
                "attachment_id": part.get("body", {}).get("attachmentId")
            }
            attachments.append(attachment_info)
        
        if "parts" in part:
            for subpart in part["parts"]:
                extract_attachments_recursive(subpart)
    
    extract_attachments_recursive(payload)
    return attachments