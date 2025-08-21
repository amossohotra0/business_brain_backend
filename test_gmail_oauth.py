#!/usr/bin/env python3
"""
Gmail OAuth Test Script
Run this to test the complete Gmail OAuth flow
"""

import requests
import webbrowser
from urllib.parse import urlparse, parse_qs

# Configuration
BASE_URL = "http://localhost:8000"
TEST_EMAIL = "mzrbutt31@gmail.com"

def test_gmail_oauth():
    print("=== Gmail OAuth Test ===")
    
    # Step 1: Login to get JWT token
    print("\n1. Logging in to get JWT token...")
    login_data = {
        "email": TEST_EMAIL,
        "password": "Msp4kist4n@"
    }
    
    try:
        login_response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
        if login_response.status_code == 200:
            token_data = login_response.json()
            jwt_token = token_data.get("access_token")
            print(f"✅ Login successful, token: {jwt_token[:50]}...")
        else:
            print(f"❌ Login failed: {login_response.text}")
            return
    except Exception as e:
        print(f"❌ Login error: {e}")
        return
    
    headers = {"Authorization": f"Bearer {jwt_token}"}
    
    # Step 2: Check current Gmail status
    print("\n2. Checking Gmail connection status...")
    try:
        gmail_response = requests.get(f"{BASE_URL}/api/v1/gmail/emails?limit=1", headers=headers)
        print(f"Gmail status: {gmail_response.status_code}")
        
        sync_response = requests.post(f"{BASE_URL}/api/v1/gmail/sync?max_results=1", headers=headers)
        if sync_response.status_code == 401:
            print("❌ Gmail not connected - need OAuth")
        else:
            print("✅ Gmail already connected")
            return
    except Exception as e:
        print(f"Error checking Gmail: {e}")
    
    # Step 3: Start OAuth flow
    print("\n3. Starting Gmail OAuth flow...")
    try:
        oauth_response = requests.get(f"{BASE_URL}/api/v1/gmail/auth", headers=headers, allow_redirects=False)
        if oauth_response.status_code in [302, 307]:
            oauth_url = oauth_response.headers.get("location")
            print(f"✅ OAuth URL generated: {oauth_url[:100]}...")
            
            print("\n🔗 MANUAL STEP REQUIRED:")
            print("1. Copy this URL and open it in your browser:")
            print(f"   {oauth_url}")
            print("2. Complete Google OAuth consent")
            print("3. After consent, you'll be redirected to the callback URL")
            print("4. The Gmail integration will be connected automatically")
            
            # Optionally open browser automatically
            try:
                webbrowser.open(oauth_url)
                print("✅ Browser opened automatically")
            except:
                print("❌ Could not open browser automatically")
                
        else:
            print(f"❌ OAuth failed: {oauth_response.text}")
    except Exception as e:
        print(f"❌ OAuth error: {e}")
    
    print("\n=== After completing OAuth in browser ===")
    print("Run this script again to test Gmail sync")

if __name__ == "__main__":
    test_gmail_oauth()