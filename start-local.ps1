$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$runtimeDirectory = Join-Path $projectRoot '.tools/runtime'
New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null

$dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
$dockerPath = if ($dockerCommand) { $dockerCommand.Source } else { 'C:/Program Files/Docker/Docker/resources/bin/docker.exe' }
$uvCommand = Get-Command uv.exe -ErrorAction SilentlyContinue
$uvPath = if ($uvCommand) { $uvCommand.Source } else { Join-Path $projectRoot '.tools/uv/uv.exe' }
$nodePath = (Get-Command node.exe -ErrorAction Stop).Source
foreach ($requiredPath in @($dockerPath, $uvPath, (Join-Path $projectRoot 'backend/.env'))) {
  if (-not (Test-Path -LiteralPath $requiredPath)) { throw "Required local file missing: $requiredPath" }
}

$httpHandler = [System.Net.Http.HttpClientHandler]::new()
$httpHandler.UseProxy = $false
$http = [System.Net.Http.HttpClient]::new($httpHandler)
$http.Timeout = [TimeSpan]::FromSeconds(3)

function Test-LocalHttp([string]$url, [bool]$backend = $false) {
  try {
    $response = $http.GetAsync($url).GetAwaiter().GetResult()
    try {
      if (-not $response.IsSuccessStatusCode) { return $false }
      if ($backend) {
        $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult() | ConvertFrom-Json
        return $body.code -eq 0 -and $body.data.service -eq 'clear-complaint-backend'
      }
      return $true
    } finally { $response.Dispose() }
  } catch { return $false }
}

function Wait-LocalHttp([string]$url, [bool]$backend = $false) {
  $deadline = [DateTime]::UtcNow.AddSeconds(60)
  while ([DateTime]::UtcNow -lt $deadline) {
    if (Test-LocalHttp $url $backend) { return }
    Start-Sleep -Seconds 1
  }
  throw "Service did not become ready: $url. See logs in $runtimeDirectory"
}

function Invoke-Docker([string[]]$arguments, [int]$timeoutSeconds = 5) {
  $process = Start-Process -FilePath $dockerPath -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $runtimeDirectory 'docker.out.log') -RedirectStandardError (Join-Path $runtimeDirectory 'docker.err.log')
  if (-not $process.WaitForExit($timeoutSeconds * 1000)) {
    $process.Kill()
    $process.WaitForExit()
    return $false
  }
  return $process.ExitCode -eq 0
}

function Assert-PortAvailable([int]$port) {
  if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
    throw "Port $port is occupied by a different or unhealthy service. No existing process was stopped."
  }
}

try {
  if (-not (Invoke-Docker @('info', '--format', '{{.ServerVersion}}'))) {
    Write-Host 'Starting Docker Desktop...'
    Start-Process -FilePath 'C:/Program Files/Docker/Docker/Docker Desktop.exe' -WindowStyle Hidden
    $deadline = [DateTime]::UtcNow.AddSeconds(90)
    while (-not (Invoke-Docker @('info', '--format', '{{.ServerVersion}}'))) {
      if ([DateTime]::UtcNow -ge $deadline) { throw 'Docker is not ready. Open Docker Desktop and finish any startup prompts, then retry.' }
      Start-Sleep -Seconds 2
    }
  }
  Write-Host 'Starting project Postgres (existing data is retained)...'
  if (-not (Invoke-Docker @('compose', '-f', 'docker-compose.yml', 'up', '-d', '--wait', '--wait-timeout', '90') 120)) {
    throw "Postgres did not start. See $runtimeDirectory/docker.err.log"
  }

  if (-not (Test-LocalHttp 'http://127.0.0.1:8000/api/health' $true)) {
    Assert-PortAvailable 8000
    Write-Host 'Starting backend...'
    Start-Process -FilePath $uvPath -ArgumentList @('run', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') `
      -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden `
      -RedirectStandardOutput (Join-Path $runtimeDirectory 'backend.out.log') -RedirectStandardError (Join-Path $runtimeDirectory 'backend.err.log')
    Wait-LocalHttp 'http://127.0.0.1:8000/api/health' $true
  }
  if (-not (Test-LocalHttp 'http://127.0.0.1:5175/')) {
    Assert-PortAvailable 5175
    Write-Host 'Starting frontend...'
    Start-Process -FilePath $nodePath -ArgumentList @('node_modules/@dcloudio/vite-plugin-uni/bin/uni.js', '--host', '127.0.0.1', '--port', '5175', '--strictPort') `
      -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden `
      -RedirectStandardOutput (Join-Path $runtimeDirectory 'frontend.out.log') -RedirectStandardError (Join-Path $runtimeDirectory 'frontend.err.log')
    Wait-LocalHttp 'http://127.0.0.1:5175/'
  }
  Wait-LocalHttp 'http://127.0.0.1:5175/api/health' $true
  Write-Host 'Ready: http://127.0.0.1:5175/'
  Write-Host "Logs: $runtimeDirectory"
} finally { $http.Dispose() }
