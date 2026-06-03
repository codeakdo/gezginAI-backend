import json
import math
import os
import time
from collections import Counter
from urllib.parse import quote

import google.generativeai as genai
import requests

from App.logger import logger
from App.models import TravelRequest

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_SEARCH_CX = os.getenv("GOOGLE_SEARCH_CX")
OPEN_METEO_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSRM_URL = "https://router.project-osrm.org/route/v1"
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "GezginAI/3.0 (travel-planner)"
PLACE_FETCH_LIMIT = 140

TRANSPORT_PROFILES = {
    "walking": "foot",
    "cycling": "cycling",
    "driving": "driving",
}

TRANSPORT_SPEED_KMH = {
    "walking": 4.6,
    "cycling": 14.0,
    "driving": 28.0,
}

TRANSPORT_LEG_LIMIT_KM = {
    "walking": 2.2,
    "cycling": 5.5,
    "driving": 14.0,
}

TRANSPORT_DAY_LIMIT_KM = {
    "walking": 12.0,
    "cycling": 30.0,
    "driving": 120.0,
}

TRANSPORT_CENTER_LIMIT_KM = {
    "walking": 4.5,
    "cycling": 9.0,
    "driving": 25.0,
}


def request_json(url: str, params: dict | None = None, headers: dict | None = None, method: str = "get", data: str | None = None):
    if method.lower() == "post":
        response = requests.post(url, params=params, headers=headers, data=data, timeout=30)
    else:
        response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def geocode_city(req: TravelRequest):
    if req.city and req.city.strip():
        try:
            payload = request_json(
                OPEN_METEO_GEOCODE_URL,
                params={"name": req.city.strip(), "count": 1, "language": "en", "format": "json"},
            )
            results = payload.get("results") or []
            if results:
                city_data = results[0]
                return {
                    "name": city_data.get("name") or req.city.strip(),
                    "country": city_data.get("country"),
                    "latitude": city_data.get("latitude"),
                    "longitude": city_data.get("longitude"),
                }
        except Exception as exc:
            logger.warning(f"City geocoding failed: {exc}")

    if req.latitude is not None and req.longitude is not None:
        return {
            "name": req.city or "Selected Location",
            "country": None,
            "latitude": req.latitude,
            "longitude": req.longitude,
        }

    return {"name": req.city or "Istanbul", "country": None, "latitude": 41.0082, "longitude": 28.9784}


def weather_code_to_text(code: int):
    mapping = {
        0: "Clear",
        1: "Mostly clear",
        2: "Partly cloudy",
        3: "Cloudy",
        45: "Foggy",
        48: "Freezing fog",
        51: "Light drizzle",
        53: "Drizzle",
        55: "Heavy drizzle",
        61: "Light rain",
        63: "Rain",
        65: "Heavy rain",
        71: "Light snow",
        73: "Snow",
        75: "Heavy snow",
        80: "Showers",
        81: "Strong showers",
        82: "Intense showers",
        95: "Thunderstorm risk",
    }
    return mapping.get(code, "Mixed weather")


def fetch_weather_context(city_context: dict, days: int):
    try:
        forecast = request_json(
            OPEN_METEO_FORECAST_URL,
            params={
                "latitude": city_context["latitude"],
                "longitude": city_context["longitude"],
                "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "auto",
                "forecast_days": max(1, min(days, 7)),
            },
        )
        daily = forecast.get("daily", {})
        weather_days = []
        for index, date in enumerate(daily.get("time", [])):
            weather_days.append(
                {
                    "date": date,
                    "summary": weather_code_to_text((daily.get("weathercode") or [0])[index]),
                    "temp_max": (daily.get("temperature_2m_max") or [None])[index],
                    "temp_min": (daily.get("temperature_2m_min") or [None])[index],
                    "rain_chance": (daily.get("precipitation_probability_max") or [None])[index],
                }
            )
        headline = ", ".join(
            f"Day {idx + 1}: {day['summary']} {round(day['temp_min'])}°-{round(day['temp_max'])}°"
            for idx, day in enumerate(weather_days[: min(3, len(weather_days))])
            if day["temp_min"] is not None and day["temp_max"] is not None
        )
        return {"headline": headline or "Forecast unavailable.", "days": weather_days}
    except Exception as exc:
        logger.warning(f"Weather lookup failed: {exc}")
        return {"headline": "Forecast unavailable.", "days": []}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float):
    # Optimized fast path for identical points
    if lat1 == lat2 and lon1 == lon2:
        return 0.0
    radius = 6371.0
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat, delta_lon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return radius * 2 * math.asin(math.sqrt(a))


def static_location_preview(latitude: float | None, longitude: float | None):
    if latitude is None or longitude is None:
        seed = quote(f"{latitude}-{longitude}-fallback")
        return f"https://picsum.photos/seed/{seed}/1200/900", "Fallback preview"
    return (
        f"https://staticmap.openstreetmap.de/staticmap.php?center={latitude},{longitude}&zoom=16&size=1200x900&markers={latitude},{longitude},lightblue1",
        "OpenStreetMap location preview",
    )


