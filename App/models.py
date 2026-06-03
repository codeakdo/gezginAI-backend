from pydantic import BaseModel, Field
from typing import List, Optional


class TravelRequest(BaseModel):
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    days: int = Field(1, ge=1, le=14)
    budget: str = "Medium"
    interests: str = "General"
    transport_mode: str = "walking"


class PlaceLocation(BaseModel):
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class PlaceDetail(BaseModel):
    place_name: str
    category: str
    description: str
    rating: Optional[float] = None
    image_url: Optional[str] = None
    time_of_day: Optional[str] = None
    price_level: Optional[str] = None
    estimated_duration_minutes: Optional[int] = None
    route_order: Optional[int] = None
    visit_tip: Optional[str] = None
    history_note: Optional[str] = None
    ai_note: Optional[str] = None
    image_attribution: Optional[str] = None
    source_url: Optional[str] = None
    location: PlaceLocation = Field(default_factory=PlaceLocation)


class RouteSummary(BaseModel):
    distance_km: float = 0
    estimated_travel_minutes: int = 0
    route_points: List[List[float]] = Field(default_factory=list)
    transport_mode: Optional[str] = None


class DailyItinerary(BaseModel):
    day: int
    theme: Optional[str] = None
    day_summary: Optional[str] = None
    local_tip: Optional[str] = None
    weather_summary: Optional[str] = None
    estimated_daily_budget: Optional[str] = None
    route_summary: RouteSummary = Field(default_factory=RouteSummary)
    places: List[PlaceDetail]


class TripResponse(BaseModel):
    city: Optional[str] = None
    trip_title: str
    clothing_advice: str
    weather_forecast: Optional[str] = None
    total_estimated_budget: Optional[str] = None
    travel_summary: Optional[str] = None
    itinerary: List[DailyItinerary]


class PlaceIdentificationResponse(BaseModel):
    ad: str
    aciklama: str
    puan: float
    kategori: str
    fiyat_seviyesi: str
    tahmini_sure: str
    resim_arama_kelimesi: str
    koordinat: Optional[dict] = None
