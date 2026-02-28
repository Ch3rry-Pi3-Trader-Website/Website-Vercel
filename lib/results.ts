import { promises as fs } from "fs";
import path from "path";
import { neon } from "@neondatabase/serverless";

type MetricRow = {
  strategy: string;
  symbol: string;
  interval: string;
  params?: Record<string, number>;
  bars: number;
  cagr: number;
  sharpe: number;
  max_drawdown: number;
  buy_hold_return?: number;
  buy_hold_cagr?: number;
  log_sharpe?: number;
  log_sortino?: number;
  log_vol_ann?: number;
  _timestamp?: number;
  _score?: number;
};

type DbMetricRow = {
  strategy: string;
  symbol: string;
  interval: string;
  params: unknown;
  bars: number;
  cagr: number;
  sharpe: number;
  max_drawdown: number;
  buy_hold_return: number;
  buy_hold_cagr: number;
  log_sharpe: number;
  log_sortino: number;
  log_vol_ann: number;
  run_at: string;
};

export type RankedSymbol = {
  symbol: string;
  strategy: string;
  score: number;
  cagr: number;
  sharpe: number;
  maxDrawdown: number;
  buyHoldCagr: number;
  logSharpe: number;
  logVolAnn: number;
};

export type ResultsPayload = {
  generatedAt: string;
  budget: number;
  holdings: string;
  ranking: RankedSymbol[];
  recommended: Array<{ symbol: string; weight: number; amount: number }>;
  notes: string[];
};

function parseTimestampFromName(fileName: string): number {
  const match = fileName.match(/metrics-(\d{8}T\d{6}\d{6})Z\.json$/);
  if (!match) return 0;
  const stamp = match[1];
  const yyyy = Number(stamp.slice(0, 4));
  const mm = Number(stamp.slice(4, 6)) - 1;
  const dd = Number(stamp.slice(6, 8));
  const hh = Number(stamp.slice(9, 11));
  const mi = Number(stamp.slice(11, 13));
  const ss = Number(stamp.slice(13, 15));
  const ms = Number(stamp.slice(15, 18));
  return Date.UTC(yyyy, mm, dd, hh, mi, ss, ms);
}

async function walk(dir: string): Promise<string[]> {
  let files: string[] = [];
  let entries: Array<{ name: string; path: string; isDirectory: boolean }> = [];
  try {
    const read = await fs.readdir(dir, { withFileTypes: true });
    entries = read.map((d) => ({
      name: d.name,
      path: path.join(dir, d.name),
      isDirectory: d.isDirectory(),
    }));
  } catch {
    return files;
  }

  await Promise.all(
    entries.map(async (entry) => {
      if (entry.isDirectory) {
        files = files.concat(await walk(entry.path));
      } else {
        files.push(entry.path);
      }
    }),
  );

  return files;
}

function scoreRow(row: MetricRow): number {
  return 0.6 * row.sharpe + 0.3 * row.cagr + 0.1 * (-row.max_drawdown);
}

function parseHoldings(raw: string): Array<{ symbol: string; shares: number }> {
  return raw
    .split(",")
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((piece) => {
      const [sym, qty] = piece.split(":");
      return {
        symbol: (sym || "").trim().toUpperCase(),
        shares: Number((qty || "0").trim()),
      };
    })
    .filter((x) => x.symbol && Number.isFinite(x.shares) && x.shares > 0);
}

function parseParams(input: unknown): Record<string, number> {
  if (!input || typeof input !== "object" || Array.isArray(input)) return {};
  const out: Record<string, number> = {};
  for (const [k, v] of Object.entries(input)) {
    if (typeof v === "number" && Number.isFinite(v)) out[k] = v;
  }
  return out;
}

function intervalToMinutes(interval: string): number {
  const val = String(interval || "").trim().toLowerCase();
  const mapping: Record<string, number> = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "60m": 60,
    "1h": 60,
    "1d": 1440,
    "1wk": 10080,
  };
  if (mapping[val]) return mapping[val];
  if (val.endsWith("m") && !Number.isNaN(Number(val.slice(0, -1)))) return Number(val.slice(0, -1));
  if (val.endsWith("h") && !Number.isNaN(Number(val.slice(0, -1)))) return Number(val.slice(0, -1)) * 60;
  if (val.endsWith("d") && !Number.isNaN(Number(val.slice(0, -1)))) return Number(val.slice(0, -1)) * 1440;
  return 1440;
}