def wikipedia_lookup(place_name: str, city_name: str):
    try:
        payload = request_json(
            WIKIPEDIA_API_URL,
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": f"{place_name} {city_name}",
                "gsrlimit": 1,
                "prop": "pageimages|extracts|info",
                "piprop": "thumbnail",
                "pithumbsize": 1200,
                "inprop": "url",
                "exintro": True,
                "explaintext": True,
                "format": "json",
            },
            headers={"User-Agent": USER_AGENT},
        )
        pages = payload.get("query", {}).get("pages", {})
        for page in pages.values():
            return {
                "image_url": (page.get("thumbnail") or {}).get("source"),
                "extract": page.get("extract"),
                "source_url": page.get("fullurl"),
                "attribution": "Wikipedia",
            }
    except Exception as exc:
        logger.warning(f"Wikipedia lookup failed ({place_name}): {exc}")
    return {"image_url": None, "extract": None, "source_url": None, "attribution": None}


def osm_commons_image(tags: dict):
    direct = tags.get("image")
    if direct and direct.startswith("http"):
        return direct, "OpenStreetMap image tag"
    commons = tags.get("wikimedia_commons")
    if commons:
        title = commons.replace("File:", "").replace(" ", "_")
        return f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(title)}", "Wikimedia Commons"
    return None, None


def geocode_place(place_name: str, city_name: str):
    try:
        payload = request_json(
            NOMINATIM_SEARCH_URL,
            params={"q": f"{place_name}, {city_name}", "format": "jsonv2", "limit": 1},
            headers={"User-Agent": USER_AGENT},
        )
        if payload:
            match = payload[0]
            return {
                "address": match.get("display_name"),
                "latitude": float(match["lat"]),
                "longitude": float(match["lon"]),
            }
    except Exception as exc:
        logger.warning(f"Place geocoding failed ({place_name}): {exc}")
    return {"address": None, "latitude": None, "longitude": None}


def search_places(query: str, limit: int = 3):
    try:
        payload = request_json(
            NOMINATIM_SEARCH_URL,
            params={"q": query, "format": "jsonv2", "limit": limit},
            headers={"User-Agent": USER_AGENT},
        )
        return payload if isinstance(payload, list) else []
    except Exception as exc:
        logger.warning(f"Place search failed ({query}): {exc}")
        return []


def parse_osm_address(tags: dict):
    parts = [tags.get("addr:street"), tags.get("addr:housenumber"), tags.get("addr:city")]
    clean = [part for part in parts if part]
    return ", ".join(clean) if clean else None


def classify_osm_category(tags: dict):
    tourism = tags.get("tourism")
    amenity = tags.get("amenity")
    leisure = tags.get("leisure")
    shop = tags.get("shop")
    historic = tags.get("historic")

    if amenity in {"restaurant", "fast_food"}:
        return "Restaurant"
    if amenity in {"cafe", "ice_cream"}:
        return "Cafe"
    if amenity in {"bar", "pub"}:
        return "Bar"
    if tourism == "museum":
        return "Museum"
    if tourism in {"gallery", "artwork"}:
        return "Gallery"
    if tourism == "viewpoint":
        return "Viewpoint"
    if leisure in {"park", "garden"}:
        return "Park"
    if shop in {"mall", "department_store", "boutique", "marketplace", "books", "fashion"}:
        return "Shopping"
    if historic or tourism == "attraction":
        return "Landmark"
    return "Experience"


def score_place(place: dict, interests: str):
    text = f"{place['category']} {place['place_name']} {' '.join(place.get('features', []))}".lower()
    score = 0
    interest_text = (interests or "").lower()
    buckets = {
        "history": ["museum", "landmark", "historic"],
        "culture": ["museum", "gallery", "landmark"],
        "food": ["restaurant", "cafe", "bar"],
        "night": ["bar"],
        "nature": ["park", "viewpoint"],
        "view": ["viewpoint", "park"],
        "shop": ["shopping"],
        "photo": ["viewpoint", "landmark", "gallery"],
    }
    for keyword, related in buckets.items():
        if keyword in interest_text and any(item in text for item in related):
            score += 4
    if place["category"] in {"Landmark", "Museum", "Restaurant", "Viewpoint"}:
        score += 2
    return score


def unique_by_name(items: list[dict]):
    seen = set()
    output = []
    for item in items:
        key = item["place_name"].strip().lower()
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output


def extract_requested_places(interests: str):
    generic_phrases = {
        "history",
        "culture",
        "history & culture",
        "local food",
        "views",
        "views & photography",
        "nightlife",
        "museums",
        "nature walks",
        "architecture",
        "books",
    }
    place_keywords = {
        "museum", "stadium", "fc", "cathedral", "park", "market", "gallery",
        "sagrada", "camp nou", "old town", "palace", "basilica", "tower",
    }
    requested = []
    for chunk in (interests or "").split(","):
        phrase = chunk.strip()
        if not phrase:
            continue
        lowered = phrase.lower()
        if lowered in generic_phrases:
            continue
        if any(keyword in lowered for keyword in place_keywords) or len(phrase.split()) >= 2:
            requested.append(phrase)
    return requested


def infer_category_from_phrase(phrase: str):
    text = phrase.lower()
    if "museum" in text:
        return "Museum"
    if "stadium" in text or "fc" in text:
        return "Landmark"
    if "cathedral" in text or "basilica" in text:
        return "Landmark"
    if "park" in text or "garden" in text:
        return "Park"
    if "market" in text or "food" in text:
        return "Restaurant"
    return "Landmark"


