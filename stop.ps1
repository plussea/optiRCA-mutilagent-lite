[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunDir = Join-Path $ProjectRoot ".run"

function Stop-ManagedProcess {
    param(
        [string]$Name,
        [string]$MetadataPath
    )

    if (-not (Test-Path $MetadataPath)) {
        Write-Host "[skip] No managed $Name process was recorded."
        return
    }

    try {
        $metadata = Get-Content -Raw -Encoding UTF8 $MetadataPath | ConvertFrom-Json
        $identities = @($metadata.launcher, $metadata.listener) | Where-Object { $_ -ne $null }
        foreach ($identity in $identities) {
            $process = Get-Process -Id ([int]$identity.pid) -ErrorAction SilentlyContinue
            if (-not $process) {
                continue
            }

            $expectedStart = [DateTime]::Parse($identity.startedAt).ToUniversalTime()
            try {
                $actualStart = $process.StartTime.ToUniversalTime()
                $actualName = $process.ProcessName
            }
            catch {
                # The process may exit naturally between lookup and inspection.
                continue
            }
            $sameStart = [Math]::Abs(($actualStart - $expectedStart).TotalSeconds) -lt 2
            $sameName = $actualName -eq $identity.processName
            if (-not ($sameStart -and $sameName)) {
                Write-Warning "Refusing to stop PID $($identity.pid): its identity no longer matches $Name."
                continue
            }

            Stop-Process -Id $process.Id -Force
        }

        Start-Sleep -Milliseconds 250

        $remainingListener = $null
        foreach ($line in (& netstat.exe -ano -p tcp)) {
            if ($line -match "^\s*TCP\s+\S+:$($metadata.port)\s+\S+\s+LISTENING\s+(\d+)\s*$") {
                $remainingListener = [int]$Matches[1]
                break
            }
        }
        if ($remainingListener) {
            Write-Warning "$Name still has a listener on port $($metadata.port) (PID $remainingListener)."
        }
        else {
            Write-Host "[stopped] $Name" -ForegroundColor Green
            Remove-Item -LiteralPath $MetadataPath -Force
        }
    }
    catch {
        Write-Warning "Could not stop ${Name}: $($_.Exception.Message)"
    }
}

Stop-ManagedProcess -Name "frontend" -MetadataPath (Join-Path $RunDir "frontend.process.json")
Stop-ManagedProcess -Name "backend" -MetadataPath (Join-Path $RunDir "backend.process.json")

Write-Host "Done. Services that were already running before start.ps1 were not stopped."
