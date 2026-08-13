[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$RunDir = Join-Path $ProjectRoot ".run"
$LogDir = Join-Path $RunDir "logs"
$VenvDir = Join-Path $ProjectRoot ".venv"
$BackendUrl = "http://127.0.0.1:8010/openapi.json"
$BackendMarker = "OptiRCA Lite"
$FrontendUrl = "http://127.0.0.1:5173"
$FrontendMarker = "<title>OptiRCA Lite</title>"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Normalize-ProcessEnvironment {
    # Some launch environments expose both Path and PATH. Start-Process treats
    # those keys as duplicates, so retain one canonical process-level entry.
    $PathValue = [Environment]::GetEnvironmentVariable(
        "Path",
        [EnvironmentVariableTarget]::Process
    )
    [Environment]::SetEnvironmentVariable(
        "PATH",
        $null,
        [EnvironmentVariableTarget]::Process
    )
    [Environment]::SetEnvironmentVariable(
        "Path",
        $PathValue,
        [EnvironmentVariableTarget]::Process
    )
}

function Test-Endpoint {
    param(
        [string]$Url,
        [string]$ExpectedText
    )
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
        return $response.StatusCode -eq 200 -and $response.Content.Contains($ExpectedText)
    }
    catch {
        return $false
    }
}

function Wait-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [string]$ExpectedText,
        [int]$TimeoutSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Endpoint -Url $Url -ExpectedText $ExpectedText) {
            Write-Host "[ready] $Name" -ForegroundColor Green
            return
        }
        Start-Sleep -Milliseconds 500
    }
    throw "$Name did not become ready within $TimeoutSeconds seconds. Check .run/logs."
}

function Get-ListeningProcess {
    param([int]$Port)

    foreach ($line in (& netstat.exe -ano -p tcp)) {
        if ($line -match "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$") {
            return Get-Process -Id ([int]$Matches[1]) -ErrorAction Stop
        }
    }
    return $null
}

function Get-ProcessIdentity {
    param(
        [System.Diagnostics.Process]$Process
    )

    return @{
        pid = $Process.Id
        processName = $Process.ProcessName
        startedAt = $Process.StartTime.ToUniversalTime().ToString("o")
    }
}

function Save-ServiceMetadata {
    param(
        [string]$Name,
        [int]$Port,
        [System.Diagnostics.Process]$Launcher,
        [string]$Path
    )

    $Listener = Get-ListeningProcess -Port $Port
    if (-not $Listener) {
        throw "No process is listening on port $Port."
    }
    @{
        name = $Name
        port = $Port
        launcher = Get-ProcessIdentity -Process $Launcher
        listener = Get-ProcessIdentity -Process $Listener
    } | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 -Path $Path
}

function Start-BackgroundProcess {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory,
        [string]$StandardOutputPath,
        [string]$StandardErrorPath
    )

    return Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput $StandardOutputPath `
        -RedirectStandardError $StandardErrorPath `
        -PassThru
}

Normalize-ProcessEnvironment

$BackendReady = Test-Endpoint -Url $BackendUrl -ExpectedText $BackendMarker
$FrontendReady = Test-Endpoint -Url $FrontendUrl -ExpectedText $FrontendMarker

