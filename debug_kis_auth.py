import os
import requests
import json
from dotenv import load_dotenv

# Force reload .env
load_dotenv(override=True)

APP_KEY = os.getenv("KIS_APP_KEY")
APP_SECRET = os.getenv("KIS_APP_SECRET")
BASE_URL = os.getenv("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443")
CANO = os.getenv("KIS_ACCOUNT_NO") # Using ACCOUNT_NO as CANO for simplicity if needed, or check KIS_CANO

print(f"--- Debugging KIS API ---")
print(f"Base URL: {BASE_URL}")
print(f"App Key: {APP_KEY[:4]}...{APP_KEY[-4:] if APP_KEY else 'None'}")
print(f"App Secret: {APP_SECRET[:4]}...{APP_SECRET[-4:] if APP_SECRET else 'None'}")

def get_access_token():
    url = f"{BASE_URL}/oauth2/tokenP"
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET
    }
    
    print(f"\n[1] Requesting Access Token from {url}...")
    try:
        res = requests.post(url, headers=headers, json=body)
        print(f"Status Code: {res.status_code}")
        data = res.json()
        if res.status_code == 200:
            print("Access Token: SUCCESS")
            return data['access_token']
        else:
            print(f"Access Token FAILED: {data}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

def test_news_api(token):
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/news-title"
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHKST01011800",
        "custtype": "P" # Individual
    }
    
    # Test with Samsung Electronics (005930)
    import time
    params = {
        "FID_NEWS_OFER_ENTP_CODE": "", # News Provider Code
        "FID_COND_MRKT_CLS_CODE": "",  # Market Class Code
        "FID_INPUT_ISCD": "005930",    # Stock Code
        "FID_TITL_CNTT": "",           # Title Content
        "FID_INPUT_DATE_1": time.strftime("%Y%m%d"), # Date
        "FID_INPUT_HOUR_1": "000000",  # Time
        "FID_RANK_SORT_CLS_CODE": "",  # Rank Sort
        "FID_INPUT_SRNO": ""           # Serial No
    }
    
    print(f"\n[2] Testing News API for 005930...")
    try:
        res = requests.get(url, headers=headers, params=params)
        print(f"Status Code: {res.status_code}")
        print(f"Response Headers: {dict(res.headers)}")
        print(f"Response Body: {res.text[:500]}...") # Print start of response
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    token = get_access_token()
    if token:
        test_news_api(token)
