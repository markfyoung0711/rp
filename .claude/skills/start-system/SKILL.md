---
name: start-system
description: Start the BidEdge API + UI (single uvicorn process serves both) and optional local logging stack. Triggered by phrases like "start system", "start API", "start UI", "start the app", "run the system", "serve locally", "start local server".
allowed-tools: Bash, Read
---

# Start System

Start the BidEdge API (which also serves the UI static files at `/`) locally. Optionally start the Loki + Grafana logging stack via docker compose.

## Before running

Ask which parts to start if the user's request is ambiguous:

- **API + UI only** (default) — one uvicorn process on port 8000. The UI is served at `http://localhost:8000/` and the API under `http://localhost:8000/api/*`.
- **API + UI + logging** — also starts Loki + Grafana via `docker compose up -d` (services: loki, grafana, loki-data). Grafana at `http://localhost:3000`, Loki at `http://localhost:3100`.
- **Logging only** — just docker compose.

Check first: is something already bound to port 8000? Run `ss -tlnp 2>/dev/null | grep :8000 || lsof -iTCP:8000 -sTCP:LISTEN 2>/dev/null`. If yes, stop and ask the user whether to kill the running process or pick a different port.

## Start the API + UI

Run in the background (it's long-lived):

```
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

If the user wants logs shipped to local Loki, prefix with the env var (set LOKI_URL if Loki is running):

```
LOKI_URL=http://localhost:3100 uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

After starting, wait ~3 seconds then probe the health endpoint:

```
curl -sf http://localhost:8000/api/health
```

If the probe fails after 10 seconds of retries, tail the uvicorn output and stop — don't claim the system is up.

## Start logging (optional)

From the repo root:

```
docker compose up -d loki grafana
```

Verify:
```
docker compose ps
curl -sf http://localhost:3100/ready && echo LOKI_OK
curl -sf http://localhost:3000/api/health && echo GRAFANA_OK
```

## After starting

Report:
- API + UI URL: `http://localhost:8000/`
- API docs (FastAPI auto): `http://localhost:8000/docs`
- Health endpoint: `http://localhost:8000/api/health`
- Grafana (if started): `http://localhost:3000`
- Process IDs / container names for stopping later

## Stopping

- **API + UI:** kill the uvicorn process by PID. `--reload` launches a supervisor + worker, so kill the supervisor (parent). `pkill -f 'uvicorn src.api.main:app'` works as a fallback.
- **Logging:** `docker compose down` (keeps volumes) or `docker compose down -v` (drops data).

## Notes

- The API serves the UI via `app.mount("/", StaticFiles(directory="src/web/static", html=True))`. One process, not two.
- `--reload` is development-only; omit for production or load testing.
- No frontend build step — the UI is plain HTML/JS in `src/web/static/index.html`.
- If the user explicitly says "production" or "deploy," this skill is not the right tool — point them at `deploy/deploy-api.sh` and `deploy/cloudbuild.api.yaml`.
