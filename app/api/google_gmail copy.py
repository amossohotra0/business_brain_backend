from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
import os
import base64
import json
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from datetime import datetime

load_dotenv()
router = APIRouter()

# In-memory token store (replace with DB in production)
user_tokens = {}
processed_message_ids = set()  # To avoid processing the same message twice

# ===== Step 1: OAuth Start =====
@router.get("/google/auth")
def google_auth():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI")],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=["https://www.googleapis.com/auth/gmail.readonly"]
    )
    flow.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true"
    )
    return RedirectResponse(auth_url)


# ===== Step 2: OAuth Callback =====
@router.get("/google/oauth2callback")
def google_callback(code: str, user_id: str = "test_user"):
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI")],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=["https://www.googleapis.com/auth/gmail.readonly"]
    )
    flow.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    flow.fetch_token(code=code)

    credentials = flow.credentials
    user_tokens[user_id] = credentials.refresh_token

    # Get Gmail profile to confirm authentication
    creds = Credentials(
        None,
        refresh_token=credentials.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
    )
    creds.refresh(GoogleRequest())
    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()

    return {
        "status": "success",
        "email": profile.get("emailAddress"),
        "refresh_token": credentials.refresh_token
    }


# ===== Step 3: Fetch Emails =====
@router.get("/google/list_emails")
def list_emails(user_id: str = "test_user"):
    if user_id not in user_tokens:
        return {"error": "User not authenticated with Gmail"}

    creds = Credentials(
        None,
        refresh_token=user_tokens[user_id],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
    )
    creds.refresh(GoogleRequest())
    service = build("gmail", "v1", credentials=creds)

    try:
        # Get latest 10 messages
        results = service.users().messages().list(userId="me", maxResults=10).execute()
        messages = results.get("messages", [])

        emails_data = []
        for msg in messages:
            msg_detail = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
            email_data = extract_complete_email_data(msg_detail)
            emails_data.append(email_data)

        return {"emails": emails_data}

    except Exception as e:
        return {"error": str(e)}


# ===== Step 4: Simple Gmail Push Webhook Using Latest Messages =====
@router.post("/google/gmail_webhook")
async def gmail_webhook(request: Request, user_id: str = "test_user"):
    """Simple webhook that fetches only the newest email when notified."""
    payload = await request.json()
    print("📩 Gmail push received:", payload)

    # Decode the Pub/Sub message data to get basic info
    try:
        message_data = payload.get("message", {}).get("data", "")
        if message_data:
            decoded_data = base64.urlsafe_b64decode(message_data).decode('utf-8')
            gmail_data = json.loads(decoded_data)
            print("📧 Decoded Gmail data:", gmail_data)
            email_address = gmail_data.get("emailAddress")
        else:
            email_address = "unknown"
    except Exception as e:
        print(f"⚠️ Could not decode push data: {e}")
        email_address = "unknown"

    # Authenticate and get Gmail service
    if user_id not in user_tokens:
        return {"error": "User not authenticated"}

    creds = Credentials(
        None,
        refresh_token=user_tokens[user_id],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
    )
    creds.refresh(GoogleRequest())
    service = build("gmail", "v1", credentials=creds)

    try:
        print("🔍 Fetching the latest message...")
        
        # Get only the latest message (most recent)
        results = service.users().messages().list(userId="me", maxResults=1).execute()
        messages = results.get("messages", [])
        
        if not messages:
            print("📭 No messages found")
            return {"status": "no_messages"}
        
        # Get the most recent message
        latest_msg = messages[0]
        msg_id = latest_msg["id"]
        
        # Check if this is actually a new message
        if msg_id in processed_message_ids:
            print(f"⏭️ Latest message {msg_id} already processed, no new email")
            return {
                "status": "no_new_emails",
                "message": "Latest message already processed"
            }
        
        # Mark as processed
        processed_message_ids.add(msg_id)
        
        print(f"🆕 Processing new message ID: {msg_id}")
        
        # Get complete message details
        full_msg = service.users().messages().get(
            userId="me", 
            id=msg_id, 
            format="full"
        ).execute()
        
        # Extract complete email data
        email_data = extract_complete_email_data(full_msg)
        
        # Print complete email info
        print("🆕 NEW EMAIL RECEIVED:")
        print(f"   ID: {email_data['id']}")
        print(f"   From: {email_data['from']}")
        print(f"   Subject: {email_data['subject']}")
        print(f"   Date: {email_data['date']}")
        print(f"   Text Body Length: {len(email_data['body_text'])} characters")
        print(f"   HTML Body Length: {len(email_data['body_html'])} characters")
        print(f"   Attachments: {len(email_data['attachments'])}")
        
        # Print the COMPLETE email body
        if email_data['body_text']:
            print(f"   📄 COMPLETE TEXT BODY:")
            print(f"{email_data['body_text']}")
        else:
            print("   📄 No text body, checking HTML...")
            if email_data['body_html']:
                print(f"   📄 HTML BODY (first 1000 chars):")
                print(f"{email_data['body_html'][:1000]}...")
        
        print("=" * 80)

        return {
            "status": "received",
            "email_address": email_address,
            "new_email": email_data  # Single new email with complete data
        }

    except Exception as e:
        print(f"❌ Error fetching emails: {e}")
        return {"status": "error", "error": str(e)}


