Escobar-v3

Overview
- FastAPI backend computes Return-to-Mean (RTM) metrics for OANDA instruments and exposes endpoints consumed by a small React frontend (built assets are in `frontend/dist`).

Backend
- Path: `backend/app.py`
- Endpoints:
  - `GET /` health check
  - `GET /api/rtm/currencies|indices|commodities` (symbols from `backend/symbol.json`)
  - `GET /api/positions` (enriches OANDA open positions with RTM)
- Env vars:
  - `OANDA_LIVE_API_KEY`: OANDA API token
  - `OANDA_LIVE_ACCOUNT_ID_3`: OANDA account ID
  - `ALLOWED_ORIGINS`: Comma-separated origins for CORS (e.g. `https://your-frontend.example.com,https://other.example.com`). Defaults to `http://localhost:5173,http://localhost:3000` for local dev.

Security
- Do not commit secrets. `backend/.env` is gitignored. Provide env vars via your runtime (Cloud Run, Docker, or shell).
- CORS is locked down. Set `ALLOWED_ORIGINS` to your deployed frontend origin(s).

Local Run
- Python: `uvicorn backend.app:app --reload --port 8080`
- Docker (from `backend/`):
  - `docker build -t rtm-api .`
  - `docker run -p 8080:8080 -e OANDA_LIVE_API_KEY=... -e OANDA_LIVE_ACCOUNT_ID_3=... -e ALLOWED_ORIGINS=http://localhost:5173 rtm-api`

Deploy
- Cloud Run (example):
  - `gcloud run deploy rtm-monitor-api --source backend --region us-central1 --allow-unauthenticated \
     --set-env-vars OANDA_LIVE_API_KEY=__SET__ --set-env-vars OANDA_LIVE_ACCOUNT_ID_3=__SET__ \
     --set-env-vars ALLOWED_ORIGINS=https://your-frontend.example.com`
  - Prefer using a secret manager for credentials.

Frontend
- Built assets in `frontend/dist`. Host statically (e.g., Firebase Hosting). Point to the backend API URL.

Notes
- `main.py` is legacy reference code and not used by the backend service.
