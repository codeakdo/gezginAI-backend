import google.generativeai as genai
import json
import os
import time
import requests
from App.logger import logger
from App.models import TravelRequest

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_SEARCH_CX = os.getenv("GOOGLE_SEARCH_CX")


def find_place_image(place_name: str, context: str):
    if not GOOGLE_API_KEY or not GOOGLE_SEARCH_CX:
        return None
    
    clean_name = place_name.split('(')[0].strip()
    query = f"{clean_name} {context} tourism"
    
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
            logger.info(f"      ✅ Bulundu: {link[:40]}...") 
            return link
        else:
            logger.warning(f"      ❌ Sonuç yok.")
    except Exception as e:
        logger.error(f"      ⚠️ Hata ({place_name}): {e}")
        pass
    return None

def enrich_data_with_images(data: dict, search_context: str):
    
    place_count = 0
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



def generate_trip_plan_ai(req: TravelRequest):
   
    if GOOGLE_API_KEY:
         genai.configure(api_key=GOOGLE_API_KEY)

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
        # Hata durumunda boş model dönelim ki API çökmesin
        return {
            "trip_title": "Plan Oluşturulamadı",
            "clothing_advice": "Lütfen tekrar deneyin.",
            "itinerary": []
        }