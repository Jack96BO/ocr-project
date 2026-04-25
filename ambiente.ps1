#Requires -Version 5.1
<#
.SYNOPSIS
    Ricostruisce l'ambiente di sviluppo per ocr-project.
.DESCRIPTION
    Crea un virtual environment Python, installa le dipendenze di sistema
    e tutti i pacchetti Python necessari per eseguire il progetto OCR.
.EXAMPLE
    .\ambiente.ps1
    .\ambiente.ps1 -PythonVersion "3.10" -VenvName "venv310"
#>

param(
    [string]$PythonVersion = "3.10",
    [string]$VenvName      = "venv310",
    [string]$ProjectDir    = $PSScriptRoot,
    [switch]$Docker                            # Se presente, costruisce ed avvia il container Docker
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Funzioni helper
# ---------------------------------------------------------------------------
function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Write-OK($msg) {
    Write-Host "    [OK] $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    Write-Host "    [WARN] $msg" -ForegroundColor Yellow
}

function Write-Fail($msg) {
    Write-Host "    [FAIL] $msg" -ForegroundColor Red
}

function Test-CommandExists($cmd) {
    return $null -ne (Get-Command $cmd -ErrorAction SilentlyContinue)
}

# ---------------------------------------------------------------------------
# Rilevamento piattaforma
# ---------------------------------------------------------------------------
$IsWin  = $IsWindows  -or ($PSVersionTable.PSVersion.Major -le 5)
$IsLin  = $IsLinux
$IsMac  = $IsMacOS

Write-Step "Rilevamento piattaforma"
if ($IsWin)      { Write-OK "Windows" }
elseif ($IsLin)  { Write-OK "Linux"   }
elseif ($IsMac)  { Write-OK "macOS"   }
else             { Write-Warn "Piattaforma non riconosciuta" }

# ---------------------------------------------------------------------------
# 1. Verifica / Installazione dipendenze di sistema
# ---------------------------------------------------------------------------
Write-Step "Dipendenze di sistema"

if ($IsLin) {
    # libGL necessaria per OpenCV/PaddleOCR
    $libgl = & bash -c "ldconfig -p 2>/dev/null | grep libGL.so.1" 2>&1
    if (-not $libgl) {
        Write-Warn "libGL.so.1 non trovata: installo..."
        & sudo apt-get update -q
        & sudo apt-get install -y libgl1 poppler-utils | Out-Null
        Write-OK "libGL e poppler-utils installati"
    } else {
        Write-OK "libGL.so.1 presente"
    }

    # poppler (per pdf2image)
    if (-not (Test-CommandExists "pdfinfo")) {
        Write-Warn "poppler-utils non trovato: installo..."
        & sudo apt-get install -y poppler-utils | Out-Null
        Write-OK "poppler-utils installato"
    } else {
        Write-OK "poppler-utils presente"
    }
}

if ($IsMac) {
    if (Test-CommandExists "brew") {
        if (-not (Test-CommandExists "pdfinfo")) {
            Write-Warn "Poppler non trovato: installo con brew..."
            & brew install poppler
        } else {
            Write-OK "poppler presente"
        }
    } else {
        Write-Warn "Homebrew non trovato. Installa manualmente: brew install poppler"
    }
}

if ($IsWin) {
    Write-Warn "Windows: assicurati di avere installato:"
    Write-Warn "  - Visual C++ Build Tools: https://visualstudio.microsoft.com/visual-cpp-build-tools/"
    Write-Warn "  - Poppler per Windows: https://github.com/oschwartz10612/poppler-windows/releases"
    Write-Warn "  - Aggiungi la cartella bin di Poppler al PATH"
}

# ---------------------------------------------------------------------------
# 2. Verifica Python
# ---------------------------------------------------------------------------
Write-Step "Verifica Python $PythonVersion"

$pythonExe = $null
$candidates = @("python$PythonVersion", "python3", "python")

foreach ($cand in $candidates) {
    if (Test-CommandExists $cand) {
        $ver = & $cand --version 2>&1
        if ($ver -match "3\.\d+") {
            $pythonExe = $cand
            Write-OK "Trovato: $cand -> $ver"
            break
        }
    }
}

if ($null -eq $pythonExe) {
    Write-Fail "Python non trovato. Installa Python $PythonVersion da https://www.python.org/downloads/"
    exit 1
}

# ---------------------------------------------------------------------------
# 3. Crea virtual environment
# ---------------------------------------------------------------------------
Write-Step "Creazione virtual environment: $VenvName"

$venvPath = Join-Path $ProjectDir $VenvName

if (Test-Path $venvPath) {
    Write-Warn "Virtual environment '$VenvName' esiste già: salto creazione"
} else {
    & $pythonExe -m venv $venvPath
    Write-OK "Creato in: $venvPath"
}

# Determina il path degli eseguibili nel venv
if ($IsWin) {
    $pip    = Join-Path $venvPath "Scripts\pip.exe"
    $python = Join-Path $venvPath "Scripts\python.exe"
} else {
    $pip    = Join-Path $venvPath "bin/pip"
    $python = Join-Path $venvPath "bin/python"
}

if (-not (Test-Path $pip)) {
    Write-Fail "pip non trovato in $pip"
    exit 1
}

# ---------------------------------------------------------------------------
# 4. Aggiorna pip / setuptools / wheel
# ---------------------------------------------------------------------------
Write-Step "Aggiornamento pip / setuptools / wheel"
& $python -m pip install --quiet --upgrade pip setuptools wheel
Write-OK "pip, setuptools, wheel aggiornati"

# ---------------------------------------------------------------------------
# 5. Installa dipendenze Python
# ---------------------------------------------------------------------------
Write-Step "Installazione dipendenze Python da requirements.txt"

$reqFile = Join-Path $ProjectDir "ocr_project\requirements.txt"
if (-not (Test-Path $reqFile)) {
    $reqFile = Join-Path $ProjectDir "ocr_project/requirements.txt"
}

if (-not (Test-Path $reqFile)) {
    Write-Fail "File requirements.txt non trovato in $reqFile"
    exit 1
}

# numpy <2 deve essere installato prima degli altri per evitare conflitti
Write-Warn "Installo numpy==1.26.4 prima degli altri pacchetti (compatibilità PaddleOCR)..."
& $pip install --quiet "numpy==1.26.4"
Write-OK "numpy==1.26.4 installato"

& $pip install --quiet -r $reqFile
Write-OK "Tutte le dipendenze installate"

# ---------------------------------------------------------------------------
# 6. Verifica importazioni critiche
# ---------------------------------------------------------------------------
Write-Step "Verifica importazioni critiche"

$checks = @(
    "import flask; print('Flask', flask.__version__)",
    "import paddleocr; print('PaddleOCR OK')",
    "import cv2; print('OpenCV', cv2.__version__)",
    "import numpy as np; print('NumPy', np.__version__)",
    "from PIL import Image; print('Pillow OK')"
)

$allOK = $true
foreach ($check in $checks) {
    $out = & $python -c $check 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-OK $out
    } else {
        Write-Fail "ERRORE: $check -> $out"
        $allOK = $false
    }
}

