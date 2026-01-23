#!/usr/bin/env python3
"""
Test script to verify the complete authentication flow
"""

import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"

def test_registration():
    """Test user registration"""
    print("Testing user registration...")
    
    test_user = {
        "email": "test@example.com",
        "password": "testpassword123",
        "phone": "1234567890"
    }
    
    try:
        response = requests.post(f"{API_BASE}/register", json=test_user)
        print(f"Registration response: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            print("✓ Registration successful")
            return True
        else:
            print("✗ Registration failed")
            return False
            
    except Exception as e:
        print(f"✗ Registration error: {e}")
        return False

def test_login():
    """Test user login"""
    print("\nTesting user login...")
    
    login_data = {
        "email": "test@example.com",
        "password": "testpassword123"
    }
    
    try:
        response = requests.post(f"{API_BASE}/login", json=login_data)
        print(f"Login response: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            print(f"✓ Login successful, token: {token[:20]}...")
            return token
        else:
            print("✗ Login failed")
            return None
            
    except Exception as e:
        print(f"✗ Login error: {e}")
        return None

def test_protected_endpoint(token):
    """Test accessing protected endpoint"""
    print("\nTesting protected endpoint...")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        response = requests.get(f"{API_BASE}/protected", headers=headers)
        print(f"Protected endpoint response: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            print("✓ Protected endpoint access successful")
            return True
        else:
            print("✗ Protected endpoint access failed")
            return False
            
    except Exception as e:
        print(f"✗ Protected endpoint error: {e}")
        return False

def test_dashboard(token):
    """Test dashboard endpoint"""
    print("\nTesting dashboard endpoint...")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        response = requests.get(f"{API_BASE}/dashboard", headers=headers)
        print(f"Dashboard response: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            print("✓ Dashboard access successful")
            return True
        else:
            print("✗ Dashboard access failed")
            return False
            
    except Exception as e:
        print(f"✗ Dashboard error: {e}")
        return False

def test_health_check():
    """Test health check endpoint"""
    print("\nTesting health check...")
    
    try:
        response = requests.get(f"{API_BASE}/health")
        print(f"Health check response: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            print("✓ Health check successful")
            return True
        else:
            print("✗ Health check failed")
            return False
            
    except Exception as e:
        print(f"✗ Health check error: {e}")
        return False

def main():
    """Run all tests"""
    print("Starting authentication flow tests...\n")
    
    # Test health check first
    health_ok = test_health_check()
    
    if not health_ok:
        print("\n❌ Server is not healthy. Please start the server first.")
        print("Run: python back/main.py")
        return
    
    # Test registration
    reg_ok = test_registration()
    
    # Test login
    token = test_login() if reg_ok else None
    
    # Test protected endpoints
    protected_ok = test_protected_endpoint(token) if token else False
    dashboard_ok = test_dashboard(token) if token else False
    
    # Summary
    print("\n" + "="*50)
    print("TEST SUMMARY:")
    print(f"✓ Health Check: {'PASS' if health_ok else 'FAIL'}")
    print(f"✓ Registration: {'PASS' if reg_ok else 'FAIL'}")
    print(f"✓ Login: {'PASS' if token else 'FAIL'}")
    print(f"✓ Protected Endpoint: {'PASS' if protected_ok else 'FAIL'}")
    print(f"✓ Dashboard: {'PASS' if dashboard_ok else 'FAIL'}")
    
    if all([health_ok, reg_ok, token, protected_ok, dashboard_ok]):
        print("\n🎉 All tests passed! Authentication flow is working correctly.")
    else:
        print("\n❌ Some tests failed. Please check the implementation.")

if __name__ == "__main__":
    main()
