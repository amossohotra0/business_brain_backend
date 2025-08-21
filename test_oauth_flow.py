#!/usr/bin/env python3
"""
OAuth Flow Test - Tests the complete Gmail OAuth process
"""

import requests
import webbrowser
import os
from dotenv import load_dotenv

load_dotenv()

def test_oauth_flow():
    print("=== Gmail OAuth Flow Test ===\n")
    
    # Login first
    login_data = {
        "email": os.getenv("TEST_EMAIL"),
        "password": os.getenv("EMAIL_PASS")
    }
    
    print("1. Logging in...")
    response = requests.post("http://localhost:8000/api/v1/auth/login", json=login_data)
    if response.status_code != 200:
        print(f"❌ Login failed: {response.text}")
        return
    
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Login successful")
    
    # Get OAuth URL
    print("\n2. Getting OAuth URL...")
    response = requests.get("http://localhost:8000/api/v1/gmail/auth", headers=headers, allow_redirects=False)
    
    if response.status_code in [302, 307]:
        oauth_url = response.headers.get("location")
        print("✅ OAuth URL generated")
        print(f"\n🔗 OAuth URL:\n{oauth_url}")
        
        print("\n3. Opening OAuth URL in browser...")
        try:
            webbrowser.open(oauth_url)
            print("✅ Browser opened")
            print("\n📋 INSTRUCTIONS:")
            print("1. Complete Google OAuth consent in the browser")
            print("2. You should be redirected to: http://localhost:8000/api/v1/gmail/oauth2callback")
            print("3. If successful, you'll see a JSON response with 'status': 'success'")
            print("4. If you get 'redirect_uri_mismatch', wait 5-10 minutes and try again")
        except:
            print("❌ Could not open browser")
            print(f"Manual: Copy this URL to your browser:\n{oauth_url}")
    else:
        print(f"❌ OAuth URL generation failed: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_oauth_flow()