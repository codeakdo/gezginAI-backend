from fastapi.testclient import TestClient
from App.main import app  
from unittest.mock import patch

client = TestClient(app)

#Validaton Tests

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


# Mock Test
def test_create_plan_with_mock_ai():
    fake_response = {
        "trip_title": "Test Tatili",
        "clothing_advice": "Şapka tak",
        "itinerary": [
            {
                "day": 1,
                "places": [
                    {
                        "place_name": "Test Müzesi",
                        "category": "Museum",
                        "description": "Harika bir yer",
                        "rating": 5.0,
                        "image_url": "http://fake.com/img.jpg",
                        "price_level": "Medium"
                    }
                ]
            }
        ]
    }

    with patch("App.main.generate_trip_plan_ai", return_value=fake_response):
        
        payload = {"city": "Berlin", "days": 1}
        response = client.post("/create-plan", json=payload)

        # 3. KONTROL
        assert response.status_code == 200
        
        data = response.json()
        assert data["trip_title"] == "Test Tatili"
        print("✅ Mocking testi başarıyla geçti! Google'a gidilmedi.")