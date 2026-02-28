# PI3 Trading Site

Single Vercel project root for PI3 Investor.

This root contains:

- Next.js app (UI + `/api/results`)
- Python backend code in `backend/` (data/strategy/CLI)

Frontend routes:

- `/` landing page
- `/results` portfolio output page

Data source priority for `GET /api/results`:

1. Postgres (`backtest_metrics`) when `POSTGRES_URL` is configured.
2. Local filesystem fallback:
   `backend/data/gold/signals/**/metrics-*.json`

If no backtest artefacts exist yet, it shows demo output.

## Run locally (Windows PowerShell)

```powershell
npm install
npm run dev
```

Open `http://localhost:3000`.

## Expected backend flow first

Generate backend artefacts so `/results` reflects real data:

```powershell
cd backend
python -m app.ingest_cli --env dev --max-symbols 50
python -m app.preprocess_cli --env dev --symbol SPY
python -m app.backtest_cli --env dev --symbol SPY --strategy momentum
python -m app.backtest_cli --env dev --symbol SPY --strategy mean_reversion
```

Then return to root and run UI:

```powershell
cd ..
npm run dev
```

## Vercel note (single project)

Project root is this folder: `pi3-trading-site`.

For production data:

1. Add Neon Postgres (Vercel integration) to the project (this sets `POSTGRES_URL`).
2. Point backend writes to the same DB using `PI3_DATABASE_URL`.

## Automation note

Automated refresh is wired as:

1. Vercel Cron calls `/api/cron/dispatch-backtests`.
2. That route dispatches GitHub Actions workflow `refresh-backtests.yml`.
3. GitHub runs Python ingest + backtests and writes metrics to Neon Postgres.

Setup details and required env vars are in [guides/setup.md](guides/setup.md).
