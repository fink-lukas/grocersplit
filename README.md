# GrocerSplit v2

A self-hosted, AI-powered receipt splitting tool for roommates.

## Features
- **AI Parsing**: Upload an image or PDF, and Gemini 1.5 Flash extracts items, prices, and quantities.
- **Persistent Sessions**: Log in once and stay logged in.
- **Item Claiming**: Multiple people can claim an item to split the cost.
- **Quantity Splitting**: Split "3x Milk" into individual items for separate claiming.
- **Rounding Logic**: Automatic handling of remainder cents.
- **Archive**: Hide completed receipts from your dashboard.
- **Mobile First**: Clean, responsive UI optimized for phone cameras.

## Prerequisites
- Docker and Docker Compose
- Gemini API Key

## Setup
1. **Environment Variables**:
   Copy `.env.example` to `.env` and fill in your values (especially `GEMINI_API_KEY`).
   ```bash
   cp .env.example .env
   ```
2. **Launch**:
   ```bash
   docker-compose up --build -d
   ```
3. **Access**:
   - Web App: `http://localhost:5173` (or your server IP)
   - API Docs: `http://localhost:8000/docs`

## Tech Stack
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL
- **Frontend**: React + Vite + Tailwind CSS
- **AI**: Google Gemini API