def build_requested_place_candidates(interests: str, city_context: dict):
    requested = []
    for phrase in extract_requested_places(interests):
        location = geocode_place(phrase, city_context["name"])
        if location.get("latitude") is None:
            continue
        if haversine_km(
            city_context["latitude"],
            city_context["longitude"],
            location["latitude"],
            location["longitude"],
        ) > 14:
            continue
        category = infer_category_from_phrase(phrase)
        place = {
            "place_name": phrase,
            "category": category,
            "description": category_description({"category": category}, city_context["name"]),
            "rating": 4.7,
            "time_of_day": None,
            "price_level": "Medium",
            "estimated_duration_minutes": 90,
            "route_order": None,
            "visit_tip": "Pinned from your custom request.",
            "history_note": None,
            "ai_note": "This stop was prioritized because you explicitly asked for it.",
            "image_url": None,
            "image_attribution": None,
            "source_url": None,
            "features": ["Requested place"],
            "location": location,
            "score": 999,
            "must_include": True,
        }
        enrich_place_metadata(place, city_context["name"])
        requested.append(place)
    return requested


def fetch_city_place_pool(city_context: dict, interests: str):
    lat = city_context["latitude"]
    lon = city_context["longitude"]
    radius = 9000
    query = f"""
[out:json][timeout:30];
(
  nwr(around:{radius},{lat},{lon})["tourism"~"museum|attraction|gallery|viewpoint|artwork"];
  nwr(around:{radius},{lat},{lon})["historic"];
  nwr(around:{radius},{lat},{lon})["amenity"~"restaurant|cafe|bar|pub|ice_cream|fast_food"];
  nwr(around:{radius},{lat},{lon})["leisure"~"park|garden"];
  nwr(around:{radius},{lat},{lon})["shop"~"mall|department_store|boutique|marketplace|books|fashion"];
);
out center tags {PLACE_FETCH_LIMIT};
"""
    try:
        payload = request_json(
            OVERPASS_URL,
            method="post",
            data=query,
            headers={"User-Agent": USER_AGENT, "Content-Type": "text/plain"},
        )
    except Exception as exc:
        logger.warning(f"OSM place pool failed: {exc}")
        return []

    places = []
    for element in payload.get("elements", []):
        tags = element.get("tags") or {}
        name = tags.get("name")
        if not name:
            continue
        latitude = element.get("lat") or (element.get("center") or {}).get("lat")
        longitude = element.get("lon") or (element.get("center") or {}).get("lon")
        if latitude is None or longitude is None:
            continue

        image_url, attribution = osm_commons_image(tags)
        wiki_hint = tags.get("wikipedia")
        category = classify_osm_category(tags)
        features = [
            feature.replace("_", " ").title()
            for feature in [
                tags.get("tourism"),
                tags.get("amenity"),
                tags.get("historic"),
                tags.get("cuisine"),
                tags.get("leisure"),
                tags.get("shop"),
            ]
            if feature
        ]

        place = {
            "place_name": name,
            "category": category,
            "description": "",
            "rating": round(4.2 + min(score_place({"category": category, "place_name": name, "features": features}, interests), 5) * 0.1, 1),
            "time_of_day": None,
            "price_level": "Medium",
            "estimated_duration_minutes": 60,
            "route_order": None,
            "visit_tip": "",
            "history_note": None,
            "ai_note": None,
            "image_url": image_url,
            "image_attribution": attribution,
            "source_url": f"https://en.wikipedia.org/wiki/{quote(wiki_hint.split(':', 1)[1].replace(' ', '_'))}" if wiki_hint and ":" in wiki_hint else None,
            "features": features[:3],
            "location": {
                "address": parse_osm_address(tags) or f"{city_context['name']} city area",
                "latitude": float(latitude),
                "longitude": float(longitude),
            },
            "score": score_place({"category": category, "place_name": name, "features": features}, interests),
        }
        places.append(place)

    requested = build_requested_place_candidates(interests, city_context)
    deduped = unique_by_name(requested + places)
    deduped.sort(
        key=lambda item: (
            -item["score"],
            haversine_km(
                city_context["latitude"],
                city_context["longitude"],
                item["location"]["latitude"],
                item["location"]["longitude"],
            ),
        )
    )
    return deduped


def category_description(place: dict, city_name: str):
    category = place["category"]
    if category == "Museum":
        return f"{city_name}'nin tarihini ve kültürünü koleksiyonlar, mimari ve atmosfer aracılığıyla keşfedebileceğiniz önemli bir durak."
    if category == "Landmark":
        return f"{city_name}'nin ruhunu hemen hissettiren, kaçırılmaması gereken ikonik bir nokta."
    if category == "Restaurant":
        return "Günü yerel lezzetlerle taçlandırmak için mükemmel bir yemek durağı."
    if category == "Cafe":
        return "Kahve, tatlı ve çevre enerjisiyle nefes almak için ideal bir mola noktası."
    if category == "Viewpoint":
        return "Şehrin siluetini ve en iyi fotoğraf açılarını yakalamak için güçlü bir görsel durak."
    if category == "Park":
        return "Tempoyu düşürüp biraz nefes almak için harika bir açık hava molası."
    if category == "Shopping":
        return "Yerel ürünler, kitaplar, tasarım veya sokak kültürü için keyifli bir keşif durağı."
    if category == "Bar":
        return "Kontrol listesi baskısı olmadan şehrin atmosferini içine çekeceğiniz sosyal bir akşam durağı."
    return f"{city_name} gününüze ritim ve çeşitlilik katan faydalı bir durak."


