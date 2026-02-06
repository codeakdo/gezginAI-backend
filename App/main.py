from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
import json
import os
import time
import requests
from typing import List, Optional
from dotenv import load_dotenv
from pathlib import Path 
from App.models import *
from App.logger import logger


# --- 1. AYARLAR VE GÜVENLİK (LOGLU BAŞLANGIÇ) ---
# .env dosyasını yükle
current_dir = Path(__file__).parent
env_path = current_dir.parent / ".env"
load_dotenv(dotenv_path=env_path)

# API Anahtarlarını Al
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_SEARCH_CX = os.getenv("GOOGLE_SEARCH_CX")

# --- AÇILIŞ EKRANI LOGLARI ---
logger.info("\n" + "="*40)
logger.info(f"🚀 GEZGİN AI BACKEND BAŞLATILIYOR...")

# API Key Kontrolü
if GOOGLE_API_KEY:
    masked_key = f"{GOOGLE_API_KEY[:5]}...{GOOGLE_API_KEY[-4:]}"
    logger.info(f"🔑 API Key:   ✅ ({masked_key})")
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    logger.info(f"🔑 API Key:   ❌ (YOK - .env dosyasını kontrol et!)")

# Search CX Kontrolü
if GOOGLE_SEARCH_CX:
    logger.info(f"🔎 Search CX: ✅ (Mevcut)")
else:
    logger.error(f"🔎 Search CX: ❌ (YOK - Resimler gelmeyecek)")

logger.info("="*40 + "\n")
# -----------------------------

# FastAPI Uygulamasını Kur
app = FastAPI()

# CORS Ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. VERİ MODELLERİ ---

#Bu kod models.py icinde yer aliyor.

# --- 3. YARDIMCI FONKSİYONLAR (LOGLU RESİM ARAMA) ---

def find_place_image(place_name: str, context: str):
    """ Google Custom Search API kullanarak mekanın resmini bulur. """
    if not GOOGLE_API_KEY or not GOOGLE_SEARCH_CX:
        return None
    
    clean_name = place_name.split('(')[0].strip()
    query = f"{clean_name} {context} tourism"
    
    # LOG: Ne arıyoruz?
    logger.info(f"   🔍 Görsel Aranıyor: {query}...")
    
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_SEARCH_CX,
        "q": query,
        "searchType": "image",
        "imgSize": "large",
        "num": 1,
        "safe": "off"
    }
    
    try:
        res = requests.get(url, params=params).json()
        if "items" in res:
            link = res["items"][0]["link"]
            # LOG: Bulundu
            logger.info(f"      ✅ Bulundu: {link[:40]}...") 
            return link
        else:
            # LOG: Bulunamadı
            logger.warning(f"      ❌ Sonuç yok.")
    except Exception as e:
        logger.error(f"      ⚠️ Hata ({place_name}): {e}")
        pass
    return None

def enrich_data_with_images(data: dict, search_context: str):
    """ JSON içindeki her mekanı gezer ve resim URL'si ekler. """
    place_count = 0
    # Toplam mekan sayısını bulalım (sadece log için)
    if "itinerary" in data:
        for day in data['itinerary']:
            place_count += len(day.get('places', []))
            
    logger.info(f"\n🎨 Görsel Tarama Başlıyor ({place_count} mekan)...")
    
    if "itinerary" in data:
        for day in data['itinerary']:
            for place in day['places']:
                img = find_place_image(place['place_name'], search_context)
                place['image_url'] = img
                time.sleep(0.1) 
    return data

# --- 4. YAPAY ZEKA MANTIĞI ---

def generate_trip_plan_ai(req: TravelRequest):
    model = genai.GenerativeModel('gemini-flash-latest')
    if req.city and req.city.strip():
        location_context = req.city
        search_context = req.city
        prompt_intro = f"Create a travel itinerary for {req.city}."
    elif req.latitude and req.longitude:
        location_context = f"coordinates {req.latitude}, {req.longitude}"
        search_context = "nearby tourist attraction"
        prompt_intro = f"I am at coordinates {req.latitude}, {req.longitude}. Create a travel itinerary for nearby places."
    else:
        location_context = "Istanbul"
        search_context = "Istanbul"
        prompt_intro = "Create a travel itinerary for Istanbul."

    logger.info(f"⏳ AI Düşünüyor... ({location_context}, {req.days} Gün, {req.budget} Bütçe)")

    prompt = f"""
    {prompt_intro}
    
    PARAMETERS:
    - Duration: {req.days} Day(s).
    - Budget Level: {req.budget}.
    - Interests: {req.interests}.
    
    INSTRUCTIONS:
    1. Prepare a detailed {req.days}-day plan.
    2. Suggest clothing advice.
    3. Provide a brief weather forecast.
    4. Include 3-5 places per day.
    5. CRITICAL: Every single day MUST include at least 1 Restaurant or Cafe for lunch/dinner.
    6. Estimate price level for EVERY place as exactly: "Low", "Medium", or "High".
    
    JSON SCHEMA:
    {{
        "trip_title": "Creative Title",
        "clothing_advice": "Short advice",
        "weather_forecast": "Weather summary", 
        "itinerary": [
            {{
                "day": 1,
                "places": [
                    {{
                        "place_name": "Name",
                        "category": "Restaurant/Cafe/Museum...",
                        "description": "Description",
                        "rating": 4.7,
                        "time_of_day": "Morning/Lunch/Evening",
                        "price_level": "Medium" 
                    }}
                ]
            }}
        ]
    }}
    """
    
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        
        clean_text = response.text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
            
        data = json.loads(clean_text)
        return enrich_data_with_images(data, search_context)
        
    except Exception as e:
        logger.error(f"💥 AI Üretim Hatası: {e}")
        return {
            "trip_title": "Plan Oluşturulamadı",
            "clothing_advice": "Lütfen tekrar deneyin.",
            "itinerary": []
        }

# --- 5. API ENDPOINT ---

@app.post("/create-plan", response_model=TripResponse)
async def create_plan(request: TravelRequest):
    logger.info(f"\n📨 YENİ İSTEK: {request.city or 'GPS'} | {request.days} Gün | {request.budget}")
    
    try:
        result = generate_trip_plan_ai(request)
        return result
    except Exception as e:
        logger.error(f"Server Hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))