# Shunya Scout

Automated daily pipeline that retrieves FIFA World Cup fixtures, scrapes tactical and betting data, and generates match reports.

## Architecture

```
Scheduler (Perplexity) → Scout (Perplexity) → Analyst (Gemini) → Report
```

Built with **LangGraph** (state machine) and **FastAPI** (API), deployed on **Railway**. Optional **Vite + React** frontend for viewing reports.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in API keys and Supabase credentials
```

### Supabase setup

1. Create a Supabase project.
2. Run `supabase/schema.sql` in the SQL editor.
3. Create a **public** Storage bucket named `reports`.
4. Enable **Email** auth under Authentication → Providers.
5. Add `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` to `.env` (backend only — never expose in the frontend).

### Authentication

Login and signup are proxied through the FastAPI backend. The React app never talks to Supabase directly — it calls `/auth/*` on the API, stores JWTs in `localStorage`, and sends `Authorization: Bearer` on protected routes.

Create users via the UI or Supabase dashboard. If email confirmation is enabled, new signups must confirm before signing in.

**Public:** `GET /health`, `POST /auth/signup`, `POST /auth/login`, `POST /auth/refresh`

**Protected (Bearer token required):** all `/run/*`, `/reports/*`, `GET /auth/me`, `POST /auth/logout`

The daily cron job (`scripts/daily_job.py`) runs server-side and does not use HTTP auth.

## Backend usage

**Run the pipeline manually:**

```bash
python run_graph.py
```

**Start the API server:**

```bash
uvicorn main:app --reload
```

**Trigger via API:**

```bash
curl -X POST http://localhost:8000/run
```

Reports are stored in Supabase (Postgres metadata + Storage PDFs). The UI supports browsing historical dates, generating missing reports for today/future matchdays, and regenerating an entire day.

## Daily email cron (9 AM Eastern)

The daily job generates reports and emails them via [Resend](https://resend.com):

```bash
python scripts/daily_job.py
```

**Local cron (recommended for exact 9 AM Eastern):**

```bash
crontab -e
# Paste the line from scripts/crontab.example (update the project path)
```

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/auth/signup` | Create account |
| POST | `/auth/login` | Sign in |
| POST | `/auth/refresh` | Refresh session |
| GET | `/auth/me` | Current user (auth required) |
| POST | `/auth/logout` | Sign out (auth required) |
| POST | `/run` | Generate or refresh all reports for a date (today/future only) |
| GET | `/reports` | List available report dates |
| GET | `/reports/{date}` | List PDF downloads for a date |
| GET | `/reports/today/latest` | List today's PDF downloads |
| GET | `/reports/{date}/{slug}.pdf` | Download match PDF |

## Frontend

**Development** (Vite dev server with API proxy):

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:8000`.

**Production build** (served by FastAPI on the same origin):

```bash
cd frontend && npm ci && npm run build
# or from repo root:
bash scripts/build.sh
```

Production builds use same-origin API calls automatically. Override with `VITE_API_URL` if needed.

## Deployment (Railway)

Single service: FastAPI serves the API and the built React app from `frontend/dist`.

### 1. Push to GitHub

Railway deploys from your connected repo.

### 2. Create a Railway project

1. [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select `shunya_scout` (or your repo name)

### 3. Set environment variables

In Railway → **Variables**, add everything from `.env.example`:

| Variable | Required |
|----------|----------|
| `PERPLEXITY_API_KEY` | Yes |
| `GEMINI_API_KEY` | Yes |
| `RESEND_API_KEY` | Yes |
| `EMAIL_FROM` | Yes |
| `EMAIL_TO` | Yes |
| `SUPABASE_URL` | Yes |
| `SUPABASE_PUBLISHABLE_KEY` | Yes |
| `SUPABASE_STORAGE_BUCKET` | Yes (`reports`) |

### 4. Build & start

`nixpacks.toml` installs Node, runs `npm ci && npm run build` in `frontend/`, then starts:

```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Run `scripts/daily_job.py` manually or via local cron (see `scripts/crontab.example`).

### 5. Verify

- Open your Railway public URL → login/signup UI loads
- `GET /health` → `{"status":"ok"}`
- Sign in, browse reports, download a PDF

### Local production test

```bash
bash scripts/build.sh
uvicorn main:app --host 0.0.0.0 --port 8000
# open http://localhost:8000
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `PERPLEXITY_API_KEY` | Perplexity API key (sonar-pro model) |
| `GEMINI_API_KEY` | Google Gemini API key |
| `RESEND_API_KEY` | Resend API key — replace `re_xxxxxxxxx` with your real key |
| `EMAIL_FROM` | Sender address (use a verified Resend domain in production) |
| `EMAIL_TO` | Recipient email for daily reports |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_PUBLISHABLE_KEY` | Publishable (anon) key — backend only, not in the React app |
| `SUPABASE_STORAGE_BUCKET` | Storage bucket for PDFs (default: `reports`) |