def category_tip(category: str, weather_summary: str):
    summary = (weather_summary or "").lower()
    if category in {"Park", "Viewpoint"} and ("rain" in summary or "showers" in summary):
        return "Küçük bir şemsiye yanınızda bulundurun ya da hava değişirse bu durağı biraz öne alın."
    if category in {"Museum", "Gallery"}:
        return "Daha sakin odalar ve daha az kalabalık için sabahın erken saatlerini tercih edin."
    if category in {"Restaurant", "Cafe"}:
        return "Yoğun yemek saatlerinden biraz önce gitmeniz daha keyifli bir deneyim sunar."
    if category == "Landmark":
        return "Sabahın erken saatleri genellikle daha iyi ışık ve daha kolay fotoğraf imkânı sağlar."
    if category == "Bar":
        return "Enerjinize göre esnek bir son durak olarak değerlendirin."
    return "Günün rahat geçmesi için programda biraz boş alan bırakın."


def mode_label(mode: str):
    return {"walking": "walking", "cycling": "cycling", "driving": "driving"}.get(mode, "walking")


def enrich_place_metadata(place: dict, city_name: str):
    wiki = wikipedia_lookup(place["place_name"], city_name)
    if wiki.get("extract") and not place.get("history_note"):
        place["history_note"] = wiki["extract"][:280].strip()
    if wiki.get("source_url") and not place.get("source_url"):
        place["source_url"] = wiki["source_url"]

    if not place.get("image_url") and wiki.get("image_url"):
        place["image_url"] = wiki["image_url"]
        place["image_attribution"] = wiki.get("attribution")

    if not place.get("image_url"):
        preview_url, attribution = static_location_preview(
            place["location"].get("latitude"),
            place["location"].get("longitude"),
        )
        place["image_url"] = preview_url
        place["image_attribution"] = attribution

    place["ai_note"] = (
        f"{place.get('time_of_day', 'Ana')} durağı olarak kullanmak en iyisi; günü dengede tutar "
        f"ve çevredeki rotaya yakın kalır."
    )
    return place


def choose_nearest(candidates: list[dict], anchor: dict | None, allowed: set[str] | None, used_names: set[str], max_leg_km: float | None):
    filtered = [item for item in candidates if item["place_name"] not in used_names and (allowed is None or item["category"] in allowed)]
    if not filtered:
        return None
    if anchor is None:
        return filtered[0]

    with_distance = []
    for item in filtered:
        distance = haversine_km(
            anchor["location"]["latitude"],
            anchor["location"]["longitude"],
            item["location"]["latitude"],
            item["location"]["longitude"],
        )
        if max_leg_km is None or distance <= max_leg_km:
            with_distance.append((distance, item))

    if with_distance:
        with_distance.sort(key=lambda pair: (pair[0], -pair[1]["score"]))
        return with_distance[0][1]

    filtered.sort(
        key=lambda item: (
            haversine_km(
                anchor["location"]["latitude"],
                anchor["location"]["longitude"],
                item["location"]["latitude"],
                item["location"]["longitude"],
            ),
            -item["score"],
        )
    )
    return filtered[0]


def choose_morning_anchor(candidates: list[dict], city_context: dict, used_names: set[str], allowed: set[str], transport_mode: str):
    center_limit = TRANSPORT_CENTER_LIMIT_KM.get(transport_mode, TRANSPORT_CENTER_LIMIT_KM["walking"])
    filtered = [
        item for item in candidates
        if item["place_name"] not in used_names and item["category"] in allowed
    ]
    if not filtered:
        return None
    close_to_center = [
        item for item in filtered
        if item.get("must_include")
        or haversine_km(
            city_context["latitude"],
            city_context["longitude"],
            item["location"]["latitude"],
            item["location"]["longitude"],
        ) <= center_limit
    ]
    target = close_to_center or filtered
    target.sort(
        key=lambda item: (
            0 if item.get("must_include") else 1,
            haversine_km(
                city_context["latitude"],
                city_context["longitude"],
                item["location"]["latitude"],
                item["location"]["longitude"],
            ),
            -item["score"],
        )
    )
    return target[0]


def assign_time_and_budget(place: dict, slot: str):
    mapping = {
        "morning": ("Morning", 90),
        "lunch": ("Lunch", 75),
        "afternoon": ("Afternoon", 90),
        "evening": ("Evening", 80),
        "night": ("Night", 90),
    }
    time_label, minutes = mapping[slot]
    place["time_of_day"] = time_label
    place["estimated_duration_minutes"] = minutes
    if place["category"] in {"Restaurant", "Bar"}:
        place["price_level"] = "Medium"
    elif place["category"] in {"Museum", "Gallery", "Shopping"}:
        place["price_level"] = "Medium"
    else:
        place["price_level"] = "Low"
    return place


