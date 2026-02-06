from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path 
import os
from App.models import TravelRequest, TripResponse
from App.logger import logger
from App.services import generate_trip_plan_ai 

# --- 1. AYARLAR ---
current_dir = Path(__file__).parent
env_path = current_dir.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Başlangıç Logları
logger.info("\n" + "="*40)
logger.info(f"🚀 GEZGİN AI BACKEND BAŞLATILIYOR...")

# API Key Kontrolü (Sadece log için, asıl kullanım services.py içinde)
if os.getenv("GOOGLE_API_KEY"):
    logger.info(f"🔑 API Key:   ✅ (Mevcut)")
else:
    logger.error(f"🔑 API Key:   ❌ (YOK)")

logger.info("\n" + "="*40 + "\n")

# --- 2. UYGULAMA ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 3. ENDPOINT ---
@app.post("/create-plan", response_model=TripResponse)
async def create_plan(request: TravelRequest):
    logger.info(f"\n📨 YENİ İSTEK: {request.city or 'GPS'} | {request.days} Gün")
    
    try:
      
        result = generate_trip_plan_ai(request)
        return result
    except Exception as e:
        logger.error(f"Server Hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))