@router.post("/google/watch_emails")
def watch_emails(user_id: str = "test_user"):
    if user_id not in user_tokens:
        return {"error": "User not authenticated with Gmail"}

    creds = Credentials(
        None,
        refresh_token=user_tokens[user_id],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
    )
    creds.refresh(GoogleRequest())
    service = build("gmail", "v1", credentials=creds)

    # Subscribe to Gmail push notifications
    body = {
        "labelIds": ["INBOX"],
        "topicName": f"projects/{os.getenv('GOOGLE_CLOUD_PROJECT')}/topics/gmail-updates"
    }
    result = service.users().watch(userId="me", body=body).execute()
    print("📡 Gmail watch started:", result)

    return {"status": "watch_started", "expiration": result.get("expiration")}


def extract_complete_email_data(full_msg):
    """Extract all email data including complete body, headers, and attachments."""
    
    # Extract headers
    headers = full_msg.get("payload", {}).get("headers", [])
    header_dict = {h["name"]: h["value"] for h in headers}
    
    # Get basic info
    subject = header_dict.get("Subject", "(No Subject)")
    from_email = header_dict.get("From", "(Unknown Sender)")
    to_email = header_dict.get("To", "")
    cc_email = header_dict.get("Cc", "")
    bcc_email = header_dict.get("Bcc", "")
    date = header_dict.get("Date", "")
    message_id = header_dict.get("Message-ID", "")
    
    # Extract complete body (both text and HTML)
    body_text, body_html = get_complete_email_body(full_msg.get("payload", {}))
    
    # Extract attachments info
    attachments = get_attachment_info(full_msg.get("payload", {}))
    
    # Get other useful fields
    thread_id = full_msg.get("threadId", "")
    snippet = full_msg.get("snippet", "")
    internal_date = full_msg.get("internalDate", "")
    
    # Convert internal date to readable format
    readable_date = ""
    if internal_date:
        try:
            readable_date = datetime.fromtimestamp(int(internal_date) / 1000).isoformat()
        except:
            readable_date = internal_date
    
    return {
        "id": full_msg.get("id"),
        "thread_id": thread_id,
        "subject": subject,
        "from": from_email,
        "to": to_email,
        "cc": cc_email,
        "bcc": bcc_email,
        "date": date,
        "readable_date": readable_date,
        "message_id": message_id,
        "snippet": snippet,
        "body_text": body_text,
        "body_html": body_html,
        "attachments": attachments,
        "labels": full_msg.get("labelIds", []),
        "headers": header_dict,  # All headers in dict format
        "size_estimate": full_msg.get("sizeEstimate", 0)
    }


def get_complete_email_body(payload):
    """Extract both plain text and HTML body content recursively."""
    plain_text = ""
    html_content = ""
    
    def extract_body_recursive(part):
        nonlocal plain_text, html_content
        
        mime_type = part.get("mimeType", "")
        
        # If this part has body data
        if "body" in part and "data" in part["body"] and part["body"]["data"]:
            try:
                decoded_data = base64.urlsafe_b64decode(part["body"]["data"]).decode(errors="ignore")
                
                if mime_type == "text/plain":
                    plain_text += decoded_data + "\n"
                elif mime_type == "text/html":
                    html_content += decoded_data + "\n"
                elif "text/" in mime_type:  # Other text types
                    plain_text += decoded_data + "\n"
                    
            except Exception as e:
                print(f"❌ Error decoding body part: {e}")
        
        # Recursively process parts
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
        
        # Check if this part is an attachment
        if part.get("filename"):
            attachment_info = {
                "filename": part.get("filename"),
                "mime_type": part.get("mimeType"),
                "size": part.get("body", {}).get("size", 0),
                "attachment_id": part.get("body", {}).get("attachmentId")
            }
            attachments.append(attachment_info)
        
        # Recursively check parts
        if "parts" in part:
            for subpart in part["parts"]:
                extract_attachments_recursive(subpart)
    
    extract_attachments_recursive(payload)
    return attachments