# ---------------------------------------------------------------------------
# 7. Docker (opzionale — usa -Docker per attivare)
# ---------------------------------------------------------------------------
if ($Docker) {
    Write-Step "Build & avvio container Docker (porta 9894)"

    if (-not (Test-CommandExists "docker")) {
        Write-Fail "Docker non trovato. Installa Docker Desktop: https://www.docker.com/products/docker-desktop"
        exit 1
    }

    $composeFile = Join-Path $ProjectDir "docker-compose.yml"
    $dockerfilePath = Join-Path $ProjectDir "Dockerfile"

    if (-not (Test-Path $dockerfilePath)) {
        Write-Fail "Dockerfile non trovato in $dockerfilePath"
        exit 1
    }

    if (Test-CommandExists "docker-compose") {
        Write-OK "Trovato docker-compose"
        Set-Location $ProjectDir
        & docker-compose up --build -d
    } elseif ((& docker compose version 2>&1) -match "compose") {
        Write-OK "Trovato docker compose (plugin)"
        Set-Location $ProjectDir
        & docker compose up --build -d
    } else {
        Write-Warn "docker-compose non trovato: eseguo build manuale"
        & docker build -t ocr-project:latest $ProjectDir
        & docker run -d --name ocr-project -p 9894:9894 `
            -v ocr_output:/app/data/output `
            --restart unless-stopped `
            ocr-project:latest
    }

    if ($LASTEXITCODE -eq 0) {
        Write-OK "Container avviato! Applicazione disponibile su http://localhost:9894"
    } else {
        Write-Fail "Errore durante l'avvio del container."
        exit 1
    }

    Write-Host ""
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "  Container Docker attivo!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Comandi utili:" -ForegroundColor White
    Write-Host "    docker logs ocr-project -f          -> log in tempo reale" -ForegroundColor Yellow
    Write-Host "    docker stop ocr-project             -> ferma il container" -ForegroundColor Yellow
    Write-Host "    docker compose down                 -> ferma e rimuove il container" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Endpoint disponibili su http://localhost:9894:" -ForegroundColor White
    Write-Host "    GET  /                  -> Interfaccia web" -ForegroundColor Gray
    Write-Host "    POST /upload            -> Upload web (multifile)" -ForegroundColor Gray
    Write-Host "    POST /api/ocr           -> API singola immagine" -ForegroundColor Gray
    Write-Host "    POST /api/ocr/batch     -> API batch multi-immagine" -ForegroundColor Gray
    Write-Host "============================================" -ForegroundColor Cyan
    exit 0
}

# ---------------------------------------------------------------------------
# 7. Riepilogo (ambiente locale)
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
if ($allOK) {
    Write-Host "  Ambiente pronto!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Per avviare il progetto in locale:" -ForegroundColor White
    if ($IsWin) {
        Write-Host "    $VenvName\Scripts\activate" -ForegroundColor Yellow
    } else {
        Write-Host "    source $VenvName/bin/activate" -ForegroundColor Yellow
    }
    Write-Host "    python ocr_project/app.py" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Per avviare con Docker (porta 9894):" -ForegroundColor White
    Write-Host "    .\ambiente.ps1 -Docker" -ForegroundColor Yellow
    Write-Host "  oppure manualmente:" -ForegroundColor White
    Write-Host "    docker compose up --build -d" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Endpoint disponibili su http://localhost:9894:" -ForegroundColor White
    Write-Host "    GET  /                  -> Interfaccia web" -ForegroundColor Gray
    Write-Host "    POST /upload            -> Upload web (multifile)" -ForegroundColor Gray
    Write-Host "    POST /api/ocr           -> API singola immagine" -ForegroundColor Gray
    Write-Host "    POST /api/ocr/batch     -> API batch multi-immagine" -ForegroundColor Gray
} else {
    Write-Host "  Ambiente incompleto: controlla gli errori sopra." -ForegroundColor Red
}
Write-Host "============================================" -ForegroundColor Cyan
