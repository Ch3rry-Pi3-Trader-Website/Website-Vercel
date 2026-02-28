import { NextRequest, NextResponse } from "next/server";
import { buildResultsPayload } from "@/lib/results";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const budgetRaw = url.searchParams.get("budget") ?? "10000";
  const holdings = url.searchParams.get("holdings") ?? "";
  const budget = Number(budgetRaw);
  const safeBudget = Number.isFinite(budget) && budget > 0 ? budget : 10000;

  const payload = await buildResultsPayload(safeBudget, holdings);
  return NextResponse.json(payload);
}
