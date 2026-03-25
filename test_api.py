import requests
import json

BASE_URL = "http://localhost:1933"
HEADERS = {
    "Content-Type": "application/json",
    "X-OpenViking-Bot-Key": "kjWSxIHxa0hRk9C/0gSFvA=="
}

def test_health():
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}\n")
        return True
    except Exception as e:
        print(f"Error: {e}\n")
        return False

def test_chat():
    print("Testing chat endpoint...")
    payload = {
        "user_id": "test_user_123",
        "query": "Openviking怎么使用"
    }
    try:
        response = requests.post(f"{BASE_URL}/api/v1/bot/chat", headers=HEADERS, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}\n")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}\n")
        return False

def test_list_memory():
    print("Testing list memory endpoint...")
    payload = {
        "user_id": "test_user_123"
    }
    try:
        response = requests.post(f"{BASE_URL}/api/v1/ov/list/memory", headers=HEADERS, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}\n")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}\n")
        return False

def test_memory_info():
    print("Testing memory info endpoint...")
    payload = {
        "user_id": "test_user_123",
        "uri": "/entities/mem_00ee38e0-6393-4293-9fc9-e6dfd8e282c1.md",
        "level": "read"
    }
    try:
        response = requests.post(f"{BASE_URL}/api/v1/ov/info/memory", headers=HEADERS, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}\n")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}\n")
        return False

def test_delete_user():
    print("Testing delete user endpoint...")
    payload = {
        "user_id": "test_user_123"
    }
    try:
        response = requests.post(f"{BASE_URL}/api/v1/ov/delete/user", headers=HEADERS, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}\n")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}\n")
        return False

def test_unauthorized():
    print("Testing unauthorized access...")
    headers = {
        "Content-Type": "application/json",
        "X-OpenViking-Bot-Key": "wrong_key"
    }
    payload = {
        "user_id": "test_user_123",
        "query": "Hello"
    }
    try:
        response = requests.post(f"{BASE_URL}/api/v1/bot/chat", headers=headers, json=payload)
        print(f"Status: {response.status_code} (expected 401)")
        print(f"Response: {response.json()}\n")
        return response.status_code == 401
    except Exception as e:
        print(f"Error: {e}\n")
        return False

if __name__ == "__main__":
    print("Starting API tests...\n")

    test_health()
    test_unauthorized()

    # If server is running, test all endpoints
    print("-" * 50)
    print("Note: Make sure the server is running first!")
    print("Start server with: python app/main.py\n")
    print("Run these tests again after starting the server.")
    print("-" * 50)
