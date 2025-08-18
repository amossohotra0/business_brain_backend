import pytest
import asyncio
import os
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import HTTPException
import json
import base64
from datetime import datetime

# Set test environment variables before importing app
os.environ.update({
    'SUPABASE_URL': 'https://rnshcmtcllyostxirtxq.supabase.co',
    'SUPABASE_KEY': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJuc2hjbXRjbGx5b3N0eGlydHhxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI4NzU2MDIsImV4cCI6MjA2ODQ1MTYwMn0.ZdYBGO3D8ceFley_svL45VQJ5wVoZozMFzS2xgrY4Ac',
    'SECRET_KEY': 'rpSXHHJ2vDM0Amcv2SAT9crDsCzAGqfbePJzwK7TiH8',
    'OPENAI_API_KEY': 'sk-test-key',
    'GOOGLE_CLIENT_ID': '44233750859-2g5pmrsed8t4f69mphrgoqsjal2o6aps.apps.googleusercontent.com',
    'GOOGLE_CLIENT_SECRET': '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',
    'GOOGLE_REDIRECT_URI': 'http://localhost:8000/api/v1/gmail/oauth2callback',
    'GOOGLE_CLOUD_PROJECT': 'turing-ember-469020-f3'
})

from app.main import app
from app.api.google_gmail import (
    get_user_gmail_token, save_user_gmail_token, save_email_to_db,
    get_user_emails, get_email_by_id, mark_email_as_read,
    get_gmail_service, extract_complete_email_data, get_complete_email_body,
    get_attachment_info, start_gmail_watch
)


