# One-time local setup for StockPilot against YOUR local PostgreSQL (the server pgAdmin shows).
# Run from the Stockpilot_BE folder:   powershell -ExecutionPolicy Bypass -File scripts\setup_local.ps1
# The password is typed into this terminal only; it is written to .env (git-ignored) and nowhere else.

param(
    [string]$PgHost = "localhost",
    [int]$Port = 5432,          # PostgreSQL 17 in your pgAdmin; use 5433 for PostgreSQL 18
    [string]$PgUser = "postgres",
    [string]$Database = "stockpilot",
    [string]$TestDatabase = "stockpilot_test"
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$psql = (Get-Command psql -ErrorAction SilentlyContinue).Source
if (-not $psql) { $psql = "C:\Program Files\PostgreSQL\17\bin\psql.exe" }

$secure = Read-Host "Password for PostgreSQL user '$PgUser' on ${PgHost}:$Port" -AsSecureString
$plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
$env:PGPASSWORD = $plain

Write-Host "Checking connection..."
& $psql -h $PgHost -p $Port -U $PgUser -d postgres -w -Atc "select 'connected to ' || version()" | Select-Object -First 1

foreach ($db in @($Database, $TestDatabase)) {
    $exists = & $psql -h $PgHost -p $Port -U $PgUser -d postgres -w -Atc "select 1 from pg_database where datname = '$db'"
    if ($exists -eq "1") { Write-Host "Database '$db' already exists." }
    else { & $psql -h $PgHost -p $Port -U $PgUser -d postgres -w -c "CREATE DATABASE $db"; Write-Host "Created database '$db'." }
}

# Update .env (URL-encode the password so characters like @ # % are safe).
$encoded = [uri]::EscapeDataString($plain)
$base = "postgresql+psycopg://${PgUser}:${encoded}@${PgHost}:$Port"
$lines = if (Test-Path .env) { Get-Content .env } else { @() }
$lines = $lines | Where-Object { $_ -notmatch '^(DATABASE_URL|TEST_DATABASE_URL)=' }
$lines += "DATABASE_URL=$base/$Database"
$lines += "TEST_DATABASE_URL=$base/$TestDatabase"
Set-Content -Path .env -Value $lines -Encoding utf8
Remove-Item Env:PGPASSWORD
Write-Host ".env updated."

& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m scripts.seed

Write-Host ""
Write-Host "Done. Start the API with:  .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload"
Write-Host "In pgAdmin: refresh '$Database' -> Schemas -> public -> Tables."
