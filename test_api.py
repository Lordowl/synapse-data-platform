import requests

print("Test API Endpoints...")
print()

base_url = "http://127.0.0.1:8000/api/v1"

# Test 1: Health check
try:
    response = requests.get("http://127.0.0.1:8000/healthcheck")
    print(f"OK Health Check: {response.status_code} - {response.json()}")
except Exception as e:
    print(f"❌ Health Check Failed: {e}")

print()

# Test 2: Folder Current (senza auth)
try:
    response = requests.get(f"{base_url}/folder/current")
    print(f"Folder Current: {response.status_code}")
    if response.status_code == 200:
        print(f"   Response: {response.json()}")
    elif response.status_code == 401:
        print(f"   ERROR: Richiede autenticazione (non dovrebbe!)")
    else:
        print(f"   Response: {response.text}")
except Exception as e:
    print(f"❌ Folder Current Failed: {e}")

print()

# Test 3: Banks Available (senza auth)
try:
    response = requests.get(f"{base_url}/banks/available")
    print(f"Banks Available: {response.status_code}")
    if response.status_code == 200:
        print(f"   Response: {response.json()}")
    elif response.status_code == 401:
        print(f"   ERROR: Richiede autenticazione (non dovrebbe!)")
    else:
        print(f"   Response: {response.text}")
except Exception as e:
    print(f"❌ Banks Available Failed: {e}")

print()
print("=" * 50)
print("Se vedi errori 401, il backend non è stato riavviato")
print("Premi CTRL+C nel terminale del backend e rilancia:")
print("  python main.py")
print("=" * 50)