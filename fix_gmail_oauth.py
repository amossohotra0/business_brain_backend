#!/usr/bin/env python3
"""
Gmail OAuth Fix Script
Fixes the redirect_uri_mismatch error
"""

import webbrowser
import os
from dotenv import load_dotenv

load_dotenv()

def fix_gmail_oauth():
    print("=== Gmail OAuth Fix ===\n")
    
    # Get current configuration
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    
    print("Current Configuration:")
    print(f"Client ID: {client_id}")
    print(f"Redirect URI: {redirect_uri}")
    
    print("\n🔧 FIXING REDIRECT URI MISMATCH ERROR")
    print("=" * 50)
    
    print("\n1. Open Google Cloud Console:")
    console_url = f"https://console.cloud.google.com/apis/credentials"
    print(f"   {console_url}")
    
    print("\n2. Find your OAuth 2.0 Client ID:")
    print(f"   Look for: {client_id}")
    
    print("\n3. Click 'Edit' on your OAuth client")
    
    print("\n4. In 'Authorized redirect URIs', add EXACTLY these URIs:")
    required_uris = [
        "http://localhost:8000/api/v1/gmail/oauth2callback",
        "http://127.0.0.1:8000/api/v1/gmail/oauth2callback"
    ]
    
    for uri in required_uris:
        print(f"   ✅ {uri}")
    
    print("\n5. Remove any other redirect URIs that don't match exactly")
    
    print("\n6. Click 'Save' and wait 5-10 minutes for changes to propagate")
    
    print("\n7. Test the OAuth flow again")
    
    # Open browser automatically
    try:
        webbrowser.open(console_url)
        print("\n✅ Browser opened automatically to Google Console")
    except:
        print("\n❌ Could not open browser automatically")
    
    print("\n" + "=" * 50)
    print("COMMON MISTAKES TO AVOID:")
    print("=" * 50)
    print("❌ Using https://localhost (should be http://)")
    print("❌ Missing /api/v1/gmail/oauth2callback path")
    print("❌ Using different port (must be 8000)")
    print("❌ Extra spaces or characters")
    print("❌ Not waiting for Google's changes to propagate")

if __name__ == "__main__":
    fix_gmail_oauth()