# Shunya Scout

Automated daily pipeline that retrieves FIFA World Cup fixtures, scrapes tactical and betting data, and generates match reports.

## Architecture

```
Scheduler (Perplexity) → Scout (Perplexity) → Analyst (Gemini) → Report
```

Built with **LangGraph** (state machine) and **FastAPI** (API), deployed on **Railway** with a daily cron job. Optional **Vite + React** frontend for viewing reports.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in PERPLEXITY_API_KEY, GEMINI_API_KEY, and RESEND_API_KEY
```

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

Reports are saved as one PDF per match at `data/reports/{date}/{team-a}-vs-{team-b}.pdf`.

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

**Railway:** `railway.toml` runs `scripts/daily_job.py` daily. Cron uses UTC — adjust the schedule in `railway.toml` if you need to account for daylight saving (9 AM EDT = `0 13 * * *`, 9 AM EST = `0 14 * * *`).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/run` | Trigger pipeline (optional `{"date": "2026-06-11"}`) |
| GET | `/reports` | List available report dates |
| GET | `/reports/{date}` | List PDF downloads for a date |
| GET | `/reports/today/latest` | List today's PDF downloads |
| GET | `/reports/{date}/{slug}.pdf` | Download match PDF |

## Frontend (optional)

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:8000`. Set `VITE_API_URL` in `.env` for production builds.

## Deployment

**Railway:** Push the repo and set `PERPLEXITY_API_KEY`, `GEMINI_API_KEY`, and `RESEND_API_KEY`. The cron job runs `scripts/daily_job.py` daily via `railway.toml`.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `PERPLEXITY_API_KEY` | Perplexity API key (sonar-pro model) |
| `GEMINI_API_KEY` | Google Gemini API key |
| `RESEND_API_KEY` | Resend API key — replace `re_xxxxxxxxx` with your real key |
| `EMAIL_FROM` | Sender address (use a verified Resend domain in production) |
| `EMAIL_TO` | Recipient email for daily reports |
