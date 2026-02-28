# PI3 Trading Site Setup Guide

This guide documents the current setup for PI3 Trading Site, including local
development, Python backend setup with `uv`, Neon Postgres, Vercel deployment,
and GitHub integration.

## Prerequisites

### Accounts

- GitHub (repo hosting)
- Vercel (deployment + environment variables)
- Neon (Postgres via Vercel Storage integration)

### Local tooling

- Node.js 20+
- npm
- Python 3.11+
- `uv`
- Git

Quick checks:

```powershell
node -v
npm -v
python --version
uv --version
git --version
```

## Project Layout

- `app/` Next.js App Router pages and API routes
- `components/` UI components
- `lib/` server-side data loading logic (`/api/results` source logic)
- `backend/` Python ingestion/preprocess/backtest pipeline
- `guides/` documentation

## Local Frontend Setup

From repo root:

```powershell
npm install
npm run dev
```

Open:

- http://localhost:3000

Core scripts:

- `npm run dev` - local dev server
- `npm run build` - production build
- `npm run start` - run production build
- `npm run lint` - lint (if configured)

## Backend Setup With uv

From repo root:

```powershell
cd backend
uv venv .venv --python 3.14
```

Activate (optional if you use `uv run`):

```powershell
.\.venv\Scripts\Activate.ps1
```

Install backend dependencies:

```powershell
uv pip install -e .
```

### If recreating backend dependencies from scratch

If you ever rebuild `pyproject.toml`, typical `uv` flow is:

```powershell
uv init
uv add click numpy pandas pyarrow pydantic pyyaml yfinance "psycopg[binary]"
```

## Backend Pipeline Commands

From `backend/`:

```powershell
# Pull market data (S&P-style universe)
uv run python -m app.ingest_cli --env prod --lookback-days 365 --max-symbols 40

# Batch preprocess + backtests across ingested symbols
uv run powershell -ExecutionPolicy Bypass -File .\scripts\run_universe_backtests.ps1 -EnvName prod -Interval 1d -MaxSymbols 40
```

These commands:

- persist Bronze/Silver/Gold files under `backend/data/`
- persist metrics into Postgres table `backtest_metrics`

## Neon Postgres Setup

1. In Vercel, open your project.
2. Go to `Storage`.
3. Add a Neon Postgres database.
4. Connect it to project `pi3-trading-site`.
5. Use prefix `POSTGRES` (recommended).

After connect, Vercel creates env vars like:

- `POSTGRES_URL`
- `POSTGRES_PRISMA_URL`
- `POSTGRES_URL_NON_POOLING`
- `POSTGRES_DATABASE_URL`
- `POSTGRES_HOST`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, etc.

## Environment Variables

### In Vercel

Check variables:

```powershell
vercel env ls
```

Pull production env vars locally (repo root):

```powershell
vercel env pull .env.production.local --environment=production
```

### For backend local runs

The backend writes to DB via `PI3_DATABASE_URL`. Set it from pulled env vars:

```powershell
cd backend
$line = (Get-Content ..\.env.production.local | Where-Object { $_ -match '^POSTGRES_URL=' } | Select-Object -First 1)
$env:PI3_DATABASE_URL = ($line -replace '^POSTGRES_URL=', '').Trim('"')
```

## Vercel Project Setup

Project root should be repository root (leave Root Directory empty in dashboard).

Build settings:

- Framework Preset: `Next.js`
- Root Directory: empty
- Output Directory: empty/default (do not set `public`)

Deploy:

```powershell
vercel --prod
```

## GitHub Integration

1. Push this repo to GitHub.
2. In Vercel project settings, connect the GitHub repository.
3. Enable automatic deployments for pushes to `main`.

Typical flow:

- Push to GitHub -> Vercel builds and deploys automatically.

## How Results Page Gets Data

`/results` reads from:

1. Postgres (`backtest_metrics`) when `POSTGRES_URL` is available.
2. Filesystem fallback (`backend/data/gold/signals`) if DB not available.

If no live data exists yet, it shows demo fallback output.