function annualizeFromTotalReturn(totalReturn: number, bars: number, interval: string): number {
  if (!Number.isFinite(totalReturn) || !Number.isFinite(bars) || bars <= 0) return 0;
  const intervalMin = intervalToMinutes(interval);
  const barsPerYear = (365 * 24 * 60) / intervalMin;
  const years = bars / barsPerYear;
  if (years <= 0) return 0;
  const start = 1.0;
  const end = 1.0 + totalReturn;
  if (end <= 0) return 0;
  return Math.pow(end / start, 1 / years) - 1.0;
}

async function loadRowsFromPostgres(): Promise<MetricRow[]> {
  const dbUrl = process.env.POSTGRES_URL || process.env.DATABASE_URL || "";
  if (!dbUrl) {
    return [];
  }

  try {
    const db = neon(dbUrl);
    const rows = (await db`
      SELECT DISTINCT ON (symbol, strategy)
        strategy,
        symbol,
        interval,
        params,
        bars,
        cagr,
        sharpe,
        max_drawdown,
        COALESCE((to_jsonb(backtest_metrics)->>'buy_hold_return')::double precision, 0) AS buy_hold_return,
        COALESCE((to_jsonb(backtest_metrics)->>'buy_hold_cagr')::double precision, 0) AS buy_hold_cagr,
        COALESCE((to_jsonb(backtest_metrics)->>'log_sharpe')::double precision, 0) AS log_sharpe,
        COALESCE((to_jsonb(backtest_metrics)->>'log_sortino')::double precision, 0) AS log_sortino,
        COALESCE((to_jsonb(backtest_metrics)->>'log_vol_ann')::double precision, 0) AS log_vol_ann,
        run_at
      FROM backtest_metrics
      ORDER BY symbol, strategy, run_at DESC, id DESC
    `) as DbMetricRow[];

    return rows.map((row) => ({
      strategy: row.strategy,
      symbol: row.symbol,
      interval: row.interval,
      params: parseParams(row.params),
      bars: Number(row.bars),
      cagr: Number(row.cagr),
      sharpe: Number(row.sharpe),
      max_drawdown: Number(row.max_drawdown),
      buy_hold_return: Number(row.buy_hold_return),
      buy_hold_cagr: Number(row.buy_hold_cagr),
      log_sharpe: Number(row.log_sharpe),
      log_sortino: Number(row.log_sortino),
      log_vol_ann: Number(row.log_vol_ann),
      _timestamp: new Date(row.run_at).getTime(),
    }));
  } catch {
    return [];
  }
}

async function loadRowsFromFilesystem(): Promise<MetricRow[]> {
  const signalsRoot = path.resolve(process.cwd(), "backend", "data", "gold", "signals");
  const files = (await walk(signalsRoot)).filter((f) => f.endsWith(".json") && f.includes("metrics-"));

  const rows: MetricRow[] = [];
  for (const file of files) {
    try {
      const txt = await fs.readFile(file, "utf8");
      const parsed = JSON.parse(txt) as MetricRow;
      const name = path.basename(file);
      const ts = parseTimestampFromName(name);
      rows.push({
        ...parsed,
        _timestamp: ts,
      });
    } catch {
      continue;
    }
  }
  return rows;
}

function buildFallbackPayload(budget: number, holdingsRaw: string): ResultsPayload {
  const fallbackRanking: RankedSymbol[] = [
    {
      symbol: "SPY",
      strategy: "momentum",
      score: 0.81,
      cagr: 0.13,
      sharpe: 1.18,
      maxDrawdown: -0.09,
      buyHoldCagr: 0.08,
      logSharpe: 1.1,
      logVolAnn: 0.19,
    },
    {
      symbol: "MSFT",
      strategy: "momentum",
      score: 0.73,
      cagr: 0.18,
      sharpe: 0.94,
      maxDrawdown: -0.14,
      buyHoldCagr: 0.16,
      logSharpe: 0.92,
      logVolAnn: 0.24,
    },
    {
      symbol: "AAPL",
      strategy: "mean_reversion",
      score: 0.64,
      cagr: 0.15,
      sharpe: 0.87,
      maxDrawdown: -0.16,
      buyHoldCagr: 0.12,
      logSharpe: 0.81,
      logVolAnn: 0.27,
    },
  ];
  const total = fallbackRanking.reduce((acc, row) => acc + row.score, 0);
  const recommended = fallbackRanking.map((row) => ({
    symbol: row.symbol,
    weight: row.score / total,
    amount: Math.round((row.score / total) * budget * 100) / 100,
  }));
  return {
    generatedAt: new Date().toISOString(),
    budget,
    holdings: holdingsRaw,
    ranking: fallbackRanking,
    recommended,
    notes: [
      "No persisted metrics found yet, showing demo output.",
      "Run backend ingest/preprocess/backtest to populate live results.",
    ],
  };
}

