# PokeJarvis UI

Browser UI for **Project_PokeJarvis**: a FastAPI adapter imports the engine from `POKEJARVIS_ROOT` (no subprocess CLI).

## Prerequisites

- Python 3.8+ for the API
- Node.js for the web app and for the Smogon calc bridge inside Project_PokeJarvis

## One-time: engine checkout

In **Project_PokeJarvis**:

```bash
pip install -r requirements.txt
npm install
```

Without `npm install` there, **Analyze** (damage matrix) returns an error about the calc bridge.

## Run the API

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set POKEJARVIS_ROOT to the absolute path of Project_PokeJarvis
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

You can export `POKEJARVIS_ROOT` instead of using `.env`.

## Run the web app

```bash
cd web
npm install
cp .env.example .env   # optional; defaults to http://127.0.0.1:8000
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`). Ensure `CORS_ORIGINS` on the API includes that origin (see `api/.env.example`).