def fallback_seed_candidates(city_context: dict):
    city = city_context["name"]
    return [
        {"query": f"Old Town, {city}", "label": "Old Town", "category": "Landmark"},
        {"query": f"Cathedral, {city}", "label": f"{city} Cathedral", "category": "Landmark"},
        {"query": f"Central Market, {city}", "label": "Central Market", "category": "Restaurant"},
        {"query": f"Museum, {city}", "label": f"{city} Museum", "category": "Museum"},
        {"query": f"City Park, {city}", "label": f"{city} Park", "category": "Park"},
        {"query": f"Viewpoint, {city}", "label": f"{city} Viewpoint", "category": "Viewpoint"},
        {"query": f"Coffee, {city}", "label": f"{city} Coffee Stop", "category": "Cafe"},
        {"query": f"Plaza Mayor, {city}", "label": f"{city} Main Square", "category": "Landmark"},
        {"query": f"Food Hall, {city}", "label": f"{city} Food Hall", "category": "Restaurant"},
        {"query": f"Botanical Garden, {city}", "label": f"{city} Botanical Garden", "category": "Park"},
        {"query": f"Art Gallery, {city}", "label": f"{city} Art Gallery", "category": "Gallery"},
        {"query": f"Bookstore, {city}", "label": f"{city} Bookshop", "category": "Shopping"},
    ]


def build_thematic_search_candidates(city_context: dict):
    thematic_queries = [
        ("best local restaurant", "Restaurant"),
        ("cafe", "Cafe"),
        ("park", "Park"),
        ("botanical garden", "Park"),
        ("viewpoint", "Viewpoint"),
        ("food market", "Restaurant"),
    ]
    candidates = []
    seen = set()
    for query, category in thematic_queries:
        results = search_places(f"{query}, {city_context['name']}", limit=2)
        for result in results:
            name = (result.get("name") or result.get("display_name", "").split(",")[0]).strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            lat = result.get("lat")
            lon = result.get("lon")
            if lat is None or lon is None:
                continue
            lat = float(lat)
            lon = float(lon)
            if haversine_km(city_context["latitude"], city_context["longitude"], lat, lon) > 8:
                continue
            seen.add(key)
            candidates.append(
                {
                    "place_name": name,
                    "category": category,
                    "description": category_description({"category": category}, city_context["name"]),
                    "rating": 4.4,
                    "time_of_day": None,
                    "price_level": "Medium",
                    "estimated_duration_minutes": 75,
                    "route_order": None,
                    "visit_tip": "Suggested from nearby thematic search.",
                    "history_note": None,
                    "ai_note": None,
                    "image_url": None,
                    "image_attribution": None,
                    "source_url": None,
                    "location": {
                        "address": result.get("display_name"),
                        "latitude": lat,
                        "longitude": lon,
                    },
                }
            )
    return candidates


def build_resilient_fallback(req: TravelRequest, city_context: dict, weather_context: dict):
    day_places = build_thematic_search_candidates(city_context)
    for seed in fallback_seed_candidates(city_context):
        location = geocode_place(seed["query"], city_context["name"])
        if location.get("latitude") is None:
            continue
        if haversine_km(
            city_context["latitude"],
            city_context["longitude"],
            location["latitude"],
            location["longitude"],
        ) > 8:
            continue
        place = {
            "place_name": seed["label"],
            "category": seed["category"],
            "description": category_description({"category": seed["category"]}, city_context["name"]),
            "rating": 4.4,
            "time_of_day": None,
            "price_level": "Medium",
            "estimated_duration_minutes": 75,
            "route_order": None,
            "visit_tip": "Use this as a flexible stop if nearby.",
            "history_note": None,
            "ai_note": None,
            "image_url": None,
            "image_attribution": None,
            "source_url": None,
            "location": location,
        }
        day_places.append(place)

    day_places = unique_by_name(day_places)

    if not day_places:
        day_places = [
            {
                "place_name": f"{city_context['name']} Center Walk",
                "category": "Landmark",
                "description": f"A compact starter route around the center of {city_context['name']}.",
                "rating": 4.3,
                "time_of_day": "Morning",
                "price_level": "Low",
                "estimated_duration_minutes": 90,
                "route_order": 1,
                "visit_tip": "Use this as a base and branch out on foot.",
                "history_note": None,
                "ai_note": "A safe fallback stop when live place data is limited.",
                "image_url": static_location_preview(city_context["latitude"], city_context["longitude"])[0],
                "image_attribution": "OpenStreetMap location preview",
                "source_url": None,
                "location": {
                    "address": city_context["name"],
                    "latitude": city_context["latitude"],
                    "longitude": city_context["longitude"],
                },
            }
        ]

    itinerary = []
    for day in range(1, req.days + 1):
        if len(day_places) <= 4:
            selected = day_places[:]
        else:
            offset = ((day - 1) * 2) % len(day_places)
            rotated = day_places[offset:] + day_places[:offset]
            selected = rotated[:4]
        prepared = []
        slots = ["morning", "lunch", "afternoon", "evening"]
        for slot, place in zip(slots, selected):
            cloned = assign_time_and_budget(dict(place), slot)
            enrich_place_metadata(cloned, city_context["name"])
            prepared.append(cloned)
        itinerary.append(
            {
                "day": day,
                "theme": "Şehir Merkezi Keşfi",
                "day_summary": f"{day}. gün, canlı öneri kaynakları sınırlı olduğundan güvenilir bir şehir merkezi rotası kullanıyor.",
                "local_tip": "Bunu temel rota olarak kullanın; yürürken daha iyi bir durak görürseniz rotayı esnetin.",
                "weather_summary": weather_context["headline"],
                "estimated_daily_budget": "Tahmini günlük harcama: 45-90 EUR",
                "places": prepared,
            }
        )

    for day in itinerary:
        enrich_day(day, req.transport_mode, city_context["name"])

    return {
        "trip_title": f"{city_context['name']} Yedek Rota Planı",
        "clothing_advice": "Rahat hareket edebileceğiniz kıyafetler giyin ve hafif bir hava katmanı yanınızda bulundurun.",
        "weather_forecast": weather_context["headline"],
        "travel_summary": "Canlı öneri kaynakları geçici olarak sınırlı olduğundan güvenilir bir yedek rota oluşturuldu.",
        "total_estimated_budget": f"Tahmini toplam: {req.days * 45}-{req.days * 90} EUR",
        "itinerary": itinerary,
    }


