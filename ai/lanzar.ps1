<#
Lanza el entrenamiento MaskablePPO en segundo plano (tarea "agente entrenado", punto 7).
Usa Start-Process (PowerShell nativo) en vez de nohup -- no hay make ni bash de por medio
en este equipo (Windows). Deja el proceso corriendo aunque se cierre esta terminal.

Uso, desde ai/:  powershell -File .\lanzar.ps1
                 (o, con pwsh en PATH:  pwsh .\lanzar.ps1)
#>

$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = "C:\Users\mondr\vygo-rl\.venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

if (-not (Test-Path (Join-Path $raiz "checkpoints\bc_policy.pt"))) {
    Write-Error "Falta checkpoints\bc_policy.pt -- correr antes: $python -m vygo.bc"
}

$reportsDir = Join-Path $raiz "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null
$logOut = Join-Path $reportsDir "train_ppo.log"
$logErr = Join-Path $reportsDir "train_ppo.err.log"

$proceso = Start-Process -FilePath $python `
    -ArgumentList @("-u", "-m", "vygo.train_ppo") `
    -WorkingDirectory $raiz `
    -RedirectStandardOutput $logOut `
    -RedirectStandardError $logErr `
    -NoNewWindow `
    -PassThru

Write-Host "MaskablePPO lanzado en segundo plano. PID=$($proceso.Id)"
Write-Host "stdout: $logOut"
Write-Host "stderr: $logErr"
Write-Host "Seguimiento en vivo:  Get-Content -Wait `"$logOut`""
Write-Host "reports/status.json y reports/train_log.jsonl se actualizan cada 25000 pasos."
Write-Host "Detener:  Stop-Process -Id $($proceso.Id)"
