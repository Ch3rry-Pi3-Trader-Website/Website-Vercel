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
  run_at: string;
};

export type RankedSymbol = {
  symbol: string;
  strategy: string;
  score: number;
  cagr: number;
  sharpe: number;
  maxDrawdown: number;
  buyHoldReturn: number;
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

async function loadRowsFromPostgres(): Promise<MetricRow[]> {
  const dbUrl = process.env.POSTGRES_URL || process.env.DATABASE_URL || "";
  if (!dbUrl) {
    return [];
  }

  try {
    const db = neon(dbUrl);
    const rows = (await db`
      SELECT DISTINCT ON (symbol, strategy)
        strategy, symbol, interval, params, bars, cagr, sharpe, max_drawdown, buy_hold_return, run_at
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
      buyHoldReturn: 0.08,
    },
    {
      symbol: "MSFT",
      strategy: "momentum",
      score: 0.73,
      cagr: 0.18,
      sharpe: 0.94,
      maxDrawdown: -0.14,
      buyHoldReturn: 0.16,
    },
    {
      symbol: "AAPL",
      strategy: "mean_reversion",
      score: 0.64,
      cagr: 0.15,
      sharpe: 0.87,
      maxDrawdown: -0.16,
      buyHoldReturn: 0.12,
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
      buyHoldReturn: row.buy_hold_return ?? 0,
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
