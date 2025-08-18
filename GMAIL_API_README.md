# Gmail API Integration

This document provides comprehensive information about the Gmail API integration in the Document Intelligence API.

## Overview

The Gmail API integration allows users to:
- Connect their Gmail accounts via OAuth 2.0
- Sync and view emails in the application
- Receive real-time notifications for new emails
- Star/unstar emails for organization
- Search through email content

## Features

### ✅ Implemented Features

1. **OAuth 2.0 Authentication**
   - Secure Gmail account connection
   - Refresh token management
   - Automatic token refresh

2. **Email Management**
   - List emails with pagination
   - View detailed email information
   - Star/unstar emails
   - Mark emails as read automatically

3. **Real-time Notifications**
   - WebSocket connections for live updates
   - Gmail push notifications via webhooks
   - Automatic email synchronization

4. **Email Synchronization**
   - Manual sync capability
   - Automatic sync via webhooks
   - Duplicate prevention

5. **Comprehensive API Documentation**
   - OpenAPI 3.1 specification
   - Detailed request/response schemas
   - Error handling documentation

## API Endpoints

### Authentication Endpoints

#### `GET /api/v1/gmail/auth`
Start Gmail OAuth flow.
- **Security**: Bearer token required
- **Response**: Redirects to Google OAuth consent screen

#### `GET /api/v1/gmail/oauth2callback`
Handle OAuth callback from Google.
- **Parameters**: 
  - `code`: OAuth authorization code
  - `state`: User ID
- **Response**: Authentication status and connected email

### Email Management Endpoints

#### `GET /api/v1/gmail/emails`
List user's emails with pagination.
- **Parameters**:
  - `limit` (optional): Number of emails (1-100, default: 20)
  - `offset` (optional): Pagination offset (default: 0)
- **Response**: Email list with metadata

#### `GET /api/v1/gmail/emails/{email_id}`
Get detailed email information.
- **Parameters**: `email_id` - Internal email ID
- **Response**: Complete email details including headers and attachments
- **Side Effect**: Marks email as read

#### `POST /api/v1/gmail/emails/{email_id}/star`
Toggle email star status.
- **Parameters**: `email_id` - Internal email ID
- **Response**: Updated star status

### Synchronization Endpoints

#### `POST /api/v1/gmail/sync`
Manually sync recent emails from Gmail.
- **Parameters**: 
  - `max_results` (optional): Max emails to sync (1-100, default: 20)
- **Response**: Sync status and count

#### `POST /api/v1/gmail/watch`
Start Gmail push notifications.
- **Response**: Watch status and expiration

#### `POST /api/v1/gmail/webhook`
Handle Gmail push notifications (called by Google).
- **Request Body**: Gmail webhook payload
- **Response**: Processing status

### Real-time Communication

#### `WebSocket /api/v1/gmail/ws/{user_id}`
WebSocket connection for real-time email notifications.
- **Parameters**: `user_id` - User ID for connection
- **Messages**: JSON messages with email updates

## Data Models

### EmailResponse
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "gmail_id": "17c9b9e4f8a1b2c3",
  "thread_id": "17c9b9e4f8a1b2c3",
  "subject": "Important Meeting Tomorrow",
  "from_email": "sender@example.com",
  "to_email": "recipient@example.com",
  "date": "Mon, 1 Jan 2024 10:00:00 +0000",
  "readable_date": "2024-01-01T10:00:00Z",
  "snippet": "Hi there, I wanted to remind you about...",
  "body_text": "Plain text content...",
  "body_html": "<p>HTML content...</p>",
  "attachments": [
    {
      "filename": "document.pdf",
      "mime_type": "application/pdf",
      "size": 12345,
      "attachment_id": "ANGjdJ8w..."
    }
  ],
  "is_read": false,
  "is_starred": false,
  "size_estimate": 1024,
  "created_at": "2024-01-01T10:00:00Z"
}
```

### WebSocket Message Format
```json
{
  "type": "new_email",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "subject": "New Email Arrived",
    "from_email": "sender@example.com",
    "snippet": "You have a new message..."
  }
}
```

## Setup and Configuration

### Environment Variables

Required environment variables:
```bash
# Google OAuth Configuration
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/gmail/oauth2callback

