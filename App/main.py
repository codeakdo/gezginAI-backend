# Load environment variables FIRST — before any app module reads os.getenv at import time
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from App.models import TravelRequest, TripResponse, PlaceIdentificationResponse
from App.logger import logger
from App.services import generate_trip_plan_ai, identify_place_from_image

# --- BAŞLANGIÇ LOGLARI ---
logger.info("\n" + "=" * 40)
logger.info("🚀 GEZGİN AI BACKEND BAŞLATILIYOR...")
if os.getenv("GOOGLE_API_KEY"):
    logger.info("🔑 API Key:   ✅ (Mevcut)")
else:
    logger.error("🔑 API Key:   ❌ (YOK — .env dosyasına GOOGLE_API_KEY ekleyin)")
logger.info("=" * 40 + "\n")

# --- UYGULAMA ---
app = FastAPI()

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Beklenmeyen Hata: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "error_type": type(exc).__name__},
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ENDPOİNTLER ---
@app.get("/")
async def healthcheck():
    return {"status": "online", "service": "GezginAI Backend", "version": "2.0.0"}


@app.post("/create-plan", response_model=TripResponse)
async def create_plan(request: TravelRequest):
    logger.info(f"\n📨 YENİ İSTEK: {request.city or 'GPS'} | {request.days} Gün")
    try:
        result = generate_trip_plan_ai(request)
        return result
    except Exception as e:
        logger.error(f"Server Hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB

@app.post("/identify-place", response_model=PlaceIdentificationResponse)
async def identify_place(image: UploadFile = File(...)):
    logger.info(f"\n📸 LENS İSTEĞİ: {image.filename} ({image.content_type})")
    try:
        mime_type = (image.content_type or "image/jpeg").lower().split(";")[0].strip()
        if mime_type not in _ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail=f"Desteklenmeyen dosya türü: {mime_type}. JPEG, PNG veya WebP yükleyin.")

        image_bytes = await image.read()
        if len(image_bytes) > _MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail="Dosya boyutu çok büyük (maksimum 10 MB).")
        if len(image_bytes) < 100:
            raise HTTPException(status_code=400, detail="Geçersiz görsel dosyası.")

        result = identify_place_from_image(image_bytes, mime_type)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lens Hatası: {e}")
        raise HTTPException(status_code=500, detail="Görsel analiz edilemedi. Lütfen tekrar deneyin.")
