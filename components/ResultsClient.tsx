"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type RankedSymbol = {
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

type Allocation = {
  symbol: string;
  weight: number;
  amount: number;
};

type ResultsPayload = {
  generatedAt: string;
  budget: number;
  holdings: string;
  ranking: RankedSymbol[];
  recommended: Allocation[];
  notes: string[];
};

function fmtPct(v: number): string {
  return `${(v * 100).toFixed(2)}%`;
}

export default function ResultsClient() {
  const [budgetInput, setBudgetInput] = useState("10000");
  const [holdingsInput, setHoldingsInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ResultsPayload | null>(null);

  async function load(budgetValue: string, holdingsValue: string) {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams({
        budget: budgetValue,
        holdings: holdingsValue,
      });
      const res = await fetch(`/api/results?${qs.toString()}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`Request failed with ${res.status}`);
      const payload = (await res.json()) as ResultsPayload;
      setData(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load results.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(budgetInput, holdingsInput);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    void load(budgetInput, holdingsInput);
  }

  const allocatedTotal = useMemo(
    () => (data ? data.recommended.reduce((acc, row) => acc + row.amount, 0) : 0),
    [data],
  );

  return (
    <div className="results-stack">
      <section className="control-panel reveal" style={{ ["--delay" as string]: "0ms" }}>
        <form onSubmit={onSubmit} className="control-form">
          <label>
            Budget (USD)
            <input
              inputMode="decimal"
              value={budgetInput}
              onChange={(e) => setBudgetInput(e.target.value)}
              placeholder="10000"
            />
          </label>
          <label>
            Current holdings
            <input
              value={holdingsInput}
              onChange={(e) => setHoldingsInput(e.target.value)}
              placeholder="AAPL:20,MSFT:10"
            />
          </label>
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? "Refreshing..." : "Update Plan"}
          </button>
        </form>
      </section>

      {error ? <p className="status-error">{error}</p> : null}

      <section className="panel reveal" style={{ ["--delay" as string]: "80ms" }}>
        <div className="panel-head">
          <h2>Recommended Allocation</h2>
          <p>{data ? `Generated ${new Date(data.generatedAt).toLocaleString()}` : "Loading..."}</p>
        </div>
        <div className="allocation-grid">
          {data?.recommended.map((row) => (
            <article key={row.symbol} className="allocation-card">
              <p className="ticker">{row.symbol}</p>
              <p className="weight">{fmtPct(row.weight)}</p>
              <p className="amount">${row.amount.toLocaleString()}</p>
            </article>
          ))}
        </div>
        <p className="allocation-total">Allocated total: ${allocatedTotal.toLocaleString()}</p>
      </section>

      <section className="panel reveal" style={{ ["--delay" as string]: "150ms" }}>
        <div className="panel-head">
          <h2>Symbol Ranking</h2>
          <p>Best strategy per symbol from persisted backtests</p>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Strategy</th>
                <th>Score</th>
                <th>CAGR</th>
                <th>Sharpe</th>
                <th>MaxDD</th>
                <th>Buy/Hold (Ann.)</th>
                <th>Log Sharpe</th>
                <th>Log Vol (Ann.)</th>
              </tr>
            </thead>
            <tbody>
              {data?.ranking.map((row) => (
                <tr key={`${row.symbol}-${row.strategy}`}>
                  <td>{row.symbol}</td>
                  <td>{row.strategy}</td>
                  <td>{row.score.toFixed(3)}</td>
                  <td>{fmtPct(row.cagr)}</td>
                  <td>{row.sharpe.toFixed(2)}</td>
                  <td>{fmtPct(row.maxDrawdown)}</td>
                  <td>{fmtPct(row.buyHoldCagr)}</td>
                  <td>{row.logSharpe.toFixed(2)}</td>
                  <td>{fmtPct(row.logVolAnn)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel reveal" style={{ ["--delay" as string]: "220ms" }}>
        <div className="panel-head">
          <h2>Notes</h2>
        </div>
        <ul className="notes">
          {data?.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
