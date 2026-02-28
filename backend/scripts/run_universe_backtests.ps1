param(
  [string]$EnvName = "prod",
  [string]$Interval = "1d",
  [int]$MaxSymbols = 0,
  [switch]$IncludeBreakout
)

$ErrorActionPreference = "Stop"

$backendRoot = Split-Path -Parent $PSScriptRoot
Set-Location $backendRoot

$bronzeRoot = Join-Path $backendRoot "data\bronze\ohlcv"
if (-not (Test-Path $bronzeRoot)) {
  throw "Bronze directory not found: $bronzeRoot. Run ingest first."
}

$symbolDirs = Get-ChildItem -Path $bronzeRoot -Directory | Where-Object { $_.Name -like "symbol=*" } | Sort-Object Name
$symbols = $symbolDirs | ForEach-Object { $_.Name.Substring(7) }

if ($MaxSymbols -gt 0) {
  $symbols = $symbols | Select-Object -First $MaxSymbols
}

if (-not $symbols -or $symbols.Count -eq 0) {
  throw "No ingested symbols found under $bronzeRoot."
}

Write-Host "[BATCH] Symbols to process: $($symbols.Count)"
Write-Host "[BATCH] Env=$EnvName Interval=$Interval"

foreach ($sym in $symbols) {
  Write-Host ""
  Write-Host "[BATCH] Processing $sym"

  try {
    python -m app.preprocess_cli --env $EnvName --symbol $sym --interval $Interval
  } catch {
    Write-Warning "[BATCH] Preprocess failed for $sym. Skipping backtests."
    continue
  }

  try {
    python -m app.backtest_cli --env $EnvName --symbol $sym --interval $Interval --strategy momentum
  } catch {
    Write-Warning "[BATCH] Momentum backtest failed for $sym."
  }

  try {
    python -m app.backtest_cli --env $EnvName --symbol $sym --interval $Interval --strategy mean_reversion
  } catch {
    Write-Warning "[BATCH] Mean-reversion backtest failed for $sym."
  }

  if ($IncludeBreakout.IsPresent) {
    try {
      python -m app.backtest_cli --env $EnvName --symbol $sym --interval $Interval --strategy breakout
    } catch {
      Write-Warning "[BATCH] Breakout backtest failed for $sym."
    }
  }
}

Write-Host ""
Write-Host "[BATCH] Completed."