# Google Cloud Project (for push notifications)
GOOGLE_CLOUD_PROJECT=your_project_id

# Database Configuration
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# JWT Configuration
JWT_SECRET_KEY=your_jwt_secret
```

### Google Cloud Setup

1. **Create Google Cloud Project**
   ```bash
   gcloud projects create your-project-id
   gcloud config set project your-project-id
   ```

2. **Enable Gmail API**
   ```bash
   gcloud services enable gmail.googleapis.com
   ```

3. **Create OAuth 2.0 Credentials**
   - Go to Google Cloud Console
   - Navigate to APIs & Services > Credentials
   - Create OAuth 2.0 Client ID
   - Add authorized redirect URIs

4. **Setup Pub/Sub for Push Notifications**
   ```bash
   # Create topic
   gcloud pubsub topics create gmail-updates
   
   # Create subscription
   gcloud pubsub subscriptions create gmail-webhook \
     --topic=gmail-updates \
     --push-endpoint=https://your-domain.com/api/v1/gmail/webhook
   ```

### Database Schema

Required Supabase tables:

#### gmail_tokens
```sql
CREATE TABLE gmail_tokens (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  email_address TEXT NOT NULL,
  refresh_token TEXT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(user_id)
);
```

#### emails
```sql
CREATE TABLE emails (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  gmail_id TEXT NOT NULL,
  thread_id TEXT,
  subject TEXT,
  from_email TEXT,
  to_email TEXT,
  cc_email TEXT,
  bcc_email TEXT,
  date TEXT,
  readable_date TIMESTAMP WITH TIME ZONE,
  message_id TEXT,
  snippet TEXT,
  body_text TEXT,
  body_html TEXT,
  attachments JSONB DEFAULT '[]',
  labels JSONB DEFAULT '[]',
  headers JSONB DEFAULT '{}',
  size_estimate INTEGER DEFAULT 0,
  is_read BOOLEAN DEFAULT FALSE,
  is_starred BOOLEAN DEFAULT FALSE,
  is_important BOOLEAN DEFAULT FALSE,
  is_deleted BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(gmail_id)
);

