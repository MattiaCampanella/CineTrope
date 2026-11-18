# Avvia CineTrope: backend semantico (FastAPI, :8000) + sito Next.js (:3000), con Bun.
# Uso:  .\run.ps1 [-Dev] [-Rebuild] [-Images] [-NoBrowser] [-ApiPort 8000] [-WebPort 3000]
#   -Dev        Next.js in modalità sviluppo (hot reload) invece di build + start
#   -Rebuild    ricostruisce lo store RDF (data/generated/store.trig, ~3 minuti)
#   -Images     scarica poster e foto da TMDB (serve TMDB_API_KEY in .env)
#   -NoBrowser  non apre il browser
param(
    [switch]$Dev,
    [switch]$Rebuild,
    [switch]$Images,
    [switch]$NoBrowser,
    [int]$ApiPort = 8000,
    [int]$WebPort = 3000
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# --- Python / backend -------------------------------------------------------
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

& $python -c "import fastapi, uvicorn, rdflib, owlrl" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Dipendenze Python mancanti. Installo da requirements.txt..." -ForegroundColor Yellow
    if (-not (Test-Path $venvPython)) { python -m venv .venv; $python = $venvPython }
    & $python -m pip install -r requirements.txt
}

$store = Join-Path $PSScriptRoot "data\generated\store.trig"
if ($Rebuild -or -not (Test-Path $store)) {
    Write-Host "Costruisco lo store (circa 3 minuti)..." -ForegroundColor Yellow
    & $python scripts/pipeline.py store --force
    if ($LASTEXITCODE -ne 0) { throw "Build dello store fallito." }
}

if ($Images) {
    Write-Host "Scarico poster e foto da TMDB..." -ForegroundColor Yellow
    & $python scripts/pipeline.py images
    if ($LASTEXITCODE -ne 0) { throw "Download immagini fallito." }
}

# --- Bun / frontend ---------------------------------------------------------
if (-not (Get-Command bun -ErrorAction SilentlyContinue)) {
    throw "Bun non trovato. Installalo da https://bun.sh (powershell -c `"irm bun.sh/install.ps1 | iex`")."
}
$web = Join-Path $PSScriptRoot "web"
Push-Location $web
try {
    if (-not (Test-Path "node_modules")) {
        Write-Host "Installo le dipendenze del sito (bun install)..." -ForegroundColor Yellow
        bun install
        if ($LASTEXITCODE -ne 0) { throw "bun install fallito." }
    }
    if (-not $Dev) {
        # Ricompila solo se manca la build o se i sorgenti sono più recenti.
        $buildId = ".next\BUILD_ID"
        $stale = -not (Test-Path $buildId)
        if (-not $stale) {
            $built = (Get-Item $buildId).LastWriteTime
            $newer = Get-ChildItem src, public, package.json, next.config.mjs -Recurse -File -ErrorAction SilentlyContinue |
                Where-Object { $_.LastWriteTime -gt $built } | Select-Object -First 1
            $stale = [bool]$newer
        }
        if ($stale) {
            Write-Host "Compilo il sito (bun run build)..." -ForegroundColor Yellow
            bun run build
            if ($LASTEXITCODE -ne 0) { throw "bun run build fallito." }
        }
    }
}
finally { Pop-Location }

# --- Avvio ------------------------------------------------------------------
$api = Start-Process -FilePath $python -PassThru -NoNewWindow `
    -ArgumentList @("-m", "uvicorn", "cinetrope.web:app", "--port", $ApiPort)
$env:CINETROPE_API = "http://127.0.0.1:$ApiPort"
$env:PORT = "$WebPort"   # Next.js legge la porta da qui

try {
    Write-Host "Attendo il backend (carica lo store)..." -ForegroundColor Yellow
    for ($i = 0; $i -lt 120; $i++) {
        try { Invoke-WebRequest "http://127.0.0.1:$ApiPort/health" -UseBasicParsing -TimeoutSec 2 | Out-Null; break }
        catch { Start-Sleep -Seconds 1 }
    }

    $url = "http://127.0.0.1:$WebPort"
    if (-not $NoBrowser) {
        Start-Job -ArgumentList $url -ScriptBlock {
            param($u)
            for ($i = 0; $i -lt 60; $i++) {
                try { Invoke-WebRequest $u -UseBasicParsing -TimeoutSec 2 | Out-Null; Start-Process $u; return }
                catch { Start-Sleep -Seconds 1 }
            }
        } | Out-Null
    }

    Write-Host "CineTrope su $url  (API su http://127.0.0.1:$ApiPort)  Ctrl+C per fermare" -ForegroundColor Green
    Push-Location $web
    try {
        if ($Dev) { bun run dev } else { bun run start }
    }
    finally { Pop-Location }
}
finally {
    # Ferma il backend quando il sito si chiude o con Ctrl+C.
    if ($api -and -not $api.HasExited) { Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue }
}
