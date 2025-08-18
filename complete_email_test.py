#!/usr/bin/env python3
"""
Complete Email Integration Test
Tests the full Gmail OAuth flow and email functionality
"""

import os
import requests
import time
import json
from dotenv import load_dotenv

load_dotenv()

class EmailIntegrationTester:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.test_email = os.getenv("TEST_EMAIL")
        self.test_password = os.getenv("EMAIL_PASS")
        self.jwt_token = None
        self.headers = {}
        
    def test_server_connection(self):
        """Test if the server is running"""
        print("1. Testing server connection...")
        try:
            response = requests.get(f"{self.base_url}/docs", timeout=5)
            if response.status_code == 200:
                print("   ✅ Server is running")
                return True
            else:
                print(f"   ❌ Server responded with status {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            print("   ❌ Server is not running. Please start with: uvicorn app.main:app --reload")
            return False
        except Exception as e:
            print(f"   ❌ Error connecting to server: {e}")
            return False
    
    def test_user_login(self):
        """Test user authentication"""
        print("\n2. Testing user login...")
        
        if not self.test_email or not self.test_password:
            print("   ❌ TEST_EMAIL or EMAIL_PASS not found in .env file")
            return False
            
        login_data = {
            "email": self.test_email,
            "password": self.test_password
        }
        
        try:
            response = requests.post(f"{self.base_url}/api/v1/auth/login", json=login_data)
            
            if response.status_code == 200:
                token_data = response.json()
                self.jwt_token = token_data.get("access_token")
                self.headers = {"Authorization": f"Bearer {self.jwt_token}"}
                print(f"   ✅ Login successful for {self.test_email}")
                return True
            else:
                print(f"   ❌ Login failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"   ❌ Login error: {e}")
            return False
    
    def test_gmail_oauth_config(self):
        """Test Gmail OAuth configuration"""
        print("\n3. Testing Gmail OAuth configuration...")
        
        # Check environment variables
        google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        google_redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
        
        issues = []
        
        if not google_client_id:
            issues.append("GOOGLE_CLIENT_ID missing")
        if not google_client_secret:
            issues.append("GOOGLE_CLIENT_SECRET missing")
        if not google_redirect_uri:
            issues.append("GOOGLE_REDIRECT_URI missing")
        elif google_redirect_uri != "http://localhost:8000/api/v1/gmail/oauth2callback":
            issues.append(f"GOOGLE_REDIRECT_URI mismatch: {google_redirect_uri}")
            
        if issues:
            print("   ❌ Configuration issues:")
            for issue in issues:
                print(f"      - {issue}")
            return False
        else:
            print("   ✅ Gmail OAuth configuration looks correct")
            return True
    
    def test_gmail_auth_endpoint(self):
        """Test Gmail OAuth initiation"""
        print("\n4. Testing Gmail OAuth initiation...")
        
        if not self.jwt_token:
            print("   ❌ No JWT token available")
            return False
            
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/gmail/auth",
                headers=self.headers,
                allow_redirects=False
            )
            
            if response.status_code in [302, 307]:
                oauth_url = response.headers.get("location")
                if oauth_url and "accounts.google.com" in oauth_url:
                    print("   ✅ OAuth URL generated successfully")
                    print(f"   🔗 OAuth URL: {oauth_url[:100]}...")
                    return True, oauth_url
                else:
                    print(f"   ❌ Invalid OAuth URL: {oauth_url}")
                    return False, None
            else:
                print(f"   ❌ OAuth initiation failed: {response.status_code} - {response.text}")
                return False, None
                
        except Exception as e:
            print(f"   ❌ OAuth error: {e}")
            return False, None
    
    def test_gmail_connection_status(self):
        """Test current Gmail connection status"""
        print("\n5. Testing Gmail connection status...")
        
        if not self.jwt_token:
            print("   ❌ No JWT token available")
            return False
            
        try:
            # Try to sync emails to check if Gmail is connected
            response = requests.post(
                f"{self.base_url}/api/v1/gmail/sync?max_results=1",
                headers=self.headers
            )
            
            if response.status_code == 200:
                print("   ✅ Gmail is already connected and working")
                return True
            elif response.status_code == 401:
                error_detail = response.json().get("detail", "")
                if "not authenticated" in error_detail.lower():
                    print("   ⚠️  Gmail not connected - OAuth required")
                    return False
                else:
                    print(f"   ❌ Authentication error: {error_detail}")
                    return False
            else:
                print(f"   ❌ Gmail sync failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"   ❌ Gmail status check error: {e}")
            return False
    
    def test_email_endpoints(self):
        """Test email-related endpoints"""
        print("\n6. Testing email endpoints...")
        
        if not self.jwt_token:
            print("   ❌ No JWT token available")
            return False
            
        endpoints_to_test = [
            ("/api/v1/gmail/emails?limit=1", "GET", "List emails"),
            ("/api/v1/gmail/watch", "POST", "Start email watch")
        ]
        
        results = {}
        
        for endpoint, method, description in endpoints_to_test:
            try:
                if method == "GET":
                    response = requests.get(f"{self.base_url}{endpoint}", headers=self.headers)
                else:
                    response = requests.post(f"{self.base_url}{endpoint}", headers=self.headers)
                
                if response.status_code == 200:
                    results[description] = "✅ Working"
                elif response.status_code == 401:
                    results[description] = "⚠️  Requires Gmail OAuth"
                else:
                    results[description] = f"❌ Error {response.status_code}"
                    
            except Exception as e:
                results[description] = f"❌ Exception: {str(e)[:50]}"
        
        for desc, status in results.items():
            print(f"   {desc}: {status}")
            
        return all("✅" in status for status in results.values())
    
    def diagnose_redirect_uri_issue(self):
        """Diagnose and provide solutions for redirect URI mismatch"""
        print("\n7. Redirect URI Diagnosis:")
        print("   The 'redirect_uri_mismatch' error occurs when:")
        print("   - Google Console redirect URI ≠ application redirect URI")
        print("   - Domain/port mismatch")
        print("   - HTTP vs HTTPS mismatch")
        
        print("\n   🔧 Solutions:")
        print("   1. Go to Google Cloud Console:")
        print("      https://console.cloud.google.com/apis/credentials")
        print("   2. Find your OAuth 2.0 Client ID")
        print("   3. Add these Authorized redirect URIs:")
        print("      - http://localhost:8000/api/v1/gmail/oauth2callback")
        print("      - http://127.0.0.1:8000/api/v1/gmail/oauth2callback")
        print("   4. Save changes and wait 5-10 minutes for propagation")
        
    def run_complete_test(self):
        """Run the complete email integration test suite"""
        print("=== Complete Email Integration Test ===")
        print(f"Testing with user: {self.test_email}")
        print("=" * 50)
        
        # Test server connection
        if not self.test_server_connection():
            return False
            
        # Test user login
        if not self.test_user_login():
            return False
            
        # Test Gmail OAuth config
        config_ok = self.test_gmail_oauth_config()
        
        # Test Gmail OAuth endpoint
        oauth_ok, oauth_url = self.test_gmail_auth_endpoint()
        
        # Test Gmail connection status
        gmail_connected = self.test_gmail_connection_status()
        
        # Test email endpoints
        endpoints_ok = self.test_email_endpoints()
        
        # Summary
        print("\n" + "=" * 50)
        print("TEST SUMMARY:")
        print("=" * 50)
        
        if gmail_connected:
            print("🎉 Gmail is already connected and working!")
            print("✅ All email functionality should be operational")
        else:
            print("⚠️  Gmail OAuth required")
            if oauth_ok and oauth_url:
                print("✅ OAuth URL generation working")
                print("\n🔗 NEXT STEPS:")
                print("1. Copy this OAuth URL and open in browser:")
                print(f"   {oauth_url}")
                print("2. Complete Google OAuth consent")
                print("3. After consent, Gmail will be connected")
            else:
                print("❌ OAuth URL generation failed")
                if not config_ok:
                    self.diagnose_redirect_uri_issue()
        
        return gmail_connected

if __name__ == "__main__":
    tester = EmailIntegrationTester()
    tester.run_complete_test()