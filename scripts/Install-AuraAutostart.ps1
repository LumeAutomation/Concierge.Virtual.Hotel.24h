$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).ProviderPath
$pythonw=Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonw)) { throw 'Python312 nao encontrado.' }
$python=Join-Path (Split-Path $pythonw -Parent) 'python.exe'
& $python -c "import psutil"
if ($LASTEXITCODE -ne 0) { throw 'Instale a dependencia operacional: python -m pip install -r requirements-operations.txt' }
$projectRoot=(& $python -c "from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())" $projectRoot).Trim()
if (Get-ScheduledTask -TaskName 'AURA - Supervisor local' -ErrorAction SilentlyContinue) { Stop-ScheduledTask -TaskName 'AURA - Supervisor local' }
$agentRoot=Join-Path $env:LOCALAPPDATA 'AURA\agent'
New-Item -ItemType Directory -Force -Path $agentRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $projectRoot 'operations.py') -Destination (Join-Path $agentRoot 'operations.py') -Force
Copy-Item -LiteralPath (Join-Path $projectRoot 'scripts\supervise.py') -Destination (Join-Path $agentRoot 'supervise.py') -Force
@{root=$projectRoot} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $agentRoot 'project.json') -Encoding UTF8
$script=Join-Path $agentRoot 'supervise.py'

$action=New-ScheduledTaskAction -Execute $pythonw -Argument ('"'+$script+'"') -WorkingDirectory $agentRoot
$user=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$trigger=New-ScheduledTaskTrigger -AtLogOn -User $user
$principal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
# 4 = normal CPU, I/O and memory priority. Default 7 starves interactive services.
$settings.Priority=4
Register-ScheduledTask -TaskName 'AURA - Supervisor local' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Inicia AURA, n8n e WAHA ao entrar no Windows; recupera processos e faz backup diario.' -Force | Out-Null
Start-ScheduledTask -TaskName 'AURA - Supervisor local'
Write-Output 'Supervisor registrado e iniciado para o usuario atual.'