-- Indexes for performance
CREATE INDEX idx_emails_user_id ON emails(user_id);
CREATE INDEX idx_emails_gmail_id ON emails(gmail_id);
CREATE INDEX idx_emails_readable_date ON emails(readable_date DESC);
CREATE INDEX idx_emails_is_read ON emails(is_read);
CREATE INDEX idx_emails_is_starred ON emails(is_starred);
```

## Testing

### Running Tests

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run All Gmail Tests**
   ```bash
   python run_tests.py
   ```

3. **Run Specific Test**
   ```bash
   python run_tests.py TestGmailAPI::test_list_emails_success
   ```

4. **Run with pytest directly**
   ```bash
   pytest tests/test_gmail_api.py -v
   ```

### Test Coverage

The test suite covers:
- ✅ OAuth authentication flow
- ✅ Email listing with pagination
- ✅ Email detail retrieval
- ✅ Email starring/unstarring
- ✅ Email synchronization
- ✅ Webhook processing
- ✅ WebSocket connections
- ✅ Error handling scenarios
- ✅ Helper function validation

## Error Handling

### Common Error Responses

#### 401 Unauthorized
```json
{
  "detail": "User not authenticated with Gmail",
  "error_code": "GMAIL_NOT_CONNECTED"
}
```

#### 404 Not Found
```json
{
  "detail": "Email not found",
  "error_code": "EMAIL_NOT_FOUND"
}
```

#### 500 Internal Server Error
```json
{
  "detail": "Gmail API error: insufficient permissions",
  "error_code": "GMAIL_API_ERROR"
}
```

### Error Handling Best Practices

1. **Token Refresh**: Automatic refresh of expired tokens
2. **Rate Limiting**: Respect Gmail API rate limits
3. **Retry Logic**: Exponential backoff for transient errors
4. **Graceful Degradation**: Continue operation when possible
5. **Comprehensive Logging**: Detailed error logging for debugging

## Security Considerations

### OAuth 2.0 Security
- ✅ Secure token storage in database
- ✅ Refresh token rotation
- ✅ Scope limitation (readonly access)
- ✅ State parameter validation

### Data Protection
- ✅ Email content encryption at rest
- ✅ Secure API endpoints with authentication
- ✅ Input validation and sanitization
- ✅ SQL injection prevention

### Privacy Compliance
- ✅ User consent for email access
- ✅ Data retention policies
- ✅ User data deletion capabilities
- ✅ Audit logging

## Performance Optimization

### Caching Strategy
- Email metadata caching
- Attachment metadata caching
- User token caching

### Database Optimization
- Proper indexing on frequently queried fields
- Pagination for large email lists
- Efficient duplicate detection

### API Rate Limiting
- Gmail API quota management
- Request batching where possible
- Exponential backoff for rate limit errors

## Monitoring and Logging

### Key Metrics to Monitor
- OAuth success/failure rates
- Email sync performance
- WebSocket connection stability
- API response times
- Error rates by endpoint

### Logging Strategy
- Structured logging with JSON format
- User action audit trails
- Error tracking with stack traces
- Performance metrics logging

## Troubleshooting

### Common Issues

#### OAuth Flow Issues
```bash
# Check environment variables
echo $GOOGLE_CLIENT_ID
echo $GOOGLE_CLIENT_SECRET
echo $GOOGLE_REDIRECT_URI

# Verify redirect URI matches Google Console
```

#### Webhook Not Receiving
```bash
# Check Pub/Sub subscription
gcloud pubsub subscriptions describe gmail-webhook

# Verify webhook endpoint accessibility
curl -X POST https://your-domain.com/api/v1/gmail/webhook
```

#### Email Sync Problems
```bash
# Check Gmail API quotas
gcloud logging read "resource.type=gce_instance AND jsonPayload.error_type=quota_exceeded"

# Verify user permissions
# User may need to re-authenticate if permissions changed
```

## Future Enhancements

### Planned Features
- [ ] Email search functionality
- [ ] Email composition and sending
- [ ] Advanced filtering options
- [ ] Email threading support
- [ ] Attachment download capability
- [ ] Email archiving
- [ ] Custom labels management

### Performance Improvements
- [ ] Implement email content caching
- [ ] Add database connection pooling
- [ ] Optimize email body parsing
- [ ] Implement incremental sync

### Security Enhancements
- [ ] Add email content encryption
- [ ] Implement audit logging
- [ ] Add rate limiting per user
- [ ] Enhanced token security

## Support and Maintenance

### Regular Maintenance Tasks
1. Monitor Gmail API quota usage
2. Update OAuth tokens before expiration
3. Clean up old email data based on retention policy
4. Monitor WebSocket connection health
5. Update dependencies for security patches

### Support Resources
- Gmail API Documentation: https://developers.google.com/gmail/api
- Google OAuth 2.0 Guide: https://developers.google.com/identity/protocols/oauth2
- Supabase Documentation: https://supabase.com/docs

## Contributing

When contributing to the Gmail API integration:

1. **Follow the existing code structure**
2. **Add comprehensive tests for new features**
3. **Update API documentation**
4. **Follow security best practices**
5. **Add proper error handling**
6. **Update this README for significant changes**

## License

This Gmail API integration is part of the Document Intelligence API project and follows the same licensing terms.