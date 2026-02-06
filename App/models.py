from pydantic import BaseModel, Field
from typing import List,Optional


class TravelRequest(BaseModel):
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    days: int = Field(1, ge=1,le=14)
    budget: str = "Medium"
    interests: str = "General"

class PlaceDetail(BaseModel):
    place_name: str
    category: str
    description: str
    rating: Optional[float] = None
    image_url: Optional[str] = None 

class DailyItinerary(BaseModel):
    day: int
    places: List[PlaceDetail]

class TripResponse(BaseModel):
    trip_title: str
    clothing_advice: str
    itinerary: List[DailyItinerary]