class TestGmailAPI:
    """Test suite for Gmail API endpoints."""
    
    def setup_method(self):
        """Setup test client and mock data."""
        self.client = TestClient(app)
        self.test_user_id = "550e8400-e29b-41d4-a716-446655440000"
        self.test_email_id = "test-email-456"
        self.test_gmail_id = "gmail-msg-789"
        
        # Mock JWT token with valid UUID
        self.mock_token = "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiNTUwZTg0MDAtZTI5Yi00MWQ0LWE3MTYtNDQ2NjU1NDQwMDAwIn0.mock"
        
        # Mock email data
        self.mock_email_data = {
            "id": self.test_email_id,
            "gmail_id": self.test_gmail_id,
            "thread_id": "thread-123",
            "subject": "Test Email",
            "from_email": "sender@example.com",
            "to_email": "recipient@example.com",
            "date": "2024-01-01T10:00:00Z",
            "readable_date": datetime(2024, 1, 1, 10, 0, 0),
            "snippet": "This is a test email",
            "body_text": "Test email body",
            "body_html": "<p>Test email body</p>",
            "attachments": [],
            "is_read": False,
            "is_starred": False,
            "size_estimate": 1024,
            "created_at": datetime.now()
        }

    @patch('app.core.security.verify_token')
    def test_list_emails_success(self, mock_verify_token):
        """Test successful email listing."""
        mock_verify_token.return_value = {"user_id": self.test_user_id}
        
        with patch('app.api.google_gmail.get_user_emails') as mock_get_emails:
            mock_get_emails.return_value = {
                "emails": [self.mock_email_data],
                "total": 1,
                "unread_count": 1
            }
            
            response = self.client.get(
                "/api/v1/gmail/emails",
                headers={"Authorization": self.mock_token}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["unread_count"] == 1
            assert len(data["emails"]) == 1
            assert data["emails"][0]["subject"] == "Test Email"

    @patch('app.core.security.verify_token')
    def test_list_emails_with_pagination(self, mock_verify_token):
        """Test email listing with pagination parameters."""
        mock_verify_token.return_value = {"user_id": self.test_user_id}
        
        with patch('app.api.google_gmail.get_user_emails') as mock_get_emails:
            mock_get_emails.return_value = {
                "emails": [],
                "total": 50,
                "unread_count": 10
            }
            
            response = self.client.get(
                "/api/v1/gmail/emails?limit=10&offset=20",
                headers={"Authorization": self.mock_token}
            )
            
            assert response.status_code == 200
            mock_get_emails.assert_called_once_with(self.test_user_id, 10, 20)

    @patch('app.core.security.verify_token')
    def test_get_email_detail_success(self, mock_verify_token):
        """Test successful email detail retrieval."""
        mock_verify_token.return_value = {"user_id": self.test_user_id}
        
        with patch('app.api.google_gmail.get_email_by_id') as mock_get_email, \
             patch('app.api.google_gmail.mark_email_as_read') as mock_mark_read:
            
            mock_get_email.return_value = {**self.mock_email_data, "cc_email": "", "bcc_email": "", "headers": {}, "labels": []}
            mock_mark_read.return_value = True
            
            response = self.client.get(
                f"/api/v1/gmail/emails/{self.test_email_id}",
                headers={"Authorization": self.mock_token}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == self.test_email_id
            assert data["subject"] == "Test Email"
            mock_mark_read.assert_called_once_with(self.test_user_id, self.test_email_id)

    @patch('app.core.security.verify_token')
    def test_get_email_detail_not_found(self, mock_verify_token):
        """Test email detail retrieval when email not found."""
        mock_verify_token.return_value = {"user_id": self.test_user_id}
        
        with patch('app.api.google_gmail.get_email_by_id') as mock_get_email:
            mock_get_email.return_value = None
            
            response = self.client.get(
                f"/api/v1/gmail/emails/{self.test_email_id}",
                headers={"Authorization": self.mock_token}
            )
            
            assert response.status_code == 404
            assert "Email not found" in response.json()["detail"]

    @patch('app.core.security.verify_token')
    def test_star_email_success(self, mock_verify_token):
        """Test successful email starring."""
        mock_verify_token.return_value = {"user_id": self.test_user_id}
        
        with patch('app.api.google_gmail.get_email_by_id') as mock_get_email, \
             patch('app.db.supabase_client.supabase') as mock_supabase:
            
            mock_get_email.return_value = self.mock_email_data
            mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{"id": self.test_email_id}]
            
            response = self.client.post(
                f"/api/v1/gmail/emails/{self.test_email_id}/star",
                headers={"Authorization": self.mock_token}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["starred"] == True
            assert "starred" in data["message"]

    @patch('app.core.security.verify_token')
    def test_sync_emails_success(self, mock_verify_token):
        """Test successful email synchronization."""
        mock_verify_token.return_value = {"user_id": self.test_user_id}
        
        mock_service = Mock()
        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": "msg1"}, {"id": "msg2"}]
        }
        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "id": "msg1",
            "payload": {"headers": []},
            "snippet": "Test"
        }
        
        with patch('app.api.google_gmail.get_gmail_service') as mock_get_service, \
             patch('app.api.google_gmail.save_email_to_db') as mock_save_email:
            
            mock_get_service.return_value = mock_service
            mock_save_email.return_value = {"id": "saved-email-1"}
            
            response = self.client.post(
                "/api/v1/gmail/sync",
                headers={"Authorization": self.mock_token}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "synced_count" in data
            assert data["synced_count"] >= 0

    @patch('app.core.security.verify_token')
    def test_gmail_auth_redirect(self, mock_verify_token):
        """Test Gmail OAuth initiation."""
        mock_verify_token.return_value = {"user_id": self.test_user_id}
        
        response = self.client.get(
            "/api/v1/gmail/auth",
            headers={"Authorization": self.mock_token},
            follow_redirects=False
        )
        
        assert response.status_code == 302
        assert "accounts.google.com" in response.headers["location"]

    def test_gmail_callback_success(self):
        """Test successful Gmail OAuth callback."""
        mock_credentials = Mock()
        mock_credentials.refresh_token = "test-refresh-token"
        
        mock_flow = Mock()
        mock_flow.credentials = mock_credentials
        
        mock_service = Mock()
        mock_service.users.return_value.getProfile.return_value.execute.return_value = {
            "emailAddress": "test@example.com"
        }
        
        with patch('app.api.google_gmail.Flow') as mock_flow_class, \
             patch('app.api.google_gmail.build') as mock_build, \
             patch('app.api.google_gmail.save_user_gmail_token') as mock_save_token, \
             patch('app.api.google_gmail.start_gmail_watch') as mock_start_watch:
            
            mock_flow_class.from_client_config.return_value = mock_flow
            mock_build.return_value = mock_service
            mock_save_token.return_value = None
            mock_start_watch.return_value = None
            
            response = self.client.get(
                "/api/v1/gmail/oauth2callback?code=test-code&state=test-user-123"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["email"] == "test@example.com"

    def test_gmail_callback_missing_code(self):
        """Test Gmail callback with missing authorization code."""
        response = self.client.get(
            "/api/v1/gmail/oauth2callback?state=test-user-123"
        )
        
        assert response.status_code == 422  # Validation error

    def test_webhook_success(self):
        """Test successful Gmail webhook processing."""
        webhook_data = {
            "message": {
                "data": base64.urlsafe_b64encode(
                    json.dumps({"emailAddress": "test@example.com"}).encode()
                ).decode()
            }
        }
        
        mock_service = Mock()
        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": "new-msg-123"}]
        }
        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "id": "new-msg-123",
            "payload": {"headers": [{"name": "Subject", "value": "New Email"}]},
            "snippet": "New email content"
        }
        
        with patch('app.db.supabase_client.supabase') as mock_supabase, \
             patch('app.api.google_gmail.get_gmail_service') as mock_get_service, \
             patch('app.api.google_gmail.save_email_to_db') as mock_save_email, \
             patch('app.api.google_gmail.notify_new_email') as mock_notify:
            
            # Mock database queries
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
                {"user_id": self.test_user_id}
            ]
            
            mock_get_service.return_value = mock_service
            mock_save_email.return_value = {"id": "saved-email-123"}
            mock_notify.return_value = None
            
            response = self.client.post(
                "/api/v1/gmail/webhook",
                json=webhook_data
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "received"
            assert data["email_saved"] == True

    def test_webhook_no_data(self):
        """Test webhook with no message data."""
        webhook_data = {"message": {}}
        
        response = self.client.post(
            "/api/v1/gmail/webhook",
            json=webhook_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "no_data"

    @patch('app.core.security.verify_token')
    def test_watch_emails_success(self, mock_verify_token):
        """Test successful Gmail watch setup."""
        mock_verify_token.return_value = {"user_id": self.test_user_id}
        
        with patch('app.api.google_gmail.start_gmail_watch') as mock_start_watch:
            mock_start_watch.return_value = {"expiration": "1234567890"}
            
            response = self.client.post(
                "/api/v1/gmail/watch",
                headers={"Authorization": self.mock_token}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "watch_started"
            assert "expiration" in data

    @patch('app.core.security.verify_token')
    def test_watch_emails_failure(self, mock_verify_token):
        """Test Gmail watch setup failure."""
        mock_verify_token.return_value = {"user_id": self.test_user_id}
        
        with patch('app.api.google_gmail.start_gmail_watch') as mock_start_watch:
            mock_start_watch.return_value = None
            
            response = self.client.post(
                "/api/v1/gmail/watch",
                headers={"Authorization": self.mock_token}
            )
            
            assert response.status_code == 500
            assert "Failed to start email watching" in response.json()["detail"]


class TestGmailHelperFunctions:
    """Test suite for Gmail helper functions."""
    
    def setup_method(self):
        """Setup test data."""
        self.test_user_id = "550e8400-e29b-41d4-a716-446655440000"
        self.test_email_data = {
            "id": "gmail-msg-123",
            "subject": "Test Email",
            "from": "sender@example.com",
            "to": "recipient@example.com"
        }

    @pytest.mark.asyncio
    async def test_get_user_gmail_token_success(self):
        """Test successful Gmail token retrieval."""
        with patch('app.db.supabase_client.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
                {"refresh_token": "test-token", "email_address": "test@example.com"}
            ]
            
            result = await get_user_gmail_token(self.test_user_id)
            
            assert result is not None
            assert result["refresh_token"] == "test-token"

    @pytest.mark.asyncio
    async def test_get_user_gmail_token_not_found(self):
        """Test Gmail token retrieval when not found."""
        with patch('app.db.supabase_client.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
            
            result = await get_user_gmail_token(self.test_user_id)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_save_user_gmail_token_success(self):
        """Test successful Gmail token saving."""
        with patch('app.db.supabase_client.supabase') as mock_supabase:
            mock_supabase.table.return_value.upsert.return_value.execute.return_value.data = [
                {"id": "token-123", "user_id": self.test_user_id}
            ]
            
            result = await save_user_gmail_token(
                self.test_user_id, 
                "test@example.com", 
                "refresh-token"
            )
            
            assert result is not None
            assert result["user_id"] == self.test_user_id

    @pytest.mark.asyncio
    async def test_save_email_to_db_success(self):
        """Test successful email saving to database."""
        with patch('app.db.supabase_client.supabase') as mock_supabase:
            # Mock check for existing email
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
            # Mock insert
            mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [
                {"id": "saved-email-123"}
            ]
            
            result = await save_email_to_db(self.test_user_id, self.test_email_data)
            
            assert result is not None
            assert result["id"] == "saved-email-123"

    @pytest.mark.asyncio
    async def test_save_email_to_db_already_exists(self):
        """Test email saving when email already exists."""
        with patch('app.db.supabase_client.supabase') as mock_supabase:
            # Mock existing email found
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
                {"id": "existing-email-123"}
            ]
            
            result = await save_email_to_db(self.test_user_id, self.test_email_data)
            
            assert result is not None
            assert result["id"] == "existing-email-123"

    def test_extract_complete_email_data(self):
        """Test email data extraction from Gmail message."""
        gmail_message = {
            "id": "msg-123",
            "threadId": "thread-123",
            "snippet": "Test email snippet",
            "sizeEstimate": 1024,
            "internalDate": "1640995200000",  # 2022-01-01 10:00:00
            "labelIds": ["INBOX", "UNREAD"],
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "To", "value": "recipient@example.com"},
                    {"name": "Date", "value": "Sat, 1 Jan 2022 10:00:00 +0000"}
                ],
                "body": {
                    "data": base64.urlsafe_b64encode(b"Test email body").decode()
                },
                "mimeType": "text/plain"
            }
        }
        
        result = extract_complete_email_data(gmail_message)
        
        assert result["id"] == "msg-123"
        assert result["subject"] == "Test Subject"
        assert result["from"] == "sender@example.com"
        assert result["to"] == "recipient@example.com"
        assert result["snippet"] == "Test email snippet"
        assert result["size_estimate"] == 1024
        assert "INBOX" in result["labels"]

    def test_get_complete_email_body_plain_text(self):
        """Test email body extraction for plain text."""
        payload = {
            "mimeType": "text/plain",
            "body": {
                "data": base64.urlsafe_b64encode(b"Plain text email body").decode()
            }
        }
        
        plain_text, html_content = get_complete_email_body(payload)
        
        assert plain_text == "Plain text email body"
        assert html_content == ""

    def test_get_complete_email_body_multipart(self):
        """Test email body extraction for multipart message."""
        payload = {
            "mimeType": "multipart/alternative",
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {
                        "data": base64.urlsafe_b64encode(b"Plain text version").decode()
                    }
                },
                {
                    "mimeType": "text/html",
                    "body": {
                        "data": base64.urlsafe_b64encode(b"<p>HTML version</p>").decode()
                    }
                }
            ]
        }
        
        plain_text, html_content = get_complete_email_body(payload)
        
        assert plain_text == "Plain text version"
        assert html_content == "<p>HTML version</p>"

    def test_get_attachment_info(self):
        """Test attachment information extraction."""
        payload = {
            "parts": [
                {
                    "filename": "document.pdf",
                    "mimeType": "application/pdf",
                    "body": {
                        "size": 12345,
                        "attachmentId": "att-123"
                    }
                },
                {
                    "filename": "image.jpg",
                    "mimeType": "image/jpeg",
                    "body": {
                        "size": 67890,
                        "attachmentId": "att-456"
                    }
                }
            ]
        }
        
        attachments = get_attachment_info(payload)
        
        assert len(attachments) == 2
        assert attachments[0]["filename"] == "document.pdf"
        assert attachments[0]["mime_type"] == "application/pdf"
        assert attachments[0]["size"] == 12345
        assert attachments[1]["filename"] == "image.jpg"

    @pytest.mark.asyncio
    async def test_get_gmail_service_success(self):
        """Test successful Gmail service creation."""
        with patch('app.api.google_gmail.get_user_gmail_token') as mock_get_token, \
             patch('app.api.google_gmail.build') as mock_build:
            
            mock_get_token.return_value = {
                "refresh_token": "test-refresh-token",
                "email_address": "test@gmail.com",
                "access_token": "test-access-token",
                "expires_at": "2025-01-01T10:00:00+00:00"
            }
            mock_service = Mock()
            mock_build.return_value = mock_service
            
            result = await get_gmail_service(self.test_user_id)
            
            assert result == mock_service

    @pytest.mark.asyncio
    async def test_get_gmail_service_no_token(self):
        """Test Gmail service creation when no token exists."""
        with patch('app.api.google_gmail.get_user_gmail_token') as mock_get_token:
            mock_get_token.return_value = None
            
            with pytest.raises(HTTPException) as exc_info:
                await get_gmail_service(self.test_user_id)
            
            assert exc_info.value.status_code == 401
            assert "not authenticated" in exc_info.value.detail


if __name__ == "__main__":
    pytest.main([__file__, "-v"])