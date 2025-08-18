#!/usr/bin/env python3
"""
Email Connection Diagnostic Tool
Identifies and fixes Gmail OAuth configuration issues
"""

import os
from dotenv import load_dotenv

load_dotenv()

def diagnose_gmail_config():
    print("=== Gmail OAuth Configuration Diagnosis ===\n")
    
    # Check environment variables
    print("1. Environment Variables:")
    google_client_id = os.getenv("GOOGLE_CLIENT_ID")
    google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    google_redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    
    print(f"   GOOGLE_CLIENT_ID: {'✅ Set' if google_client_id else '❌ Missing'}")
    print(f"   GOOGLE_CLIENT_SECRET: {'✅ Set' if google_client_secret else '❌ Missing'}")
    print(f"   GOOGLE_REDIRECT_URI: {google_redirect_uri}")
    
    # Analyze redirect URI
    print("\n2. Redirect URI Analysis:")
    if google_redirect_uri:
        if "localhost:8000" in google_redirect_uri:
            print("   ⚠️  Using localhost - this may cause issues in production")
        if google_redirect_uri.startswith("http://"):
            print("   ⚠️  Using HTTP - Google requires HTTPS for production")
        if "/api/v1/gmail/oauth2callback" in google_redirect_uri:
            print("   ✅ Correct callback path")
        else:
            print("   ❌ Incorrect callback path")
    
    # Common issues and solutions
    print("\n3. Common Issues & Solutions:")
    print("   Issue: redirect_uri_mismatch")
    print("   Causes:")
    print("   - Redirect URI in Google Console doesn't match .env file")
    print("   - Using different domain/port than configured")
    print("   - Missing trailing slash or incorrect path")
    
    print("\n4. Required Google Console Configuration:")
    print("   Go to: https://console.cloud.google.com/apis/credentials")
    print("   Add these Authorized redirect URIs:")
    print("   - http://localhost:8000/api/v1/gmail/oauth2callback")
    print("   - http://127.0.0.1:8000/api/v1/gmail/oauth2callback")
    
    # Test different redirect URIs
    print("\n5. Testing Redirect URI Variations:")
    test_uris = [
        "http://localhost:8000/api/v1/gmail/oauth2callback",
        "http://127.0.0.1:8000/api/v1/gmail/oauth2callback",
        "https://localhost:8000/api/v1/gmail/oauth2callback"
    ]
    
    for uri in test_uris:
        status = "✅ Recommended" if uri == google_redirect_uri else "⚠️  Alternative"
        print(f"   {uri} - {status}")

def fix_redirect_uri():
    """Update the redirect URI to the correct format"""
    print("\n=== Fixing Redirect URI ===")
    
    # Read current .env
    with open('.env', 'r') as f:
        lines = f.readlines()
    
    # Update redirect URI
    updated_lines = []
    for line in lines:
        if line.startswith('GOOGLE_REDIRECT_URI='):
            updated_lines.append('GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/gmail/oauth2callback\n')
            print("✅ Updated GOOGLE_REDIRECT_URI in .env file")
        else:
            updated_lines.append(line)
    
    # Write back to .env
    with open('.env', 'w') as f:
        f.writelines(updated_lines)
    
    print("✅ Configuration updated successfully")

if __name__ == "__main__":
    diagnose_gmail_config()
    
    # Ask user if they want to fix the redirect URI
    fix_it = input("\nDo you want to fix the redirect URI? (y/n): ").lower().strip()
    if fix_it == 'y':
        fix_redirect_uri()
        print("\n🔄 Please restart your server for changes to take effect")
        print("📋 Don't forget to update Google Console with the correct redirect URI!")