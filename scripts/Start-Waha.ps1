$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$dockerBin = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin'
if (-not (Test-Path (Join-Path $dockerBin 'docker.exe'))) {
    $dockerBin = 'C:\Program Files\Docker\Docker\resources\bin'
}
$env:PATH = "$dockerBin;$env:PATH"
$dockerExe = Join-Path $dockerBin 'docker.exe'
$localState = Join-Path $projectRoot 'runtime\waha'
New-Item -ItemType Directory -Force -Path $localState | Out-Null
$envFile = Join-Path $localState '.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    $apiKey = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
    $dashboardPassword = [guid]::NewGuid().ToString('N')
    @(
        "WAHA_API_KEY=$apiKey"
        'WAHA_DASHBOARD_ENABLED=true'
        'WAHA_DASHBOARD_USERNAME=admin'
        "WAHA_DASHBOARD_PASSWORD=$dashboardPassword"
        'WHATSAPP_SWAGGER_USERNAME=admin'
        "WHATSAPP_SWAGGER_PASSWORD=$dashboardPassword"
        'WAHA_PRINT_QR=false'
        'WAHA_LOG_LEVEL=warn'
        'WAHA_EVENTS_DOWNLOAD_MEDIA=false'
        'WHATSAPP_DEFAULT_ENGINE=WEBJS'
    ) | Set-Content -LiteralPath $envFile -Encoding ASCII
}
& $dockerExe compose -p aura-qr -f (Join-Path $projectRoot 'infra\waha\compose.yaml') up -d
if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel iniciar o WAHA.' }
Write-Output 'Painel: http://localhost:3000/dashboard/'
Write-Output 'Credenciais locais: runtime\waha\.env (nao compartilhar)'