def build_structured_itinerary_from_pool(req: TravelRequest, city_context: dict, weather_context: dict):
    pool = fetch_city_place_pool(city_context, req.interests)
    if not pool:
        return None

    used_names: set[str] = set()
    itinerary = []
    category_counter = Counter()
    leg_limit = TRANSPORT_LEG_LIMIT_KM.get(req.transport_mode, TRANSPORT_LEG_LIMIT_KM["walking"])

    for day in range(1, req.days + 1):
        day_weather = weather_context["days"][day - 1]["summary"] if day - 1 < len(weather_context["days"]) else weather_context["headline"]
        scenic_allowed = {"Landmark", "Museum", "Gallery", "Park", "Viewpoint", "Shopping", "Experience"}
        evening_allowed = {"Viewpoint", "Bar", "Restaurant", "Landmark", "Cafe"}

        attractions = [item for item in pool if item["category"] in scenic_allowed and item["place_name"] not in used_names]
        attractions.sort(key=lambda item: (0 if item.get("must_include") else 1, category_counter[item["category"]], -item["score"]))
        morning = choose_morning_anchor(attractions, city_context, used_names, scenic_allowed, req.transport_mode)
        if not morning:
            morning = choose_nearest(pool, None, scenic_allowed, used_names, leg_limit)
        if not morning:
            break
        used_names.add(morning["place_name"])
        category_counter[morning["category"]] += 1

        lunch = choose_nearest(pool, morning, {"Restaurant", "Cafe"}, used_names, leg_limit)
        if lunch:
            used_names.add(lunch["place_name"])
            category_counter[lunch["category"]] += 1

        afternoon_anchor = lunch or morning
        afternoon = choose_nearest(pool, afternoon_anchor, scenic_allowed, used_names, leg_limit)
        if afternoon:
            used_names.add(afternoon["place_name"])
            category_counter[afternoon["category"]] += 1

        evening_anchor = afternoon or lunch or morning
        evening = choose_nearest(pool, evening_anchor, evening_allowed, used_names, leg_limit)
        if evening:
            used_names.add(evening["place_name"])
            category_counter[evening["category"]] += 1

        optional = choose_nearest(pool, evening or afternoon_anchor, scenic_allowed | {"Cafe", "Restaurant"}, used_names, leg_limit)
        if optional and req.days <= 3:
            used_names.add(optional["place_name"])
            category_counter[optional["category"]] += 1

        sequence = [
            ("morning", morning),
            ("lunch", lunch),
            ("afternoon", afternoon),
            ("evening", evening),
            ("night", optional),
        ]

        day_places = []
        for slot, candidate in sequence:
            if not candidate:
                continue
            place = dict(candidate)
            place["description"] = category_description(place, city_context["name"])
            place["visit_tip"] = category_tip(place["category"], day_weather)
            place = assign_time_and_budget(place, slot)
            place = enrich_place_metadata(place, city_context["name"])
            day_places.append(place)
            time.sleep(0.05)

        theme = "Kültür ve Şehir Belleği"
        top_categories = {place["category"] for place in day_places}
        if {"Park", "Viewpoint"} & top_categories:
            theme = "Açık Hava Manzaraları ve Yavaş Tempo"
        if {"Restaurant", "Cafe", "Bar"} & top_categories and len(top_categories) <= 3:
            theme = "Lezzetlerle Mahalle Keşfi"

        itinerary.append(
            {
                "day": day,
                "theme": theme,
                "day_summary": f"{day}. gün, {city_context['name']} şehir merkezinde birbirine yakın ve doğal bir akışla birbirine bağlanan duraklar içeriyor.",
                "local_tip": "Rota, gün boyunca bunaltıcı hissetmemesi için bilinçli olarak kompakt tutuldu.",
                "weather_summary": day_weather,
                "estimated_daily_budget": "Tahmini günlük harcama: 55-110 EUR",
                "places": day_places,
            }
        )

    if not itinerary:
        return None

    return {
        "trip_title": f"{city_context['name']} Şehir Rotası",
        "clothing_advice": "Rahat yürüyüş ayakkabısı giyin ve değişken hava için yanınıza ince bir üst kat alın.",
        "weather_forecast": weather_context["headline"],
        "travel_summary": f"{req.days} günlük, tekrarsız durakları olan ve {mode_label(req.transport_mode)} temposuna göre planlanmış, gerçek yemek molalarını da içeren bir rota.",
        "total_estimated_budget": f"Tahmini toplam: {req.days * 55}-{req.days * 110} EUR",
        "itinerary": itinerary,
    }


