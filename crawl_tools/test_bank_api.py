"""
Test finding API endpoints for Vietnamese bank interest rates
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import json
from datetime import datetime

print(f"\n{'='*60}")
print("Testing Bank API Endpoints")
print(f"{'='*60}")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
}

############## Test Techcombank API
print(f"\n--- Techcombank API Test ---")

tcb_apis = [
    "https://techcombank.com/api/interest-rate",
    "https://techcombank.com/api/v1/interest-rate",
    "https://api.techcombank.com/interest-rates",
    "https://techcombank.com/api/rates",
    "https://techcombank.com/cong-cu-tien-ich/api/lai-suat",
]

for url in tcb_apis:
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"  {url}: {r.status_code}")
        if r.status_code == 200 and r.text:
            print(f"    Response: {r.text[:200]}...")
    except Exception as e:
        print(f"  {url}: Error - {type(e).__name__}")


############## Test MB Bank API
print(f"\n--- MB Bank API Test ---")

mbb_apis = [
    "https://www.mbbank.com.vn/api/interest-rate",
    "https://www.mbbank.com.vn/api/v1/rates",
    "https://api.mbbank.com.vn/rates",
    "https://www.mbbank.com.vn/Fee/GetInterestRate",
    "https://www.mbbank.com.vn/lai-suat/api",
]

for url in mbb_apis:
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"  {url}: {r.status_code}")
        if r.status_code == 200 and r.text:
            print(f"    Response: {r.text[:200]}...")
    except Exception as e:
        print(f"  {url}: Error - {type(e).__name__}")


############## Test VPBank API
print(f"\n--- VPBank API Test ---")

vpb_apis = [
    "https://www.vpbank.com.vn/api/interest-rate",
    "https://www.vpbank.com.vn/api/v1/rates",
    "https://api.vpbank.com.vn/rates",
    "https://www.vpbank.com.vn/cong-cu-tien-ich/api/bang-lai-suat",
]

for url in vpb_apis:
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"  {url}: {r.status_code}")
        if r.status_code == 200 and r.text:
            print(f"    Response: {r.text[:200]}...")
    except Exception as e:
        print(f"  {url}: Error - {type(e).__name__}")


############## Alternative: Try third-party aggregator APIs
print(f"\n--- Third-party Aggregator APIs ---")

aggregator_apis = [
    "https://api.vietstock.vn/finance/interest-rate",
    "https://cafef.vn/api/lai-suat-ngan-hang",
]

for url in aggregator_apis:
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"  {url}: {r.status_code}")
        if r.status_code == 200 and r.text:
            print(f"    Response: {r.text[:200]}...")
    except Exception as e:
        print(f"  {url}: Error - {type(e).__name__}")


print(f"\n{'='*60}")
print("API test completed")
print(f"{'='*60}")