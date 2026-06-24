param(
    [string]$ReleaseDir = ".release",
    [int]$Port = 8010,
    [switch]$SkipStart
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ReleasePath = Join-Path $Root $ReleaseDir
$StagingPath = "$ReleasePath.staging"
$PreviousPidPath = Join-Path $ReleasePath "uvicorn.pid"
$ProdUrl = "http://127.0.0.1:$Port"

function Assert-PathUnderRoot {
    param([string]$Path)

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $fullRoot = [System.IO.Path]::GetFullPath($Root)
    if (-not $fullPath.StartsWith($fullRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to operate outside project root: $fullPath"
    }
}

function Invoke-Checked {
    param(
        [string]$Label,
        [scriptblock]$Command
    )

    Write-Host "== $Label =="
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Stop-PreviousRelease {
    $idsToStop = New-Object System.Collections.Generic.HashSet[int]
    if (-not (Test-Path -LiteralPath $PreviousPidPath)) {
        $pidText = ""
    } else {
        $pidText = (Get-Content -LiteralPath $PreviousPidPath -Raw).Trim()
    }

    if ($pidText) {
        [void]$idsToStop.Add([int]$pidText)
    }

    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        [void]$idsToStop.Add([int]$listener.OwningProcess)
    }

    foreach ($id in $idsToStop) {
        $process = Get-Process -Id $id -ErrorAction SilentlyContinue
        if (-not $process) {
            continue
        }
        Write-Host "Stopping previous release process $id"
        Stop-Process -Id $process.Id -Force
    }
    Start-Sleep -Seconds 1
}

function Test-PortFree {
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) {
        throw "Port $Port is already in use by process $($listener.OwningProcess). Stop it or choose another -Port."
    }
}

function Copy-ReleaseFiles {
    New-Item -ItemType Directory -Path $StagingPath | Out-Null
    Copy-Item -LiteralPath (Join-Path $Root "app") -Destination (Join-Path $StagingPath "app") -Recurse
    Copy-Item -LiteralPath (Join-Path $Root "pyproject.toml") -Destination $StagingPath
    Copy-Item -LiteralPath (Join-Path $Root "uv.lock") -Destination $StagingPath
    Copy-Item -LiteralPath (Join-Path $Root "README.md") -Destination $StagingPath
    Copy-Item -LiteralPath (Join-Path $Root ".env.example") -Destination $StagingPath

    $envPath = Join-Path $Root ".env"
    if (Test-Path -LiteralPath $envPath) {
        Copy-Item -LiteralPath $envPath -Destination $StagingPath
        Write-Host "Copied local .env into release without printing secrets."
    } else {
        Write-Warning "No root .env found. Release will rely on user/system environment variables."
    }
}

function Start-Release {
    Test-PortFree

    $pythonPath = Join-Path $ReleasePath ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        throw "Release Python runtime not found: $pythonPath"
    }

    $stdoutPath = Join-Path $ReleasePath "uvicorn.out.log"
    $stderrPath = Join-Path $ReleasePath "uvicorn.err.log"
    $pidPath = Join-Path $ReleasePath "uvicorn.pid"

    $process = Start-Process `
        -FilePath $pythonPath `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", [string]$Port) `
        -WorkingDirectory $ReleasePath `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -PassThru

    Set-Content -LiteralPath $pidPath -Value $process.Id

    $deadline = (Get-Date).AddSeconds(20)
    do {
        Start-Sleep -Milliseconds 500
        try {
            $health = Invoke-RestMethod -Uri "$ProdUrl/api/health"
            if ($health.status -eq "ok") {
                Write-Host "Release is running at $ProdUrl"
                return
            }
        } catch {
            if ($process.HasExited) {
                $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Tail 40 } else { "" }
                throw "Release process exited before health check passed. $stderr"
            }
        }
    } while ((Get-Date) -lt $deadline)

    throw "Release did not pass health check at $ProdUrl/api/health within timeout."
}

Push-Location $Root
try {
    Assert-PathUnderRoot $ReleasePath
    Assert-PathUnderRoot $StagingPath

    Invoke-Checked "pytest" { uv run pytest }
    Invoke-Checked "compileall" { uv run python -m compileall app tests }

    $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
    if ($nodeCommand) {
        Invoke-Checked "app.js syntax" { node --check .\app\static\app.js }
    } else {
        Write-Warning "Node.js not found; skipped app.js syntax check."
    }

    Invoke-Checked "diff whitespace check" { git diff --check }

    Stop-PreviousRelease

    if (Test-Path -LiteralPath $StagingPath) {
        Remove-Item -LiteralPath $StagingPath -Recurse -Force
    }

    if (Test-Path -LiteralPath $ReleasePath) {
        Remove-Item -LiteralPath $ReleasePath -Recurse -Force
    }

    Copy-ReleaseFiles

    Push-Location $StagingPath
    try {
        $previousLinkMode = $env:UV_LINK_MODE
        $env:UV_LINK_MODE = "copy"
        try {
            Invoke-Checked "release dependency sync" { uv sync --frozen --no-dev }
        } finally {
            $env:UV_LINK_MODE = $previousLinkMode
        }
    } finally {
        Pop-Location
    }

    Move-Item -LiteralPath $StagingPath -Destination $ReleasePath

    if (-not $SkipStart) {
        Start-Release
        Invoke-RestMethod -Uri "$ProdUrl/api/config/status" | ConvertTo-Json -Depth 5
    }

    Write-Host "Local release deploy complete: $ReleasePath"
} finally {
    Pop-Location
}