def order_places_for_route(places: list[dict]):
    order = {"Morning": 0, "Lunch": 1, "Afternoon": 2, "Evening": 3, "Night": 4}
    ordered = sorted(places, key=lambda item: order.get(item.get("time_of_day"), 99))
    for index, place in enumerate(ordered, start=1):
        place["route_order"] = index
    return ordered


def build_route_summary(places: list[dict], transport_mode: str):
    coordinate_pairs = []
    for place in places:
        lat = place["location"].get("latitude")
        lon = place["location"].get("longitude")
        if lat is None or lon is None:
            continue
        coordinate_pairs.append((lon, lat))

    profile = TRANSPORT_PROFILES.get(transport_mode, "foot")
    if len(coordinate_pairs) >= 2:
        route_string = ";".join(f"{lon},{lat}" for lon, lat in coordinate_pairs)
        try:
            payload = request_json(
                f"{OSRM_URL}/{profile}/{route_string}",
                params={"overview": "full", "geometries": "geojson", "steps": "false"},
                headers={"User-Agent": USER_AGENT},
            )
            routes = payload.get("routes") or []
            if routes:
                route = routes[0]
                geometry = route.get("geometry", {}).get("coordinates", [])
                return {
                    "distance_km": round(route.get("distance", 0) / 1000, 1),
                    "estimated_travel_minutes": int(round(route.get("duration", 0) / 60)),
                    "route_points": [[lat, lon] for lon, lat in geometry],
                    "transport_mode": transport_mode,
                }
        except Exception as exc:
            logger.warning(f"OSRM route failed for {transport_mode}, using straight-line fallback: {exc}")

    points = [[lat, lon] for lon, lat in coordinate_pairs]
    distance_km = 0.0
    for index in range(1, len(points)):
        prev = points[index - 1]
        curr = points[index]
        distance_km += haversine_km(prev[0], prev[1], curr[0], curr[1])
    speed = TRANSPORT_SPEED_KMH.get(transport_mode, TRANSPORT_SPEED_KMH["walking"])
    minutes = int(round((distance_km / max(speed, 1)) * 60))
    return {
        "distance_km": round(distance_km, 1),
        "estimated_travel_minutes": minutes,
        "route_points": points,
        "transport_mode": transport_mode,
    }


def enforce_route_distance_limit(day: dict, transport_mode: str):
    max_distance = TRANSPORT_DAY_LIMIT_KM.get(transport_mode, TRANSPORT_DAY_LIMIT_KM["walking"])
    places = list(day.get("places", []))
    if len(places) <= 3:
        day["route_summary"] = build_route_summary(places, transport_mode)
        return day

    route_summary = build_route_summary(places, transport_mode)
    while route_summary["distance_km"] > max_distance and len(places) > 3:
        removable_indices = [index for index, place in enumerate(places) if not place.get("must_include")]
        if not removable_indices:
            break
        remove_index = removable_indices[-1]
        places.pop(remove_index)
        route_summary = build_route_summary(places, transport_mode)

    day["places"] = order_places_for_route(places)
    day["route_summary"] = route_summary
    return day


def enrich_day(day: dict, transport_mode: str, city_name: str):
    ordered_places = order_places_for_route(day.get("places", []))
    day["places"] = [enrich_place_metadata(place, city_name) for place in ordered_places]
    day["route_summary"] = build_route_summary(day["places"], transport_mode)
    return enforce_route_distance_limit(day, transport_mode)


def normalize_ai_response(data: dict, city_context: dict, weather_context: dict, transport_mode: str):
    city_lat = city_context.get("latitude")
    city_lon = city_context.get("longitude")
    MAX_KM = 90  # discard places hallucinated outside the city area

    for day_index, day in enumerate(data.get("itinerary", [])):
        day.setdefault("theme", f"Day {day.get('day', day_index + 1)}")
        day.setdefault("day_summary", f"A balanced day inside {city_context['name']} with a tighter route flow.")
        day.setdefault("local_tip", "Use the route as a backbone and keep one flexible stop open.")
        day.setdefault(
            "weather_summary",
            weather_context["days"][day_index]["summary"] if day_index < len(weather_context["days"]) else weather_context["headline"],
        )
        day.setdefault("estimated_daily_budget", "Estimated daily spend: 60-120 EUR")

        # Build a precise city string that includes country for Nominatim
        city_str = city_context["name"]
        if city_context.get("country"):
            city_str = f"{city_context['name']}, {city_context['country']}"

        valid_places = []
        for place in day.get("places", []):
            # Always geocode — never trust AI-hallucinated coordinates
            geo = geocode_place(place["place_name"], city_str)
            if not geo.get("latitude"):
                # Second attempt: just place name + city
                geo = geocode_place(place["place_name"], city_context["name"])

            if geo.get("latitude") and city_lat and city_lon:
                dist = haversine_km(city_lat, city_lon, geo["latitude"], geo["longitude"])
                if dist > MAX_KM:
                    logger.warning(
                        f"Skipping '{place['place_name']}' — geocoded {dist:.0f} km from {city_context['name']}"
                    )
                    continue
                place["location"] = geo
            elif geo.get("latitude"):
                place["location"] = geo
            else:
                # Geocoding failed entirely — fall back to city centre so the pin is at least in the right country
                place["location"] = {"latitude": city_lat or 0.0, "longitude": city_lon or 0.0}

            place.setdefault("description", category_description(place, city_context["name"]))
            place.setdefault("visit_tip", category_tip(place.get("category", "Experience"), day["weather_summary"]))
            place.setdefault("estimated_duration_minutes", 75)
            enrich_place_metadata(place, city_context["name"])
            time.sleep(0.03)
            valid_places.append(place)

        day["places"] = valid_places
        enrich_day(day, transport_mode, city_context["name"])
    return data


