from fastapi.testclient import TestClient
from App.main import app  

client = TestClient(app)

# 1. TEST: Her şey doğru girilince sistem çalışıyor mu? (Happy Path)
def test_create_plan_valid():
    payload = {
        "city": "Berlin",
        "days": 3,
        "budget": "High",
        "interests": "History"
    }
  
    response = client.post("/create-plan", json=payload)
    
    # Beklentimiz: 200 OK dönmesi (AI çalışırsa)

# 2. TEST: Gün sayısı 0 girilirse hata veriyor mu? (Edge Case)
def test_create_plan_invalid_days_zero():
    payload = {
        "city": "Paris",
        "days": 0,  #(En az 1 olmalı)
        "budget": "Medium"
    }
    response = client.post("/create-plan", json=payload)
    
    # Beklentimiz: 422 Unprocessable Entity (Validation Error)
    assert response.status_code == 422 
    print("✅ 0 gün testi geçti!")

# 3. TEST: Gün sayısı 15 girilirse hata veriyor mu?
def test_create_plan_invalid_days_too_many():
    payload = {
        "city": "Paris",
        "days": 15,  #(En fazla 14 olmalı)
        "budget": "Medium"
    }
    response = client.post("/create-plan", json=payload)
    
    assert response.status_code == 422
    print("✅ 15 gün testi geçti!")