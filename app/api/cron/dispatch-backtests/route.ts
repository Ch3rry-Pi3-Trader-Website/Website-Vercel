import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function requireEnv(name: string): string {
  const value = process.env[name]?.trim() || "";
  if (!value) {
    throw new Error(`missing_env:${name}`);
  }
  return value;
}

function isAuthorized(req: NextRequest): boolean {
  const secret = process.env.CRON_SECRET?.trim() || "";
  if (!secret) return false;
  const header = req.headers.get("authorization") || "";
  return header === `Bearer ${secret}`;
}

export async function GET(req: NextRequest) {
  if (!isAuthorized(req)) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  try {
    const githubToken = requireEnv("GITHUB_TOKEN");
    const githubOwner = requireEnv("GITHUB_OWNER");
    const githubRepo = requireEnv("GITHUB_REPO");
    const workflowFile = process.env.GITHUB_WORKFLOW_FILE?.trim() || "refresh-backtests.yml";
    const workflowRef = process.env.GITHUB_WORKFLOW_REF?.trim() || "main";

    const envName = process.env.CRON_ENV_NAME?.trim() || "prod";
    const lookbackDays = process.env.CRON_LOOKBACK_DAYS?.trim() || "365";
    const maxSymbols = process.env.CRON_MAX_SYMBOLS?.trim() || "40";
    const interval = process.env.CRON_INTERVAL?.trim() || "1d";
    const workers = process.env.CRON_WORKERS?.trim() || "2";
    const includeBreakout = process.env.CRON_INCLUDE_BREAKOUT?.trim() || "false";

    const url = `https://api.github.com/repos/${githubOwner}/${githubRepo}/actions/workflows/${workflowFile}/dispatches`;
    const response = await fetch(url, {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${githubToken}`,
        "Content-Type": "application/json",
        "User-Agent": "pi3-trading-site-cron",
      },
      body: JSON.stringify({
        ref: workflowRef,
        inputs: {
          env_name: envName,
          lookback_days: lookbackDays,
          max_symbols: maxSymbols,
          interval,
          workers,
          include_breakout: includeBreakout,
        },
      }),
      cache: "no-store",
    });

    if (!response.ok) {
      const text = await response.text();
      return NextResponse.json(
        { ok: false, error: "github_dispatch_failed", status: response.status, detail: text.slice(0, 400) },
        { status: 502 },
      );
    }

    return NextResponse.json({
      ok: true,
      dispatched: true,
      workflow: workflowFile,
      ref: workflowRef,
      inputs: {
        env_name: envName,
        lookback_days: lookbackDays,
        max_symbols: maxSymbols,
        interval,
        workers,
        include_breakout: includeBreakout,
      },
      at: new Date().toISOString(),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "unknown_error";
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}
