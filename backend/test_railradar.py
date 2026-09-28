import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("RAILRADAR_API_KEY")

url = "https://api.railradar.in/v1/trains/12919/live"

headers = {
    "Authorization": f"Bearer {api_key}"
}

response = requests.get(url, headers=headers, timeout=30)

print("HTTP Status:", response.status_code)

if response.status_code == 200:
    print("RailRadar API: SUCCESS")
else:
    print("RailRadar API: FAILED")
    print("Response:", response.text[:300])