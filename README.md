# 🌍 GezginAI - Generative Travel API

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-High%20Performance-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-8E75B2?style=for-the-badge&logo=google&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**Next-generation travel planning engine powered by Generative AI.**
*Creates personalized, context-aware itineraries in milliseconds.*

[Report Bug](https://github.com/codeakdo/GezginAI-Backend/issues) · [Request Feature](https://github.com/codeakdo/GezginAI-Backend/issues)

</div>

---

## 🚀 Overview

**GezginAI** is a robust backend service designed to transform abstract travel preferences into concrete, day-by-day itineraries. Built with **FastAPI** and integrated with **Google Gemini Pro**, it serves as an intelligent layer for any travel application, website, or service.

### Core Capabilities
* 🧠 **AI-Powered Logic:** Uses Large Language Models (LLMs) to understand nuanced user requests.
* ⚡ **High Concurrency:** Asynchronous architecture ensures low latency even under load.
* 🌐 **Global Coverage:** Generates plans for any city or region worldwide.
* 🔌 **Easy Integration:** Clean RESTful API endpoints for seamless frontend connection.

---

## 🛠 Tech Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Language** | Python 3.10+ | Core logic and scripting. |
| **Framework** | FastAPI | Modern, high-performance web framework. |
| **AI Engine** | Google Gemini Pro | Generative model for itinerary creation. |
| **Server** | Uvicorn | Lightning-fast ASGI server. |

---

## ⚡ Installation & Setup

### 1. Clone the Repository
```bash
git clone [https://github.com/codeakdo/GezginAI-Backend.git](https://github.com/codeakdo/GezginAI-Backend.git)
cd GezginAI-Backend
```

### 2. Environment Setup
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configuration 
Create a .env file in the root directory to store your credentials securely:
```bash 
GEMINI_API_KEY=your_google_api_key_here
GOOGLE_SEARCH_CX=your_google_photos_search_api_key_here(optional)
```

### 4. Launch Server
```bash
uvicorn main:app --reload
```

## 📡 API Endpoints

### 🟢 Status Check
**`GET /`**
Checks if the API is running and responsive.

```json
{
  "status": "online",
  "service": "GezginAI Backend",
  "version": "1.0.0"
}
```

### 🗺️ Generate Travel Plan
**`POST /plan`**
Generates a detailed, day-by-day travel itinerary based on user preferences using Google Gemini AI.

**Request Body:**
```json
{
  "city": "Tokyo",
  "days": 3,
  "weather": "sunny",
  "budget": "High",
  "interests": "Anime, Sushi, Temples"
}
```
Response Example:

```
{
  "destination": "Tokyo",
  "itinerary": [
    {
      "day": 1,
      "morning": "Visit Senso-ji Temple to experience traditional culture...",
      "lunch": "Enjoy premium Omakase Sushi at Tsukiji Outer Market...",
      "weather": "2°C degree",
      "clothing": "Mostly snowy wear gloves and warm clothes, Don't forget to bring a hat to protect your ears from the cold ",
      "burget": "Average a Student Budget around 40 Euro per day",
      "evening": "Explore Akihabara for anime shops and gaming centers..."
    }
  ]
}
```



