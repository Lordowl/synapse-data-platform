import requests
import json

# Ottieni un token (usa le credenziali di test)
login_response = requests.post(
    "http://127.0.0.1:8000/api/v1/auth/login",
    data={"username": "admin_sparkasse", "password": "password"}
)

if login_response.status_code == 200:
    token = login_response.json()["access_token"]

    # Chiamata all'endpoint test-packages-v2
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        "http://127.0.0.1:8000/api/v1/reportistica/test-packages-v2?type_reportistica=Mensile",
        headers=headers
    )

    if response.status_code == 200:
        data = response.json()
        print(f"Total packages: {len(data)}")
        print("\nPackages:")
        for pkg in data:
            print(f"\n  Package: {pkg['package']}")
            print(f"    Pre-Check Status: {pkg.get('pre_check')}")
            print(f"    Pre-Check Anno: {pkg.get('anno_precheck')}")
            print(f"    Pre-Check Settimana: {pkg.get('settimana_precheck')}")
            print(f"    Pre-Check Mese: {pkg.get('mese_precheck')}")
            print(f"    Pre-Check Data: {pkg.get('data_esecuzione')}")
            print(f"    Prod Status: {pkg.get('prod')}")
            print(f"    Prod Anno: {pkg.get('anno_prod')}")
            print(f"    Prod Settimana: {pkg.get('settimana_prod')}")
            print(f"    Prod Mese: {pkg.get('mese_prod')}")
            print(f"    Prod Data: {pkg.get('data_esecuzione_prod')}")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
else:
    print(f"Login failed: {login_response.status_code}")
    print(login_response.text)
