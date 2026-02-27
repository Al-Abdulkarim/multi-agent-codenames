import requests
import json

url = "http://localhost:8000/api/game/new"
payload = {
    "board_size": 25,
    "difficulty": "medium",
    "human_role": "spymaster",
    "human_team": "red",
    "api_key": "dummy_key",
}

try:
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print("Response Content:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")