function rowsToPayload(
  rows: MetricRow[],
  budget: number,
  holdingsRaw: string,
  sourceLabel: string,
): ResultsPayload {
  const latestBySymbolStrategy = new Map<string, MetricRow>();
  for (const row of rows) {
    const key = `${row.symbol}|${row.strategy}`;
    const current = latestBySymbolStrategy.get(key);
    if (!current || (row._timestamp || 0) > (current._timestamp || 0)) {
      latestBySymbolStrategy.set(key, row);
    }
  }

  const bestBySymbol = new Map<string, MetricRow>();
  for (const row of latestBySymbolStrategy.values()) {
    row._score = scoreRow(row);
    const existing = bestBySymbol.get(row.symbol);
    if (!existing || (row._score || -Infinity) > (existing._score || -Infinity)) {
      bestBySymbol.set(row.symbol, row);
    }
  }

  const ranking: RankedSymbol[] = [...bestBySymbol.values()]
    .sort((a, b) => (b._score || 0) - (a._score || 0))
    .slice(0, 8)
    .map((row) => ({
      symbol: row.symbol,
      strategy: row.strategy,
      score: row._score || 0,
      cagr: row.cagr,
      sharpe: row.sharpe,
      maxDrawdown: row.max_drawdown,
      buyHoldCagr:
        row.buy_hold_cagr ??
        annualizeFromTotalReturn(row.buy_hold_return ?? 0, row.bars, row.interval),
      logSharpe: row.log_sharpe ?? 0,
      logVolAnn: row.log_vol_ann ?? 0,
    }));

  const positives = ranking.filter((r) => r.score > 0);
  const universe = positives.length > 0 ? positives : ranking.slice(0, 3);
  const totalScore = universe.reduce((acc, row) => acc + Math.max(row.score, 0.001), 0);
  const recommended = universe.map((row) => {
    const weight = Math.max(row.score, 0.001) / totalScore;
    return {
      symbol: row.symbol,
      weight,
      amount: Math.round(weight * budget * 100) / 100,
    };
  });

  const holdings = parseHoldings(holdingsRaw);
  const heldSymbols = new Set(holdings.map((h) => h.symbol));
  const notes = [
    `Source: ${sourceLabel}.`,
    `Based on ${rows.length} persisted backtest snapshots.`,
    holdings.length === 0
      ? "No holdings provided: recommendation assumes a fresh portfolio."
      : "Holdings provided: use allocations to guide buy/sell rebalancing.",
  ];

  const missingFromPlan = holdings
    .filter((h) => !recommended.some((r) => r.symbol === h.symbol))
    .map((h) => h.symbol);
  if (missingFromPlan.length > 0) {
    notes.push(`Existing holdings outside top-ranked set: ${missingFromPlan.join(", ")}.`);
  }
  const newIdeas = recommended.filter((r) => !heldSymbols.has(r.symbol)).map((r) => r.symbol);
  if (newIdeas.length > 0) {
    notes.push(`Potential additions from model ranking: ${newIdeas.join(", ")}.`);
  }

  return {
    generatedAt: new Date().toISOString(),
    budget,
    holdings: holdingsRaw,
    ranking,
    recommended,
    notes,
  };
}

export async function buildResultsPayload(
  budget: number,
  holdingsRaw: string,
): Promise<ResultsPayload> {
  const pgRows = await loadRowsFromPostgres();
  if (pgRows.length > 0) {
    return rowsToPayload(pgRows, budget, holdingsRaw, "postgres");
  }

  const fsRows = await loadRowsFromFilesystem();
  if (fsRows.length > 0) {
    return rowsToPayload(fsRows, budget, holdingsRaw, "filesystem");
  }

  return buildFallbackPayload(budget, holdingsRaw);
}