def generate_plan_with_ai(req: TravelRequest, city_context: dict, weather_context: dict):
    api_key = os.getenv("GOOGLE_API_KEY") or GOOGLE_API_KEY
    if not api_key:
        return build_structured_itinerary_from_pool(req, city_context, weather_context)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""
Create JSON only for a polished travel planner app.

City: {city_context['name']}
Days: {req.days}
Budget: {req.budget}
Interests: {req.interests}
Transport mode: {req.transport_mode}
Weather context: {weather_context['headline']}

Rules:
- Build exactly {req.days} days.
- Do not repeat places across days.
- Include 4 or 5 places per day.
- Include at least one restaurant or cafe every day.
- Favor route-compact sequencing for {req.transport_mode}.
- Use only these time_of_day values: Morning, Lunch, Afternoon, Evening, Night.
- Use only these price_level values: Low, Medium, High.
- Favor real, geocodable places.
- CRITICAL: ALL text fields (trip_title, clothing_advice, weather_forecast, travel_summary, total_estimated_budget, theme, day_summary, local_tip, estimated_daily_budget, description, visit_tip) MUST be written in Turkish (Türkçe). Place names (place_name) must remain in their original local language.

Schema:
{{
  "trip_title": "string",
  "clothing_advice": "string",
  "weather_forecast": "string",
  "travel_summary": "string",
  "total_estimated_budget": "string",
  "itinerary": [
    {{
      "day": 1,
      "theme": "string",
      "day_summary": "string",
      "local_tip": "string",
      "estimated_daily_budget": "string",
      "places": [
        {{
          "place_name": "string",
          "category": "string",
          "description": "string",
          "rating": 4.7,
          "time_of_day": "Morning",
          "price_level": "Medium",
          "estimated_duration_minutes": 90,
          "visit_tip": "string"
        }}
      ]
    }}
  ]
}}
"""
    response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    clean_text = response.text.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
    data = json.loads(clean_text)
    return normalize_ai_response(data, city_context, weather_context, req.transport_mode)


def generate_trip_plan_ai(req: TravelRequest):
    city_context = geocode_city(req)
    weather_context = fetch_weather_context(city_context, req.days)
    logger.info(
        f"Generating plan: {city_context['name']} | {req.days} days | {req.budget} budget | {req.interests} | {req.transport_mode}"
    )

    data = None
    try:
        data = generate_plan_with_ai(req, city_context, weather_context)
    except Exception as exc:
        logger.error(f"AI plan generation failed: {exc}")

    if not data:
        data = build_structured_itinerary_from_pool(req, city_context, weather_context)

    if not data or not data.get("itinerary"):
        data = build_resilient_fallback(req, city_context, weather_context)

    for day in data.get("itinerary", []):
        if not day.get("route_summary"):
            enrich_day(day, req.transport_mode, city_context["name"])

    data["city"] = city_context["name"]
    data.setdefault("weather_forecast", weather_context["headline"])
    data.setdefault("travel_summary", f"A {req.days}-day plan is ready.")
    data.setdefault("total_estimated_budget", f"Estimated total: {req.days * 55}-{req.days * 110} EUR")
    return data


def identify_place_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    api_key = os.getenv("GOOGLE_API_KEY") or GOOGLE_API_KEY
    if not api_key:
        raise ValueError("GOOGLE_API_KEY eksik — .env dosyasına GOOGLE_API_KEY=... ekleyin")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    logger.info(f"Lens: {mime_type}, {len(image_bytes)} bytes")

    prompt = """You are a travel expert. Analyze this image and identify the place/landmark.
Return ONLY a JSON object with these exact keys:
{
  "ad": "Exact place name (keep original language, e.g. Pantheon, Eiffel Tower, Galata Kulesi)",
  "aciklama": "2-3 sentences about this place history and significance, written in Turkish",
  "puan": 4.5,
  "kategori": "Turkish category: Müze / Tarihi Yer / Park / Restoran / Camii / Kilise / Plaj / Kafe / Alışveriş",
  "fiyat_seviyesi": "Düşük or Orta or Yüksek",
  "tahmini_sure": "1-2 saat",
  "resim_arama_kelimesi": "English search query for this specific place",
  "koordinat": {"lat": 41.0082, "lng": 28.9784}
}
puan MUST be a decimal number (e.g. 4.5). koordinat MUST be real GPS coordinates of the identified place."""

    import google.ai.generativelanguage as glm
    image_part = glm.Part(inline_data=glm.Blob(mime_type=mime_type, data=image_bytes))

    response = model.generate_content(
        [prompt, image_part],
        generation_config={"response_mime_type": "application/json"},
    )

    text = response.text.strip()
    logger.info(f"Lens AI response: {text[:400]}")

    return json.loads(text)
