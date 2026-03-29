# GrocerSplit v2

A self-hosted, highly-concurrent, AI-powered receipt splitting tool for roommates.

## Features
- **AI Parsing via Gemini 2.5 Flash**: Upload an image or PDF, and AI extracts items, prices, and quantities automatically.
- **API Key Cycling**: Supports multiple Gemini API keys in the `.env` file (separated by commas) to bypass rate limits automatically.
- **Home Assistant Webhook Integration**: Instantly sends push notifications to users when new receipts are uploaded or items are assigned. 
- **Non-Blocking Architecture**: Backend processes massive AI requests in isolated thread-pools without freezing the rest of the application.
- **Persistent Sessions**: Log in once and stay reliably authenticated using secure token refreshments.
- **Granular Splitting**: Multiple people can claim a single item, or automatically split bulk orders (e.g. "3x Milk").
- **Mobile First**: Clean, responsive React UI optimized identically for phone cameras and desktop.

## Prerequisites
- Docker and Docker Compose
- Google Gemini API Key(s) (Available free at Google AI Studio)

## Setup
1. **Environment Variables**:
   Copy `.env.example` to `.env`. This project uses strict schema validation (`pydantic-settings`); your application will securely fail to boot if mandatory fields are missing.
   ```bash
   cp .env.example .env
   ```
   **Important Fields Check**:
   - `GEMINI_API_KEY`: Can be a single key, or multiple keys separated by commas (e.g. `key1,key2`).
   - `HA_BASE_URL` & `HA_WEBHOOK_ID`: Required if integrating with Home Assistant.
   - `DATABASE_URL`: Required for the PostgreSQL backend.

2. **Launch**:
   ```bash
   docker-compose up --build -d
   ```
3. **Access**:
   - Web App: `http://localhost:5173` (or your local tailscale/device IP!)
   - API Docs: `http://localhost:8000/docs`

## Tech Stack
- **Backend Architecture**: FastAPI (Python), utilizing Service Layers (`/services`), `BackgroundTasks`, and Asyncio/Threadpool integration.
- **Database**: PostgreSQL (via SQLModel & Alembic)
- **Frontend**: React + Vite + Tailwind CSS + Lucide Icons
- **AI Processing**: Google `generativeai` package & Pillow

## Updating
To update the application with the latest repository changes:
1. Pull the latest code:
   ```bash
   git pull origin main
   ```
2. Rebuild the backend and frontend explicitly to capture requirement changes:
   ```bash
   docker compose build
   docker compose up -d
   ```
