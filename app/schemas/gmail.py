from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime


class GmailAuthResponse(BaseModel):
    """Response for Gmail authentication."""
    status: str = Field(..., description="Authentication status")
    email: Optional[str] = Field(None, description="Connected Gmail email address")
    message: str = Field(..., description="Status message")


class EmailAttachment(BaseModel):
    """Email attachment information."""
    filename: str = Field(..., description="Attachment filename")
    mime_type: str = Field(..., description="MIME type of the attachment")
    size: int = Field(..., description="Size of the attachment in bytes")
    attachment_id: Optional[str] = Field(None, description="Gmail attachment ID")


class EmailResponse(BaseModel):
    """Basic email response model."""
    id: str = Field(..., description="Internal email ID")
    gmail_id: str = Field(..., description="Gmail message ID")
    thread_id: Optional[str] = Field(None, description="Gmail thread ID")
    subject: Optional[str] = Field(None, description="Email subject")
    from_email: Optional[str] = Field(None, description="Sender email address")
    to_email: Optional[str] = Field(None, description="Recipient email address")
    date: Optional[str] = Field(None, description="Email date string")
    readable_date: Optional[datetime] = Field(None, description="Parsed email date")
    snippet: Optional[str] = Field(None, description="Email snippet")
    body_text: Optional[str] = Field(None, description="Plain text body")
    body_html: Optional[str] = Field(None, description="HTML body")
    attachments: List[EmailAttachment] = Field(default=[], description="Email attachments")
    is_read: bool = Field(..., description="Whether email is read")
    is_starred: bool = Field(..., description="Whether email is starred")
    size_estimate: int = Field(..., description="Estimated size in bytes")
    created_at: datetime = Field(..., description="When email was saved to database")


class EmailDetailResponse(EmailResponse):
    """Detailed email response with additional fields."""
    cc_email: Optional[str] = Field(None, description="CC email addresses")
    bcc_email: Optional[str] = Field(None, description="BCC email addresses")
    headers: Dict[str, Any] = Field(default={}, description="Email headers")
    labels: List[str] = Field(default=[], description="Gmail labels")


class EmailListResponse(BaseModel):
    """Response for email list endpoint."""
    emails: List[EmailResponse] = Field(..., description="List of emails")
    total: int = Field(..., description="Total number of emails")
    unread_count: int = Field(..., description="Number of unread emails")


class EmailStarResponse(BaseModel):
    """Response for starring/unstarring emails."""
    starred: bool = Field(..., description="New starred status")
    message: str = Field(..., description="Status message")


class EmailSyncResponse(BaseModel):
    """Response for email sync operation."""
    message: str = Field(..., description="Sync status message")
    synced_count: int = Field(..., description="Number of emails synced")


class GmailWatchResponse(BaseModel):
    """Response for Gmail watch setup."""
    status: str = Field(..., description="Watch status")
    expiration: Optional[str] = Field(None, description="Watch expiration timestamp")


class WebhookResponse(BaseModel):
    """Response for Gmail webhook."""
    status: str = Field(..., description="Webhook processing status")
    email_saved: Optional[bool] = Field(None, description="Whether email was saved")
    email_id: Optional[str] = Field(None, description="Saved email ID")
    error: Optional[str] = Field(None, description="Error message if any")


class WebSocketMessage(BaseModel):
    """WebSocket message format."""
    type: str = Field(..., description="Message type")
    data: Dict[str, Any] = Field(..., description="Message data")


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")