if (-not $BackendReady) {
    $BackendOccupant = Get-ListeningProcess -Port 8010
    if ($BackendOccupant) {
        throw "Port 8010 is occupied by $($BackendOccupant.ProcessName) (PID $($BackendOccupant.Id)), not OptiRCA Lite."
    }

    $VenvPython = Join-Path $VenvDir "Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        if ($SkipInstall) {
            throw "Python virtual environment is missing. Run start.ps1 without -SkipInstall once."
        }
        $SystemPython = Get-Command python -ErrorAction SilentlyContinue
        if (-not $SystemPython) {
            throw "Python 3.10+ was not found in PATH."
        }
        Write-Host "[setup] Creating Python virtual environment..." -ForegroundColor Cyan
        & $SystemPython.Source -c "import sys; raise SystemExit(sys.version_info < (3, 10))"
        if ($LASTEXITCODE -ne 0) { throw "Python 3.10 or newer is required." }
        & $SystemPython.Source -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) { throw "Failed to create the Python virtual environment." }
    }

    if (-not $SkipInstall) {
        Push-Location $BackendDir
        try {
            $PreviousErrorAction = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            & $VenvPython -c "import fastapi, langgraph, lancedb, multipart, openai, optirc_lite, pydantic_settings, uvicorn" 2>$null
            $DependenciesReady = $LASTEXITCODE -eq 0
            $ErrorActionPreference = $PreviousErrorAction
            if (-not $DependenciesReady) {
                Write-Host "[setup] Installing backend dependencies..." -ForegroundColor Cyan
                & $VenvPython -m pip install -e $BackendDir
                if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed." }
            }
        }
        finally {
            if ($PreviousErrorAction) {
                $ErrorActionPreference = $PreviousErrorAction
            }
            Pop-Location
        }
    }

    Write-Host "[start] Backend API on http://127.0.0.1:8010" -ForegroundColor Cyan
    $BackendProcess = Start-BackgroundProcess `
        -FilePath $VenvPython `
        -ArgumentList @("-m", "optirc_lite.api.main") `
        -WorkingDirectory $BackendDir `
        -StandardOutputPath (Join-Path $LogDir "backend.stdout.log") `
        -StandardErrorPath (Join-Path $LogDir "backend.stderr.log")
    Wait-Endpoint -Name "Backend API" -Url $BackendUrl -ExpectedText $BackendMarker
    Save-ServiceMetadata `
        -Name "backend" `
        -Port 8010 `
        -Launcher $BackendProcess `
        -Path (Join-Path $RunDir "backend.process.json")
}
else {
    Write-Host "[reuse] Backend is already running." -ForegroundColor DarkGreen
}

if (-not $FrontendReady) {
    $FrontendOccupant = Get-ListeningProcess -Port 5173
    if ($FrontendOccupant) {
        throw "Port 5173 is occupied by $($FrontendOccupant.ProcessName) (PID $($FrontendOccupant.Id)), not OptiRCA Lite."
    }

    $Node = Get-Command node.exe -ErrorAction SilentlyContinue
    $Npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $Node -or -not $Npm) {
        throw "Node.js 18+ and npm were not found in PATH."
    }
    $NodeMajor = & $Node.Source -p "Number(process.versions.node.split('.')[0])"
    if ($LASTEXITCODE -ne 0 -or [int]$NodeMajor -lt 18) {
        throw "Node.js 18 or newer is required. Found $(& $Node.Source --version)."
    }

    $ViteCommand = Join-Path $FrontendDir "node_modules\.bin\vite.cmd"
    if (-not (Test-Path $ViteCommand)) {
        if ($SkipInstall) {
            throw "Frontend dependencies are missing. Run start.ps1 without -SkipInstall once."
        }
        Write-Host "[setup] Installing frontend dependencies..." -ForegroundColor Cyan
        Push-Location $FrontendDir
        try {
            & $Npm.Source ci
            if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
        }
        finally {
            Pop-Location
        }
    }

    Write-Host "[start] Frontend on http://127.0.0.1:5173" -ForegroundColor Cyan
    $FrontendProcess = Start-BackgroundProcess `
        -FilePath $Npm.Source `
        -ArgumentList @("run", "dev") `
        -WorkingDirectory $FrontendDir `
        -StandardOutputPath (Join-Path $LogDir "frontend.stdout.log") `
        -StandardErrorPath (Join-Path $LogDir "frontend.stderr.log")
    Wait-Endpoint -Name "Frontend" -Url $FrontendUrl -ExpectedText $FrontendMarker
    Save-ServiceMetadata `
        -Name "frontend" `
        -Port 5173 `
        -Launcher $FrontendProcess `
        -Path (Join-Path $RunDir "frontend.process.json")
}
else {
    Write-Host "[reuse] Frontend is already running." -ForegroundColor DarkGreen
}

Write-Host ""
Write-Host "OptiRCA Lite is running." -ForegroundColor Green
Write-Host "  Workbench: http://127.0.0.1:5173"
Write-Host "  API docs:  http://127.0.0.1:8010/docs"
Write-Host "  Stop:      .\stop.ps1"

if (-not $NoBrowser) {
    Start-Process $FrontendUrl
}
